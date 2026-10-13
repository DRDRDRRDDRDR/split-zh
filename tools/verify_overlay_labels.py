# -*- coding: utf-8 -*-
"""Gate: the five in-world prompt labels we translated must sit where retail's
English sat, not where the CJK fallback happened to drop them.

WHAT IS CHECKED
    For each of the five labels the gate reads offset_top and offset_bottom out
    of the shipped main.scn and requires them to equal the value the renderer
    measurement produced (work/rendertest/overlay_probe.gd, 1:1, engine's own
    renderer) with a tolerance of TOL parent units.

    It also re-derives the LIFT from the two measured ink centres and requires
    the difference between our shipped pair and retail's pair to equal that lift
    -- so a future edit that moves the label but keeps the file self-consistent
    still fails.

WHY IT MATTERS
    Retail tuned these offsets for Mx437 (ascent ~0.75 em).  Our Chinese shapes
    through the Noto Sans SC fallback (ascent 1.16 em) and the ink drifts.  The
    same class of bug shipped twice already (the nano labels, v1.5.1), so the
    check is pinned to measured pixels rather than to a formula.

NEGATIVE CONTROLS
    --legacy   retail offsets           (the pre-translation geometry)
    --iter1    the analytic shaped-ascent prediction applied (7.5222 / 7.6833 /
               18.0700 / 8.5627 / 8.5627) -- the model that over-lifted by up to
               13x on `your mind is at`; it must fail.
"""
import hashlib
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
TOL = 0.01

CT = "\u5173\u952e\u601d\u7eea\u4f1a\u5728\u73af\u5883\u4e2d\u4ee5\u89c6\u89c9\u5f62\u5f0f\u5448\u73b0\u3002\n\u968f\u65f6\u952e\u5165\u5373\u53ef\u786e\u8ba4\u5b83\u4eec\u3002"
MIND = "[center]\u4f60\u5fc3\u795e\u5b89\u5b9a\u3002[/center]"
SPACE = "\u6309 SPACE \u786e\u8ba4\u3002"
ALT = "< \u6309\u4f4f ALT \u62bd\u79bb\u81ea\u8eab >"
PIVOT = "< \u7528 A \u6216 D \u8f6c\u52a8\u9888\u690e >"

# name, text, back-offsets of top/bottom, retail band, phase0 ink centre,
# phase1 ink centre, shipped band
CASES = [
    ("center text", CT, 128, 112, (67.0, 160.0), 102.292, 103.024, (66.268, 159.268)),
    ("your mind is at", MIND, 100, 84, (-54.0, 32.0), -24.984, -11.624, (-67.360, 18.640)),
    ("press space to accept", SPACE, 128, 112, (150.0, 243.0), 168.332, 170.364, (147.968, 240.968)),
    ("hold alt to distance yourself", ALT, 128, 112, (703.0, 782.0), 723.136, 724.959, (701.176, 780.176)),
    ("pivot your cervical spine with A or D", PIVOT, 128, 112, (703.0, 782.0), 723.551, 724.176, (702.375, 781.375)),
]

MODE = "current"
for flag, m in (("--legacy", "legacy"), ("--iter1", "iter1")):
    if flag in sys.argv:
        MODE = m

raw = open(DIST, "rb").read()
print("=" * 96)
print("OVERLAY LABEL GATE (%s)  -  %s" % (MODE, DIST))
print("=" * 96)
print("  %d B  sha256 %s" % (len(raw), hashlib.sha256(raw).hexdigest().upper()))
print("")

h = IS.scan_entries(raw)
blob, ent = IS.blob_of(raw, h, SCENE)
rd = variant_walk.Reader(blob, rsrc.parse(blob))
rd.walk()
seen = {}
for s in rd.slots:
    t = s.get("text")
    if isinstance(t, str):
        seen.setdefault(t, []).append(s["off"])

fails = []
for name, text, tb, bb, retail, c0, c1, want in CASES:
    offs = seen.get(text)
    if not offs or len(offs) != 1:
        fails.append("%s: expected exactly 1 text slot, got %r" % (name, offs))
        continue
    off = offs[0]
    got_top = struct.unpack_from("<f", blob, off - tb)[0]
    got_bot = struct.unpack_from("<f", blob, off - bb)[0]
    lift = c1 - c0                       # positive means "must move up"
    exp_top = retail[0] - lift
    exp_bot = retail[1] - lift
    if MODE == "legacy":
        exp_top, exp_bot = retail
    elif MODE == "iter1":
        # re-derive what the analytic model would have written: its predictions
        # were 7.5222 / 7.6833 / 18.0700 / 8.5627 / 8.5627
        pred = {"center text": 7.6833, "your mind is at": 18.0700,
                "press space to accept": 7.5222, "hold alt to distance yourself": 8.5627,
                "pivot your cervical spine with A or D": 8.5627}[name]
        exp_top, exp_bot = retail[0] - pred, retail[1] - pred
    ok = abs(got_top - exp_top) <= TOL and abs(got_bot - exp_bot) <= TOL
    print("  %-40s off=%d  top %9.4f (want %9.4f)  bottom %9.4f (want %9.4f)  lift %+7.4f  %s"
          % (name, off, got_top, exp_top, got_bot, exp_bot, lift, "OK" if ok else "FAIL"))
    if not ok:
        fails.append("%s: top/bottom %.4f/%.4f != %.4f/%.4f"
                     % (name, got_top, got_bot, exp_top, exp_bot))
    # height must be preserved: retail height == shipped height
    if abs((got_bot - got_top) - (retail[1] - retail[0])) > TOL:
        fails.append("%s: height changed %.4f != %.4f"
                     % (name, got_bot - got_top, retail[1] - retail[0]))

print("")
if MODE != "current":
    print("VERDICT: %s (negative control, %d complaint(s) as intended)"
          % ("FAIL" if fails else "PASS - CONTROL DID NOT FAIL", len(fails)))
    for f in fails:
        print("  ! %s" % f)
    sys.exit(1 if fails else 1)
if fails:
    print("VERDICT: FAIL - %d problem(s)" % len(fails))
    for f in fails:
        print("  ! %s" % f)
    sys.exit(1)
print("VERDICT: PASS - 5 overlay labels restored to the ink band retail's English used")
