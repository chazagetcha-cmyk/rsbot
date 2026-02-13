import pyautogui
import time
import json

waypoints = []

print("Walk your route in game and press F8 to drop a waypoint at each spot.")
print("Press F9 when done to save.")
print("Starting in 3 seconds...")
time.sleep(3)

from pynput import keyboard

def on_press(key):
    try:
        if key == keyboard.Key.f8:
            x, y = pyautogui.position()
            waypoints.append((x, y))
            print(f"Waypoint {len(waypoints)} saved at ({x}, {y})")
        elif key == keyboard.Key.f9:
            with open("C:\\rsbot\\waypoints.json", "w") as f:
                json.dump(waypoints, f)
            print(f"Saved {len(waypoints)} waypoints to waypoints.json!")
            return False
    except Exception as e:
        print(e)

with keyboard.Listener(on_press=on_press) as listener:
    listener.join()