import win32gui
import win32process
import psutil

def window_enum_handler(hwnd, windows):
    """Callback function for enumerating windows"""
    if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
        windows.append(hwnd)

def get_window_tasks():
    """Get all visible windows with their process names"""
    windows = []
    win32gui.EnumWindows(window_enum_handler, windows)
    
    print("Window Tasks with Process Names:")
    print("-" * 50)
    
    for hwnd in windows:
        title = win32gui.GetWindowText(hwnd)
        try:
            # Get process ID
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            # Get process name
            process = psutil.Process(pid)
            process_name = process.name()
            
            print(f"Window: {title}")
            print(f"Process: {process_name} (PID: {pid})")
            print(f"Handle: {hwnd}")
            print("-" * 30)
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"Window: {title}")
            print(f"PID: {pid} (Process details unavailable)")
            print("-" * 30)

if __name__ == "__main__":
    get_window_tasks()
