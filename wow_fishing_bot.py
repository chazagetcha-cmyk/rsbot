from rs_bot import RSBot
import pyautogui
import time
import random
import numpy as np
from PIL import ImageGrab


class WoWFishingBot(RSBot):
    """
    World of Warcraft pixel fishing bot.

    CALIBRATION STEPS:
      1. Run color_sampler.py, hover over the bobber's red/orange feather
         during a test cast, and copy the printed RGB into BOBBER_COLOR.
      2. Set CAST_KEY to the keybind you use for your Fishing ability.
      3. Set LURE_KEY to an action bar keybind for a macro that applies
         your lure to the fishing pole, e.g.:
           /use Nightcrawlers
           /use 16  (equip main-hand)
         Place the macro on your action bar and bind it to LURE_KEY.
      4. Adjust SPLASH_THRESHOLD if you get false positives (lower) or
         missed bites (raise). Log the raw 'change' value printed each
         poll iteration to find your sweet spot.

    ABORT: Move the mouse to the top-left corner of the screen at any time.
    """

    # --- Tune these to your game window and keybinds ---

    CAST_KEY           = '1'           # keybind that casts your Fishing ability
    BOBBER_COLOR       = (200, 80, 40) # red/orange feather; calibrate with color_sampler.py
    BOBBER_TOLERANCE   = 25            # per-channel tolerance for color matching (0-255)

    SPLASH_THRESHOLD   = 15            # mean pixel-change to count as a splash/bite
    BOBBER_REGION_HALF = 40            # half-size (px) of the crop box around the bobber

    CAST_SETTLE_TIME   = 2.5           # seconds after cast for bobber to land on water
    BITE_TIMEOUT       = 25            # seconds to watch before giving up and recasting
    POLL_INTERVAL      = 0.15          # seconds between frame captures while watching
    POST_LOOT_WAIT     = 1.5           # seconds to wait after looting before next cast
    MAX_CAST_ATTEMPTS  = 3             # times to retry find_bobber if not found after cast

    LURE_KEY           = '2'           # keybind that applies lure to fishing pole
    LURE_DURATION      = 570           # seconds between lure applications (buff = 600 s;
                                       # apply 30 s early to avoid gap)
    LURE_APPLY_WAIT    = 3.0           # seconds to wait after applying lure (animation + GCD)

    # -------------------------------------------------------

    def cast_line(self):
        """Press the cast keybind and wait for the bobber to land."""
        pyautogui.press(self.CAST_KEY)
        self.wait(self.CAST_SETTLE_TIME, 0.5)

    def find_bobber(self):
        """Return screen coordinates (x, y) of the bobber, or None if not found."""
        return self.find_color(self.BOBBER_COLOR, tolerance=self.BOBBER_TOLERANCE)

    def get_bobber_region(self, bobber_pos):
        """Return a PIL-compatible bbox (left, top, right, bottom) around the bobber."""
        cx, cy = bobber_pos
        half = self.BOBBER_REGION_HALF
        left   = max(0, cx - half)
        top    = max(0, cy - half)
        right  = cx + half
        bottom = cy + half
        return (left, top, right, bottom)

    def capture_bobber_frame(self, bobber_pos):
        """Capture the bobber region as a grayscale numpy array."""
        bbox = self.get_bobber_region(bobber_pos)
        img  = ImageGrab.grab(bbox=bbox)
        return np.array(img.convert('L'))

    def detect_bite(self, prev_frame, curr_frame):
        """Return True if the bobber region changed enough to indicate a splash."""
        diff   = np.abs(curr_frame.astype(int) - prev_frame.astype(int))
        change = np.mean(diff)
        return change > self.SPLASH_THRESHOLD

    def loot(self, bobber_pos):
        """Right-click the bobber to collect the fish."""
        cx, cy = bobber_pos
        rx = cx + random.randint(-5, 5)
        ry = cy + random.randint(-5, 5)
        pyautogui.moveTo(rx, ry, duration=random.uniform(0.2, 0.5))
        pyautogui.rightClick()
        self.wait(self.POST_LOOT_WAIT, 0.3)

    def apply_lure(self):
        """Apply a lure to the fishing pole using the configured keybind."""
        pyautogui.press(self.LURE_KEY)
        self.wait(self.LURE_APPLY_WAIT, 0.3)
        self.last_lure_time = time.time()
        print("[BOT] Lure applied.")

    def lure_needed(self):
        """Return True if the lure buff has expired and a new one should be applied."""
        return (time.time() - self.last_lure_time) >= self.LURE_DURATION

    def fish_once(self):
        """
        Execute one full fishing attempt: cast → find bobber → watch → loot.
        Returns True if a fish was caught, False on timeout or bobber not found.
        """
        self.cast_line()

        # Retry finding the bobber a few times in case of lag or color mismatch
        bobber_pos = None
        for attempt in range(self.MAX_CAST_ATTEMPTS):
            bobber_pos = self.find_bobber()
            if bobber_pos:
                break
            print(f"[BOT] Bobber not found (attempt {attempt + 1}/{self.MAX_CAST_ATTEMPTS}), retrying...")
            self.wait(1.0, 0.3)
        else:
            print("[BOT] Bobber never found — skipping this cast.")
            return False

        print(f"[BOT] Bobber at {bobber_pos}, watching for bite...")

        prev_frame = self.capture_bobber_frame(bobber_pos)
        deadline   = time.time() + self.BITE_TIMEOUT

        while time.time() < deadline:
            time.sleep(self.POLL_INTERVAL)
            curr_frame = self.capture_bobber_frame(bobber_pos)

            if self.detect_bite(prev_frame, curr_frame):
                # Small human-like reaction delay
                self.wait(0.15, 0.1)
                self.loot(bobber_pos)
                return True

            prev_frame = curr_frame  # rolling update — diff only against previous frame

        print("[BOT] Timeout — no bite. Recasting.")
        return False

    def run(self):
        """Main fishing loop. Move mouse to top-left corner to stop."""
        self.running       = True
        self.last_lure_time = 0   # 0 forces lure application on first iteration
        cast_count  = 0
        fish_count  = 0

        print("[BOT] WoW Fishing started. Move mouse to top-left corner to stop.")

        while self.running:
            if self.lure_needed():
                print("[BOT] Applying lure...")
                self.apply_lure()

            cast_count += 1
            print(f"[BOT] Cast #{cast_count}...")
            success = self.fish_once()

            if success:
                fish_count += 1
                print(f"[BOT] Fish caught: {fish_count} total.")

            self.wait(0.5, 0.2)  # brief pause between cycles


if __name__ == "__main__":
    # Set game_region to (x, y, width, height) of your WoW window,
    # or leave None to use the full screen.
    # Example: game_region=(0, 0, 1920, 1080)
    #
    # Before running:
    #   1. Run color_sampler.py to calibrate BOBBER_COLOR
    #   2. Set up a WoW macro on LURE_KEY to apply your lure
    #   3. Make sure your Fishing ability is on CAST_KEY

    bot = WoWFishingBot(game_region=None)
    print("[WoW Fishing Bot] Starting in 3 seconds — switch to WoW now...")
    time.sleep(3)
    bot.run()
