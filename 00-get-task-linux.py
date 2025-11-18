import subprocess
import psutil
import re

def get_window_tasks():
    """Get all visible windows with their process names"""
    print("Window Tasks with Process Names:")
    print("-" * 50)
    
    try:
        # Method 1: Using wmctrl (most reliable for window titles)
        result = subprocess.run(['wmctrl', '-lp'], capture_output=True, text=True)
        
        if result.returncode == 0:
            windows = parse_wmctrl_output(result.stdout)
        else:
            # Method 2: Using xprop if wmctrl is not available
            windows = get_windows_with_xprop()
            
    except FileNotFoundError:
        # Method 3: Fallback using psutil and basic X window info
        windows = get_windows_fallback()
    
    for window in windows:
        print(f"Window: {window['title']}")
        print(f"Process: {window['process_name']} (PID: {window['pid']})")
        print(f"Window ID: {window['window_id']}")
        print("-" * 30)

def parse_wmctrl_output(output):
    """Parse wmctrl output to extract window information"""
    windows = []
    lines = output.strip().split('\n')
    
    for line in lines:
        # wmctrl -lp format: 0x0280000b  0 1234   hostname  Window Title
        match = re.match(r'^(0x[0-9a-f]+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(.*)$', line)
        if match:
            window_id, desktop, pid, host, title = match.groups()
            
            if title and title != "N/A":  # Filter out empty/placeholder titles
                try:
                    process = psutil.Process(int(pid))
                    process_name = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
                    process_name = "Unknown"
                
                windows.append({
                    'window_id': window_id,
                    'pid': int(pid),
                    'title': title,
                    'process_name': process_name
                })
    
    return windows

def get_windows_with_xprop():
    """Alternative method using xprop to get window information"""
    windows = []
    
    try:
        # Get list of window IDs using xwininfo
        result = subprocess.run(['xwininfo', '-root', '-tree'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            # Parse window IDs from xwininfo output
            window_ids = re.findall(r'0x[0-9a-f]+', result.stdout)
            
            for window_id in window_ids[:10]:  # Limit to first 10 windows for performance
                try:
                    # Get window properties
                    xprop_result = subprocess.run(['xprop', '-id', window_id], 
                                                 capture_output=True, text=True)
                    
                    if xprop_result.returncode == 0:
                        window_info = parse_xprop_output(xprop_result.stdout, window_id)
                        if window_info and window_info['title']:
                            windows.append(window_info)
                except:
                    continue
                    
    except FileNotFoundError:
        pass
        
    return windows

def parse_xprop_output(output, window_id):
    """Parse xprop output to extract window information"""
    lines = output.split('\n')
    title = ""
    pid = None
    
    for line in lines:
        if '_NET_WM_NAME(' in line:
            # Extract window title
            match = re.search(r'= "([^"]*)"', line)
            if match:
                title = match.group(1)
        elif '_NET_WM_PID(' in line:
            # Extract process ID
            match = re.search(r'= (\d+)', line)
            if match:
                pid = int(match.group(1))
    
    if pid:
        try:
            process = psutil.Process(pid)
            process_name = process.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            process_name = "Unknown"
    else:
        process_name = "Unknown"
        pid = 0
    
    return {
        'window_id': window_id,
        'pid': pid,
        'title': title,
        'process_name': process_name
    }

def get_windows_fallback():
    """Fallback method using psutil to get running processes"""
    windows = []
    
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            windows.append({
                'window_id': f"0x{proc.info['pid']:08x}",
                'pid': proc.info['pid'],
                'title': proc.info['name'],
                'process_name': proc.info['name']
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return windows

if __name__ == "__main__":
    get_window_tasks()
