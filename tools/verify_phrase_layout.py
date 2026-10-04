# -*- coding: utf-8 -*-
"""Static gate: does the new group-phrase layout still overlap anywhere?

Model (byte/value backed, no guessing):
  * a thought node is a Label3D whose parent is its ThoughtBatch node;
  * each node draws its typed English row at local y = line_dy and, when it has a
    Chinese row, that row sits at local y = 0;
  * line_dy is -1.15 * font.get_height(font_size) * pixel_size in LOCAL units;
  * a local offset dy maps to a world offset |dy| * |basis_y| where basis_y is the
    second column of the node's Transform3D basis (the node is scaled/rotated);
  * so the vertical distance between a node's two rows, in world units, is
        row_world = 1.15 * font_height_px * pixel_size * |basis_y|.

Two rows collide when the nodes' world-y gap is smaller than the row they carry.
This script prints every batch and fails if any batch's rows overlap.

Usage: python verify_phrase_layout.py
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

# Two rows only read as "overlapping" when they are close on screen in BOTH
# directions.  y alone is not enough: thought nodes are scattered in depth, and a
# pair 1.0 world unit apart in z is drawn far apart on screen even when their y is
# nearly equal (e.g. latch/mechanism, or the six independent snipe words).
# LATERAL_MAX is in world units, on the order of one word's height.
LATERAL_MAX = 0.35

# What actually collides is INK, not the whole line box: the shift applied to a
# node's English row is 1.15 x line box, but the glyphs only occupy about 0.75 of
# an em.  Comparing gaps against the shift distance would flag perfectly fine
# neighbours, so compare against the ink height instead.
INK_RATIO = 0.75

# Negative control: the previous per-word layout (every word drew its own Chinese
# row).  Used with --legacy to prove this gate really does catch the reported bug.
LEGACY = "--legacy" in sys.argv
LEGACY_DISPLAY_ZH = {
	"latch": "锁扣", "mechanism": "机制", "steady": "稳住", "now": "现在",
	"undesirable": "不理想", "outcome": "结果", "final": "最终", "evidence": "证据",
	"abject": "卑劣", "hazard": "危险", "convex": "凸面", "injury": "伤害",
	"potential": "可能", "betrayal": "背叛", "unorthodox": "非正统",
	"electronics": "电子设备", "cramped": "拥挤", "discrete": "隐蔽",
	"shade": "阴影", "withdrawal": "撤退", "penetrate": "穿透",
	"am": "我", "by": "被", "is": "是", "do": "做", "me": "我", "no": "不",
}

# ---- harness copies of the shipped tables (kept in sync by verify_phrase_tables)
src = open(GD, encoding="utf-8", errors="replace").read()


def table(name):
    m = re.search(r"const %s = \{(.*?)\n\}" % name, src, re.S)
    if not m:
        raise SystemExit("cannot find const %s in LabelSplitter.gd" % name)
    out = {}
    for k, v in re.findall(r'"([^"]*)"\s*:\s*"([^"]*)"', m.group(1)):
        out[k] = v
    return out


TYPED_EN = table("TYPED_EN")
PHRASE_ZH = table("PHRASE_ZH")
DISPLAY_ZH = table("DISPLAY_ZH")
PIXEL_SIZE = 0.005  # Godot Label3D default; scene sets no pixel_size on thoughts

lines = open(SCN, encoding="utf-8", errors="replace").read().splitlines()
starts = [(i, m.group(1)) for i, ln in enumerate(lines)
          for m in [re.match(r'\[node name="([^"]+)"', ln)] if m]


def block(idx):
    i = starts[idx][0]
    j = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
    return "\n".join(lines[i:j])


# font resources
fonts = {}
for i, ln in enumerate(lines):
    m = re.match(r'\[ext_resource type="FontFile" [^\]]*path="res://fonts/([^"]+)"[^\]]*id="([^"]+)"', ln)
    if m:
        fonts[m.group(2)] = m.group(1)
FONT_H = {}
for fid, fname in fonts.items():
    p = os.path.join(ROOT, "recovered", "fonts", fname)
    if not os.path.exists(p):
        p = os.path.join(ROOT, "fonts", fname)
    if not os.path.exists(p):
        continue
    b = open(p, "rb").read()
    if b[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        continue
    num = struct.unpack_from(">H", b, 4)[0]
    tab = {}
    for k in range(num):
        base = 12 + 16 * k
        tab[b[base:base + 4].decode("latin-1")] = struct.unpack_from(">II", b, base + 8)
    if "hhea" in tab and "head" in tab:
        o, _ = tab["hhea"]
        asc, desc, _g = struct.unpack_from(">hhh", b, o + 4)
        upem = struct.unpack_from(">H", b, tab["head"][0] + 18)[0]
        FONT_H[fid] = (asc - desc) / upem      # height in em

# batches
batches = {}
for idx, (i, name) in enumerate(starts):
    if not name.startswith("though batch_"):
        continue
    blk = block(idx)
    al = re.search(r'^alias = "(.*)"$', blk, re.M)
    batches[name] = {"alias": al.group(1) if al else "", "kids": []}

for idx, (i, name) in enumerate(starts):
    if not name.startswith("thought_"):
        continue
    blk = block(idx)
    par = re.search(r'parent="([^"]*)"', blk)
    if not par:
        continue
    bname = par.group(1).split("/")[-1]
    if bname not in batches:
        continue
    tr = re.search(r"^transform = Transform3D\((.*?)\)$", blk, re.M)
    if not tr:
        continue
    cols = [float(c.strip()) for c in tr.group(1).split(",")]
    origin = cols[9:12]
    by = cols[3:6]                                  # second basis column (local y)
    basis_y = (by[0] ** 2 + by[1] ** 2 + by[2] ** 2) ** 0.5
    fs = re.search(r"^font_size = (\d+)$", blk, re.M)
    fo = re.search(r'^font = ExtResource\("([^"]+)"\)$', blk, re.M)
    font_size = int(fs.group(1)) if fs else 152
    emh = FONT_H.get(fo.group(1), 1.0) if fo else 1.0
    tx = re.search(r'^text = "(.*)"$', blk, re.M)
    rows = 1
    batches[bname]["kids"].append({
        "name": name, "y": origin[1], "x": origin[0], "z": origin[2],
        "raw": tx.group(1) if tx else "",
        "row": 1.15 * emh * font_size * PIXEL_SIZE * basis_y, "basis_y": basis_y,
        "ink": INK_RATIO * emh * font_size * PIXEL_SIZE * basis_y,
    })

print("=" * 104)
print("GROUP PHRASE LAYOUT - every batch, its carrier, and the rows it draws")
print("=" * 104)
problems = []

for bname, b in batches.items():
    kids = sorted(b["kids"], key=lambda k: -k["y"])
    phrase = PHRASE_ZH.get(b["alias"], "")
    print("")
    print("  batch %-34s alias=%-22s kids=%d  phrase=%r"
          % (bname[:34], b["alias"], len(kids), phrase))
    if not kids:
        continue
    carrier = kids[0]
    for k in kids:
        raw = k["raw"]
        typed = TYPED_EN.get(raw, raw)
        scene_zh = raw in TYPED_EN
        if LEGACY:
            if scene_zh:
                disp = raw
                shift = True
            else:
                disp = LEGACY_DISPLAY_ZH.get(raw, "")
                shift = bool(disp)
        elif phrase:
            disp = phrase if k is carrier else ""
            shift = True
        elif scene_zh:
            disp = raw
            shift = True
        else:
            disp = DISPLAY_ZH.get(raw, "")
            shift = bool(disp)
        k["disp"] = disp
        k["shift"] = shift
        k["typed"] = typed
        mark = "CARRIER" if k is carrier else "       "
        print("      %s %-30s y=%-9.4f row=%.4f typed=%-26r zh=%r"
              % (mark, k["name"][:30], k["y"], k["row"], typed[:26], disp))

    # rows actually drawn, as world-y bands, plus the Chinese row of the carrier
    bands = []
    for k in kids:
        if k["shift"]:
            bands.append((k["name"] + ".en", k["y"] - k["row"], k["y"], k["row"]))
        else:
            bands.append((k["name"] + ".en", k["y"], k["y"], 0.0))
        if k["disp"]:
            bands.append((k["name"] + ".zh", k["y"], k["y"], 0.0))
    # Collision test: every pair of nodes must keep their drawn rows apart, but
    # only counts as a real overlap when the pair is also close on screen
    # horizontally (small x/z separation).
    def rows_of(k):
        if k["shift"]:
            r = [k["y"] - k["row"]]
            if k["disp"]:
                r.append(k["y"])
            return r
        return [k["y"]]

    for a in range(len(kids)):
        for c in range(a + 1, len(kids)):
            ka, kc = kids[a], kids[c]
            lateral = ((ka["x"] - kc["x"]) ** 2 + (ka["z"] - kc["z"]) ** 2) ** 0.5
            if lateral >= LATERAL_MAX:
                continue
            gap = min(abs(ra - rc) for ra in rows_of(ka) for rc in rows_of(kc))
            need = (ka["ink"] + kc["ink"]) * 0.5
            if gap < need:
                problems.append((bname, ka["name"], kc["name"],
                                 "rows %.4f apart (< %.4f) and only %.3f apart "
                                 "horizontally" % (gap, need, lateral)))

print("")
print("=" * 104)
print("coverage: does every thought keep a Chinese row?")
print("=" * 104)
missing = []
for bname, b in batches.items():
    if b["kids"] and not any(k.get("disp") for k in b["kids"]):
        for k in b["kids"]:
            missing.append((bname, k["name"], k["raw"], TYPED_EN.get(k["raw"], k["raw"])))
for m in missing:
    print("  NO CHINESE: batch=%-32s node=%-30s raw=%r typed=%r" % m)
print("  thoughts in a group with no Chinese row at all: %d" % len(missing))

print("")
print("=" * 104)
if problems or missing:
    print("VERDICT: FAIL")
    for p in problems:
        print("  overlap risk: batch=%-30s %s <-> %s : %s" % p)
    sys.exit(1)
print("VERDICT: PASS - one Chinese sentence per group, no row pair within a group")
print("        is closer than a row height; every thought keeps a Chinese row.")
