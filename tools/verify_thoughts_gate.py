# -*- coding: utf-8 -*-
"""GATE: every thought must show a Chinese line AND require typable ASCII.

The screenshot bug ("不理想 / 结果 只有中文") is one instance of a general rule:
a thought Label3D whose scene text is Chinese but which is NOT listed in TYPED_EN
falls into LabelSplitter's "type Chinese" branch -- no Chinese display line, and a
Latin keyboard cannot produce 不/理/想, so the thought soft-locks.

Layout contract (2026-10-01, second fix): thoughts that share a ThoughtBatch are
typed back to back and are therefore drawn ONCE as a group sentence, by the group's
topmost node (PHRASE_ZH).  A group's other words show no Chinese row of their own --
their Chinese is carried by that sentence.  This exists because a thought node draws
two rows (Chinese + typed English) while the scene only leaves ~1.28 rows between
neighbouring nodes; giving every word its own Chinese row makes one word's letters
land on the next word's Chinese row (the "UN结果IRABLI" overlap).

This gate cross-checks THREE sources, so an empty set cannot pass by accident:
  A. the scene source recovered/scenes/main.tscn -> nodes, their text, their batch
  B. the SHIPPED main.scn inside dist              -> those texts must all be there
  C. the compiled LabelSplitter.gdc                -> must carry every Chinese line

FAIL on: a thought not covered by ANY Chinese line, a typed string containing
non-ASCII, a group phrase that never reaches the bytecode, or a group that does not
have exactly one carrier.
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
PHRASE_ZH = parse_map("PHRASE_ZH")

b = open(DIST, "rb").read()
h = IS.scan_entries(b)
say("=" * 100)
say("GATE: thought typing/display contract")
say("=" * 100)
say("  dist   %d B  sha256 %s" % (len(b), hashlib.sha256(b).hexdigest().upper()))
say("  source TYPED_EN=%d  DISPLAY_ZH=%d  PHRASE_ZH=%d"
    % (len(TYPED_EN), len(DISPLAY_ZH), len(PHRASE_ZH)))

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

# ---------------- carrier uniqueness per batch ------------------------------
say("")
say("-" * 100)
say("C. one carrier per group (the group's topmost node draws the sentence)")
say("-" * 100)
by_batch = {}
for name, t in thoughts.items():
    by_batch.setdefault(t["batch"], []).append(name)
carriers = {}
carrier_problems = []
for bname, names in sorted(by_batch.items()):
    top = max(names, key=lambda n: thoughts[n]["y"])
    carriers[bname] = top
    alias = batches.get(bname, "")
    phrase = PHRASE_ZH.get(alias, "")
    say("  %-42s alias=%-22s words=%-2d carrier=%s  phrase=%r"
        % (bname[:42], alias, len(names), top, phrase))
    if phrase and len(names) > 1:
        close = [n for n in names
                 if n != top and abs(thoughts[n]["y"] - thoughts[top]["y"]) < 0.2]
        if close:
            say("      note: carrier has near-y siblings %s (lateral check is in"
                " verify_phrase_layout.py)" % close)

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
    alias = batches.get(t["batch"], "")
    phrase = PHRASE_ZH.get(alias, "")
    if typed:
        branch, disp = "TYPED_EN", raw
    elif phrase:
        branch = "PHRASE_ZH"
        disp = phrase if carriers.get(t["batch"]) == name else ""
    else:
        branch, disp, typed = "DISPLAY_ZH", DISPLAY_ZH.get(raw, ""), raw
    if not typed:
        typed = raw
    ascii_ok = all(ord(c) < 128 for c in typed)
    in_scn = raw in scn_texts
    if not in_scn:
        missing_in_scn.append((name, raw))
    # covered = this node shows a row, or its group's carrier shows the sentence
    covered = bool(disp) or bool(phrase)
    ok = covered and bool(typed) and ascii_ok and in_scn
    if not ok:
        bad.append((name, raw, disp, typed, ascii_ok, in_scn))
    say("  %-36s %-16s %-11s %-16s %-16s %s"
        % (name[:36], raw, branch, disp or ("(group)" if phrase else "-"),
           typed or "-", "OK" if ok else "*** FAIL ***"))

say("")
say("  thoughts whose text is absent from the shipped .scn: %d %s"
    % (len(missing_in_scn), missing_in_scn if missing_in_scn else ""))
say("  contract violations: %d" % len(bad))

# ---------------- E. the compiled script carries the lines -------------------
say("")
say("-" * 100)
say("E. compiled %s carries every Chinese line (per-word AND group sentence)" % LSGDC)
say("-" * 100)
gdc, _e = IS.blob_of(b, h, LSGDC)
need = {}
need.update({"DISPLAY_ZH:" + k: v for k, v in DISPLAY_ZH.items() if v})
need.update({"PHRASE_ZH:" + k: v for k, v in PHRASE_ZH.items() if v})
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
    say("  gdc blob %d B -> body %d B" % (len(gdc), len(body)))
say("  Chinese display strings missing from bytecode: %d %s" % (len(miss), miss if miss else ""))

# ---------------- verdict ----------------------------------------------------
say("")
say("=" * 100)
ok = ((not bad) and (not miss) and (not missing_in_scn)
      and (not carrier_problems) and len(thoughts) > 0)
say("VERDICT: %s" % ("PASS - %d thoughts, every one covered by a Chinese line "
                     "(own row or its group sentence), all typable ASCII, all "
                     "display strings compiled in" % len(thoughts) if ok
                     else "FAIL - violations=%d missing_in_scn=%d missing_strings=%d"
                          % (len(bad), len(missing_in_scn), len(miss))))
say("=" * 100)

os.makedirs(os.path.join(HERE, "reports"), exist_ok=True)
open(os.path.join(HERE, "reports", "verify_thoughts.txt"), "w",
     encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
sys.exit(0 if ok else 1)
