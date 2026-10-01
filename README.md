# s.p.l.i.t 简体中文汉化安装器

面向 Steam 正版 **s.p.l.i.t**（Mike Klubnika，Godot 4.4.1）的 Windows 简体中文汉化安装器。

> GitHub Actions 会在发布版本 tag 时自动构建 `s.p.l.i.t-zh-installer.zip` 并上传到 GitHub Release。安装包不含游戏本体；首次安装需用户提供 Steam 原版 `split.exe`。

> ## 法律声明
> 本仓库不含游戏本体，也不含任何可独立运行的游戏文件。补丁载荷仅包含修改过的 Godot 资源条目，必须由你自备 Steam 正版游戏才能使用。安装器会校验原版 EXE 的 SHA256，只接受未经修改的指定正版版本。本补丁为非官方民间汉化，与作者、发行商无关。

## 汉化内容

| 项目 | 内容 |
|---|---|
| 翻译文本 | 458 条英文转简体中文 |
| 场景文本 | 37 处文本替换及等值槽位修复 |
| 过场字幕 | 67 条 |
| 中文字体 | 新增 Noto Sans SC 字体资源，由 13 个字体资源引用 |
| 对白切分 | 支持全角冒号说话人前缀 |
| UI 贴图 | 13 张贴图中的烘焙英文替换为中文 |
| 思维文本 | 输入英文、屏幕显示中文；alias 与触发逻辑保留原文 |

思维输入仍要求玩家键入英文，以保持原有逐字输入机制；对应中文会在画面显示。

## 校验值

| 文件 | 大小 | SHA256 |
|---|---:|---|
| 原版 `split.exe`（用户自备） | 407,187,680 B | `2F5E7E3EC06E1E3ECA3623E75DF65DE342DC39E21B886B59BA5D455BC752C9F6` |
| v1.1.0 `payload.zip` | 34,100,519 B | `42CD4762EBD9AAD9A2D7D347BD120FF508268AB6716DD0631057D2B855E50D0B` |
| 本机参考构建 `split.exe` | 415,217,163 B | `83C09CDE6204746360CCDC062BB43C59C12AEB1D0037AF87BFA700E931258AC1` |

不同合法 PCK 布局可能使最终 EXE 整文件哈希不同；应用器逐条校验资源，不要求生成物与本机参考 EXE 整文件相同。

## 安装

1. 从 [Releases](https://github.com/DRDRDRRDDRDR/split-zh/releases/latest) 下载 `s.p.l.i.t-zh-installer.zip` 并解压。
2. 关闭游戏，运行 `install.ps1`。
3. 在窗口中选择 Steam 安装目录内的正版原版 `split.exe`。需要 Python 3.8+，无需额外 pip 套件。
4. 安装器校验原版和 payload，生成汉化 EXE 并核对资源条目后，备份原版为 `split.exe.orig.bak` 再安装。
5. 用 `verify.ps1` 检查安装；用 `uninstall.ps1` 从原版备份回滚。

安装收据绑定当前汉化 EXE 与原版备份哈希。若 Steam 或其他 Mod 改动了游戏文件，验证会报告不一致，卸载也会拒绝覆盖未知文件。

## GitHub Actions 发布

推送 `v*` tag 时，`.github/workflows/release-installer.yml` 从 v1.1.0 取得并校验固定 payload，构建 Windows 安装器 ZIP、逐文件 SHA256 清单及压缩包摘要，并自动创建 Release。手动运行 workflow 只生成预览 artifact，不创建正式 Release。

Release 资产包括安装器 ZIP、独立 `payload.zip` 和安装器 ZIP 的 SHA256 文件。仓库和资产均不包含游戏本体或 `split.exe`。

## 本地构建验证

- PCK 索引摘要：1347/1347 自洽。
- GDScript 字节码：117/117 可解析。
- 完整思维版离线交付一致性验收通过。
- 原版输入应用器测试：资源条目 1347/1347 相同。

游戏内思维排版、打字机动画和中文渲染仍需实际运行截图确认；静态验收不替代运行时验证。
