# -*- coding: utf-8 -*-
"""Run every acceptance gate in one shot and print a single verdict.

Each gate is a standalone read-only script that exits 0 on PASS.  This runner exists
because the gates were previously invoked by hand, so it was easy to run five and
forget the sixth -- exactly how the tab-label bug survived a "all gates pass" claim.

Usage: python run_all_gates.py            # run all
       python run_all_gates.py --quick    # skip the two slow structural gates
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (script, what it proves)
GATES = [
    ("verify_pck_md5.py",        "index digests match the bytes they index"),
    ("verify_gdc_bytecode.py",   "compiled GDScript is valid and carries the text"),
    ("verify_thoughts_gate.py",  "every thought has a displayable Chinese form"),
    ("verify_phrase_layout.py",  "batched thoughts share one row, no overlap"),
    ("verify_tab_label.py",      "labels sit in the band retail drew them in"),
    ("verify_nano_labels.py",    "nano editor labels are centred in their boxes"),
    ("verify_overlay_labels.py", "translated overlay labels keep retail's ink band"),
    ("verify_logic_keys.py",     "control-flow literals survive translation"),
    ("verify_delivery.py",       "release/ matches dist, pins agree, rollback valid"),
]
QUICK = {"verify_pck_md5.py", "verify_gdc_bytecode.py"}

quick = "--quick" in sys.argv
results = []
for script, proves in GATES:
    path = os.path.join(HERE, script)
    if quick and script in QUICK:
        results.append((script, proves, None, "skipped (--quick)"))
        print("  %-26s SKIP  %s" % (script, proves))
        continue
    if not os.path.isfile(path):
        results.append((script, proves, 1, "script missing"))
        print("  %-26s FAIL  %s  (script missing)" % (script, proves))
        continue
    p = subprocess.run([sys.executable, path], capture_output=True, cwd=HERE)
    out = (p.stdout or b"").decode("utf-8", "replace")
    verdict = ""
    for line in out.splitlines():
        if line.startswith("VERDICT"):
            verdict = line.strip()
    ok = p.returncode == 0
    results.append((script, proves, 0 if ok else 1, verdict))
    print("  %-26s %-4s %s" % (script, "PASS" if ok else "FAIL", proves))
    if not ok and verdict:
        print("      %s" % verdict)

failed = [r for r in results if r[2] == 1]
print("")
print("=" * 96)
if failed:
    print("VERDICT: FAIL - %d of %d gate(s) failed:"
          % (len(failed), len(results)))
    for script, proves, _rc, _v in failed:
        print("   %s  (%s)" % (script, proves))
    sys.exit(1)
ran = [r for r in results if r[2] == 0]
print("VERDICT: PASS - %d/%d gate(s) passed%s."
      % (len(ran), len(results), " (some skipped)" if quick else ""))
print("=" * 96)