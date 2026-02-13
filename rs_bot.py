import pyautogui
import time
import random
from PIL import ImageGrab, Image
import numpy as np

# Safety: move mouse to corner to abort
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

class RSBot:
    def __init__(self, game_region=None):
        """
        game_region: (x, y, width, height) of your game window
        Leave None to use full screen
        """
        self.region = game_region
        self.running = False

    def screenshot(self):
        """Capture the game window"""
        if self.region:
            x, y, w, h = self.region
            return ImageGrab.grab(bbox=(x, y, x+w, y+h))
        return ImageGrab.grab()

    def click(self, x, y, offset=5):
        """Click with small random offset to look human"""
        rx = x + random.randint(-offset, offset)
        ry = y + random.randint(-offset, offset)
        pyautogui.moveTo(rx, ry, duration=random.uniform(0.2, 0.5))
        pyautogui.click()

    def wait(self, base, variance=0.5):
        """Sleep for base ± variance seconds"""
        time.sleep(base + random.uniform(-variance, variance))

    def find_color(self, target_rgb, tolerance=20):
        """Find pixel(s) matching a color in the game window"""
        img = np.array(self.screenshot())
        r, g, b = target_rgb
        mask = (
            (np.abs(img[:,:,0].astype(int) - r) < tolerance) &
            (np.abs(img[:,:,1].astype(int) - g) < tolerance) &
            (np.abs(img[:,:,2].astype(int) - b) < tolerance)
        )
        ys, xs = np.where(mask)
        if len(xs) == 0:
            return None
        # Return center of matched region
        cx = int(np.mean(xs))
        cy = int(np.mean(ys))
        if self.region:
            cx += self.region[0]
            cy += self.region[1]
        return (cx, cy)