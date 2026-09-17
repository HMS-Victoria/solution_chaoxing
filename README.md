# 输入到光标（Type at Cursor）

> 把一段文本当键盘输入打到你鼠标光标所在的输入框里。
> 目标页面禁用粘贴（`paste` 事件被拦）时，这个工具依然有效。

Python 3.9 · 纯标准库（`ctypes` + `tkinter`）· 单文件 · Windows

---

## 一、它解决什么问题

**超星学习通 / 大夏学堂**这类作业系统的富文本编辑器会在页面里监听并 `preventDefault()` 掉 `paste` 事件，于是「复制 → 粘贴」这条路被从浏览器层面堵死了。手打几千字显然不现实。

一个自然的想法是写油猴脚本把拦截拆掉，但这条路有几个绕不开的麻烦：

| 浏览器侧方案（油猴 / 扩展） | 本工具（操作系统侧注入） |
|---|---|
| 要针对每个站点的 DOM 结构写选择器，站点改版就失效 | 不关心任何 DOM，**任何**输入框都能用 |
| 富文本编辑器（如 UEditor / 自定义 contenteditable）不走原生 `paste`，注入内容常常丢格式或整段丢失 | 等价于真人逐字敲键盘，编辑器收到的是标准按键序列 |
| 需要装扩展 / 脚本管理器，赋予其读取所有页面的权限 | 零依赖、零扩展权限，双击即用 |
| 部分站点会检测 `event.isTrusted` 来识别脚本注入 | 走 OS 输入队列，浏览器标记为 `isTrusted: true`，**无法与真人输入区分** |

本工具走的是最后一行这条路线：**根本不产生 `paste` 事件**，所以也就无所谓被不被拦。

---

## 二、原理

页面拦的是 `paste` 事件，而本工具从头到尾不碰剪贴板，而是调用 Win32 `SendInput` 在**操作系统输入层**注入按键：

```python
INPUT_KEYBOARD  = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004   # 直接把 UTF-16 码元当按键送进去

class INPUT(ctypes.Structure):
    # Union 里必须带上 MOUSEINPUT：它是最大的成员，决定了 x64 下 INPUT == 40 字节。
    # 少写一个成员会让 sizeof(INPUT) 变小，SendInput 直接返回 0 且不报错。
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]
```

关键在 `KEYEVENTF_UNICODE`：它让你**跳过虚拟键码和键盘布局**，直接把一个 UTF-16 码元作为按键事件提交。于是：

- **中文不需要输入法**，不需要模拟 Ctrl+Space，也不会弹出候选框；
- **emoji 等非 BMP 字符**由 Python 侧自动拆成代理对（`units()` 用 `utf-16-le` 编码，一个字符拆成 1~2 个码元）；
- 浏览器收到的是货真价实的 `keydown` / `keypress` / `keyup`，`event.isTrusted === true`。

换行单独处理：浏览器 `textarea` 对 Unicode 的 `\n` 经常直接丢弃，所以换行改为发送真正的回车键（`VK_RETURN`），且可用复选框关掉。

按下与抬起两个事件放在**同一次** `SendInput` 调用里提交，避免字符顺序错乱。

---

## 三、功能

- **全局热键 F8**：不用切换窗口，在目标输入框里按 F8 就开始输入。
- **不往自己窗口里打字**：当前台窗口是本工具自己时，F8 会提示「请先点一下目标输入框」，不会把文本打进自己的编辑框。
- **倒计时**：0~10 秒可调，留出你点进目标输入框的时间（按 F8 触发时固定 0.6 秒）。
- **每字符间隔**：0~200 毫秒可调。0 是最快，25 毫秒接近正常手速，遇到丢失字符时调大。
- **随时中止**：「停止」按钮，或直接关窗口。
- **实时进度**：`已输入 1234/5000`，长文本不会让你猜它卡没卡住。
- **中文与 emoji 原生支持**：无需输入法，无需切换键盘布局。
- **自检**：`py -3.9 type_at_cursor.pyw --selftest` 校验结构体尺寸与编码逻辑，输出 `ok`。
- **崩溃可见**：`pythonw` 没有控制台，所以启动失败会把 traceback 写到 `%TEMP%\type_at_cursor.log` 并弹窗告诉你路径，而不是「双击没反应」。
- **纯标准库**：`ctypes` + `tkinter` + `threading`，无任何第三方依赖，不需要 `pip install`。

---

## 四、快速开始

### 方式 1：直接跑源码（需要 Python 3.9+）

```cmd
启动.cmd
```

或手动：

```cmd
py -3.9 type_at_cursor.pyw
```

### 方式 2：自己构建免安装 exe

```cmd
build_exe.cmd
```

需要 `py -3.9 -m pip install pyinstaller`（`pyinstaller-hooks-contrib` 会作为依赖自动装上，不必手动指定）。产物在 `dist\`：`TypeAtCursor.exe` 与中文名的 `输入到光标.exe`（同一份文件的两个名字，内容完全一致）。构建脚本刻意**全 ASCII**——`.cmd` 用 OEM 代码页解析，里面直接写中文字面量会乱码，所以中文文件名是用 `[char]0x8F93...` 拼出来的。

### 用法

```
1. 把文本粘到工具窗口里        （本工具自己不拦粘贴，可正常 Ctrl+V）
2. 点一下目标输入框，让光标落在里面
3. 按 F8                      （全局生效，不用切窗口）
   ── 或者点「开始输入」，用倒计时留出切换窗口的时间 ──
```

推荐参数：倒计时 `3` 秒、每字符间隔 `25` 毫秒。文本特别长（上万字）时把间隔调到 `0` 会快很多，代价是偶发丢字。

---

## 五、仓库结构

```
.
├── type_at_cursor.pyw   # 全部源码，单文件 322 行
├── 启动.cmd             # 双击启动（pyw -3.9）
├── build_exe.cmd        # PyInstaller 单文件打包
├── .gitignore           # dist/ 等构建产物不入库
└── .gitattributes       # 钉死 LF，抵消本机 core.autocrlf=true
```

仓库里只有 6 个文件、约 25 KB，没有任何二进制。`dist/` 里那两个 9.3 MB 的 exe 被有意排除——它们可由 `build_exe.cmd` 完整复现，没必要进版本库。

源码分三段，边界是刻意的：

```
Win32 定义      INPUT / KEYBDINPUT 结构体与 SendInput 绑定
纯函数部分      normalize / units / key_events / send / selftest   ← 无 IO，可单测
界面部分        App（tkinter）+ 子线程注入
```

`selftest()` 覆盖的正是纯函数部分——因为真正会出错的是**结构体内存布局**而不是界面：

```python
def selftest():
    expect = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(INPUT) == expect, "sizeof(INPUT)=%d，应为 %d" % (ctypes.sizeof(INPUT), expect)
    assert units("\U0001F600") == (0xD83D, 0xDE00)
    assert normalize("a\r\nb\rc\n") == "a\nb\nc\n"
    ...
    print("ok")
```

---

## 六、几个值得说明的实现细节

**1. `sizeof(INPUT)` 必须是 40 字节（x64）**
`INPUT` 是一个带 union 的结构体，union 的最大成员是 `MOUSEINPUT`。少写一个 union 成员会让整个结构体变小，而 `SendInput` **不会报错**——它只是返回 0，表现为「什么都没发生」。这是本类代码最经典的坑，所以它被写进了注释和自检断言。

**2. `GetForegroundWindow` 必须显式设置 `restype`**
`ctypes` 默认把返回值当 `c_int`，64 位下句柄会被截断，`GetWindowThreadProcessId` 就查不到正确的进程。所以：

```python
user32.GetForegroundWindow.restype = wintypes.HWND  # 不设 restype 会被截成 32 位
```

**3. Tk 不是线程安全的**
注入在子线程里跑（否则倒计时和输入会卡住界面），但子线程**绝不碰任何控件**，只通过 `self._msg` / `self._finish` 两个标志向主线程传话，主线程每 80 毫秒轮询一次并更新界面。

**4. 热键用轮询而不是键盘钩子**
主线程的轮询循环里顺便查 `GetAsyncKeyState(VK_F8)`，而不是装 `WH_KEYBOARD_LL`。代价是 F8 仍会被前台程序收到（浏览器里 F8 无默认行为，无妨），收益是省掉一整套消息循环与钩子生命周期管理。真需要吞掉这个键再换钩子方案。

**5. 换行发回车而不是 `\n`**
见第二节。可用「换行按回车」关掉，关掉后换行会被完全跳过。

---

## 七、已知限制

如实列出，不粉饰：

1. **管理员权限窗口无法注入**。Windows 的 UIPI 机制禁止低完整性进程向高完整性进程发送输入。如果目标浏览器以管理员身份运行，`SendInput` 会返回 0，工具会提示「输入被系统拒绝，请以管理员身份重新启动本工具」。
2. **F8 仍会被前台程序收到**（见第六节第 4 点）。不吞键是刻意取舍。
3. **长文本需要时间**。输入耗时 ≈ 字符数 × 每字符间隔。5000 字 × 25 毫秒 ≈ 2 分钟，期间请勿切换焦点。
4. **不读剪贴板**。文本必须由你手动粘进工具窗口——这是刻意的：读剪贴板会引入额外的权限与隐私面。
5. **不能后台输入**。注入的是全局按键，只会进入**当前前台窗口**；运行期间请勿 Alt+Tab。
6. **个别编辑器会吞掉超快输入**。某些富文本编辑器对按键做了防抖或异步处理，间隔为 `0` 时可能丢字，把间隔调大即可。
7. **仅 Windows**。`SendInput` / `KEYEVENTF_UNICODE` 是 Win32 API；macOS 与 Linux 需要各自的原生实现（`CGEventPost` / `uinput`）。
8. **无自动化测试，只有自检**。`--selftest` 覆盖纯函数与结构体布局；界面与注入路径需要真实桌面环境，无法在 CI 里跑。

---

## 八、免责声明

**本工具是一个通用文本输入辅助工具，不是针对任何特定平台或系统的绕过方案。**

- 它只做一件事：把你**自己提供**的文本，以键盘输入的形式送入**你自己**当前聚焦的输入框。
- 它不读取、不篡改、不代答任何内容，不联网，不访问剪贴板，不注入任何进程，不修改任何页面。
- 请仅用于**你自己撰写的内容**的录入。是否使用键盘模拟方式提交内容，由你所在机构的学术规范与平台用户协议决定，**使用者自行承担相应责任**。
- 本工具无法帮助你回答你不会的题——它只是把字打进去，一个字都不会替你想。

---

## 九、开发

```cmd
:: 自检（纯函数 + 结构体布局）
py -3.9 type_at_cursor.pyw --selftest

:: 语法检查
py -3.9 -m py_compile type_at_cursor.pyw

:: 打包
build_exe.cmd
```

`dist/` 被 `.gitignore` 排除：exe 可由 `build_exe.cmd` 完整复现，单个 9.3 MB，没必要进版本库。

---

## 十、许可

未附加开源许可证文件。如需使用、修改或分发，请先联系仓库作者。
