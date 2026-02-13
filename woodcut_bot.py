import pyautogui
import time
import random
from PIL import ImageGrab
import numpy as np

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

class WoodcuttingBot:
    TREE_COLOR = (76, 57, 32)  # your tree trunk color
    TOLERANCE  = 30

    def __init__(self):
        self.running = False

    def screenshot(self):
        return ImageGrab.grab()

    def click(self, x, y):
        x += random.randint(-5, 5)
        y += random.randint(-5, 5)
        pyautogui.moveTo(x, y, duration=random.uniform(0.2, 0.5))
        pyautogui.click()

    def wait(self, base, variance=0.5):
        time.sleep(base + random.uniform(-variance, variance))

    def find_tree(self):
        img = np.array(self.screenshot())
        r, g, b = self.TREE_COLOR
        mask = (
            (np.abs(img[:,:,0].astype(int) - r) < self.TOLERANCE) &
            (np.abs(img[:,:,1].astype(int) - g) < self.TOLERANCE) &
            (np.abs(img[:,:,2].astype(int) - b) < self.TOLERANCE)
        )
        ys, xs = np.where(mask)
        if len(xs) == 0:
            return None
        return (int(np.mean(xs)), int(np.mean(ys)))

    def run(self):
        self.running = True
        print("[BOT] Woodcutting started! Move mouse to top-left corner to stop.")
        while self.running:
            tree = self.find_tree()
            if tree:
                print(f"[BOT] Found tree at {tree}, chopping...")
                self.click(*tree)
                self.wait(6, 2)
            else:
                print("[BOT] No tree found, waiting...")
                self.wait(2)

if __name__ == "__main__":
    bot = WoodcuttingBot()
    bot.run()