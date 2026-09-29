# v1.0.0 · s.p.l.i.t 简体中文汉化补丁

## ⚠️ 本补丁不含游戏本体，需自备正版

`payload.zip` 里只有 **73 个被改动的游戏资源条目**（编译后的 GDScript、场景、字体、重绘贴图），
**不是**可独立运行的游戏。你必须拥有 Steam 正版 **s.p.l.i.t**，补丁才能应用。

## 下载与用法

1. 下载本 Release 的资产 **`payload.zip`**（34,094,587 B）。
2. 下载仓库里的 [`apply_patch.py`](https://github.com/DRDRDRRDDRDR/split-zh/blob/main/apply_patch.py)（纯标准库，只需 Python 3.8+）。
3. 备份你自己的原版 exe，然后运行：

   ```powershell
   python apply_patch.py --exe "C:\Program Files (x86)\Steam\steamapps\common\s.p.l.i.t\split_Windows\split.exe" --payload payload.zip --out split_zh.exe
   ```

4. 退出游戏与 Steam，把 `split_zh.exe` 覆盖回游戏目录的 `split.exe`。

详见 [README](https://github.com/DRDRDRRDDRDR/split-zh#readme)。

## 校验值

| 文件 | 大小 | SHA256 |
|---|---|---|
| `payload.zip`（本资产） | 34,094,587 B | `C0B92BDC03E1CD5129F4A6BFFCB84F16609F24338156303A278158B7086CC9A8` |
| 原版 `split.exe`（你自备的零售原版） | 407,187,680 B | `2F5E7E3EC06E1E3ECA3623E75DF65DE342DC39E21B886B59BA5D455BC752C9F6` |

应用器会先校验你那份 exe 的 SHA256，**与原版不一致会拒绝并说明原因**（退出码 2）。

## 修订（2026-09-29，资产已就地替换）

初版资产随附的应用器没有缺陷，但**官方成品那条构建路径有三个问题**，本次已一并修复并
重新生成载荷（v1.0.0 从未被证明可用，所以直接替换而不是另开 v1.0.1）：

1. **13 条 PCK 索引摘要未刷新 ⇒ 汉化版「点开始」卡死**（Windows 事件 1002）。当年用
   「等长原地覆盖」换贴图像素时没同步刷新索引里的 16 字节 MD5，而 Godot 在**加载** PCK
   时校验这个摘要。现已全部刷新为 `md5(条目字节)`，并新增常驻验收门
   `work/verify_pck_md5.py`（1347/1347 自洽）防止复发。
2. **对白标点缺失**：早前删除名字两侧填充空格时把该加标点的地方连成了一句话。已按
   **英文原文**逐条补回 19 处（逗号 / 问号 / 一个多余的逗号），语料与 `.gd` 源码同步。
3. **标点那次的落地方式把字节码写坏了 ⇒ 汉化版点开始即闪退**（Windows 事件 1000）。
   当时是**绕过编译器直接改 `.gdc` 常量表**，违反了 `_encode_string()` 的 4 字节补齐约定，
   常量表整体错位，Godot 报
   `Index token.type = 116 is out of bounds (Token::TK_MAX = 99)`。
   现已改为**真的重编译**（`gdre_tools.exe --headless --compile=Chat_Content.gd
   --bytecode=4.3.0` + `work/splice_gdc.py` 落盘），并新增常驻验收门
   `work/verify_gdc_bytecode.py`：把 Godot 的
   `GDScriptTokenizerBuffer::set_code_buffer()` 复刻成纯 Python，对成品里 117 个 `.gdc`
   逐个解析，解析不吃满缓冲区或出现 `token.type >= 99` 即 FAIL（负测试
   `work/verify_gdc_bytecode_negctl.py` 用崩过的构建当样本，确认这道门真的会响）。

## 本次做了什么（汉化内容）

- 458 条文本翻译为简体中文；6 个场景 37 处真实文本槽位替换；`forest road.tscn` 67 条过场字幕。
- 新增中文字体 `res://fonts/cjk.fontdata`（Noto Sans SC，7,743,989 B），13 个 `.fontdata` 改为外部引用它。
- 1 处代码改动：`scripts/Chat.gd` 兼容全角「：」对白切分。
- 13 张 UI 贴图重绘（把**烘进像素里的**英文改成中文，等长替换）。

## 自证（本机实测）

以零售原版 exe 为输入跑应用器：

- **解包后条目 1347 个，逐条字节相同 1347，不同 0** ✓
- 与官方成品 `dist/split.exe` 比对：条目名集合相同，共同条目 1347 个**逐条相同 1347，不同 0** ✓
- `VERDICT: PASS`（完整报告见仓库内 [`e2e-report.txt`](https://github.com/DRDRDRRDDRDR/split-zh/blob/main/e2e-report.txt)）

判据说明：**不是**「整文件逐字节相同」——官方成品当初是经 GDRE 全量重建 PCK 再叠加两次
splice 得到的，数据区布局与本应用器的最小改动方案必然不同；条目是自包含的，布局差异不影响语义。
产物体积 415,203,627 B（官方成品 415,215,257 B，差 11,630 B 全部来自数据区间隙布局）。

## 实机确认状态

构建阶段的自动化验证（PCK 结构、逐槽位字节回读、字形覆盖率 990/990、PE 完整性、索引摘要
自洽）全部通过。

- **已确认真机可玩**：用户实机跑过修复后的构建 —— 主菜单 → 点开始 → 进入游戏，聊天里是
  汉字而非方框/空白（此前卡死的根因是 13 条索引摘要没刷新，已修）。
- **仍需目视确认**：① 中文在等宽终端里的换行/溢出；② 打字机逐字动画在中文下的表现；
  ③ 2026-09-29 新增的 19 处标点修正尚未重新走一遍真机。第 ③ 项在机器可判的层面已经干净：
  `Chat_Content.gd` → GDRE 编译 → 落进 exe 的 `.gdc` → GDRE 反编译，往返得到的 `.gd` 与
  源文件**逐字节相同**，且成品里 117 个 `.gdc` 全部通过字节码解析门
  `work/verify_gdc_bytecode.py`。

## 法律声明

游戏本体及原始资源版权归原作者 Mike Klubnika 所有。本补丁为**非官方**民间汉化，
与作者、发行商无关，**不含游戏本体**，需自备正版。若权利人提出异议，本仓库与本 Release 会立即下架。
