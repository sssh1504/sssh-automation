"""執行後輸出所有 Chrome 視窗標題，寫入 diagnose.txt。"""
import ctypes, ctypes.wintypes

user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.POINTER(ctypes.c_int))

lines = []

def cb(hwnd, _):
    if user32.IsWindowVisible(hwnd):
        buf = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, buf, 512)
        t = buf.value
        if "Chrome" in t or "sssh" in t or "松山" in t or "首頁" in t:
            lines.append(f"HWND={hwnd}  title={t!r}")
    return True

user32.EnumWindows(EnumWindowsProc(cb), None)

with open("diagnose.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) if lines else "（找不到 Chrome 視窗）")

print("完成，請查看 diagnose.txt")
