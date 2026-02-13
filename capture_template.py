import pyautogui
import time
from PIL import ImageGrab

print("Hover over the CENTER of the tree trunk and hold still...")
time.sleep(3)

x, y = pyautogui.position()
print(f"Capturing around position: {x}, {y}")

# Grab a small 60x60 region around your mouse
img = ImageGrab.grab(bbox=(x-30, y-30, x+30, y+30))
img.save("C:\\rsbot\\tree_template.png")
print("Done! Saved tree_template.png")