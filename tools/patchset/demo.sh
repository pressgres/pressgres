#!/usr/bin/env bash
# R-005 demo: strict, hash-locked patch series against pristine WordPress 7.1.5
# (PHP) and Gutenberg 89408c2 (JS source), plus a rebase dry run.
#
# Usage: tools/patchset/demo.sh [REFERENCE_ROOT]
#   REFERENCE_ROOT defaults to ../reference relative to the repository's parent
#   (i.e. /Users/.../pressgres/reference). Nothing under REFERENCE_ROOT is modified.
#   Upstream copies are made under tools/patchset/.work/ (gitignored).
set -uo pipefail
export LC_ALL=C

HERE="$(cd "$(dirname "$0")" && pwd -P)"
REPO="$(cd "$HERE/../.." && pwd -P)"
REF="${1:-$(cd "$REPO/../../reference" 2>/dev/null && pwd -P)}"
WP_SRC="$REF/wordpress-develop-7.1.5/src"
GB_SRC="$REF/gutenberg-89408c2"
PS="$HERE/bin/patchset"
WP_SERIES="$HERE/examples/patches/wordpress/7.1.5"
GB_SERIES="$HERE/examples/patches/gutenberg/89408c2"
WORK="$HERE/.work"

[ -d "$WP_SRC" ] || { echo "FATAL: $WP_SRC not found (pass REFERENCE_ROOT)"; exit 1; }
[ -d "$GB_SRC" ] || { echo "FATAL: $GB_SRC not found (pass REFERENCE_ROOT)"; exit 1; }

failures=0
expect() { # expect <wanted-exit-code> <label> -- cmd...
	local want="$1" label="$2"; shift 3
	echo
	echo "### $label"
	echo "\$ $*" | sed "s#$WORK#.work#g; s#$HERE#tools/patchset#g"
	"$@" 2>&1 | sed "s#$WORK#.work#g; s#$HERE#tools/patchset#g; s#/var/folders/[^ ]*#<tmp>#g"
	local got="${PIPESTATUS[0]}"
	if [ "$got" = "$want" ]; then echo "--> exit $got (expected)"; else echo "--> exit $got (EXPECTED $want)"; failures=$((failures + 1)); fi
}

fresh_copy() { rm -rf "$2"; mkdir -p "$2"; rsync -a --exclude .git --exclude node_modules "$1/" "$2/"; }

echo "R-005 patchset demo  (git: $(git --version | awk '{print $3}'), host: $(uname -s))"
rm -rf "$WORK"; mkdir -p "$WORK"
fresh_copy "$WP_SRC" "$WORK/wp-7.1.5"
fresh_copy "$GB_SRC" "$WORK/gutenberg-89408c2"

if [ "${RELOCK:-0}" = 1 ]; then
	"$PS" lock "$WORK/wp-7.1.5" "$WP_SERIES"
	"$PS" lock "$WORK/gutenberg-89408c2" "$GB_SERIES"
fi

# 1. Happy path: PHP core series.
expect 0 "1. apply WordPress series to pristine 7.1.5 src/" -- "$PS" apply "$WORK/wp-7.1.5" "$WP_SERIES"
expect 0 "1b. php -l on patched files" -- sh -c "cd '$WORK/wp-7.1.5' && for f in wp-settings.php wp-includes/post.php wp-includes/pressgres-object-id.php; do php -l \$f; done"
expect 0 "1c. helper smoke test (absint stubbed; illustrative)" -- php -r "function absint(\$v){return abs((int)\$v);} require '$WORK/wp-7.1.5/wp-includes/pressgres-object-id.php'; var_dump(pressgres_object_id('0190F3A2-7B1C-7DEF-8ABC-0123456789AB'), pressgres_object_id('42'));"
expect 0 "1d. generated modification notice" -- cat "$WORK/wp-7.1.5/PRESSGRES-MODIFICATIONS.txt"

# 2. Happy path: Gutenberg JS source series (rebuild of wp-includes/js/dist not run here).
expect 0 "2. apply Gutenberg series to pristine 89408c2 source" -- "$PS" apply "$WORK/gutenberg-89408c2" "$GB_SERIES"

# 3. Tampered upstream: one byte changed in a file the series does NOT touch.
fresh_copy "$WP_SRC" "$WORK/wp-tampered"
printf '\n' >> "$WORK/wp-tampered/wp-includes/formatting.php"
expect 1 "3. tampered upstream tree is rejected before any patch is applied" -- "$PS" apply "$WORK/wp-tampered" "$WP_SERIES"

# 4. Tampered patch file.
cp -R "$WP_SERIES" "$WORK/series-tampered"
sed -i.bak 's/modified 2026-11-22\./modified 2026-11-23./' "$WORK/series-tampered/0002-post-ids-use-object-id-helper.patch" && rm "$WORK/series-tampered/"*.bak
fresh_copy "$WP_SRC" "$WORK/wp-7.1.5-b"
expect 1 "4. tampered patch file is rejected by the series hash manifest" -- "$PS" apply "$WORK/wp-7.1.5-b" "$WORK/series-tampered"

# 5. Simulated next upstream release, offset only: 3 comment lines added at the top of post.php.
fresh_copy "$WP_SRC" "$WORK/wp-next-offset"
perl -0pi -e 's|\A<\?php\n|<?php\n// Simulated upstream change 1.\n// Simulated upstream change 2.\n// Simulated upstream change 3.\n|' "$WORK/wp-next-offset/wp-includes/post.php"
expect 1 "5a. strict apply refuses a drifted tree (offset-only drift)" -- "$PS" apply "$WORK/wp-next-offset" "$WP_SERIES"
expect 3 "5b. rebase-check dry run (offset-only drift)" -- "$PS" rebase-check "$WORK/wp-next-offset" "$WP_SERIES"

# 6. Simulated next upstream release with a real conflict: is_sticky() cast line changed upstream.
fresh_copy "$WP_SRC" "$WORK/wp-next-conflict"
perl -0pi -e 's|(function is_sticky\( \$post_id = 0 \) \{\n)\t\$post_id = absint\( \$post_id \);|$1\t\$post_id = (int) \$post_id; // simulated upstream security fix|' "$WORK/wp-next-conflict/wp-includes/post.php"
expect 3 "6. rebase-check dry run (conflicting upstream change)" -- "$PS" rebase-check "$WORK/wp-next-conflict" "$WP_SERIES"

# Remove the upstream copies (thousands of third-party files) unless asked to keep them.
[ "${KEEP_WORK:-0}" = 1 ] || rm -rf "$WORK"

echo
if [ "$failures" -eq 0 ]; then echo "DEMO RESULT: all scenarios behaved as expected"; else echo "DEMO RESULT: $failures scenario(s) did NOT behave as expected"; exit 1; fi
