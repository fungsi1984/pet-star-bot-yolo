import os
import random
from time import sleep

import cv2 as cv
import numpy as np
import win32api  # Used for mouse clicking
import win32con
import win32gui
import win32ui
from PIL import Image


# ====================================================================
# AUTO-CLICKER FUNCTION
# ====================================================================
def click_at_coordinate(x, y):
    """Performs a left mouse click at the specified screen coordinates."""
    # Convert to integer coordinates for the API call
    x = int(x)
    y = int(y)

    # 1. Move the mouse to the desired position
    win32api.SetCursorPos((x, y))

    # 2. Press the left button down
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
    # A short, random delay simulates human click speed and prevents missed inputs
    sleep(random.uniform(0.01, 0.05))

    # 3. Release the left button
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)


class WindowCapture:
    w = 0
    h = 0
    hwnd = None
    cropped_x = 0
    cropped_y = 0

    def __init__(self, window_name):
        self.hwnd = win32gui.FindWindow(None, window_name)
        if not self.hwnd:
            raise Exception("Window not found: {}".format(window_name))

        window_rect = win32gui.GetWindowRect(self.hwnd)
        self.w = window_rect[2] - window_rect[0]
        self.h = window_rect[3] - window_rect[1]

        # Calculate border and title bar to get client area coordinates
        border_pixels = 8
        titlebar_pixels = 30
        self.w = self.w - (border_pixels * 2)
        self.h = self.h - titlebar_pixels - border_pixels
        self.cropped_x = border_pixels
        self.cropped_y = titlebar_pixels

    def get_screenshot(self):
        wDC = win32gui.GetWindowDC(self.hwnd)
        dcObj = win32ui.CreateDCFromHandle(wDC)
        cDC = dcObj.CreateCompatibleDC()
        dataBitMap = win32ui.CreateBitmap()
        dataBitMap.CreateCompatibleBitmap(dcObj, self.w, self.h)
        cDC.SelectObject(dataBitMap)
        cDC.BitBlt(
            (0, 0),
            (self.w, self.h),
            dcObj,
            (self.cropped_x, self.cropped_y),
            win32con.SRCCOPY,
        )

        signedIntsArray = dataBitMap.GetBitmapBits(True)
        img = np.frombuffer(signedIntsArray, dtype="uint8")
        img.shape = (self.h, self.w, 4)

        dcObj.DeleteDC()
        cDC.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, wDC)
        win32gui.DeleteObject(dataBitMap.GetHandle())

        img = img[..., :3]
        img = np.ascontiguousarray(img)

        return img

    def get_screen_position(self, pos):
        """Translate a pixel position from the client area (captured area) to
        absolute screen coordinates required for win32api."""
        # Get the screen position of the window's top-left corner
        window_rect = win32gui.GetWindowRect(self.hwnd)
        x_on_screen = window_rect[0] + self.cropped_x
        y_on_screen = window_rect[1] + self.cropped_y

        # Add the relative position (pos) to the screen position
        return (x_on_screen + pos[0], y_on_screen + pos[1])

    def generate_image_dataset(self):
        if not os.path.exists("images"):
            os.mkdir("images")
        while True:
            img = self.get_screenshot()
            im = Image.fromarray(img[..., [2, 1, 0]])
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

        # If you plan to utilize more than six classes, please include additional colors in this list.
        self.colors = [
            (0, 0, 255),
            (0, 255, 0),
            (255, 0, 0),
            (255, 255, 0),
            (255, 0, 255),
            (0, 255, 255),
        ]

    def proccess_image(self, img):
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

window_name = "PetStar£¨V1.16.52£©"
cfg_file_name = "./yolov4-tiny/yolov4-tiny-custom.cfg"
weights_file_name = "yolov4-tiny-custom_last.weights"

wincap = WindowCapture(window_name)
improc = ImageProcessor(wincap.get_window_size(), cfg_file_name, weights_file_name)

while True:
    ss = wincap.get_screenshot()

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

        # 3. FIX: Set the target window as the foreground window before clicking
        # This prevents the pywintypes.error by ensuring the target app has focus.
        win32gui.SetForegroundWindow(wincap.hwnd)
        sleep(0.01)  # Small delay to ensure the OS registers the foreground change

        print(
            f"Clicking on {coordinate['class_name']} at screen coords: ({center_x_absolute}, {center_y_absolute})"
        )

        # 4. Perform the click
        click_at_coordinate(center_x_absolute, center_y_absolute)

        # Break after the first object is clicked to prevent over-clicking
        # or misclicks from overlapping bounding boxes.
        break

    print()

    # Consider adding a sleep delay here if the loop runs too fast for the game/application
    sleep(1)

print("Finished.")
