# s.p.l.i.t 简体中文汉化安装器

## 安装

下载 `s.p.l.i.t-zh-installer.zip` 并解压，运行 `install.ps1`，选择 Steam 正版游戏目录内未经修改的 `split.exe`。安装器会校验原版哈希与 payload，调用标准库应用器构建并逐条验证资源，再备份原版为 `split.exe.orig.bak` 并安装。

`verify.ps1` 使用 `split-zh-install.json` 收据校验已安装 EXE 和原版备份；`uninstall.ps1` 仅在当前 EXE 与收据一致时回滚，防止覆盖 Steam 更新或其他 Mod。

## 自动构建

GitHub Actions 在推送 `v*` tag 时从已发布的 v1.1.0 获取固定 payload，检查长度与 SHA256，组装安装器 ZIP、逐文件 SHA256 清单和包 SHA256，并创建正式 Release。手动 dispatch 仅生成预览 artifact。

## 资产

- `s.p.l.i.t-zh-installer.zip`：Windows 安装器、安装/验证/回滚脚本、Python 应用器、payload 和文档。
- `payload.zip`：74 个汉化资源条目，不含游戏 EXE。
- `s.p.l.i.t-zh-installer.zip.sha256`：安装器压缩包 SHA256。

## 固定载荷校验

| 文件 | 大小 | SHA256 |
|---|---|---|
| `payload.zip`（本资产） | 34,101,396 B | `A1BE6695AB647E57543564B03C81D5D0449D4AE7602F2D09E94F5ED00144B1B6` |
| 原版 `split.exe`（你自备的零售原版） | 407,187,680 B | `2F5E7E3EC06E1E3ECA3623E75DF65DE342DC39E21B886B59BA5D455BC752C9F6` |

发布参考 `split.exe` 为 `415,218,046` 字节，SHA256 `4E558057CCF746121D65EB07F475B108E6F7DB978C0FA5A93B56107C8F87B40B`。用户机器上的 PCK 布局可能不同，最终 EXE 整文件哈希可不同；应用器以 1347 个资源条目逐条一致作为验收标准。

## v1.3.0 修复

`undesirable` / `outcome` / `no` 三个思维词此前落入「敲中文」分支：既无中文显示行，玩家也无法用拉丁键盘输入汉字（会卡住）。现已改为与其他思维一致的正确形态——场景文本保持英文供玩家照敲，中文由 `LabelSplitter` 的显示行画在上方，触发 alias 保持英文不变。改动为等长替换，场景偏移零变化。

## 注意

汉化包不含游戏本体。请自备 Steam 正版 s.p.l.i.t。思维文本需键入英文，屏幕显示中文；程序 alias 保持原样。游戏实际显示、排版与打字机动画仍需运行时画面验证。
