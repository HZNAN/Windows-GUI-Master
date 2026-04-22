# pywinauto UI Automation 定位方式

## 核心概念

pywinauto 使用 **Windows UI Automation (UIA)** 或 **Win32 API** 来操作 Windows GUI 控件。

**不需要应用厂商提供任何东西**，Windows 系统自动维护每 个应用的控件树。

## 定位方式

### 1. 通过控件文本定位（最常用）

```python
from pywinauto import Application

app = Application(backend="uia").connect(title="飞书")
app.window(title="飞书")['发送'].click()
app.window(title="飞书")['输入框'].type_keys("Hello")
```

### 2. 通过控件类型定位

```python
app.Button.click()           # 点击按钮
app.Edit.type_keys("text")   # 输入文本
app.ComboBox.select("选项") # 选择下拉框
```

### 3. 通过窗口句柄定位

```python
from pywinauto import Desktop

# 连接已运行的窗口
app = Application(backend="uia").connect(handle=window_handle)
```

### 4. 打印控件树（用于探索）

```python
app.window(title="飞书").print_control_identifiers()
# 输出控件结构：
# 0 | None | 'NavigationPane'
# 1 | None | 'DocumentList'
# 2 | Button | '发送'
```

## 主要操作

| 操作 | 代码 | 说明 |
|------|------|------|
| 点击 | `app['控件名'].click()` | 左键点击 |
| 右键 | `app['控件名'].right_click_input()` | 右键点击 |
| 双击 | `app['控件名'].double_click_input()` | 左键双击 |
| 输入文本 | `app['控件名'].type_keys("text")` | 键盘输入 |
| 按住 | `app['控件名'].select()` | 选中/按住 |
| 获取文本 | `app['控件名'].texts()` | 获取控件文本 |
| 等待 | `app['控件名'].wait('visible')` | 等待控件出现 |
| 拖拽 | `app['控件名'].drag_input(to='目标')` | 拖拽到目标 |

## 拖拽示例

```python
# 方式1: 拖拽到目标控件
app['文件'].drag_input(to='目标文件夹')

# 方式2: 拖拽到坐标
app['文件'].drag_input(coords=(100, 200))
```

## 后端选择

```python
# Win32 API（默认，兼容性更好）
app = Application(backend="win32")

# UIAutomation（更现代，支持更多控件）
app = Application(backend="uia")
```

## 与 pyautogui 对比

| 特性 | pywinauto | pyautogui |
|------|-----------|------------|
| 定位方式 | UI 控件树 | 图像匹配 |
| 坐标 | 相对坐标，自动更新 | 绝对坐标，需重新截图 |
| 依赖 | Windows API | 图像识别 |
| 适用场景 | Windows 原生应用 | 任何应用 |

## 使用场景

- 需要操作 Windows 原生应用（记事本、文件资源管理器）
- 控件有明确的文本标签
- 窗口会被拖动或调整大小
- 需要获取/设置控件内容

## 未来可能的集成

考虑在 AI Agent 中增加 pywinauto 作为备选方案，当截图+坐标方式失败时，可以尝试通过 UI Automation 定位控件。
