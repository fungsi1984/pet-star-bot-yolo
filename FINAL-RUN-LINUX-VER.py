import os
import random
from time import sleep

import cv2 as cv
import numpy as np
from PIL import Image
import pyautogui
from Xlib import display, X
import subprocess

# ====================================================================
# AUTO-CLICKER FUNCTION (Linux version)
# ====================================================================
def click_at_coordinate(x, y):
    """Performs a left mouse click at the specified screen coordinates."""
    # Convert to integer coordinates
    x = int(x)
    y = int(y)
    
    # Use pyautogui for mouse control on Linux
    pyautogui.moveTo(x, y)
    sleep(random.uniform(0.01, 0.05))
    pyautogui.click(x, y)


class WindowCapture:
    w = 0
    h = 0
    window_id = None
    cropped_x = 0
    cropped_y = 0

    def __init__(self, window_name):
        # Find window by name using xprop
        try:
            result = subprocess.check_output(
                ['xprop', '-root', '_NET_CLIENT_LIST_STACKING']
            ).decode()
            window_ids = [
                line.split('# ')[1] 
                for line in result.split('\n') 
                if '#' in line
            ][0].split(', ')
            
            for wid in window_ids:
                wid = wid.strip()
                if not wid.startswith('0x'):
                    continue
                try:
                    name_result = subprocess.check_output(
                        ['xprop', '-id', wid, 'WM_NAME']
                    ).decode()
                    if window_name in name_result:
                        self.window_id = wid
                        break
                except:
                    continue
                    
            if not self.window_id:
                raise Exception("Window not found: {}".format(window_name))
                
        except Exception as e:
            raise Exception("Error finding window: {}".format(e))

        # Get window geometry
        try:
            geom_result = subprocess.check_output(
                ['xwininfo', '-id', self.window_id]
            ).decode()
            
            lines = geom_result.split('\n')
            for line in lines:
                if 'Width:' in line:
                    self.w = int(line.split(':')[1].strip())
                elif 'Height:' in line:
                    self.h = int(line.split(':')[1].strip())
                elif 'Absolute upper-left X:' in line:
                    self.cropped_x = int(line.split(':')[1].strip())
                elif 'Absolute upper-left Y:' in line:
                    self.cropped_y = int(line.split(':')[1].strip())
                    
        except Exception as e:
            raise Exception("Error getting window geometry: {}".format(e))

    def get_screenshot(self):
        """Capture window using pure Python/pyautogui approach"""
        try:
            # Capture the entire screen
            screenshot = pyautogui.screenshot()
            img = cv.cvtColor(np.array(screenshot), cv.COLOR_RGB2BGR)
            
            # Crop to the window region
            if (self.cropped_x >= 0 and self.cropped_y >= 0 and 
                self.cropped_x + self.w <= img.shape[1] and 
                self.cropped_y + self.h <= img.shape[0]):
                img = img[self.cropped_y:self.cropped_y + self.h, 
                         self.cropped_x:self.cropped_x + self.w]
            else:
                print(f"Warning: Window coordinates out of bounds. Using full screenshot.")
                
            return img
            
        except Exception as e:
            print(f"Screenshot error: {e}")
            # Fallback: return black image
            return np.zeros((self.h, self.w, 3), dtype=np.uint8)

    def get_screen_position(self, pos):
        """Translate a pixel position from the client area to absolute screen coordinates."""
        return (self.cropped_x + pos[0], self.cropped_y + pos[1])

    def generate_image_dataset(self):
        if not os.path.exists("images"):
            os.mkdir("images")
        while True:
            img = self.get_screenshot()
            im = Image.fromarray(cv.cvtColor(img, cv.COLOR_BGR2RGB))
            im.save(f"./images/img_{len(os.listdir('images'))}.jpeg")
            sleep(1)

    def get_window_size(self):
        return (self.w, self.h)


class ImageProcessor:
    W = 0
    H = 0
    net = None
    ln = None
    classes = {}
    colors = []

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
        for i, line in enumerate(lines):
            self.classes[i] = line.strip()

        self.colors = [
            (0, 0, 255),
            (0, 255, 0),
            (255, 0, 0),
            (255, 255, 0),
            (255, 0, 255),
            (0, 255, 255),
        ]

    def proccess_image(self, img):
        # Resize image to expected size if needed
        if img.shape[1] != self.W or img.shape[0] != self.H:
            img = cv.resize(img, (self.W, self.H))
            
        blob = cv.dnn.blobFromImage(img, 1 / 255.0, (416, 416), swapRB=True, crop=False)
        self.net.setInput(blob)
        outputs = self.net.forward(self.ln)
        outputs = np.vstack(outputs)

        coordinates = self.get_coordinates(outputs, 0.5)

        self.draw_identified_objects(img, coordinates)

        return coordinates

    def get_coordinates(self, outputs, conf):
        boxes = []
        confidences = []
        classIDs = []

        for output in outputs:
            scores = output[5:]

            classID = np.argmax(scores)
            confidence = scores[classID]
            if confidence > conf:
                x, y, w, h = output[:4] * np.array([self.W, self.H, self.W, self.H])
                p0 = int(x - w // 2), int(y - h // 2)
                boxes.append([*p0, int(w), int(h)])
                confidences.append(float(confidence))
                classIDs.append(classID)

        indices = cv.dnn.NMSBoxes(boxes, confidences, conf, conf - 0.1)

        if len(indices) == 0:
            return []

        coordinates = []
        for i in indices.flatten():
            (x, y) = (boxes[i][0], boxes[i][1])
            (w, h) = (boxes[i][2], boxes[i][3])

            coordinates.append(
                {
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "class": classIDs[i],
                    "class_name": self.classes[classIDs[i]],
                }
            )
        return coordinates

    def draw_identified_objects(self, img, coordinates):
        for coordinate in coordinates:
            x = coordinate["x"]
            y = coordinate["y"]
            w = coordinate["w"]
            h = coordinate["h"]
            classID = coordinate["class"]

            color = self.colors[classID]

            cv.rectangle(img, (x, y), (x + w, y + h), color, 2)
            cv.putText(
                img,
                self.classes[classID],
                (x, y - 10),
                cv.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )
        cv.imshow("window", img)


# ====================================================================
# MAIN APPLICATION LOOP
# ====================================================================

window_name = "PetStar"  # Adjust window name for Linux
cfg_file_name = "./yolov4-tiny/yolov4-tiny-custom.cfg"
weights_file_name = "yolov4-tiny-custom_last.weights"

try:
    wincap = WindowCapture(window_name)
    print(f"Window found: {wincap.w}x{wincap.h} at ({wincap.cropped_x}, {wincap.cropped_y})")
    
    improc = ImageProcessor(wincap.get_window_size(), cfg_file_name, weights_file_name)

    while True:
        ss = wincap.get_screenshot()
        
        # Check if we got a valid screenshot
        if ss is None or ss.size == 0:
            print("Invalid screenshot, skipping...")
            sleep(1)
            continue

        if cv.waitKey(1) == ord("q"):
            cv.destroyAllWindows()
            break

        coordinates = improc.proccess_image(ss)

        for coordinate in coordinates:
            print(f"Detected: {coordinate}")

            # 1. Find the center of the detected object (relative to the captured area)
            center_x_relative = coordinate["x"] + (coordinate["w"] // 2)
            center_y_relative = coordinate["y"] + (coordinate["h"] // 2)

            # 2. Translate relative window coordinates to absolute screen coordinates
            center_x_absolute, center_y_absolute = wincap.get_screen_position(
                (center_x_relative, center_y_relative)
            )

            print(
                f"Clicking on {coordinate['class_name']} at screen coords: ({center_x_absolute}, {center_y_absolute})"
            )

            # 3. Perform the click
            click_at_coordinate(center_x_absolute, center_y_absolute)

            # Break after the first object is clicked
            break

        print()
        sleep(1)

    print("Finished.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
