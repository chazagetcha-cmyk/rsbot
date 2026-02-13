import pyautogui, time

# Run this, hover over a rock/tree/fishing spot,
# and it will print the color under your cursor
print("Hover over the object you want to detect...")
time.sleep(3)

x, y = pyautogui.position()
screenshot = pyautogui.screenshot()
color = screenshot.getpixel((x, y))
print(f"Position: ({x}, {y})  |  RGB: {color}")
# Example output: Position: (743, 412)  |  RGB: (80, 60, 40)