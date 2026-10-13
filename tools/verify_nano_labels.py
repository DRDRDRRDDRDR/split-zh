# -*- coding: utf-8 -*-
"""Gate: the 9 nano-editor labels must sit centrally inside their cream boxes.

Regression for the "编辑页面字太高了" defect: an earlier patch lifted every
box-bound label by 0.41*font_size = 27.06 Control-space units.  That figure is
the extra ascent the CJK fallback adds in the label's LOCAL font space; because
the nodes carry `scale = 0.386718`, the correct displacement in the PARENT space
is 0.41 * 66 * 0.386718 = 10.46 units.  27.06 over-shot by 2.59x and pushed the
glyphs above their boxes (window screenshot 3c6f0ac8... 2026-10-13 15:18).

Model (validated against the pre-lift screenshot m00221-feb60c3a.jpg):
    baseline   = offset_top + ascent * font_size * scale
    ascent     = 1.16 em   (Noto Sans SC hhea 1160/1000 -- the fallback chain's
                            maximum governs, Godot uses it for Latin lines too)
    em_px      = 66 * 0.386718 = 25.5234 parent units
    ink_above  = 0.8410 em, ink_below = 0.0750 em   (FreeType, 状态)
  At lift 0 this predicts the CJK ink top at row 106.4 for `rect header`
  (bar top 99.5, 0.567 px/unit); the screenshot measures 105.5..106.

Target: ink centred in the 30-unit box -- `offset_top = box_top - 4.8317`.

Negative controls:
    --legacy  retail 144/205 etc. (pushed the ink below the box)
    --iter1   the 27.06 over-lift 116.94/177.94 etc. (pushed it above the box)

Usage: python verify_nano_labels.py [--legacy|--iter1]
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
D_TOP, D_BOTTOM, D_FONT = -104, -88, -8

EM_PX = 66 * 0.386718
ASCENT, INK_ABOVE, INK_BELOW = 1.16, 0.8410, 0.0750
INK_H = (INK_ABOVE + INK_BELOW) * EM_PX
BOX_H = 30.0
MIN_MARGIN = 2.0
TOL = 0.01
CENTRE = (ASCENT - INK_ABOVE) * EM_PX - (BOX_H - INK_H) / 2.0     # 4.8317

MODE = "current"
for a in ("--legacy", "--iter1"):
    if a in sys.argv:
        MODE = a[2:]

# text -> (box name, box top, retail top, bad-lift top)
SPEC = [
    ("GNU nano 16.2",                 "rect header",             140.0, 144.0, 116.94),
    ("\u53c2\u8003\u8868 490",        "rect header",             140.0, 144.0, 116.94),
    ("\u6a21\u5f0f\uff1a\u7f16\u8f91", "rect header",             140.0, 144.0, 116.94),
    ("CTRL + G \uff1a\u5e2e\u52a9",    "rect view help",          790.0, 793.0, 765.94),
    ("\u4fdd\u5b58\u66f4\u6539\uff1f",  "rect save changes ?",     790.0, 794.0, 766.94),
    ("CTRL + X \uff1a\u9000\u51fa",    "rect exit editing",       831.0, 835.0, 807.94),
    ("Y \uff1a\u662f",                 "rect save changes yes",   831.0, 835.0, 807.94),
    ("N \uff1a\u5426",                 "rect save changes no",    831.0, 835.0, 807.94),
]
EXPECTED_SLOTS = 9          # CTRL + X ：退出 appears twice


def want(box_top, retail_top, bad_top):
    if MODE == "legacy":
        return retail_top, retail_top + 61.0
    if MODE == "iter1":
        return bad_top, bad_top + 61.0
    return box_top - CENTRE, box_top - CENTRE + 61.0


def main():
    print("=" * 90)
    print("NANO LABEL GATE   mode=%s   %s" % (MODE, DIST))
    print("=" * 90)
    b = open(DIST, "rb").read()
    h = IS.scan_entries(b)
    blob, _ent = IS.blob_of(b, h, SCENE)
    rd = variant_walk.Reader(blob, rsrc.parse(blob))
    rd.walk()

    spec = {}
    for t, box, btop, rtop, bad in SPEC:
        spec.setdefault(t, (box, btop, rtop, bad))
    seen = {}
    fails = 0
    for s in rd.slots:
        t = s.get("text")
        if not isinstance(t, str) or t not in spec:
            continue
        box, btop, rtop, bad = spec[t]
        got_top = struct.unpack_from("<f", blob, s["off"] + D_TOP)[0]
        got_bot = struct.unpack_from("<f", blob, s["off"] + D_BOTTOM)[0]
        font = struct.unpack_from("<i", blob, s["off"] + D_FONT)[0]
        want_top, want_bot = want(btop, rtop, bad)
        # Grade the geometry of the candidate under test, not the file's value, so
        # the negative controls show *why* those numbers break the box.
        cand = got_top if MODE == "current" else want_top
        seen[t] = seen.get(t, 0) + 1

        ink_top = cand + (ASCENT - INK_ABOVE) * EM_PX
        ink_bot = ink_top + INK_H
        m_top = ink_top - btop
        m_bot = (btop + BOX_H) - ink_bot
        bad_pos = abs(got_top - want_top) > TOL or abs(got_bot - want_bot) > TOL
        bad_box = font != 66 or m_top < MIN_MARGIN or m_bot < MIN_MARGIN
        ok = not bad_pos and not bad_box
        if not ok:
            fails += 1
        print("  %-16r %-22s top=%8.4f bottom=%8.4f font=%d  ink %.2f..%.2f "
              "box %.1f..%.1f  margins %+6.2f/%+6.2f  %s"
              % (t, box, cand, cand + 61.0, font, ink_top, ink_bot,
                 btop, btop + BOX_H, m_top, m_bot, "OK" if ok else "FAIL"))
    print("")
    total = sum(seen.values())
    if total != EXPECTED_SLOTS:
        print("  slot count %d != %d" % (total, EXPECTED_SLOTS))
        fails += 1
    print("  slots found: %d   failures: %d" % (total, fails))
    print("")
    if MODE == "current":
        print("VERDICT: %s" % ("PASS" if fails == 0 else "FAIL"))
    else:
        print("VERDICT: %s (negative control, expected FAIL)"
              % ("FAIL" if fails else "UNEXPECTED PASS"))
    return 0 if ((fails == 0) == (MODE == "current")) else 1


if __name__ == "__main__":
    sys.exit(main())
