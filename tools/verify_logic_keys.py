# -*- coding: utf-8 -*-
"""GATE: no scene-supplied string that a script branches on was translated away.

The risk this guards
--------------------
Some player-visible text doubles as a control-flow key.  Two live examples:

  Login.gd:86   if "Replacing." in line_array[index]:                  wait_next = true
  Login.gd:87   if "[  OK  ] bounce: isa pool size: 16 pages" in line_array[index]:
                    show_login = true                       <- without it: soft-lock
  NanoEditor.gd:141  "trusted device list":                <- nano save-check key

The boot log those first two read IS translated into Chinese, so a translator who
"finishes the job" by also translating those two lines would soft-lock the game: the
login screen would never appear.

How the gate decides
--------------------
For every literal a script COMPARES against (==, !=, `in`, match arm, begins_with,
ends_with) it checks, in order:

  1. present in the shipped executable's raw bytes?          -> OK (ships verbatim)
  2. present in some .tscn SOURCE?                            -> FAIL (it is scene-supplied
        display text, so it must also be in the shipped scene, and it is not)
  3. otherwise (script-internal alias, never displayed)       -> OK

Rule 2 is what makes this sound.  Note the shipped .gdc bytecode is ZSTD-compressed, so
a script-internal literal is NOT findable by a byte search -- that is expected and is
why rule 3 exists.  A literal that only ever lived in a script cannot be translated out
from under the script, because translation only touches scene/bytecode strings
deliberately.

Negative control: --legacy re-runs with the boot-log keys treated as translated away,
which must FAIL.

Read-only.  Usage: python verify_logic_keys.py [--legacy]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = os.path.join(ROOT, "recovered", "scripts")
SCENEDIR = os.path.join(ROOT, "recovered", "scenes")
DIST = os.path.join(ROOT, "dist", "split.exe")
LEGACY = "--legacy" in sys.argv

# the two keys whose loss would be a hard soft-lock; used by the negative control
CRITICAL = ["[  OK  ] bounce: isa pool size: 16 pages", "Replacing."]

STR = re.compile(r'"((?:[^"\\]|\\.)*)"')
PATTERNS = [
    re.compile(STR.pattern + r'\s+in\s'),                   # "X" in ...
    re.compile(r'\bin\s+' + STR.pattern),                   # in "X"
    re.compile(r'==\s*' + STR.pattern),                     # == "X"
    re.compile(r'!=\s*' + STR.pattern),                     # != "X"
    re.compile(r'^\s*' + STR.pattern + r'\s*:\s*$'),        # match arm  "X":
    re.compile(r'\.begins_with\(\s*' + STR.pattern),
    re.compile(r'\.ends_with\(\s*' + STR.pattern),
]
IGNORE = re.compile(r"^([\s\W]*|[a-z_]+|[A-Z_]+|res://.*|user://.*|/.*|\.\.+)$")

exe = open(DIST, "rb").read()
scene_text = []
for root, _d, files in os.walk(SCENEDIR):
    for fn in files:
        if fn.endswith(".tscn"):
            scene_text.append(open(os.path.join(root, fn), encoding="utf-8",
                                   errors="replace").read())
SCENES = "\n".join(scene_text)

print("=" * 104)
print("GATE: script comparison literals%s" % ("   [--legacy negative control]" if LEGACY else ""))
print("=" * 104)
if LEGACY:
    # pretend the two soft-lock keys were translated away
    exe = exe.replace(CRITICAL[0].encode("utf-8"), b"")
    exe = exe.replace(CRITICAL[1].encode("utf-8"), b"")

rows, seen = [], set()
for fn in sorted(os.listdir(SRC)):
    if not fn.endswith(".gd"):
        continue
    for n, line in enumerate(open(os.path.join(SRC, fn), encoding="utf-8",
                                  errors="replace"), 1):
        if line.strip().startswith("#"):
            continue
        for pat in PATTERNS:
            for m in pat.finditer(line):
                lit = m.group(1)
                if len(lit) < 4 or IGNORE.match(lit) or (fn, lit) in seen:
                    continue
                seen.add((fn, lit))
                rows.append((fn, n, lit))

problems = []
for fn, n, lit in rows:
    if lit.encode("utf-8") in exe:
        verdict = "in build"
    elif lit in SCENES:
        verdict = "*** scene text MISSING from build ***"
        problems.append((fn, n, lit))
    else:
        verdict = "script-internal (exempt)"
    print("  %-24s:%-5d %-46r %s" % (fn, n, lit[:46], verdict))

print("")
print("  distinct comparison literals: %d" % len(rows))
if problems:
    print("")
    print("VERDICT: FAIL - %d scene-supplied literal(s) a script branches on are no"
          % len(problems))
    print("        longer in the build; control flow that depends on them is broken:")
    for fn, n, lit in problems:
        print("           %s:%d  %r" % (fn, n, lit[:64]))
    sys.exit(1)
print("")
print("VERDICT: PASS - every scene-supplied literal the scripts branch on is still")
print("        byte-present in the build; the rest are script-internal aliases that")
print("        translation never touches.")