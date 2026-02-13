#!/usr/bin/env python3
"""
Smart Woodcutting Bot — vision-based, no hardcoded waypoints.

Uses screen reading to know where it is and what to do:
  - Finds trees by scanning the game screen (color detection + clustering)
  - Navigates via the minimap (clicks bank/tree icons)
  - Detects when inventory is full
  - Banks and returns to the tree area automatically

Usage:
    1. Run calibrate.py first to create bot_config.json
    2. python smart_woodcutter.py
"""

import os
import sys
import json
import time
import math
import random

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

from rs_bot import RSBot

pyautogui.FAILSAFE = True

# ─── Config ─────────────────────────────────────────────────────────

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"[ERROR] Config not found: {CONFIG_PATH}")
        print("Run  python calibrate.py  first to set up your bot.")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


# ─── Bot ─────────────────────────────────────────────────────────────

class SmartWoodcutter(RSBot):
    """
    State-machine woodcutting bot with visual awareness.

    States
    ------
    FIND_TREE      – scan the game screen for a tree to chop
    CHOPPING       – wait for the current chop to finish
    WALK_TO_BANK   – inventory full, navigate to the bank via minimap
    BANKING        – deposit all items
    WALK_TO_TREES  – after banking, walk back toward the tree area
    """

    # State names
    FIND_TREE = "FIND_TREE"
    CHOPPING = "CHOPPING"
    WALK_TO_BANK = "WALK_TO_BANK"
    BANKING = "BANKING"
    WALK_TO_TREES = "WALK_TO_TREES"

    def __init__(self, config):
        game_region = config.get("game_region")
        super().__init__(game_region=game_region)

        self.config = config

        # Minimap
        mm = config["minimap"]
        self.mm_center = tuple(mm["center"])
        self.mm_radius = mm["radius"]

        # Inventory
        inv = config["inventory"]
        self.inv_origin = tuple(inv["top_left"])  # center of first slot
        self.inv_slot_w = inv["slot_width"]
        self.inv_slot_h = inv["slot_height"]
        self.inv_cols = inv.get("cols", 4)
        self.inv_rows = inv.get("rows", 7)
        self.inv_empty_color = tuple(inv["empty_color"])

        # Colors & tolerances
        colors = config["colors"]
        tol = config.get("tolerances", {})

        self.tree_color = tuple(colors["tree_trunk"])
        self.tree_tol = tol.get("tree_trunk", 30)

        self.canopy_color = tuple(colors["tree_canopy"]) if "tree_canopy" in colors else None
        self.canopy_tol = tol.get("tree_canopy", 35)

        self.mm_tree_color = tuple(colors["minimap_tree"])
        self.mm_tree_tol = tol.get("minimap_tree", 40)

        self.mm_bank_color = tuple(colors["minimap_bank"])
        self.mm_bank_tol = tol.get("minimap_bank", 40)

        self.bank_booth_color = tuple(colors["bank_booth"])
        self.bank_booth_tol = tol.get("bank_booth", 30)

        # Deposit-all button screen position (set during calibration)
        self.deposit_all_pos = config.get("deposit_all_pos")

        # Player is always at the center of the game viewport
        if game_region:
            self.screen_center = (
                game_region[0] + game_region[2] // 2,
                game_region[1] + game_region[3] // 2,
            )
        else:
            sw, sh = pyautogui.size()
            self.screen_center = (sw // 2, sh // 2)

        # Session stats
        self.trees_chopped = 0
        self.bank_trips = 0

    # ── Vision helpers ───────────────────────────────────────────

    def _grab_region(self, bbox):
        """Grab a screen rectangle as a numpy RGB array."""
        return np.array(ImageGrab.grab(bbox=bbox))

    def _minimap_bbox(self):
        cx, cy = self.mm_center
        r = self.mm_radius
        return (cx - r, cy - r, cx + r, cy + r)

    def _find_color_clusters(self, img, rgb, tolerance, min_area=20):
        """
        Return a list of (cx, cy, area) clusters of pixels matching *rgb*
        within *tolerance*, sorted largest-first.
        """
        r, g, b = rgb
        mask = (
            (np.abs(img[:, :, 0].astype(int) - r) < tolerance)
            & (np.abs(img[:, :, 1].astype(int) - g) < tolerance)
            & (np.abs(img[:, :, 2].astype(int) - b) < tolerance)
        ).astype(np.uint8) * 255

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        clusters = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            clusters.append((cx, cy, area))

        clusters.sort(key=lambda c: c[2], reverse=True)
        return clusters

    # ── Screen-level detection ───────────────────────────────────

    def _has_canopy_above(self, img, cx, cy, search_h=60):
        """Check if there are leaf/canopy-colored pixels above a trunk cluster."""
        if self.canopy_color is None:
            return True  # no canopy color configured, skip check
        # Look in a rectangle above the trunk center
        top = max(0, cy - search_h)
        left = max(0, cx - 30)
        right = min(img.shape[1], cx + 30)
        region = img[top:cy, left:right]
        if region.size == 0:
            return False
        r, g, b = self.canopy_color
        t = self.canopy_tol
        mask = (
            (np.abs(region[:, :, 0].astype(int) - r) < t)
            & (np.abs(region[:, :, 1].astype(int) - g) < t)
            & (np.abs(region[:, :, 2].astype(int) - b) < t)
        )
        return mask.sum() > 15  # need a handful of canopy pixels

    def find_trees_on_screen(self):
        """Return [(screen_x, screen_y), ...] for every tree visible."""
        img = np.array(self.screenshot())
        clusters = self._find_color_clusters(img, self.tree_color, self.tree_tol, min_area=30)

        ox, oy = (self.region[0], self.region[1]) if self.region else (0, 0)
        trees = []
        for cx, cy, _ in clusters:
            if self._has_canopy_above(img, cx, cy):
                trees.append((cx + ox, cy + oy))
        return trees

    def find_nearest_tree(self):
        """Closest tree to the player character, or None."""
        trees = self.find_trees_on_screen()
        if not trees:
            return None
        pcx, pcy = self.screen_center
        return min(trees, key=lambda t: (t[0] - pcx) ** 2 + (t[1] - pcy) ** 2)

    def find_bank_booth_on_screen(self):
        """Find the bank booth on the game screen, or None."""
        img = np.array(self.screenshot())
        clusters = self._find_color_clusters(
            img, self.bank_booth_color, self.bank_booth_tol, min_area=40
        )
        if not clusters:
            return None
        cx, cy, _ = clusters[0]
        ox, oy = (self.region[0], self.region[1]) if self.region else (0, 0)
        return (cx + ox, cy + oy)

    # ── Minimap detection ────────────────────────────────────────

    def _find_on_minimap(self, rgb, tolerance):
        """
        Find the mean position of *rgb* on the circular minimap.
        Returns (screen_x, screen_y) or None.
        """
        bbox = self._minimap_bbox()
        img = self._grab_region(bbox)

        h, w = img.shape[:2]
        cx0, cy0 = w // 2, h // 2
        Y, X = np.ogrid[:h, :w]
        circle = (X - cx0) ** 2 + (Y - cy0) ** 2 <= self.mm_radius ** 2

        r, g, b = rgb
        color_match = (
            (np.abs(img[:, :, 0].astype(int) - r) < tolerance)
            & (np.abs(img[:, :, 1].astype(int) - g) < tolerance)
            & (np.abs(img[:, :, 2].astype(int) - b) < tolerance)
        )

        combined = color_match & circle
        ys, xs = np.where(combined)
        if len(xs) == 0:
            return None

        return (int(np.mean(xs)) + bbox[0], int(np.mean(ys)) + bbox[1])

    def find_bank_on_minimap(self):
        return self._find_on_minimap(self.mm_bank_color, self.mm_bank_tol)

    def find_trees_on_minimap(self):
        return self._find_on_minimap(self.mm_tree_color, self.mm_tree_tol)

    # ── Inventory ────────────────────────────────────────────────

    def _inv_slot_center(self, col, row):
        """Screen coords of the center of inventory slot (col, row) — 0-indexed."""
        x = self.inv_origin[0] + col * self.inv_slot_w
        y = self.inv_origin[1] + row * self.inv_slot_h
        return (x, y)

    def _is_slot_occupied(self, col, row):
        """True when the given inventory slot contains an item."""
        sx, sy = self._inv_slot_center(col, row)
        pad = 5
        sample = self._grab_region((sx - pad, sy - pad, sx + pad, sy + pad))
        avg = sample.mean(axis=(0, 1))

        er, eg, eb = self.inv_empty_color
        diff = abs(avg[0] - er) + abs(avg[1] - eg) + abs(avg[2] - eb)
        return diff > 30

    def is_inventory_full(self):
        """True when the last few inventory slots all contain items."""
        # Check last 3 slots to reduce false positives from a single bad sample
        last_row = self.inv_rows - 1
        slots_to_check = [
            (self.inv_cols - 1, last_row),   # slot 28
            (self.inv_cols - 2, last_row),   # slot 27
            (self.inv_cols - 3, last_row),   # slot 26
        ]
        occupied = sum(self._is_slot_occupied(c, r) for c, r in slots_to_check)
        return occupied >= 2  # at least 2 of 3 must look full

    # ── Idle / tree-still-there checks ───────────────────────────

    def is_player_idle(self, box_size=60, threshold=5.0):
        """Compare two quick screenshots around the player to detect motion."""
        pcx, pcy = self.screen_center
        bbox = (pcx - box_size, pcy - box_size, pcx + box_size, pcy + box_size)
        img1 = self._grab_region(bbox)
        time.sleep(0.8)
        img2 = self._grab_region(bbox)
        diff = np.mean(np.abs(img1.astype(float) - img2.astype(float)))
        return diff < threshold

    def is_tree_still_there(self, pos, radius=15):
        """Check whether tree-colored pixels remain near *pos*."""
        x, y = pos
        img = self._grab_region((x - radius, y - radius, x + radius, y + radius))
        r, g, b = self.tree_color
        t = self.tree_tol
        mask = (
            (np.abs(img[:, :, 0].astype(int) - r) < t)
            & (np.abs(img[:, :, 1].astype(int) - g) < t)
            & (np.abs(img[:, :, 2].astype(int) - b) < t)
        )
        return mask.sum() / mask.size > 0.10

    # ── Actions ──────────────────────────────────────────────────

    def click_minimap(self, x, y):
        """Click a spot on the minimap and wait for the walk."""
        self.click(x, y, offset=3)
        self.wait(3, 1)

    def is_bank_open(self):
        """Heuristic: check if the deposit-all button area looks different from the game world."""
        if not self.deposit_all_pos:
            return True  # can't verify without a known button position
        bx, by = self.deposit_all_pos
        pad = 12
        sample = self._grab_region((bx - pad, by - pad, bx + pad, by + pad))
        # Bank UI tends to be a uniform grey/brown panel — low variance vs game world
        return float(np.std(sample)) < 50

    def open_bank(self, booth_pos):
        self.click(*booth_pos, offset=3)
        self.wait(2, 0.5)
        if not self.is_bank_open():
            # Try one more time with a direct click (no offset)
            print("[BOT] Bank may not have opened, clicking again...")
            self.click(*booth_pos, offset=1)
            self.wait(2, 0.5)

    def deposit_all(self):
        if self.deposit_all_pos:
            self.click(*self.deposit_all_pos, offset=3)
        else:
            # Fallback: some servers support a hotkey
            pyautogui.hotkey("ctrl", "d")
        self.wait(1, 0.3)

    def close_bank(self):
        pyautogui.press("escape")
        self.wait(0.5, 0.2)

    def _random_minimap_point(self, min_dist=30):
        """Pick a random walkable point on the minimap."""
        angle = random.uniform(0, 2 * math.pi)
        dist = random.randint(min_dist, self.mm_radius - 10)
        rx = int(self.mm_center[0] + dist * math.cos(angle))
        ry = int(self.mm_center[1] + dist * math.sin(angle))
        return (rx, ry)

    # ── Main loop ────────────────────────────────────────────────

    def run(self):
        self.running = True
        state = self.FIND_TREE
        current_tree = None
        scan_miss = 0  # consecutive scans with no tree on screen
        max_scan_miss = 5
        bank_retries = 0       # consecutive failed deposit attempts
        max_bank_retries = 3
        walk_to_bank_attempts = 0
        max_walk_to_bank = 10  # max minimap clicks before giving up
        walk_from_bank_steps = 0
        min_walk_from_bank = 3  # must walk away at least this many times before scanning

        print("[BOT] Smart Woodcutter started!")
        print("[BOT] Move mouse to top-left corner to emergency-stop.")
        print()

        while self.running:
            try:
                # ── FIND_TREE ────────────────────────────────────
                if state == self.FIND_TREE:
                    if self.is_inventory_full():
                        print("[BOT] Inventory full — heading to bank.")
                        self.bank_trips += 1
                        state = self.WALK_TO_BANK
                        continue

                    tree = self.find_nearest_tree()
                    if tree:
                        print(f"[BOT] Tree at {tree}, chopping...")
                        self.click(*tree, offset=3)
                        current_tree = tree
                        scan_miss = 0
                        state = self.CHOPPING
                        self.wait(1, 0.3)
                    else:
                        scan_miss += 1
                        if scan_miss >= max_scan_miss:
                            # Try the minimap for tree icons
                            mm_trees = self.find_trees_on_minimap()
                            if mm_trees:
                                print(f"[BOT] Trees on minimap, walking there...")
                                self.click_minimap(*mm_trees)
                            else:
                                print("[BOT] No trees anywhere — exploring...")
                                self.click_minimap(*self._random_minimap_point())
                            scan_miss = 0
                        else:
                            print(f"[BOT] No tree on screen (scan {scan_miss}/{max_scan_miss})")
                            self.wait(1.5, 0.5)

                # ── CHOPPING ─────────────────────────────────────
                elif state == self.CHOPPING:
                    self.wait(4, 1)  # typical chop animation time

                    if current_tree and not self.is_tree_still_there(current_tree):
                        self.trees_chopped += 1
                        print(f"[BOT] Tree down! (total: {self.trees_chopped})")
                        state = self.FIND_TREE
                    elif self.is_player_idle():
                        print("[BOT] Idle — tree gone or unreachable.")
                        state = self.FIND_TREE
                    else:
                        print("[BOT] Still chopping...")

                # ── WALK_TO_BANK ─────────────────────────────────
                elif state == self.WALK_TO_BANK:
                    booth = self.find_bank_booth_on_screen()
                    if booth:
                        print("[BOT] Bank booth visible — opening...")
                        self.open_bank(booth)
                        walk_to_bank_attempts = 0
                        bank_retries = 0
                        state = self.BANKING
                    else:
                        walk_to_bank_attempts += 1
                        if walk_to_bank_attempts > max_walk_to_bank:
                            print("[BOT] Can't find bank after many attempts — going back to chopping.")
                            walk_to_bank_attempts = 0
                            state = self.FIND_TREE
                            continue

                        bank_mm = self.find_bank_on_minimap()
                        if bank_mm:
                            print(f"[BOT] Bank on minimap, walking... ({walk_to_bank_attempts}/{max_walk_to_bank})")
                            self.click_minimap(*bank_mm)
                        else:
                            print(f"[BOT] Bank not on minimap, exploring... ({walk_to_bank_attempts}/{max_walk_to_bank})")
                            self.click_minimap(*self._random_minimap_point())

                # ── BANKING ──────────────────────────────────────
                elif state == self.BANKING:
                    print("[BOT] Depositing inventory...")
                    self.deposit_all()
                    self.wait(1, 0.3)

                    if not self.is_inventory_full():
                        print("[BOT] Deposit done — heading back to trees.")
                        self.close_bank()
                        bank_retries = 0
                        walk_from_bank_steps = 0
                        state = self.WALK_TO_TREES
                    else:
                        bank_retries += 1
                        print(f"[BOT] Deposit may have failed (attempt {bank_retries}/{max_bank_retries})")
                        if bank_retries >= max_bank_retries:
                            print("[BOT] Too many deposit failures — closing and re-opening bank.")
                            self.close_bank()
                            self.wait(1, 0.3)
                            bank_retries = 0
                            state = self.WALK_TO_BANK

                # ── WALK_TO_TREES ────────────────────────────────
                elif state == self.WALK_TO_TREES:
                    # Always walk away from the bank first — the bank
                    # interior has brown wood that looks like trees to
                    # the color scanner, so we can't trust on-screen
                    # tree detection until we've moved away.
                    if walk_from_bank_steps < min_walk_from_bank:
                        walk_from_bank_steps += 1
                        mm_trees = self.find_trees_on_minimap()
                        if mm_trees:
                            print(f"[BOT] Trees on minimap, walking... (step {walk_from_bank_steps}/{min_walk_from_bank})")
                            self.click_minimap(*mm_trees)
                        else:
                            bank_mm = self.find_bank_on_minimap()
                            if bank_mm:
                                dx = self.mm_center[0] - bank_mm[0]
                                dy = self.mm_center[1] - bank_mm[1]
                                tx = int(self.mm_center[0] + dx * 0.8)
                                ty = int(self.mm_center[1] + dy * 0.8)
                                print(f"[BOT] Walking away from bank... (step {walk_from_bank_steps}/{min_walk_from_bank})")
                                self.click_minimap(tx, ty)
                            else:
                                self.click_minimap(*self._random_minimap_point())
                    elif self.find_nearest_tree():
                        print("[BOT] Trees in sight — resuming chopping.")
                        walk_from_bank_steps = 0
                        state = self.FIND_TREE
                        continue
                    else:
                        mm_trees = self.find_trees_on_minimap()
                        if mm_trees:
                            print("[BOT] Trees on minimap, walking...")
                            self.click_minimap(*mm_trees)
                        else:
                            print("[BOT] No trees found, exploring...")
                            self.click_minimap(*self._random_minimap_point())

            except pyautogui.FailSafeException:
                print("\n[BOT] Failsafe triggered — stopping.")
                break
            except Exception as exc:
                print(f"[BOT] Error: {exc}")
                self.wait(2)

        self.running = False
        print()
        print(f"[BOT] Session over.")
        print(f"  Trees chopped : {self.trees_chopped}")
        print(f"  Bank trips    : {self.bank_trips}")


# ─── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = load_config()
    bot = SmartWoodcutter(cfg)

    print("[BOT] Starting in 5 seconds — switch to your game window!")
    time.sleep(5)

    bot.run()
