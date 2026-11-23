"""Unit tests for tools/core-phpunit/ratchet.py (stdlib unittest).

Run: python3 -m unittest discover -s tools/core-phpunit/tests -v
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.dirname(HERE))

import ratchet  # noqa: E402

EXPECTED = ["Tests_Foo::test_a", "Tests_Foo::test_b", "Tests_Foo::test_c with data set #0"]
CONTROL = EXPECTED + ["Tests_Bar::test_d"]
META = {"tests": 6, "pass": 3, "failure": 1, "error": 1, "skipped": 1, "pass_rate": 50.0, "comparable_pass_rate": 75.0}


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def fx(name):
    return os.path.join(FIX, name)


class RatchetCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.expected = os.path.join(d, "expected-pass.txt")
        self.control = os.path.join(d, "mysql-control-pass.txt")
        self.meta = os.path.join(d, "baseline.json")
        self.flaky = os.path.join(d, "flaky.txt")
        ratchet.write_list(self.expected, EXPECTED)
        ratchet.write_list(self.control, CONTROL)
        with open(self.meta, "w") as fh:
            json.dump(META, fh)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args):
        argv = ["--expected", self.expected, "--control", self.control, "--meta", self.meta, "--flaky", self.flaky]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ratchet.main(argv + list(args))
        return rc, out.getvalue() + err.getvalue()

    # --- check ---------------------------------------------------------

    def test_unchanged_run_passes(self):
        rc, out = self.run_cli("check", fx("baseline.xml"))
        self.assertEqual(rc, 0, out)
        self.assertIn("RATCHET: PASS", out)
        self.assertIn("comparable_pass_rate=75.00%", out)

    def test_improvement_passes_and_lists_newly_passing(self):
        md = os.path.join(self.tmp.name, "summary.md")
        outdir = os.path.join(self.tmp.name, "out")
        rc, out = self.run_cli("check", fx("improved.xml"), "--summary-md", md, "--out-dir", outdir)
        self.assertEqual(rc, 0, out)
        self.assertIn("NEWLY PASSING Tests_Bar::test_d", out)
        self.assertIn("ratchet.py update", out)
        text = read(md)
        self.assertIn("ratchet PASS", text)
        self.assertIn("### Newly passing", text)
        self.assertIn("100.00 %", text)  # comparable pass rate 4/4
        self.assertEqual(ratchet.read_list(os.path.join(outdir, "newly-passing.txt")), {"Tests_Bar::test_d"})
        cand = ratchet.read_list(os.path.join(outdir, "expected-pass.candidate.txt"))
        self.assertEqual(cand, set(EXPECTED) | {"Tests_Bar::test_d"})
        meta = json.loads(read(os.path.join(outdir, "baseline.candidate.json")))
        self.assertEqual(meta["pass"], 4)
        self.assertEqual(meta["comparable_pass_rate"], 100.0)

    def test_regression_fails_with_status_and_missing(self):
        md = os.path.join(self.tmp.name, "summary.md")
        rc, out = self.run_cli("check", fx("regressed.xml"), "--summary-md", md)
        self.assertEqual(rc, 1, out)
        self.assertIn("REGRESSION [error] Tests_Foo::test_b", out)
        self.assertIn("REGRESSION [missing] Tests_Foo::test_c with data set #0", out)
        self.assertIn("2 expected-pass test(s) no longer pass", out)
        self.assertIn("ratchet FAIL", read(md))

    def test_duplicate_id_passes_only_if_every_occurrence_passes(self):
        rc, out = self.run_cli("check", fx("duplicate.xml"))
        self.assertEqual(rc, 1, out)
        self.assertIn("REGRESSION [failure] Tests_Foo::test_a", out)

    def test_flaky_ids_are_ignored(self):
        ratchet.write_list(self.flaky, ["Tests_Foo::test_b", "Tests_Foo::test_c with data set #0"])
        rc, out = self.run_cli("check", fx("regressed.xml"))
        self.assertEqual(rc, 0, out)
        self.assertIn("flaky_passing=0/2", out)

    def test_test_count_drop_over_one_percent_fails(self):
        rc, out = self.run_cli("check", fx("collapsed.xml"))
        self.assertEqual(rc, 1, out)
        self.assertIn("test count: 2 JUnit tests is more than 1% below the baseline 6", out)
        # Same run is fine when the tolerance is large enough.
        rc, out = self.run_cli("check", fx("collapsed.xml"), "--max-count-drop-pct", "80")
        self.assertNotIn("test count:", out)

    def test_count_drop_within_tolerance_passes(self):
        with open(self.meta, "w") as fh:
            json.dump(dict(META, tests=6), fh)
        rc, _ = self.run_cli("check", fx("baseline.xml"))
        self.assertEqual(rc, 0)

    def test_zero_tests_is_a_bootstrap_failure(self):
        md = os.path.join(self.tmp.name, "summary.md")
        log = os.path.join(self.tmp.name, "phpunit.log")
        with open(log, "w") as fh:
            fh.write("Installing...\nWordPress database error: statement type 'CREATE' is not allowed\n")
        rc, out = self.run_cli("check", fx("empty.xml"), "--summary-md", md, "--phpunit-log", log)
        self.assertEqual(rc, 1, out)
        self.assertIn("contains 0 tests", out)
        self.assertIn("statement type 'CREATE'", out)
        self.assertIn("did not reach PHPUnit", read(md))

    def test_missing_junit_is_a_bootstrap_failure(self):
        rc, out = self.run_cli("check", os.path.join(self.tmp.name, "nope.xml"))
        self.assertEqual(rc, 1)
        self.assertIn("JUnit file not found", out)

    def test_truncated_junit_is_a_bootstrap_failure(self):
        bad = os.path.join(self.tmp.name, "trunc.xml")
        with open(fx("baseline.xml")) as src, open(bad, "w") as dst:
            dst.write(src.read()[:300])
        rc, out = self.run_cli("check", bad)
        self.assertEqual(rc, 1)
        self.assertIn("not valid XML", out)

    def test_invalid_xml_characters_are_tolerated(self):
        rc, out = self.run_cli("check", fx("invalid-char.xml"))
        # test_b's name changed (U+FFFE replaced), so it counts as missing; parsing must not crash.
        self.assertEqual(rc, 1, out)
        self.assertIn("tests=6", out)

    def test_empty_expected_list_is_a_usage_error(self):
        ratchet.write_list(self.expected, [])
        rc, out = self.run_cli("check", fx("baseline.xml"))
        self.assertEqual(rc, 2)
        self.assertIn("expected-pass list missing or empty", out)

    def test_csv_row(self):
        path = os.path.join(self.tmp.name, "run.csv")
        self.run_cli("check", fx("improved.xml"), "--csv", path, "--label", "x")
        rows = read(path).splitlines()
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0].startswith("label,utc,git_sha,bootstrap,tests,pass"))
        self.assertIn(",x,", "," + rows[1])
        self.assertTrue(rows[1].endswith(",0,1,pass"))

    # --- update / passing ---------------------------------------------

    def test_update_replaces_list_with_intersection_of_runs(self):
        rc, out = self.run_cli("update", fx("improved.xml"), fx("baseline.xml"))
        self.assertEqual(rc, 0, out)
        # test_d passes in only one run: unstable, left out.
        self.assertIn("UNSTABLE Tests_Bar::test_d", out)
        self.assertEqual(ratchet.read_list(self.expected), set(EXPECTED))
        meta = json.loads(read(self.meta))
        self.assertEqual(meta["tests"], 6)
        self.assertEqual(meta["expected_pass"], 3)
        self.assertIn("generated_utc", meta)

    def test_update_merge_only_adds(self):
        rc, _ = self.run_cli("update", fx("regressed.xml"), "--merge")
        self.assertEqual(rc, 0)
        self.assertEqual(ratchet.read_list(self.expected), set(EXPECTED) | {"Tests_Foo::test_c with data set #1"})
        rc, _ = self.run_cli("update", fx("regressed.xml"))
        self.assertEqual(ratchet.read_list(self.expected), {"Tests_Foo::test_a", "Tests_Foo::test_c with data set #1"})

    def test_passing_subcommand(self):
        out = os.path.join(self.tmp.name, "p.txt")
        rc, _ = self.run_cli("passing", fx("improved.xml"), "--out", out)
        self.assertEqual(rc, 0)
        self.assertEqual(ratchet.read_list(out), set(CONTROL))

    def test_escape_id_keeps_one_line(self):
        self.assertEqual(ratchet.escape_id("A::b with data set \"x\ny\\z\""), 'A::b with data set "x\\ny\\\\z"')


if __name__ == "__main__":
    unittest.main()
