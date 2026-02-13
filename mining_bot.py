from rs_bot import RSBot  # your base class from step 2
import pyautogui, time, random

class MiningBot(RSBot):
    # --- Tune these to your game window ---
    ROCK_COLOR   = (80, 65, 50)   # brown/grey of a minable rock
    ORE_COLOR    = (100, 80, 60)  # color when ore is present
    BANK_HOTKEY  = 'b'            # or a bank booth position
    INVENTORY_XY = (730, 220)    # click here to open inventory

    def is_inventory_full(self):
        """Check if inv is full by sampling the 28th slot"""
        # Simple approach: count non-empty looking pixels in inv area
        # Adjust (700, 450, 770, 470) to your inventory area
        img = np.array(self.screenshot())
        inv_slice = img[450:470, 700:770]
        # If the last slot looks different from empty, it's full
        return np.std(inv_slice) > 10

    def bank_items(self):
        """Walk to bank and deposit (adapt to your server's layout)"""
        pyautogui.press(self.BANK_HOTKEY)
        self.wait(2, 0.5)
        # Click "Deposit All" button — find its screen coords
        pyautogui.click(395, 460)  # update this!
        self.wait(1)
        pyautogui.press('esc')
        self.wait(1)

    def mine_rock(self):
        pos = self.find_color(self.ROCK_COLOR, tolerance=25)
        if pos:
            self.click(*pos)
            self.wait(4, 1)  # wait for mining animation
            return True
        return False

    def run(self):
        self.running = True
        print("[BOT] Mining started. Move mouse to corner to stop.")
        while self.running:
            if self.is_inventory_full():
                print("[BOT] Inventory full — banking...")
                self.bank_items()
            else:
                found = self.mine_rock()
                if not found:
                    print("[BOT] No rock found, waiting...")
                    self.wait(2)

# Run it
if __name__ == "__main__":
    bot = MiningBot(game_region=(0, 0, 800, 600))
    bot.run()