import pyautogui
import cv2
import numpy as np
import time
import random
from PIL import ImageGrab

pyautogui.FAILSAFE = True

TEMPLATE_PATH = "C:\\rsbot\\tree_template.png"
THRESHOLD = 0.6  # match confidence, lower = more lenient

import pyautogui
import cv2
import numpy as np
import time
import random
import json
from PIL import ImageGrab

pyautogui.FAILSAFE = True

TEMPLATE_PATH = "C:\\rsbot\\tree_template.png"
WAYPOINTS_PATH = "C:\\rsbot\\waypoints.json"
THRESHOLD = 0.6
WAYPOINT_WAIT = 3  # seconds to walk between waypoints

def screenshot():
    img = ImageGrab.grab()
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def find_tree():
    template = cv2.imread(TEMPLATE_PATH)
    screen = screenshot()
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    print(f"[BOT] Tree match confidence: {max_val:.2f}")
    if max_val >= THRESHOLD:
        h, w = template.shape[:2]
        cx = max_loc[0] + w // 2
        cy = max_loc[1] + h // 2
        return (cx, cy)
    return None

def click(x, y, variance=5):
    x += random.randint(-variance, variance)
    y += random.randint(-variance, variance)
    pyautogui.moveTo(x, y, duration=random.uniform(0.2, 0.5))
    pyautogui.click()

def wait(base, variance=0.5):
    time.sleep(base + random.uniform(-variance, variance))

def load_waypoints():
    with open(WAYPOINTS_PATH, "r") as f:
        return json.load(f)

def walk_to(x, y):
    print(f"[BOT] Walking to waypoint ({x}, {y})...")
    click(x, y, variance=8)
    wait(WAYPOINT_WAIT, 1)

# Main loop
print("[BOT] Loading waypoints...")
waypoints = load_waypoints()
print(f"[BOT] Loaded {len(waypoints)} waypoints.")
print("[BOT] Starting! Move mouse to top-left corner to stop.")

trees_chopped = 0
waypoint_index = 0

while True:
    # Check for a tree first
    tree = find_tree()
    if tree:
        print(f"[BOT] Tree spotted! Chopping... ({trees_chopped + 1} total)")
        click(*tree)
        trees_chopped += 1
        wait(6, 2)
    else:
        # No tree — walk to next waypoint
        wx, wy = waypoints[waypoint_index]
        walk_to(wx, wy)
        waypoint_index = (waypoint_index + 1) % len(waypoints)  # loop back to start