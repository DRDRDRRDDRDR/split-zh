# -*- coding: utf-8 -*-
"""apply_patch.py -- s.p.l.i.t 简体中文汉化补丁应用器（纯 Python 标准库）。

用途
----
把 release/payload.zip（只含「被改动的 PCK 条目」，**不含游戏本体**）打进用户
自己那份**正版** split.exe，生成 `--out` 指定的汉化版 exe。

    python apply_patch.py --exe "C:\\path\\to\\split.exe" --payload release\\payload.zip --out split_zh.exe

为什么可以这样发补丁
--------------------
split.exe 把 Godot 的 PCK 直接内嵌在 PE 尾部：`[PE 镜像][PCK 索引][数据区][12 字节 trailer]`。
索引在数据区**之前**，所以「按条目换字节」只需要改索引、PE 段大小和尾部 trailer，
不必重编译、不必重新导入资源。补丁包因此只带 72 个被改条目 + 1 个新增条目
（`fonts/cjk.fontdata`），体积 32.5 MB，而不是整个 415 MB 的 exe。

新增条目会让索引变长（本例 138748 -> 138808 字节），而索引后面紧跟着数据区，
**所以必须把数据区整体后移**给索引腾地方：
  * 后移量取 16 字节对齐（本例 64 字节），只改 PCK 头里的 file_base；
  * 条目 ofs 是相对 base 的，base 跟着 file_base 一起后移 ⇒ **已有条目的 ofs 全都不用改**；
  * 数据区后移后，再把 72 个差异条目**按 ofs 从大到小**就地替换（长度变了就顺带
    平移其后的条目 ofs），最后把新条目数据追加到数据区末尾、写进索引。
  * 总共只需回填：PCK 索引全部记录、PCK 头 file_base、尾部 ds、PE `pck` 段的
    SizeOfRawData(=ds+12)。这与 work/splice_gdc.py / work/inject_slots.py 的做法一致。

自检判据（重要）
----------------
**不是**「产物与 dist/split.exe 逐字节相同」——做不到，也不该这么要求：官方成品
dist/split.exe 是先用 GDRE `--pck-patch/--embed` **全量重建**过 PCK（条目按 16 字节
重排、条目间间隙从 9734 B 变成 21358 B）再叠加两次二进制 splice 得到的；而本脚本是
从零售 exe 出发做**最小改动**，数据区布局必然不同，逐字节相同在物理上不成立。

**正确判据是「解包后逐条相同」**：产物与 dist/split.exe 的条目名集合相同，且 1347 个
同名条目的字节**逐条逐字节相同**。条目是自包含的（RSRC/编译字节码/贴图/字体，
内部偏移都是相对 blob 的），布局差异不影响语义。传 `--ref` 即会自动做这项比对。

纯文件 I/O，不启动游戏 / Godot / GDRE（RULES.md R1）。
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _first_existing(paths):
    for p in paths:
        if os.path.isfile(p):
            return p
    return paths[0]


# 两种摆放都支持：源码树里（release/payload.zip）与单独分发的仓库里（脚本同目录）
DEFAULT_PAYLOAD = _first_existing([os.path.join(ROOT, "release", "payload.zip"),
                                   os.path.join(HERE, "payload.zip"),
                                   os.path.join(os.path.dirname(ROOT), "release", "payload.zip")])
DEFAULT_REF = os.path.join(ROOT, "dist", "split.exe")   # 官方成品，仅用于本机自检
GDPC = b"GDPC"
INDEX_AT = 96              # pck_start + 96 = count 字段
ALIGN = 16                 # file_base 对齐（实测 dist 亦为 16：138808 -> 138816）


# --------------------------------------------------------------------------- PCK
def scan_pck(b):
    """解析内嵌 PCK，返回头部信息与**带槽位偏移**的条目表（可原地回填）。

    与 work/pckutil.py 的 pck_scan 解析同一格式；额外记录 ofs_at/size_at/md5_at/flags_at。
    """
    eof = len(b)
    if b[eof - 4:eof] != GDPC:
        raise SystemExit("不是有效的 split.exe：文件末尾没有 GDPC trailer")
    ds = struct.unpack_from("<Q", b, eof - 12)[0]
    pck_start = eof - 12 - ds
    if pck_start < 0 or b[pck_start:pck_start + 4] != GDPC:
        raise SystemExit("不是有效的 split.exe：找不到 PCK 头（GDPC）")
    pack_format = struct.unpack_from("<I", b, pck_start + 4)[0]
    ver = struct.unpack_from("<III", b, pck_start + 8)
    flags = struct.unpack_from("<I", b, pck_start + 20)[0]
    file_base = struct.unpack_from("<Q", b, pck_start + 24)[0]
    base = (file_base + pck_start) if (flags & 2) else file_base

    p = pck_start + INDEX_AT
    count = struct.unpack_from("<I", b, p)[0]
    p += 4
    entries = {}
    order = []
    for _ in range(count):
        plen = struct.unpack_from("<I", b, p)[0]
        p += 4
        name = b[p:p + plen].rstrip(b"\x00").decode("utf-8", "replace")
        p += plen
        p = (p + 3) & ~3
        ofs_at = p
        ofs, size = struct.unpack_from("<QQ", b, p)
        p += 16
        md5_at = p
        md5 = bytes(b[p:p + 16])
        p += 16
        flags_at = p
        eflags = struct.unpack_from("<I", b, p)[0]
        p += 4
        entries[name] = dict(name=name, ofs=ofs, size=size, md5=md5, eflags=eflags,
                             ofs_at=ofs_at, size_at=ofs_at + 8, md5_at=md5_at,
                             flags_at=flags_at)
        order.append(name)
    return dict(eof=eof, ds=ds, pck_start=pck_start, base=base, flags=flags,
                file_base=file_base, pack_format=pack_format, ver=ver,
                count=count, entries=entries, order=order, index_end=p)


def pe_sections(b):
    e = struct.unpack_from("<I", b, 0x3C)[0]
    if b[e:e + 4] != b"PE\x00\x00":
        raise SystemExit("不是有效的 PE 文件")
    nsec = struct.unpack_from("<H", b, e + 6)[0]
    optsz = struct.unpack_from("<H", b, e + 20)[0]
    sec = e + 24 + optsz
    out = []
    for i in range(nsec):
        s = sec + 40 * i
        name = b[s:s + 8].rstrip(b"\x00").decode("latin1")
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", b, s + 8)
        out.append(dict(name=name, vsize=vsize, vaddr=vaddr, rsize=rsize,
                        raddr=raddr, rsize_at=s + 16))
    return out


def blob_of(b, info, name):
    e = info["entries"][name]
    p0 = info["base"] + e["ofs"]
    return bytes(b[p0:p0 + e["size"]])


def name_field_len(name):
    """PCK 索引里「名字字段」的长度。

    实测（零售 exe 与 dist 一致，1346/1347 条全部满足）：plen = ceil4(len(name))，
    名字用 0x00 补齐到该长度，**没有额外的对齐填充**。
    （早期误用 len(name)+1 —— 当 len%4==0 时会多出 4 字节，索引总长会偏大。）
    """
    n = len(name.encode("utf-8"))
    return (n + 3) // 4 * 4


def rec_size(name):
    """一条索引记录占用的字节数：u32 plen + 名字字段 + ofs(8) + size(8) + md5(16) + flags(4)。"""
    return 4 + name_field_len(name) + 36


def pack_record(name, ofs, size, md5, eflags):
    nb = name.encode("utf-8")
    nb += b"\x00" * (name_field_len(name) - len(nb))
    return (struct.pack("<I", len(nb)) + nb
            + struct.pack("<QQ", ofs, size) + md5 + struct.pack("<I", eflags))


def sha256_file(path, bufsize=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            c = f.read(bufsize)
            if not c:
                break
            h.update(c)
    return h.hexdigest().upper()


# ------------------------------------------------------------------------ payload
def read_payload(path):
    """读出 manifest 与各条目字节，并逐条核对 len/sha256（补丁自身损坏要能当场发现）。"""
    if not os.path.isfile(path):
        raise SystemExit("找不到补丁包: %s" % path)
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "manifest.json" not in names:
            raise SystemExit("补丁包损坏：缺少 manifest.json")
        man = json.loads(z.read("manifest.json").decode("utf-8"))
        entries = {}
        for kind in ("differ", "new"):
            for it in man.get(kind, []):
                zname = "entries/" + it["name"]
                if zname not in names:
                    raise SystemExit("补丁包损坏：缺少 %s" % zname)
                raw = z.read(zname)
                if len(raw) != it["len"]:
                    raise SystemExit("补丁包损坏：%s 长度 %d != manifest %d"
                                     % (it["name"], len(raw), it["len"]))
                got = hashlib.sha256(raw).hexdigest()
                if got != it["sha256"]:
                    raise SystemExit("补丁包损坏：%s sha256 不符" % it["name"])
                entries[it["name"]] = (raw, kind)
    return man, entries


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="把 s.p.l.i.t 简体中文汉化补丁打进你自己那份正版 split.exe")
    ap.add_argument("--exe", required=True, help="输入：你自己的正版原版 split.exe")
    ap.add_argument("--payload", default=DEFAULT_PAYLOAD,
                    help="补丁包 payload.zip（默认 release/payload.zip）")
    ap.add_argument("--out", required=True, help="输出：汉化版 exe 路径")
    ap.add_argument("--ref", default=None,
                    help="可选：官方成品 dist/split.exe，用于「逐条相同」自检")
    ap.add_argument("--report", default=None, help="可选：把报告写到指定文本文件")
    ap.add_argument("--no-ref-check", action="store_true",
                    help="即使存在 --ref 也跳过逐条比对")
    args = ap.parse_args()

    t0 = time.time()
    L = []

    def say(s=""):
        L.append(str(s))
        print(s, flush=True)

    def die(msg):
        say("")
        say("拒绝应用：%s" % msg)
        if args.report:
            open(args.report, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
        sys.exit(2)

    say("=" * 78)
    say("s.p.l.i.t 简体中文汉化补丁 · 应用器")
    say("=" * 78)

    exe = os.path.abspath(args.exe)
    out = os.path.abspath(args.out)
    if not os.path.isfile(exe):
        die("输入文件不存在: %s" % exe)
    if os.path.abspath(exe) == out:
        die("--out 不能等于 --exe（会破坏你自己的原版 exe，官方原版是唯一的回滚来源）")

    # ① 校验原版哈希 —— 防止把补丁打到别人已经改过的文件上
    man, payload = read_payload(args.payload)
    say("补丁包   : %s" % os.path.abspath(args.payload))
    say("  manifest: pristine %s (%d B)"
        % (man["pristine_sha256"], man["pristine_len"]))
    say("            patched  %s (%d B)"
        % (man["patched_sha256"], man["patched_len"]))
    say("  条目     : differ=%d  new=%d  dropped=%d"
        % (len(man["differ"]), len(man["new"]), len(man["dropped"])))
    elen = os.path.getsize(exe)
    esha = sha256_file(exe)
    say("")
    say("输入 exe : %s" % exe)
    say("  长度   : %d B" % elen)
    say("  SHA256 : %s" % esha)
    if esha != man["pristine_sha256"]:
        die("输入 exe 的 SHA256 与补丁包要求的原版不一致。\n"
            "          要求: %s\n"
            "          实际: %s\n"
            "          说明: 本补丁只适用于**未被修改过的正版原版** split.exe；\n"
            "                该文件要么不是原版，要么已被其它工具/补丁改过。\n"
            "                请在 Steam 里「验证游戏文件完整性」还原后再试。"
            % (man["pristine_sha256"], esha))
    if elen != man["pristine_len"]:
        die("输入 exe 长度 %d != manifest %d" % (elen, man["pristine_len"]))
    say("  -> 与补丁包要求一致 ✓")

    # ② 逐条核对补丁条目（read_payload 已完成 len/sha256 校验）
    differ = {it["name"]: payload[it["name"]][0] for it in man["differ"]}
    new = {it["name"]: payload[it["name"]][0] for it in man["new"]}
    say("")
    say("补丁条目 : %d 个（differ %d + new %d），字节数已逐条与 manifest 核对 ✓"
        % (len(differ) + len(new), len(differ), len(new)))

    b = bytearray(open(exe, "rb").read())
    info = scan_pck(bytes(b))
    old_base = info["base"]
    old_ds = info["ds"]
    index_at = info["pck_start"] + INDEX_AT
    say("PCK      : pck_start=%d flags=%d file_base=%d base=%d ds=%d 条目=%d"
        % (info["pck_start"], info["flags"], info["file_base"], old_base, old_ds,
           info["count"]))

    # 复用 work/pckutil.py 做交叉校验（打包给最终用户时可不必带它）
    try:
        sys.path.insert(0, HERE)
        import pckutil  # noqa
        ref_info = pckutil.pck_scan(bytes(b))
        same_names = set(ref_info["entries"]) == set(info["entries"])
        same_ofs = all(ref_info["entries"][n][:2] == (info["entries"][n]["ofs"],
                                                      info["entries"][n]["size"])
                       for n in info["entries"])
        say("  交叉校验 work/pckutil.py: 名字集合 %s / ofs+size %s"
            % ("一致" if same_names else "不一致", "一致" if same_ofs else "不一致"))
        if not (same_names and same_ofs):
            die("内部解析与 work/pckutil.py 不一致，中止")
    except ImportError:
        say("  交叉校验 work/pckutil.py: 未找到（独立分发模式，跳过）")

    # 记录编码自检：用同一套 pack_record 把原索引重建一遍，必须与盘上逐字节相同。
    # 这条检查能在任何写盘之前抓住索引编码错误（例如把名字字段长度算成 len+1 时，
    # 会凭空多出 1504 字节）。
    rebuilt = bytearray()
    for n in info["order"]:
        e = info["entries"][n]
        rebuilt += pack_record(n, e["ofs"], e["size"], e["md5"], e["eflags"])
    on_disk = bytes(b[index_at + 4:info["index_end"]])
    if bytes(rebuilt) != on_disk:
        die("索引编码自检失败：按实测约定重建的原索引与盘上不一致"
            "（重建 %d B / 盘上 %d B）" % (len(rebuilt), len(on_disk)))
    say("  索引编码 : 重建 %d 条记录与原索引逐字节相同 ✓" % info["count"])

    # 条目自相矛盾检查
    spans = sorted((e["ofs"], e["size"], n) for n, e in info["entries"].items())
    prev_end = 0
    prev_ofs = -1
    for o, s, n in spans:
        if o <= prev_ofs:
            die("原版 PCK 条目 ofs 非严格递增（%s），本脚本的就地替换策略不适用" % n)
        if o < prev_end:
            die("原版 PCK 条目重叠（%s），本脚本的就地替换策略不适用" % n)
        prev_ofs, prev_end = o, o + s
    for n in list(differ):
        if n not in info["entries"]:
            die("补丁要求替换的条目在原版里不存在: %s" % n)
    for n in list(new):
        if n in info["entries"]:
            die("补丁要求新增的条目在原版里已存在: %s" % n)

    # ③ 组装：索引扩容 -> 数据区后移 -> 差异条目就地替换 -> 新条目追加 -> 回填索引
    old_index_len = info["index_end"] - index_at
    new_index_len = old_index_len + sum(rec_size(n) for n in new)
    old_data_rel = old_base - info["pck_start"]
    new_data_rel = max(old_data_rel, (INDEX_AT + new_index_len + ALIGN - 1) // ALIGN * ALIGN)
    shift = new_data_rel - old_data_rel
    say("")
    say("索引     : %d -> %d B（+%d，新增 %s）"
        % (old_index_len, new_index_len, new_index_len - old_index_len, list(new)))
    say("数据区   : base %d -> %d（后移 %d B，%d 字节对齐）"
        % (old_base, info["pck_start"] + new_data_rel, shift, ALIGN))

    if shift:
        b[old_base:old_base] = b"\x00" * shift
    base = info["pck_start"] + new_data_rel

    todo = sorted((n for n in differ), key=lambda n: -info["entries"][n]["ofs"])
    grew = shrank = 0
    for n in todo:
        e = info["entries"][n]
        blob = differ[n]
        delta = len(blob) - e["size"]
        p0 = base + e["ofs"]
        b[p0:p0 + e["size"]] = blob
        if delta:
            for ent in info["entries"].values():
                if ent["ofs"] > e["ofs"]:
                    ent["ofs"] += delta
        e["size"] = len(blob)
        e["md5"] = hashlib.md5(blob).digest()
        if delta > 0:
            grew += 1
        elif delta < 0:
            shrank += 1
    say("差异条目 : 就地替换 %d 个（变大 %d / 变小 %d / 等长 %d）"
        % (len(todo), grew, shrank, len(todo) - grew - shrank))

    for n in new:
        blob = new[n]
        trailer_at = len(b) - 12
        ofs = trailer_at - base
        b[trailer_at:trailer_at] = blob
        info["entries"][n] = dict(name=n, ofs=ofs, size=len(blob),
                                  md5=hashlib.md5(blob).digest(), eflags=0,
                                  ofs_at=None, size_at=None, md5_at=None, flags_at=None)
        info["order"].append(n)
        say("新增条目 : %s  %d B  ofs=%d（追加在数据区末尾）" % (n, len(blob), ofs))

    # 回填索引（未改动条目从盘上原样读回 md5，不能凭内存里的字段 —— 见 RULES 踩坑①）
    idx = bytearray(struct.pack("<I", len(info["order"])))
    for n in info["order"]:
        e = info["entries"][n]
        if e["md5"] is None:
            e["md5"] = bytes(b[e["md5_at"]:e["md5_at"] + 16])
        idx += pack_record(n, e["ofs"], e["size"], e["md5"], e["eflags"])
    if len(idx) != new_index_len:
        die("索引长度自检失败: 计算 %d != 实际 %d" % (new_index_len, len(idx)))
    b[index_at:index_at + len(idx)] = idx
    b[index_at + len(idx):base] = b"\x00" * (base - index_at - len(idx))

    # PCK 头 file_base：flags&2 存相对值，否则存绝对值
    if info["flags"] & 2:
        struct.pack_into("<Q", b, info["pck_start"] + 24, new_data_rel)
    else:
        struct.pack_into("<Q", b, info["pck_start"] + 24, base)

    # 尾部 ds + PE `pck` 段 SizeOfRawData
    ds = len(b) - 12 - info["pck_start"]
    struct.pack_into("<Q", b, len(b) - 12, ds)
    pck_sec = [s for s in pe_sections(b) if s["name"] == "pck"]
    if not pck_sec:
        die("PE 里找不到 pck 段")
    pck_sec = pck_sec[0]
    if pck_sec["rsize"] != old_ds + 12:
        die("PE `pck` 段 SizeOfRawData(%d) != 旧 ds+12(%d)，文件结构异常"
            % (pck_sec["rsize"], old_ds + 12))
    struct.pack_into("<I", b, pck_sec["rsize_at"], ds + 12)

    d = os.path.dirname(out)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out, "wb") as f:
        f.write(b)          # bytearray 直接落盘，不做整份拷贝
    del b
    osha = sha256_file(out)
    say("")
    say("已写出   : %s" % out)
    say("  长度   : %d B（原版 %d，%+d；其中索引扩容后移 %d + 条目长度差 %+d）"
        % (os.path.getsize(out), elen, os.path.getsize(out) - elen, shift,
           os.path.getsize(out) - elen - shift))
    say("  ds     : %d -> %d   PE pck rsize -> %d"
        % (old_ds, ds, ds + 12))
    say("  SHA256 : %s" % osha)

    # ④⑤ 自检：重新解包，逐条比对
    say("")
    say("-" * 78)
    say("自检（判据：解包后条目逐条字节相同；**不要求**与任何 exe 整文件逐字节相同）")
    say("-" * 78)
    ob = open(out, "rb").read()
    oi = scan_pck(ob)
    pb = open(exe, "rb").read()
    pr_info = scan_pck(pb)
    # 期望的产物条目集合 = 原版 1346 条（未改动的 1274 条原样保留）∪ differ ∪ new
    exp_names = set(pr_info["order"]) | set(differ) | set(new)

    ok = True
    if oi["count"] != len(exp_names):
        say("  !! 条目数 %d != 期望 %d" % (oi["count"], len(exp_names)))
        ok = False
    if set(oi["order"]) != exp_names:
        miss = sorted(exp_names - set(oi["order"]))
        extra = sorted(set(oi["order"]) - exp_names)
        say("  !! 条目名集合不符 缺 %s 多 %s" % (miss[:5], extra[:5]))
        ok = False
    bad = []
    for n in oi["order"]:
        got = blob_of(ob, oi, n)
        if n in differ:
            want = differ[n]            # 补丁里的新字节
        elif n in new:
            want = new[n]               # 补丁新增条目
        elif n in pr_info["entries"]:
            want = blob_of(pb, pr_info, n)   # 未改动条目：应与原版逐字节相同
        else:
            want = None
        if got != want:
            bad.append(n)
    say("  解包比对: 条目 %d 个，相同 %d，不同 %d"
        % (len(oi["order"]), len(oi["order"]) - len(bad), len(bad)))
    if bad:
        say("  !! 不一致: %s" % bad[:10])
        ok = False
    del pb, pr_info

    ref = args.ref or (DEFAULT_REF if os.path.isfile(DEFAULT_REF) else None)
    if ref and not args.no_ref_check:
        ref = os.path.abspath(ref)
        if os.path.isfile(ref) and os.path.abspath(ref) != out:
            rb = open(ref, "rb").read()
            ri = scan_pck(rb)
            rset, oset = set(ri["order"]), set(oi["order"])
            common = sorted(rset & oset)
            same = 0
            diff = []
            for n in common:
                if blob_of(ob, oi, n) == blob_of(rb, ri, n):
                    same += 1
                else:
                    diff.append(n)
            say("  与参照 exe 逐条比对 (%s):" % os.path.relpath(ref, ROOT))
            say("    参照条目数 %d / 产物条目数 %d" % (len(rset), len(oset)))
            say("    条目名集合相同: %s" % ("是" if rset == oset else "否"))
            say("    共同条目 %d 个，逐条相同 %d，不同 %d" % (len(common), same, len(diff)))
            if diff:
                say("    不同条目: %s" % diff[:10])
            if rset != oset or diff:
                ok = False
            else:
                say("    => %d 条逐条字节相同 ✓（整文件字节不同属正常：官方成品是"
                    "GDRE 全量重建 + 两次 splice 的产物，数据区布局必然不同）" % len(common))
        else:
            say("  (未找到参照 exe %s，跳过逐条比对)" % ref)

    say("")
    say("VERDICT: %s   (%.1fs)" % ("PASS" if ok else "FAIL", time.time() - t0))
    if args.report:
        open(args.report, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
