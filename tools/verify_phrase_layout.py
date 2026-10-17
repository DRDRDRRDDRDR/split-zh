# -*- coding: utf-8 -*-
"""GATE: with per-word Chinese, does any row land on another row?

Contract under test (2026-10-17): every word owns the Chinese for itself and that
Chinese is drawn in ONE shared slot per group, at the group's topmost node.  The
slot's TEXT advances as the player moves from word to word, and empties when the
group is finished.

Why the slot is shared rather than one row per word -- and what this gate proves:

  * A word's typed English row sits one row below its own origin, leaving room for a
    Chinese row at the origin.
  * The scene leaves far less than one row between neighbouring words.  Measured for
    the drill group: 0.0296 of world space against a 0.0400 row height.
  * Therefore a Chinese row at EACH word's own origin lands on a neighbour's English
    row.  That is the "UN结果IRABLI" overlap players reported, and it is what the
    --legacy mode reproduces so this gate cannot pass a broken layout.

Model (all values read from the scene, no guessing):
    row height in a node's local units = 1.15 * em_height * font_size * pixel_size
    the same height in world units    = that, times |basis_y| of the node's basis
    ink height                        = 0.75 of the row for ASCII,
                                        0.916 for the CJK fallback that draws 状态

A pair only counts as an on-screen collision when the two nodes are also close
laterally (LATERAL_MAX): thought words are scattered in depth, so two words 1.0 apart
in z are drawn far apart even at equal y.
"""
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCN = os.path.join(ROOT, "recovered", "scenes", "main.tscn")
GD = os.path.join(ROOT, "recovered", "scripts", "LabelSplitter.gd")

LATERAL_MAX = 0.35
INK_RATIO = 0.75
ZH_INK_RATIO = 0.916
PIXEL_SIZE = 0.005

# Negative control: the layout where EVERY word drew its own Chinese row at its own
# origin, which is the overlap players reported.  --legacy must FAIL.
LEGACY = "--legacy" in sys.argv

src = open(GD, encoding="utf-8", errors="replace").read()


def table(name):
    m = re.search(r"const %s = \{(.*?)\n\}" % name, src, re.S)
    if not m:
        raise SystemExit("cannot find const %s in LabelSplitter.gd" % name)
    return dict(re.findall(r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"', m.group(1)))


TYPED_EN = table("TYPED_EN")
DISPLAY_ZH = table("DISPLAY_ZH")

lines = open(SCN, encoding="utf-8", errors="replace").read().splitlines()
starts = [(i, m.group(1)) for i, ln in enumerate(lines)
          for m in [re.match(r'\[node name="([^"]+)"', ln)] if m]


def block(idx):
    i = starts[idx][0]
    j = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
    return "\n".join(lines[i:j])


fonts = {}
for ln in lines:
    m = re.match(r'\[ext_resource type="FontFile" [^\]]*path="res://fonts/([^"]+)"[^\]]*id="([^"]+)"', ln)
    if m:
        fonts[m.group(2)] = m.group(1)
FONT_H = {}
for fid, fname in fonts.items():
    for base in (os.path.join(ROOT, "recovered", "fonts", fname),
                 os.path.join(ROOT, "fonts", fname)):
        if not os.path.exists(base):
            continue
        b = open(base, "rb").read()
        if b[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
            continue
        num = struct.unpack_from(">H", b, 4)[0]
        tab = {}
        for k in range(num):
            o = 12 + 16 * k
            tab[b[o:o + 4].decode("latin-1")] = struct.unpack_from(">II", b, o + 8)
        if "hhea" in tab and "head" in tab:
            asc, desc, _g = struct.unpack_from(">hhh", b, tab["hhea"][0] + 4)
            upem = struct.unpack_from(">H", b, tab["head"][0] + 18)[0]
            FONT_H[fid] = (asc - desc) / upem

batches = {}
for idx, (i, name) in enumerate(starts):
    if name.startswith("though batch_"):
        blk = block(idx)
        al = re.search(r'^alias = "(.*)"$', blk, re.M)
        batches[name] = {"alias": al.group(1) if al else "", "kids": []}

for idx, (i, name) in enumerate(starts):
    if not name.startswith("thought_"):
        continue
    blk = block(idx)
    par = re.search(r'parent="([^"]*)"', blk)
    bname = par.group(1).split("/")[-1] if par else ""
    if bname not in batches:
        continue
    tr = re.search(r"^transform = Transform3D\((.*?)\)$", blk, re.M)
    if not tr:
        continue
    cols = [float(c.strip()) for c in tr.group(1).split(",")]
    fs = re.search(r"^font_size = (\d+)$", blk, re.M)
    fo = re.search(r'^font = ExtResource\("([^"]+)"\)$', blk, re.M)
    tx = re.search(r'^text = "(.*)"$', blk, re.M)
    font_size = int(fs.group(1)) if fs else 152
    emh = FONT_H.get(fo.group(1), 1.0) if fo else 1.0
    by = cols[3:6]
    basis_y = (by[0] ** 2 + by[1] ** 2 + by[2] ** 2) ** 0.5
    row = 1.15 * emh * font_size * PIXEL_SIZE * basis_y
    batches[bname]["kids"].append({
        "name": name, "y": cols[10], "x": cols[9], "z": cols[11],
        "raw": tx.group(1) if tx else "",
        "row": row,
        "ink_en": INK_RATIO * emh * font_size * PIXEL_SIZE * basis_y,
        "ink_zh": ZH_INK_RATIO * font_size * PIXEL_SIZE * basis_y,
    })

print("=" * 104)
print("PER-WORD CHINESE LAYOUT%s" % ("   [LEGACY NEGATIVE CONTROL]" if LEGACY else ""))
print("=" * 104)
problems = []
checked = 0

for bname, b in sorted(batches.items(), key=lambda kv: kv[1]["alias"]):
    kids = sorted(b["kids"], key=lambda k: -k["y"])
    if not kids:
        continue
    alias = b["alias"]
    # Every word that owns Chinese, and where its row is drawn under this contract.
    has_zh = []
    for k in kids:
        raw = k["raw"]
        typed = TYPED_EN.get(raw, "")
        scene_zh = typed != ""
        disp = raw if scene_zh else DISPLAY_ZH.get(raw, "")
        k["has_zh"] = bool(disp)
        k["typed"] = typed if scene_zh else raw
        if disp:
            has_zh.append(k)
    slot = kids[0]
    print("")
    print("  batch %-38s alias=%-20s words=%-2d with-zh=%-2d slot=%s"
          % (bname[:38], alias, len(kids), len(has_zh), slot["name"][:28]))
    for k in kids:
        mark = "SLOT" if k is slot else "    "
        print("      %s %-32s y=%-9.4f row=%.4f ink_en=%.4f ink_zh=%.4f typed=%-22r zh=%s"
              % (mark, k["name"][:32], k["y"], k["row"], k["ink_en"], k["ink_zh"],
                 k["typed"][:22], "yes" if k["has_zh"] else "-"))

    # Row positions under test.
    #  non-legacy: exactly one Chinese row, at the slot's own origin.  Every word's
    #              English row is shifted down one row (the group shifts uniformly).
    #  legacy:     every word's Chinese at its own origin, same uniform shift.
    zh_rows = []       # (label, world y, ink height, node)
    en_rows = []
    for k in kids:
        en_rows.append((k["name"] + ".en", k["y"] - k["row"], k["ink_en"], k))
        if LEGACY:
            if k["has_zh"]:
                zh_rows.append((k["name"] + ".zh", k["y"], k["ink_zh"], k))
        else:
            if k is slot and k["has_zh"]:
                zh_rows.append((k["name"] + ".zh", k["y"], k["ink_zh"], k))

    for zl, zy, zink, zk in zh_rows:
        for el, ey, eink, ek in en_rows:
            if ek is zk:
                continue
            lat = ((zk["x"] - ek["x"]) ** 2 + (zk["z"] - ek["z"]) ** 2) ** 0.5
            if lat >= LATERAL_MAX:
                continue
            checked += 1
            gap = abs(zy - ey)
            need = (zink + eink) * 0.5
            if gap < need:
                problems.append((bname, zl, el, gap, need, lat))
    # two Chinese rows are never simultaneous under the new contract, but under
    # legacy they are, so check them against each other too.
    for a in range(len(zh_rows)):
        for c in range(a + 1, len(zh_rows)):
            zl, zy, zink, zk = zh_rows[a]
            el, ey, eink, ek = zh_rows[c]
            lat = ((zk["x"] - ek["x"]) ** 2 + (zk["z"] - ek["z"]) ** 2) ** 0.5
            if lat >= LATERAL_MAX:
                continue
            checked += 1
            gap = abs(zy - ey)
            need = (zink + eink) * 0.5
            if gap < need:
                problems.append((bname, zl, el, gap, need, lat))

print("")
print("=" * 104)
print("  pairs checked   : %d" % checked)
print("  collisions      : %d" % len(problems))
for p in problems[:24]:
    print("    %-36s %-26s <-> %-26s gap=%.4f need=%.4f lateral=%.3f" % p)
print("")
print("=" * 104)
if problems:
    print("VERDICT: FAIL - %d row collision(s); the Chinese row lands on an English row."
          % len(problems))
    sys.exit(1)
print("VERDICT: PASS - one Chinese row per group, in the clear space above the")
print("        group's topmost word; it collides with no word's English row.")
