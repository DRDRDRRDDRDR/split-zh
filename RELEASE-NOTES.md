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

`payload.zip` 大小 `34,100,519` 字节，SHA256 `42CD4762EBD9AAD9A2D7D347BD120FF508268AB6716DD0631057D2B855E50D0B`。

发布参考 `split.exe` 为 `415,217,163` 字节，SHA256 `83C09CDE6204746360CCDC062BB43C59C12AEB1D0037AF87BFA700E931258AC1`。用户机器上的 PCK 布局可能不同，最终 EXE 整文件哈希可不同；应用器以 1347 个资源条目逐条一致作为验收标准。

## 注意

汉化包不含游戏本体。请自备 Steam 正版 s.p.l.i.t。思维文本需键入英文，屏幕显示中文；程序 alias 保持原样。游戏实际显示、排版与打字机动画仍需运行时画面验证。
