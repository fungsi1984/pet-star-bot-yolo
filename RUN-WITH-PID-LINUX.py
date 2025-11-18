import os
import random
from time import sleep
import subprocess
import psutil
import re

import cv2 as cv
import numpy as np
from PIL import Image
import pyautogui

# ====================================================================
# WINDOW FINDER UTILITIES
# ====================================================================
def find_window_by_pid(pid):
    """Find window by process ID"""
    try:
        result = subprocess.run(['wmctrl', '-lp'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    window_id, desktop, window_pid, host = parts[0:4]
                    title = ' '.join(parts[4:])
                    
                    if int(window_pid) == pid:
                        return {
                            'window_id': window_id,
                            'pid': pid,
                            'title': title,
                            'process_name': psutil.Process(pid).name()
                        }
    except:
        pass
    return None

def find_window_by_process_name(process_name):
    """Find windows by process name"""
    windows = []
    try:
        result = subprocess.run(['wmctrl', '-lp'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    window_id, desktop, pid, host = parts[0:4]
                    title = ' '.join(parts[4:])
                    
                    try:
                        process = psutil.Process(int(pid))
                        proc_name = process.name()
                        if process_name.lower() in proc_name.lower():
                            windows.append({
                                'window_id': window_id,
                                'pid': pid,
                                'title': title,
                                'process_name': proc_name
                            })
                    except:
                        continue
    except:
        pass
    return windows

def list_all_windows():
    """List all available windows"""
    print("Available Windows:")
    print("-" * 50)
    try:
        result = subprocess.run(['wmctrl', '-lp'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    window_id, desktop, pid, host = parts[0:4]
                    title = ' '.join(parts[4:])
                    
                    try:
                        process_name = psutil.Process(int(pid)).name()
                    except:
                        process_name = "Unknown"
                    
                    print(f"PID: {pid} | Process: {process_name} | Title: {title}")
    except FileNotFoundError:
        print("wmctrl not installed. Install with: sudo apt install wmctrl")

# ====================================================================
# AUTO-CLICKER FUNCTION
# ====================================================================
def click_at_coordinate(x, y):
    """Performs a left mouse click at the specified screen coordinates."""
    x = int(x)
    y = int(y)
    
    pyautogui.moveTo(x, y)
    sleep(random.uniform(0.01, 0.05))
    pyautogui.click(x, y)

# ====================================================================
# WINDOW CAPTURE (PID-BASED)
# ====================================================================
class WindowCapture:
    def __init__(self, window_name=None, process_name=None, pid=None):
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0
        self.window_title = ""
        
        # Priority 1: Use PID if provided
        if pid:
            window_info = find_window_by_pid(pid)
            if window_info:
                self.window_title = window_info['title']
                self.window_id = window_info['window_id']
                print(f"Found window by PID {pid}: '{self.window_title}'")
            else:
                raise Exception(f"No window found for PID: {pid}")
        
        # Priority 2: Use process name if provided
        elif process_name:
            windows = find_window_by_process_name(process_name)
            if windows:
                self.window_title = windows[0]['title']
                self.window_id = windows[0]['window_id']
                print(f"Found window by process '{process_name}': '{self.window_title}'")
            else:
                raise Exception(f"No window found for process: {process_name}")
        
        # Priority 3: Use window title
        elif window_name:
            self.window_title = window_name
            try:
                result = subprocess.run(['xdotool', 'search', '--name', window_name], 
                                      capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    self.window_id = result.stdout.strip().split('\n')[0]
                    print(f"Found window by title: '{window_name}'")
                else:
                    raise Exception(f"Window not found: {window_name}")
            except Exception as e:
                raise Exception(f"Error finding window: {e}")
        
        else:
            raise Exception("No window identifier provided")
        
        # Get window geometry
        self._get_window_geometry()

    def _get_window_geometry(self):
        """Get window position and size"""
        try:
            geom = subprocess.run(['xwininfo', '-id', self.window_id], 
                                capture_output=True, text=True)
            if geom.returncode == 0:
                lines = geom.stdout.split('\n')
                for line in lines:
                    if 'Absolute upper-left X:' in line:
                        self.x = int(line.split(':')[1].strip())
                    elif 'Absolute upper-left Y:' in line:
                        self.y = int(line.split(':')[1].strip())
                    elif 'Width:' in line:
                        self.w = int(line.split(':')[1].strip())
                    elif 'Height:' in line:
                        self.h = int(line.split(':')[1].strip())
                
                print(f"Window geometry: {self.w}x{self.h} at ({self.x}, {self.y})")
            else:
                raise Exception("Failed to get window geometry")
                
        except Exception as e:
            raise Exception(f"Error getting window geometry: {e}")

    def get_screenshot(self):
        """Capture only the game window"""
        try:
            screenshot = pyautogui.screenshot(region=(self.x, self.y, self.w, self.h))
            img = cv.cvtColor(np.array(screenshot), cv.COLOR_RGB2BGR)
            return img
        except Exception as e:
            print(f"Screenshot error: {e}")
            return np.zeros((self.h, self.w, 3), dtype=np.uint8)

    def get_screen_position(self, pos):
        """Convert window coordinates to screen coordinates"""
        return (self.x + pos[0], self.y + pos[1])

    def get_window_size(self):
        return (self.w, self.h)

# ====================================================================
# IMAGE PROCESSOR (YOLO)
# ====================================================================
class ImageProcessor:
    def __init__(self, img_size, cfg_file, weights_file):
        np.random.seed(42)
        self.net = cv.dnn.readNetFromDarknet(cfg_file, weights_file)
        self.net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
        self.ln = self.net.getLayerNames()
        self.ln = [self.ln[i - 1] for i in self.net.getUnconnectedOutLayers()]
        self.W = img_size[0]
        self.H = img_size[1]

        with open("yolov4-tiny/obj.names", "r") as file:
            lines = file.readlines()
        self.classes = {i: line.strip() for i, line in enumerate(lines)}

        self.colors = [
            (0, 0, 255), (0, 255, 0), (255, 0, 0),
            (255, 255, 0), (255, 0, 255), (0, 255, 255),
        ]

    def proccess_image(self, img):
        # Resize if needed
        if img.shape[1] != self.W or img.shape[0] != self.H:
            img = cv.resize(img, (self.W, self.H))
            
        blob = cv.dnn.blobFromImage(img, 1/255.0, (416, 416), swapRB=True, crop=False)
        self.net.setInput(blob)
        outputs = self.net.forward(self.ln)
        outputs = np.vstack(outputs)

        coordinates = self.get_coordinates(outputs, 0.5)
        self.draw_identified_objects(img, coordinates)
        return coordinates

    def get_coordinates(self, outputs, conf):
        boxes, confidences, classIDs = [], [], []

        for output in outputs:
            scores = output[5:]
            classID = np.argmax(scores)
            confidence = scores[classID]
            if confidence > conf:
                x, y, w, h = output[:4] * np.array([self.W, self.H, self.W, self.H])
                p0 = int(x - w//2), int(y - h//2)
                boxes.append([*p0, int(w), int(h)])
                confidences.append(float(confidence))
                classIDs.append(classID)

        indices = cv.dnn.NMSBoxes(boxes, confidences, conf, conf-0.1)
        if len(indices) == 0:
            return []

        coordinates = []
        for i in indices.flatten():
            x, y, w, h = boxes[i]
            coordinates.append({
                "x": x, "y": y, "w": w, "h": h,
                "class": classIDs[i],
                "class_name": self.classes[classIDs[i]]
            })
        return coordinates

    def draw_identified_objects(self, img, coordinates):
        for coord in coordinates:
            x, y, w, h = coord["x"], coord["y"], coord["w"], coord["h"]
            color = self.colors[coord["class"] % len(self.colors)]
            
            cv.rectangle(img, (x, y), (x+w, y+h), color, 2)
            cv.putText(img, coord["class_name"], (x, y-10), 
                      cv.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        cv.imshow(f"Game Window - Press 'q' to quit", img)

# ====================================================================
# MAIN APPLICATION LOOP
# ====================================================================
cfg_file_name = "./yolov4-tiny/yolov4-tiny-custom.cfg"
weights_file_name = "yolov4-tiny-custom_last.weights"

try:
    print("=" * 60)
    print("PET STAR BOT - LINUX VERSION (PID-BASED)")
    print("=" * 60)
    
    # List available windows first
    list_all_windows()
    print("-" * 60)
    
    # Try different methods to find the window
    print("Attempting to find game window...")
    
    # METHOD 1: Use PID (most reliable)
    wincap = None
    try:
        print("Trying PID-based detection...")
        wincap = WindowCapture(pid=13503)  # Use the PID you found
    except Exception as e:
        print(f"PID method failed: {e}")
        
        # METHOD 2: Use process name
        try:
            print("Trying process name detection...")
            wincap = WindowCapture(process_name="PetStarClient.exe")
        except Exception as e:
            print(f"Process name method failed: {e}")
            
            # METHOD 3: Use window title
            try:
                print("Trying window title detection...")
                wincap = WindowCapture(window_name="PetStar")
            except Exception as e:
                print(f"Window title method failed: {e}")
                raise Exception("Could not find game window using any method")
    
    improc = ImageProcessor(wincap.get_window_size(), cfg_file_name, weights_file_name)
    
    print("Bot started successfully!")
    print("Press 'q' in the OpenCV window to quit")
    print("=" * 60)
    
    while True:
        # Capture screenshot
        screenshot = wincap.get_screenshot()
        
        if screenshot is None or screenshot.size == 0:
            print("Screenshot failed, retrying...")
            sleep(1)
            continue

        # Process image and detect objects
        coordinates = improc.proccess_image(screenshot)
        
        # Check for quit key
        if cv.waitKey(1) & 0xFF == ord('q'):
            print("Quit signal received...")
            break

        # Click on first detected object
        for coordinate in coordinates:
            print(f"Detected: {coordinate['class_name']} at ({coordinate['x']}, {coordinate['y']})")
            
            # Calculate center of detected object
            center_x = coordinate["x"] + coordinate["w"] // 2
            center_y = coordinate["y"] + coordinate["h"] // 2
            
            # Convert to screen coordinates
            screen_x, screen_y = wincap.get_screen_position((center_x, center_y))
            
            print(f"Clicking at screen coordinates: ({screen_x}, {screen_y})")
            click_at_coordinate(screen_x, screen_y)
            break  # Only click first object per frame
        
        # Small delay to prevent spamming
        sleep(0.5)

    cv.destroyAllWindows()
    print("Bot stopped successfully!")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
