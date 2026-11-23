#!/bin/sh
set -eu
umask 077
mkdir /scratch/uploads /scratch/cache
export PRESSGRES_QUERY_LOG=/scratch/cache/queries.jsonl
export TMPDIR=/scratch/cache

# The parent stays alive to copy observations after the PHP child is killed.
# The driver also enforces an independent container-level deadline.
status=0
timeout -s KILL 4 php -d memory_limit=64M -d max_execution_time=0 \
    /harness/activate.php "$1" > /scratch/cache/php-output.log 2>&1 || status=$?
printf 'R006 kernel\n'
awk '/^(Uid|Gid|CapEff|NoNewPrivs|Seccomp):/ {print}' /proc/self/status
awk 'NR > 1 && $2 == "00000000" {print "DefaultIPv4Route: 1"}' /proc/net/route
printf 'R006 events\n'
if [ -f /scratch/cache/events.jsonl ]; then cat /scratch/cache/events.jsonl; fi
printf '\nR006 queries\n'
if [ -f "$PRESSGRES_QUERY_LOG" ]; then cat "$PRESSGRES_QUERY_LOG"; fi
printf '\nR006 files\n'
find /scratch/uploads /scratch/cache -type f | LC_ALL=C sort
printf 'R006 end\n'
if [ "$status" -ne 0 ] && [ "$status" -ne 137 ]; then
    tail -c 4096 /scratch/cache/php-output.log >&2
    if [ -f /scratch/cache/wp-debug.log ]; then tail -c 4096 /scratch/cache/wp-debug.log >&2; fi
fi
exit "$status"
