# 输入到光标（Type at Cursor）

[下载最新发行版](https://github.com/HMS-Victoria/solution_chaoxing/releases/latest) · [中文使用说明](README-zh-CN.txt) · [发行验收记录](docs/release-readiness/2026-09-20/VERIFICATION.md)

**下载 exe → 双击 → 粘贴文本 → 选择目标窗口 → 按 F8。**

当前版本：**v1.0.0 / Windows x64**。本地包位于 `dist/v1.0.0/`。包已生成，实际环境验收待完成；具体已执行测试与限制见验收记录，尤其不把开发机测试视为未安装 Python 的全新 Windows 用户验收。

## 普通用户使用

1. 下载 `TypeAtCursor-Windows-x64.exe`、`README-zh-CN.txt` 和 `SHA256SUMS`。
2. 双击 exe，把自己的文本粘贴到工具窗口。
3. 点进记事本等目标程序的输入位置，按 F8，约 0.6 秒后开始输入。
4. 也可点击“开始输入”，在默认 3 秒倒计时内切到目标输入框。
5. 需要中止时切回工具点“停止”，或关闭工具。F8 只负责开始。

发行 exe 内置运行环境，不要求安装 Python、联网、账号或模型。正常使用不需要管理员权限；请让目标程序同样以普通权限运行。`启动.cmd` 是源码启动入口，不能当作免环境包。

只提供一个主程序文件名，不需要同时下载多份 exe。GitHub 自动生成的源码压缩包也不是发行程序。

## 前台窗口与停止行为

- 文字输入到**当时的前台输入框**，不会锁定最初选中的窗口，也不支持后台输入。
- 运行中切换窗口，后续字符就会进入新窗口。先停止，再切换目标；切回工具点停止的途中仍可能有字符输入。
- 开始时焦点若还在工具自身，会取消本次输入；这一保护只在开始时检查。
- 停止不会撤销已经输入的文字。请先在空白记事本中试用自造文本。
- 换行默认发送回车；关闭“换行按回车”会跳过换行。不要对准按回车就发送消息或执行命令的界面。
- 中文和 emoji 按 UTF-16 码元发送，具体显示与接收效果由目标编辑器决定。默认每字符 25 毫秒；丢字时调大。
- F8 仍会被前台程序收到。本工具不保存输入文本、不主动读取剪贴板、不联网。

## 适用系统与限制

发行目标为 Windows 10 / 11 x64，实际测试平台及未验证项见[验收记录](docs/release-readiness/2026-09-20/VERIFICATION.md)。不支持 macOS/Linux/Windows ARM 的原生版本。

部分编辑器可能拒绝或丢失模拟输入，不能保证适用于所有输入框。Windows 权限隔离可能阻止向管理员窗口输入；先将目标程序以普通权限重开。程序未签名，可能出现来源提示；不要关闭系统安全防护。

首次启动会把内置运行环境解压到系统临时目录。启动异常写入 `%TEMP%\type_at_cursor.log`，不会把用户文本作为正常运行日志保存。进度统计按原文本字符计算，关闭换行输入时也计入被跳过的换行。

## 开发者：源码运行与固定构建

保留原有单文件 `type_at_cursor.pyw`、标准库 `ctypes` + `tkinter`，以及 `build_exe.cmd` 入口。运行源码可用带 Tk 的 Python；本次发行固定 **CPython 3.9.13 x64、PyInstaller 6.20.0、hooks 2026.4**。其余构建依赖（含传递依赖）固定在 `requirements-build.txt`。

```cmd
:: 源码启动，要求已安装 Python 3.9
启动.cmd

:: 创建项目内 .venv-build、安装固定构建依赖、自检、回归与 onefile/windowed 打包
build_exe.cmd

:: Python 启动器不可用时，可显式指定已安装的 3.9.13 x64
set "BUILD_PYTHON=C:\path\to\Python39\python.exe"
build_exe.cmd

:: 离线逻辑验证（不会发送真实按键）
.venv-build\Scripts\python.exe type_at_cursor.pyw --selftest
.venv-build\Scripts\python.exe test_release.py
```

首次准备构建环境需要下载依赖。依赖只安装到本项目 `.venv-build/`，不修改全局环境。开发者需有完整的 Tcl/Tk 文件；受限账号读取不到基础 Python 的 Tcl 时，不能据此认定打包程序缺失 Tk。

版本号定义在 `type_at_cursor.pyw` 的 `APP_VERSION`，同时写入窗口标题与 exe 文件属性。变更版本时同步更新中文说明和发行草稿。

输出：

- `dist/v1.0.0/TypeAtCursor-Windows-x64.exe`
- `dist/v1.0.0/README-zh-CN.txt`
- `dist/v1.0.0/SHA256SUMS`

构建记录保存在 `build/v<版本>-<时间>/`，包含完整日志、版本资源、源码 SHA-256、依赖版本和 Git 基线。已存在的发行目录会阻止重建，请先明确归档旧目录；不会自动删除历史发行包。`dist/` 顶层若有旧版两个 exe，是历史本地产物，不在本次上传清单中。

“可重复构建”指固定输入、工具版本和命令并能重建运行包。脚本固定 Python hash seed 和时间戳，并留存每次输出哈希；跨机器逐字节一致性需另行验证，不能仅凭版本固定作此保证。

## 实现与测试范围

`SendInput` 配合 `KEYEVENTF_UNICODE` 注入系统键盘事件；中文与非 BMP 字符拆成 UTF-16 码元。换行使用 `VK_RETURN`。x64 下 `INPUT` 为 40 字节，union 必须包含 `MOUSEINPUT`；窗口句柄的返回类型显式设为 `HWND`。

Tk 界面在主线程，输入工作在线程中，通过受锁保护的状态消息更新主界面，避免完成或停止提示在刷新时丢失。F8 使用轮询，不安装键盘钩子。`--selftest` 校验结构布局与编码，`test_release.py` 模拟输入成功、部分失败、换行跳过、自身焦点及取消路径；这些都不能替代记事本实测。

发行记录与交接位于 `docs/release-readiness/2026-09-20/`。真实验收只使用自造文本，不涉及真实作业系统。

## 使用范围与许可

这是通用文本输入辅助工具，只把用户自己提供的文本送往用户选中的前台输入框。请仅用于有权录入的场景，遵守目标程序和所在机构的规则。

仓库未附加开源许可证文件；其他使用、修改或分发授权请联系仓库作者。
