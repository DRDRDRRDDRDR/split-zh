# v1.0.0 · s.p.l.i.t 简体中文汉化补丁

## ⚠️ 本补丁不含游戏本体，需自备正版

`payload.zip` 里只有 **73 个被改动的游戏资源条目**（编译后的 GDScript、场景、字体、重绘贴图），
**不是**可独立运行的游戏。你必须拥有 Steam 正版 **s.p.l.i.t**，补丁才能应用。

## 下载与用法

1. 下载本 Release 的资产 **`payload.zip`**（34,094,559 B）。
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
| `payload.zip`（本资产） | 34,094,559 B | `367DA1AB572814F622074C4B3DF6264088C388BE17B0E6B99CEECCEA6F4C94A5` |
| 原版 `split.exe`（你自备的零售原版） | 407,187,680 B | `2F5E7E3EC06E1E3ECA3623E75DF65DE342DC39E21B886B59BA5D455BC752C9F6` |

应用器会先校验你那份 exe 的 SHA256，**与原版不一致会拒绝并说明原因**（退出码 2）。

## 本次做了什么（汉化内容）

- 458 条文本翻译为简体中文；6 个场景 37 处真实文本槽位替换；`forest road.tscn` 67 条过场字幕。
- 新增中文字体 `res://fonts/cjk.fontdata`（Noto Sans SC，7,743,989 B），13 个 `.fontdata` 改为外部引用它。
- 1 处代码改动：`scripts/Chat.gd` 兼容全角「：」对白切分。
- 12 张 UI 贴图重绘（把**烘进像素里的**英文改成中文，等长替换）。

## 自证（本机实测）

以零售原版 exe 为输入跑应用器：

- **解包后条目 1347 个，逐条字节相同 1347，不同 0** ✓
- 与官方成品 `dist/split.exe` 比对：条目名集合相同，共同条目 1347 个**逐条相同 1347，不同 0** ✓
- `VERDICT: PASS`（完整报告见仓库内 [`e2e-report.txt`](https://github.com/DRDRDRRDDRDR/split-zh/blob/main/e2e-report.txt)）

判据说明：**不是**「整文件逐字节相同」——官方成品当初是经 GDRE 全量重建 PCK 再叠加两次
splice 得到的，数据区布局与本应用器的最小改动方案必然不同；条目是自包含的，布局差异不影响语义。
产物体积 415,203,603 B（官方成品 415,215,233 B，差 11,630 B 全部来自数据区间隙布局）。

## 尚未验证 / 需要你实机确认

构建阶段的自动化验证（PCK 结构、逐槽位字节回读、字形覆盖率 990/990、PE 完整性）全部通过，
但**「进游戏看到中文」尚未由用户实机确认**：

1. 中文是否显示为汉字（而非方框/问号/空白）；
2. 中文在等宽终端里的换行/溢出；
3. 打字机逐字动画在中文下的表现。

## 法律声明

游戏本体及原始资源版权归原作者 Mike Klubnika 所有。本补丁为**非官方**民间汉化，
与作者、发行商无关，**不含游戏本体**，需自备正版。若权利人提出异议，本仓库与本 Release 会立即下架。
