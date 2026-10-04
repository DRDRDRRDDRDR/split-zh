# -*- coding: utf-8 -*-
"""GATE: the three live hkIRC24 / chat labels carry the screenshot-verified offsets.

The target values were solved from the player's own screenshots, not from a font
model (two model attempts were wrong; the measurement was not):

  shot A (no lift)     #d9xb1 ink rows 307..328  centre 317.5 px
  shot B (22.96 lift)  #d9xb1 ink rows 285..306  centre 295.5 px
  => 22 px / 22.96 units = 0.9582 px per label unit
  tab box interior     rows 284..330 -> centre 307 px
  => the word must rise (317.5-307)/0.9582 = 10.96 units from retail's place

  chat name        : 246.04 / 297.04   (retail 257 / 308)
  chat name header : 304.04 / 355.04   (retail 315 / 366)
  status (状态)     : 251.88 / 302.88  font 38   (verified correct by the player)

Negative controls:
  --legacy  the original shipping values        (every label too low)
  --iter1   first correction (状态 only)         (状态 overshot the other way)
  --iter2   second correction (22.96 lift)      (ASCII labels overshot)

Read-only.  Usage: python verify_tab_label.py [--legacy|--iter1|--iter2]
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import inject_slots as IS                                   # noqa: E402
import rsrc                                                 # noqa: E402
import variant_walk                                         # noqa: E402

DIST = os.path.join(ROOT, "dist", "split.exe")
SCENE = "res://.godot/exported/133200997/export-3ad5c15c4f3250da0cc7c1af1770d85f-main.scn"
MODE = next((a for a in sys.argv[1:] if a.startswith("--")), "")
TOL = 0.06                      # tolerance in label units on the pinned values
D_TOP, D_BOTTOM, D_FONT = -84, -68, -8

EXPECT = {
    "\u72b6\u6001#0": (251.88, 302.88, 38, "status(状态)"),
    "#d9xb1#329": (246.04, 297.04, 56, "chat name"),
    "#d9xb1#58": (304.04, 355.04, 56, "chat name header"),
}
ALT = {
    "--legacy": {
        "\u72b6\u6001#0": (257.00, 308.00, 56),
        "#d9xb1#329": (257.00, 308.00, 56),
        "#d9xb1#58": (315.00, 366.00, 56),
    },
    "--iter1": {
        "\u72b6\u6001#0": (267.55, 318.55, 38),
        "#d9xb1#329": (257.00, 308.00, 56),
        "#d9xb1#58": (315.00, 366.00, 56),
    },
    "--iter2": {
        "\u72b6\u6001#0": (251.88, 302.88, 38),
        "#d9xb1#329": (234.04, 285.04, 56),
        "#d9xb1#58": (292.04, 343.04, 56),
    },
}

b = open(DIST, "rb").read()
h = IS.scan_entries(b)
blob, _e = IS.blob_of(b, h, SCENE)
rd = variant_walk.Reader(blob, rsrc.parse(blob))
rd.walk()

seen = {}
for s in rd.slots:
    t = s.get("text")
    if t not in ("\u72b6\u6001", "#d9xb1"):
        continue
    off = s["off"]
    left = struct.unpack_from("<f", blob, off - 92)[0]
    key = t + ("#0" if t == "\u72b6\u6001" else "#%d" % int(left))
    seen[key] = (struct.unpack_from("<f", blob, off + D_TOP)[0],
                 struct.unpack_from("<f", blob, off + D_BOTTOM)[0],
                 struct.unpack_from("<i", blob, off + D_FONT)[0])

print("=" * 96)
print("GATE: hkIRC24 / chat label offsets (screenshot-verified)%s"
      % ("   [%s negative control]" % MODE if MODE else ""))
print("=" * 96)
problems = []
for key, (e_top, e_bot, e_font, name) in EXPECT.items():
    got = seen.get(key)
    if got is None:
        problems.append("%s: slot missing" % name)
        continue
    want = ALT.get(MODE, {}).get(key) if MODE else (e_top, e_bot, e_font)
    if want is None:
        want = (e_top, e_bot, e_font)
    ok = (abs(got[0] - want[0]) <= TOL and abs(got[1] - want[1]) <= TOL
          and got[2] == want[2])
    if not ok:
        problems.append("%s: top=%.2f bottom=%.2f font=%d, expected %.2f/%.2f/%d"
                        % (name, got[0], got[1], got[2], want[0], want[1], want[2]))
    print("  %-18s top=%-8.2f bottom=%-8.2f font=%-3d  expected %-8.2f %-8.2f %-3d  %s"
          % (name, got[0], got[1], got[2], want[0], want[1], want[2],
             "OK" if ok else "*** FAIL ***"))

print("")
if problems:
    print("VERDICT: FAIL")
    for p in problems:
        print("   %s" % p)
    sys.exit(1)
print("VERDICT: PASS - all three labels carry the offsets solved from the player's")
print("        screenshots: status 251.88/302.88 f38; #d9xb1 246.04/297.04 and")
print("        304.04/355.04 at f56.")
