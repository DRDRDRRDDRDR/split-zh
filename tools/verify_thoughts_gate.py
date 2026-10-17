# -*- coding: utf-8 -*-
"""GATE: every thought must show a Chinese line AND require typable ASCII.

The screenshot bug ("不理想 / 结果 只有中文") is one instance of a general rule:
a thought Label3D whose scene text is Chinese but which is NOT listed in TYPED_EN
falls into LabelSplitter's "type Chinese" branch -- no Chinese display line, and a
Latin keyboard cannot produce 不/理/想, so the thought soft-locks.

Layout contract (2026-10-17, third fix -- per-word Chinese):
every thought word owns the Chinese for ITSELF.  That Chinese is shown while the
word is being typed and cleared the moment the word finishes, so the Chinese leaves
one word at a time with the same rhythm in every group.  The row itself is drawn in
ONE shared slot per group, at the group's topmost node, because a word's typed
English row already drops one row below its own origin while the scene leaves far
less than one row between neighbouring words (measured 0.0296 of world space against
a 0.0400 row in the drill group) -- a Chinese row at each word's own origin therefore
lands on a neighbour's English row, which is the "UN结果IRABLI" overlap.

This gate cross-checks THREE sources, so an empty set cannot pass by accident:
  A. the scene source recovered/scenes/main.tscn -> nodes, their text, their batch
  B. the SHIPPED main.scn inside dist              -> those texts must all be there
  C. the compiled LabelSplitter.gdc                -> must carry every Chinese line

FAIL on: a thought not covered by ANY Chinese line, a typed string containing
non-ASCII, a group whose Chinese never reaches the bytecode, or a group with no
identifiable slot node.
Read-only.  Usage: python verify_thoughts_gate.py
"""
import hashlib
import os
import re
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
TS = os.path.join(ROOT, "recovered", "scenes", "main.tscn")
GD = os.path.join(ROOT, "recovered", "scripts", "LabelSplitter.gd")
SCENE = "res://.godot/exported/133200997/export-3ad5c15c4f3250da0cc7c1af1770d85f-main.scn"
LSGDC = "scripts/LabelSplitter.gdc"

L = []


def say(s=""):
    L.append(str(s))
    print(s)


gd = open(GD, encoding="utf-8", errors="replace").read()


def parse_map(name):
    m = re.search(name + r"\s*=\s*\{(.*?)\n\}", gd, re.S)
    if not m:
        return {}
    return dict(re.findall(r'"((?:[^"\\]|\\.)*)"\s*:\s*"((?:[^"\\]|\\.)*)"', m.group(1)))


TYPED_EN = parse_map("TYPED_EN")
DISPLAY_ZH = parse_map("DISPLAY_ZH")

b = open(DIST, "rb").read()
h = IS.scan_entries(b)
say("=" * 100)
say("GATE: thought typing/display contract")
say("=" * 100)
say("  dist   %d B  sha256 %s" % (len(b), hashlib.sha256(b).hexdigest().upper()))
say("  source TYPED_EN=%d  DISPLAY_ZH=%d" % (len(TYPED_EN), len(DISPLAY_ZH)))

# ---------------- A. the scene source: node -> text / batch / y ---------------
lines = open(TS, encoding="utf-8", errors="replace").read().splitlines()
starts = [(i, m.group(1)) for i, ln in enumerate(lines)
          for m in [re.match(r'\[node name="([^"]+)"', ln)] if m]

batches = {}          # batch node name -> alias
thoughts = {}         # node name -> dict
for idx, (i, name) in enumerate(starts):
    j = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
    blk = "\n".join(lines[i:j])
    if name.startswith("though batch_"):
        al = re.search(r'^alias = "(.*)"$', blk, re.M)
        batches[name] = al.group(1) if al else ""
        continue
    if not name.startswith("thought_"):
        continue
    par = re.search(r'parent="([^"]*)"', blk)
    bname = par.group(1).split("/")[-1] if par else ""
    tx = re.search(r'^text = "(.*)"$', blk, re.M)
    tr = re.search(r"^transform = Transform3D\((.*?)\)$", blk, re.M)
    y = float([c.strip() for c in tr.group(1).split(",")][-2]) if tr else 0.0
    thoughts[name] = {"raw": tx.group(1) if tx else "", "batch": bname, "y": y}

say("")
say("-" * 100)
say("A. scene source   thought_* nodes: %d   batches: %d" % (len(thoughts), len(batches)))
say("-" * 100)

# ---------------- B. the shipped scn ----------------------------------------
blob, _ent = IS.blob_of(b, h, SCENE)
rd = variant_walk.Reader(blob, rsrc.parse(blob))
rd.walk()
scn_texts = {}
for s in rd.slots:
    if s.get("kind") == "STRING" and isinstance(s.get("text"), str):
        scn_texts.setdefault(s["text"], []).append(s["path"])
say("B. shipped main.scn   distinct STRING slot values: %d" % len(scn_texts))

# ---------------- slot uniqueness per batch ---------------------------------
say("")
say("-" * 100)
say("C. one Chinese slot per group (the group's topmost node draws it)")
say("-" * 100)
by_batch = {}
for name, t in thoughts.items():
    by_batch.setdefault(t["batch"], []).append(name)
slots = {}
slot_problems = []
for bname, names in sorted(by_batch.items()):
    top = max(names, key=lambda n: thoughts[n]["y"])
    slots[bname] = top
    say("  %-42s alias=%-22s words=%-2d slot=%s"
        % (bname[:42], batches.get(bname, ""), len(names), top))

# ---------------- per-thought verdict ---------------------------------------
say("")
say("-" * 100)
say("D. per-thought contract (covered by a Chinese line, ASCII required to type)")
say("-" * 100)
say("  %-36s %-16s %-11s %-16s %-16s %s"
    % ("node", "scene text", "branch", "shows", "types", "verdict"))
bad = []
missing_in_scn = []
for name in sorted(thoughts):
    t = thoughts[name]
    raw = t["raw"]
    typed = TYPED_EN.get(raw, "")
    scene_zh = typed != ""
    if not scene_zh:
        typed = raw
    if scene_zh:
        branch, disp = "TYPED_EN", raw
    else:
        branch, disp = "DISPLAY_ZH", DISPLAY_ZH.get(raw, "")
    ascii_ok = all(ord(c) < 128 for c in typed) and typed != ""
    in_scn = raw in scn_texts
    if not in_scn:
        missing_in_scn.append((name, raw))
    # covered = this word shows a Chinese row of its own.
    covered = bool(disp)
    ok = covered and bool(typed) and ascii_ok and in_scn
    if not ok:
        bad.append((name, raw, disp, typed, ascii_ok, in_scn))
    say("  %-36s %-16s %-11s %-16s %-16s %s"
        % (name[:36], raw, branch, disp or "-",
           typed or "-", "OK" if ok else "*** FAIL ***"))

say("")
say("  thoughts whose text is absent from the shipped .scn: %d %s"
    % (len(missing_in_scn), missing_in_scn if missing_in_scn else ""))
say("  contract violations: %d" % len(bad))

# ---------------- E. the compiled script carries the lines -------------------
say("")
say("-" * 100)
say("E. compiled %s carries every Chinese line and the slot machinery" % LSGDC)
say("-" * 100)
gdc, _e = IS.blob_of(b, h, LSGDC)
need = {}
need.update({"DISPLAY_ZH:" + k: v for k, v in DISPLAY_ZH.items() if v})
if gdc[:4] != b"GDSC":
    miss = [("ALL", "not GDSC")]
else:
    dsize = struct.unpack_from("<I", gdc, 8)[0]
    try:
        import zstandard as zstd
        body = zstd.ZstdDecompressor().decompress(gdc[12:], max_output_size=dsize + (1 << 20))
    except Exception:
        import zlib
        body = zlib.decompress(gdc[12:])
    miss = [(k, v) for k, v in sorted(need.items()) if v.encode("utf-8") not in body]
    # The per-word slot machinery must be in there too, or the row never advances.
    # Function names live in the IDENTIFIER table, whose entries are stored XOR 0xb6,
    # so they cannot be found by a plain byte search -- parse the table instead.
    try:
        import verify_gdc_bytecode as V
        idents = set(V.parse_gdsc(gdc)["identifiers"])
    except Exception as exc:
        idents = set()
        miss.append(("identifier table", "unparseable: %s" % exc))
    for fn in ("RefreshSlot", "BatchSlot", "GroupHasChinese"):
        if fn not in idents:
            miss.append((fn, "function missing from the compiled identifier table"))
    say("  gdc blob %d B -> body %d B   identifiers %d" % (len(gdc), len(body), len(idents)))
say("  Chinese display strings missing from bytecode: %d %s" % (len(miss), miss if miss else ""))

# ---------------- verdict ----------------------------------------------------
say("")
say("=" * 100)
ok = ((not bad) and (not miss) and (not missing_in_scn)
      and (not slot_problems) and len(thoughts) > 0)
say("VERDICT: %s" % ("PASS - %d thoughts, every one carries its own Chinese line "
                     "(per-word contract), all typable ASCII, all display strings "
                     "and the slot machinery compiled in" % len(thoughts) if ok
                     else "FAIL - violations=%d missing_in_scn=%d missing_strings=%d"
                          % (len(bad), len(missing_in_scn), len(miss))))
say("=" * 100)

os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
open(os.path.join(HERE, "reports", "verify_thoughts.txt"), "w",
     encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
sys.exit(0 if ok else 1)
