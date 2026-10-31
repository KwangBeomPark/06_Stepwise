"""Windows UI Element Selector & Simulate Click service (Section 7 & Phase 4).

Pure ctypes implementation combining Win32 HWND hierarchy inspection,
control attribute matching (AutomationId/CtrlId, Name, ClassName, ControlType),
window-relative coordinate anchoring, and background Simulate Click
(BM_CLICK / WM_LBUTTONDOWN+UP+DBLCLK via SendMessageTimeoutW / PostMessageW).
"""

from __future__ import annotations

import ctypes
import fnmatch
import os
import time
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

from stepwise.core.variables import substitute_variables
from stepwise.services.screen import get_screen_info
from stepwise.services.window_win import (
    _get_window_long,
    get_window_title,
    list_visible_windows,
    user32,
)

# Win32 Constants
GA_ROOT = 2
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
BM_CLICK = 0x00F5

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_RBUTTONDBLCLK = 0x0206
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MBUTTONDBLCLK = 0x0209

MK_LBUTTON = 0x0001
MK_RBUTTON = 0x0002
MK_MBUTTON = 0x0010

SMTO_NORMAL = 0x0000
SMTO_ABORTIFHUNG = 0x0002
ERROR_TIMEOUT = 1460

BS_TYPEMASK = 0x0000000F
BS_CHECKBOX = 0x00000002
BS_AUTOCHECKBOX = 0x00000003
BS_RADIOBUTTON = 0x00000004
BS_GROUPBOX = 0x00000007
BS_AUTORADIOBUTTON = 0x00000009
GWL_STYLE = -16
CWP_SKIPINVISIBLE = 0x0001
CWP_SKIPDISABLED = 0x0002

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND

user32.ChildWindowFromPointEx.argtypes = [
    wintypes.HWND,
    wintypes.POINT,
    wintypes.UINT,
]
user32.ChildWindowFromPointEx.restype = wintypes.HWND

user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetAncestor.restype = wintypes.HWND

user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int

user32.GetDlgCtrlID.argtypes = [wintypes.HWND]
user32.GetDlgCtrlID.restype = ctypes.c_int

user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.IsHungAppWindow.argtypes = [wintypes.HWND]
user32.IsHungAppWindow.restype = wintypes.BOOL

user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL

user32.EnumChildWindows.argtypes = [wintypes.HWND, WNDENUMPROC, wintypes.LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL

user32.PostMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.PostMessageW.restype = wintypes.BOOL

user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_size_t),
]
user32.SendMessageTimeoutW.restype = wintypes.LPARAM


def get_class_name(hwnd: int) -> str:
    """Return the Win32 class name of an HWND."""
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    length = user32.GetClassNameW(hwnd, buf, 256)
    return buf.value if length > 0 else ""


def get_control_text(hwnd: int) -> str:
    """Retrieve text of a control via GetWindowTextW or WM_GETTEXT."""
    if not hwnd:
        return ""
    title = get_window_title(hwnd)
    if title:
        return title
    res = ctypes.c_size_t(0)
    ret = user32.SendMessageTimeoutW(
        hwnd, WM_GETTEXTLENGTH, 0, 0, SMTO_ABORTIFHUNG, 100, ctypes.byref(res)
    )
    length = int(res.value) if ret else 0
    if 0 < length < 4096:
        buf = ctypes.create_unicode_buffer(length + 2)
        buf_addr = ctypes.cast(buf, ctypes.c_void_p).value or 0
        user32.SendMessageTimeoutW(
            hwnd,
            WM_GETTEXT,
            length + 1,
            buf_addr,
            SMTO_ABORTIFHUNG,
            100,
            ctypes.byref(res),
        )
        return buf.value
    return ""


def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Return (left, top, width, height) in physical screen pixels."""
    if not hwnd or not user32.IsWindow(hwnd):
        return None
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    w = max(0, rect.right - rect.left)
    h = max(0, rect.bottom - rect.top)
    return (rect.left, rect.top, w, h)


def infer_control_type(hwnd: int, class_name: str) -> str:
    """Infer a standardized UIA-like ControlType name from Win32 class & style."""
    cls_lower = class_name.lower()
    if "button" in cls_lower or "btn" in cls_lower:
        style = _get_window_long(hwnd, GWL_STYLE) if hwnd else 0
        btn_type = int(style) & BS_TYPEMASK
        if btn_type in (BS_CHECKBOX, BS_AUTOCHECKBOX):
            return "CheckBox"
        if btn_type in (BS_RADIOBUTTON, BS_AUTORADIOBUTTON):
            return "RadioButton"
        if btn_type == BS_GROUPBOX:
            return "Group"
        return "Button"
    if "edit" in cls_lower or "textbox" in cls_lower or "richedit" in cls_lower:
        return "Edit"
    if "combobox" in cls_lower:
        return "ComboBox"
    if "listbox" in cls_lower or "listview" in cls_lower or "syslistview" in cls_lower:
        return "List"
    if "systreeview" in cls_lower or "tree" in cls_lower:
        return "Tree"
    if "static" in cls_lower or "label" in cls_lower:
        return "Text"
    if "systabcontrol" in cls_lower or "tab" in cls_lower:
        return "Tab"
    return "Pane"


@dataclass
class UIElementInfo:
    hwnd: int
    root_hwnd: int
    window_title: str
    window_class: str
    control_type: str
    automation_id: str
    name: str
    class_name: str
    rect: tuple[int, int, int, int]  # (left, top, width, height)
    rel_x: int = 0
    rel_y: int = 0
    ctrl_rel_x: int = 0
    ctrl_rel_y: int = 0
    dpi_scale: int = 100
    is_root_anchor: bool = False
    supports_simulate: bool = True

    @property
    def center(self) -> tuple[int, int]:
        left, top, w, h = self.rect
        if w > 0 and h > 0:
            return (left + w // 2, top + h // 2)
        return (left + self.rel_x, top + self.rel_y)

    def _scale_offset(self, offset: int) -> int:
        if self.dpi_scale and self.dpi_scale > 0:
            cur_scale = int(get_screen_info().get("scale_percent", 100) or 100)
            if cur_scale > 0 and cur_scale != self.dpi_scale:
                return int(round(offset * (cur_scale / float(self.dpi_scale))))
        return offset

    def target_point(self) -> tuple[int, int]:
        """Compute best click point in physical screen coordinates."""
        left, top, w, h = self.rect
        if self.hwnd != self.root_hwnd:
            # For list/tree/pane controls, preserve exact clicked cell/offset if inside bounds
            if self.control_type in ("List", "Tree", "Pane", "Tab") and (
                self.ctrl_rel_x > 0 or self.ctrl_rel_y > 0
            ):
                sx = self._scale_offset(self.ctrl_rel_x)
                sy = self._scale_offset(self.ctrl_rel_y)
                if 0 <= sx <= w and 0 <= sy <= h:
                    return (left + sx, top + sy)
            return self.center

        if self.rel_x > 0 or self.rel_y > 0:
            return (
                left + self._scale_offset(self.rel_x),
                top + self._scale_offset(self.rel_y),
            )
        return (left + w // 2, top + h // 2)

    def to_selector_dict(self) -> dict[str, Any]:
        """Serialize into clean JSON selector structure."""
        return {
            "window_title": self.window_title,
            "window_class": self.window_class,
            "control_type": self.control_type,
            "automation_id": self.automation_id,
            "name": self.name,
            "class_name": self.class_name,
            "rel_x": self.rel_x,
            "rel_y": self.rel_y,
            "ctrl_rel_x": self.ctrl_rel_x,
            "ctrl_rel_y": self.ctrl_rel_y,
            "dpi_scale": self.dpi_scale,
            "is_root_anchor": self.is_root_anchor,
            "bbox": list(self.rect),
        }

    def summary_label(self) -> str:
        """Return compact human-readable label for UI display."""
        ident = self.name or self.automation_id or self.class_name or "Element"
        if len(ident) > 28:
            ident = ident[:25] + "..."
        win = self.window_title[:20] + "..." if len(self.window_title) > 23 else self.window_title
        return f'[{self.control_type}] "{ident}" in "{win}"'


def _enumerate_child_hwnds(root_hwnd: int) -> list[int]:
    children: list[int] = []

    def _cb(hwnd: int, lparam: int) -> bool:
        if user32.IsWindowVisible(hwnd):
            children.append(hwnd)
        return True

    proc = WNDENUMPROC(_cb)
    user32.EnumChildWindows(root_hwnd, proc, 0)
    return children


def inspect_element_at(
    x: int, y: int, exclude_self: bool = True
) -> UIElementInfo | None:
    """Inspect the deepest visible UI element at physical coordinates (x, y).

    If a Stepwise overlay window is at (x, y) and exclude_self=True, sees through
    the overlay by finding the topmost visible non-Stepwise window in Z-order.
    """
    pt = wintypes.POINT(int(x), int(y))
    raw_hwnd = user32.WindowFromPoint(pt)
    root_hwnd = (user32.GetAncestor(raw_hwnd, GA_ROOT) or raw_hwnd) if raw_hwnd else 0

    if exclude_self and root_hwnd:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(root_hwnd, ctypes.byref(pid))
        if pid.value == os.getpid():
            root_hwnd = 0
            raw_hwnd = 0

    if not root_hwnd:
        if not exclude_self:
            return None
        # Find topmost visible non-self window containing (x, y) in Z-order
        for win_hwnd, _ in list_visible_windows(exclude_self=True):
            w_rect = get_window_rect(win_hwnd)
            if w_rect:
                wl, wt, ww, wh = w_rect
                if wl <= x < wl + ww and wt <= y < wt + wh:
                    root_hwnd = win_hwnd
                    raw_hwnd = win_hwnd
                    break
        if not root_hwnd:
            return None

    root_rect = get_window_rect(root_hwnd)
    if not root_rect:
        return None

    win_title = get_window_title(root_hwnd)
    win_class = get_class_name(root_hwnd)

    # Find smallest visible child control containing (x, y), preferring non-groupbox controls
    best_hwnd = raw_hwnd
    best_area = root_rect[2] * root_rect[3] + 1
    best_rect = get_window_rect(raw_hwnd) or root_rect

    for child in _enumerate_child_hwnds(root_hwnd):
        c_rect = get_window_rect(child)
        if not c_rect:
            continue
        cl, ct, cw, ch = c_rect
        if cw <= 0 or ch <= 0:
            continue
        if cl <= x <= cl + cw and ct <= y <= ct + ch:
            cls_name = get_class_name(child)
            c_type = infer_control_type(child, cls_name)
            area = cw * ch
            # Penalize groupboxes so inner buttons win
            if c_type == "Group":
                area *= 10
            if area < best_area:
                best_area = area
                best_hwnd = child
                best_rect = c_rect

    is_root = best_hwnd == root_hwnd
    cls_name = get_class_name(best_hwnd)
    ctrl_type = infer_control_type(best_hwnd, cls_name)
    ctrl_id_int = user32.GetDlgCtrlID(best_hwnd) if not is_root else 0
    auto_id = str(ctrl_id_int) if ctrl_id_int > 0 else ""

    # Do NOT store mutable user-entered content for Edit/ComboBox controls or root window title
    if is_root or ctrl_type in ("Edit", "ComboBox"):
        elem_name = ""
    else:
        elem_name = get_control_text(best_hwnd).strip()

    rel_x = int(x - root_rect[0])
    rel_y = int(y - root_rect[1])
    ctrl_rel_x = int(x - best_rect[0])
    ctrl_rel_y = int(y - best_rect[1])
    cur_scale = int(get_screen_info().get("scale_percent", 100) or 100)

    return UIElementInfo(
        hwnd=best_hwnd,
        root_hwnd=root_hwnd,
        window_title=win_title,
        window_class=win_class,
        control_type=ctrl_type,
        automation_id=auto_id,
        name=elem_name,
        class_name=cls_name,
        rect=best_rect,
        rel_x=rel_x,
        rel_y=rel_y,
        ctrl_rel_x=ctrl_rel_x,
        ctrl_rel_y=ctrl_rel_y,
        dpi_scale=cur_scale,
        is_root_anchor=is_root,
        supports_simulate=True,
    )


def _matches_pattern(value: str, pattern: str, allow_substring: bool = False) -> bool:
    """Case-insensitive match supporting '*' and '?' wildcards.

    By default requires exact match unless wildcards are used (or allow_substring=True for window titles).
    """
    v = value.strip().lower()
    p = pattern.strip().lower()
    if not p:
        return True
    if "*" in p or "?" in p:
        return fnmatch.fnmatchcase(v, p)
    if allow_substring:
        return v == p or p in v
    return v == p


def resolve_selector(
    selector: dict[str, Any],
    row_data: dict[str, Any] | None = None,
    exclude_self: bool = True,
) -> UIElementInfo:
    """Locate a single UI element on screen matching the selector specification.

    Raises LookupError if 0 elements match or if >=2 elements match ambiguously.
    """
    if not selector or not isinstance(selector, dict):
        raise LookupError("UI Selector is empty or invalid.")

    raw_win_title = str(selector.get("window_title") or "").strip()
    raw_name = str(selector.get("name") or "").strip()
    win_title_pat = (
        substitute_variables(raw_win_title, row_data or {}, strict=True)
        if raw_win_title
        else ""
    )
    name_pat = (
        substitute_variables(raw_name, row_data or {}, strict=True)
        if raw_name
        else ""
    )
    win_class_pat = str(selector.get("window_class") or "").strip()
    auto_id_pat = str(selector.get("automation_id") or "").strip()
    cls_pat = str(selector.get("class_name") or "").strip()
    ctrl_type_pat = str(selector.get("control_type") or "").strip()
    rel_x = int(selector.get("rel_x") or 0)
    rel_y = int(selector.get("rel_y") or 0)
    ctrl_rel_x = int(selector.get("ctrl_rel_x") or 0)
    ctrl_rel_y = int(selector.get("ctrl_rel_y") or 0)
    dpi_scale = int(selector.get("dpi_scale") or 100)
    raw_is_root = selector.get("is_root_anchor")

    # 1. Find candidate top-level windows
    visible_wins = list_visible_windows(exclude_self=exclude_self)
    matched_roots: list[tuple[int, str, str]] = []
    for hwnd, title in visible_wins:
        w_cls = get_class_name(hwnd)
        if win_title_pat and not _matches_pattern(title, win_title_pat, allow_substring=True):
            continue
        if win_class_pat and w_cls.lower() != win_class_pat.lower():
            continue
        matched_roots.append((hwnd, title, w_cls))

    if not matched_roots:
        raise LookupError(
            f'Target window not found for selector (window_title="{win_title_pat or "*"}", '
            f'window_class="{win_class_pat or "*"}").'
        )

    # 2. Search child controls within matched root windows
    candidates: list[UIElementInfo] = []
    for root_hwnd, root_title, root_cls in matched_roots:
        root_rect = get_window_rect(root_hwnd)
        if not root_rect:
            continue

        # Determine if this selector targets a child control vs the root window itself
        if raw_is_root is False:
            has_child_criteria = True
        elif raw_is_root is True:
            has_child_criteria = False
        else:
            has_child_criteria = bool(
                auto_id_pat
                or name_pat
                or (cls_pat and cls_pat.lower() != root_cls.strip().lower())
                or (ctrl_type_pat and ctrl_type_pat.lower() != "pane")
            )

        if has_child_criteria:
            children = _enumerate_child_hwnds(root_hwnd)
            for child in children:
                c_cls = get_class_name(child)
                c_type = infer_control_type(child, c_cls)
                c_id_int = user32.GetDlgCtrlID(child)
                c_id = str(c_id_int) if c_id_int > 0 else ""
                c_name = get_control_text(child).strip()

                if auto_id_pat and c_id != auto_id_pat:
                    continue
                if cls_pat and c_cls.lower() != cls_pat.lower():
                    continue
                if ctrl_type_pat and c_type.lower() != ctrl_type_pat.lower():
                    continue
                if name_pat and not _matches_pattern(c_name, name_pat, allow_substring=False):
                    continue

                c_rect = get_window_rect(child)
                if not c_rect or c_rect[2] <= 0 or c_rect[3] <= 0:
                    continue

                candidates.append(
                    UIElementInfo(
                        hwnd=child,
                        root_hwnd=root_hwnd,
                        window_title=root_title,
                        window_class=root_cls,
                        control_type=c_type,
                        automation_id=c_id,
                        name=c_name,
                        class_name=c_cls,
                        rect=c_rect,
                        rel_x=rel_x,
                        rel_y=rel_y,
                        ctrl_rel_x=ctrl_rel_x,
                        ctrl_rel_y=ctrl_rel_y,
                        dpi_scale=dpi_scale,
                        is_root_anchor=False,
                        supports_simulate=True,
                    )
                )
        else:
            # Root-window / relative-coordinate element
            candidates.append(
                UIElementInfo(
                    hwnd=root_hwnd,
                    root_hwnd=root_hwnd,
                    window_title=root_title,
                    window_class=root_cls,
                    control_type=ctrl_type_pat or infer_control_type(root_hwnd, root_cls),
                    automation_id=auto_id_pat,
                    name="",
                    class_name=cls_pat or root_cls,
                    rect=root_rect,
                    rel_x=rel_x,
                    rel_y=rel_y,
                    ctrl_rel_x=ctrl_rel_x,
                    ctrl_rel_y=ctrl_rel_y,
                    dpi_scale=dpi_scale,
                    is_root_anchor=True,
                    supports_simulate=True,
                )
            )

    if not candidates:
        raise LookupError(
            f'UI element not found inside window "{win_title_pat}" '
            f'(automation_id="{auto_id_pat}", name="{name_pat}", class="{cls_pat}").'
        )

    if len(candidates) > 1:
        idx = selector.get("index")
        if idx is not None and 0 <= int(idx) < len(candidates):
            return candidates[int(idx)]
        raise LookupError(
            f"Ambiguous UI selector: matched {len(candidates)} elements in "
            f'"{win_title_pat}". Refine Automation ID or Name to uniquely identify the target.'
        )

    return candidates[0]


def make_lparam(client_x: int, client_y: int) -> int:
    """Pack signed 16-bit client coordinates into Win32 LPARAM."""
    return ((int(client_y) & 0xFFFF) << 16) | (int(client_x) & 0xFFFF)


def _resolve_deepest_child_at_screen_pt(hwnd: int, screen_x: int, screen_y: int) -> int:
    """Drill down from a parent HWND to the deepest visible child window at (screen_x, screen_y)."""
    curr = hwnd
    for _ in range(16):
        pt = wintypes.POINT(int(screen_x), int(screen_y))
        if not user32.ScreenToClient(curr, ctypes.byref(pt)):
            break
        child = user32.ChildWindowFromPointEx(
            curr, pt, CWP_SKIPINVISIBLE | CWP_SKIPDISABLED
        )
        if not child or child == curr:
            break
        curr = int(child)
    return curr


def simulate_click_at_hwnd(
    hwnd: int,
    screen_x: int,
    screen_y: int,
    button: str = "left",
    clicks: int = 1,
    use_bm_click: bool = False,
    timeout_ms: int = 2000,
) -> tuple[bool, str]:
    """Perform a background Simulate Click without moving the hardware mouse cursor.

    Uses BM_CLICK for standard Win32 Button controls or client-coordinate
    WM_LBUTTONDOWN / WM_LBUTTONUP / WM_LBUTTONDBLCLK messages via PostMessageW.
    """
    if not hwnd or not user32.IsWindow(hwnd):
        return False, "Target window handle is no longer valid."

    # If hwnd is a container/root window, drill down to the deepest child at (screen_x, screen_y)
    target_hwnd = _resolve_deepest_child_at_screen_pt(hwnd, screen_x, screen_y) or hwnd

    btn = button.lower()
    if use_bm_click and btn == "left" and clicks == 1:
        res = ctypes.c_size_t(0)
        ok = user32.SendMessageTimeoutW(
            target_hwnd,
            BM_CLICK,
            0,
            0,
            SMTO_ABORTIFHUNG,
            timeout_ms,
            ctypes.byref(res),
        )
        if ok:
            return True, ""
        err = ctypes.get_last_error()
        # If BM_CLICK opened a modal dialog, SendMessageTimeoutW times out (ERROR_TIMEOUT=1460)
        # while the window is responsive (not hung). Do NOT double-click via fallback!
        if err == ERROR_TIMEOUT:
            if user32.IsHungAppWindow(target_hwnd):
                return False, "Target application window is not responding (hung)."
            return True, ""

    pt = wintypes.POINT(int(screen_x), int(screen_y))
    if not user32.ScreenToClient(target_hwnd, ctypes.byref(pt)):
        return False, "Could not convert screen coordinates to client coordinates."

    lparam = make_lparam(pt.x, pt.y)
    if btn == "right":
        down_msg, up_msg, dbl_msg, wparam = (
            WM_RBUTTONDOWN,
            WM_RBUTTONUP,
            WM_RBUTTONDBLCLK,
            MK_RBUTTON,
        )
    elif btn == "middle":
        down_msg, up_msg, dbl_msg, wparam = (
            WM_MBUTTONDOWN,
            WM_MBUTTONUP,
            WM_MBUTTONDBLCLK,
            MK_MBUTTON,
        )
    else:
        down_msg, up_msg, dbl_msg, wparam = (
            WM_LBUTTONDOWN,
            WM_LBUTTONUP,
            WM_LBUTTONDBLCLK,
            MK_LBUTTON,
        )

    total_clicks = max(1, int(clicks))
    for i in range(total_clicks):
        # On the second click of a double-click, send WM_*BUTTONDBLCLK per Win32 convention
        msg_to_send = dbl_msg if (i == 1 and total_clicks == 2) else down_msg
        if not user32.PostMessageW(target_hwnd, msg_to_send, wparam, lparam):
            err = ctypes.get_last_error()
            if err == 5:
                return (
                    False,
                    "Simulate Click blocked by Windows UIPI (target app is running as Administrator).",
                )
            return False, f"PostMessageW(down) failed with Win32 error {err}."
        time.sleep(0.02)
        if not user32.PostMessageW(target_hwnd, up_msg, 0, lparam):
            err = ctypes.get_last_error()
            return False, f"PostMessageW(up) failed with Win32 error {err}."

    return True, ""


def execute_selector_or_simulate_click(
    target_mode: str,
    selector: dict[str, Any] | None,
    x: int,
    y: int,
    button: str = "left",
    clicks: int = 1,
    click_method: str = "hardware",
    row_data: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """Unified handler for Click action supporting Coordinates/Selector and Hardware/Simulate."""
    from stepwise.services.input_win import click_at

    target_hwnd = 0
    use_bm_click = False
    target_x, target_y = int(x), int(y)

    if target_mode == "selector":
        if not selector:
            return False, "Target mode is set to UI Selector, but no selector is configured."
        try:
            elem = resolve_selector(selector, row_data=row_data, exclude_self=True)
        except Exception as e:
            return False, str(e)
        target_x, target_y = elem.target_point()
        target_hwnd = elem.hwnd
        use_bm_click = elem.control_type == "Button" and elem.hwnd != elem.root_hwnd

    if click_method == "simulate":
        if not target_hwnd:
            pt = wintypes.POINT(target_x, target_y)
            target_hwnd = int(user32.WindowFromPoint(pt) or 0)
            if not target_hwnd:
                return False, f"No window found at ({target_x}, {target_y}) for Simulate Click."
            cls_name = get_class_name(target_hwnd)
            use_bm_click = infer_control_type(target_hwnd, cls_name) == "Button"

        return simulate_click_at_hwnd(
            hwnd=target_hwnd,
            screen_x=target_x,
            screen_y=target_y,
            button=button,
            clicks=clicks,
            use_bm_click=use_bm_click,
        )

    if not click_at(target_x, target_y, button=button, clicks=clicks):
        return (
            False,
            "The mouse could not reach or click the target. Check the screen coordinates and application permissions.",
        )
    return True, ""
