# Win32Overlay WndProc 绑定陷阱

## 问题

`Win32Overlay._create_window_class()` 在首次注册 Windows 窗口类时，将 `WndProc` 绑定到**第一个实例的 `self._wnd_proc`**。此后所有窗口消息（WM_PAINT、WM_DESTROY 等）都会路由到这个被绑定的旧实例，而不是当前活跃实例。

## 触发条件

1. 第一个 `Win32Overlay` 实例注册窗口类 `"VirtualCursorOverlay"`
2. 该实例被销毁（`close()` → `DestroyWindow`），`hwnd` 置为 0
3. 创建第二个 `Win32Overlay` 实例
4. `_create_window_class()` 发现类已注册，直接返回（不更新 WndProc）
5. 新实例创建的窗口用的仍是旧实例的 WndProc
6. 旧实例 `_visible = False`（被 `close()` 置位），因此 `_on_paint()` 直接返回，光标永远不绘制

## 关键代码路径

```python
# drivers/win32_overlay.py:311-318
def _create_window_class(self) -> str:
    try:
        win32gui.GetClassInfo(None, class_name)
        return class_name  # ← 第二次调用: 类已存在，直接返回，WndProc 仍是旧实例的
    except:
        pass
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = self._wnd_proc  # ← 第一次调用: 绑定 self（第一个实例）到 WndProc
    ...
```

```python
# drivers/win32_overlay.py:340-342
def _on_paint(self):
    if not self._visible:  # ← 旧实例 _visible = False → 直接返回，不绘制
        return
```

## 解决方案

**不要让 `Win32Overlay` 实例的生命周期跨越 Windows 窗口类的生命周期。**

在当前架构中：
- `_cleanup()` 只调用 `vc.hide()` 隐藏窗口，不调用 `close()` 销毁
- 窗口类只注册一次，WndProc 绑定到第一个也是唯一的实例
- 后续 task 复用同一个 `Win32Overlay` 实例，`show()` / `hide()` 切换可见性

## 深层原因

Win32 窗口类的 WndProc 是**类级别**的（per-class），不是每个窗口一个。pywin32 在 `RegisterClass` 时捕获 Python bound method 作为回调函数指针，而 bound method 中的 `self` 引用在注册时就固定了。
