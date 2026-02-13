#!/usr/bin/env python3
"""
Calibration tool for Smart Woodcutter.

Walks you through pointing at key UI elements so the bot knows
where everything is on YOUR screen / private server client.

Saves results to bot_config.json — you only need to run this once
(or again if your window size / game client changes).

Usage:
    python calibrate.py
"""

import os
import sys
import json
import time

import numpy as np
import pyautogui
from PIL import ImageGrab

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_config.json")


def prompt(msg):
    """Show a step and wait for the user to press Enter."""
    input(f"\n>>> {msg}\n    Press ENTER when ready...")


def mouse_pos():
    p = pyautogui.position()
    return [p[0], p[1]]


def color_at_mouse():
    x, y = pyautogui.position()
    return list(pyautogui.screenshot().getpixel((x, y))[:3])


def sample_color(seconds=2):
    """Average the color under the cursor over a few seconds."""
    print(f"    Sampling for {seconds}s — hold mouse steady...")
    colors = []
    end = time.time() + seconds
    while time.time() < end:
        colors.append(color_at_mouse())
        time.sleep(0.1)
    avg = np.mean(colors, axis=0).astype(int).tolist()
    print(f"    Sampled RGB: ({avg[0]}, {avg[1]}, {avg[2]})")
    return avg


def calibrate():
    config = {}

    print("=" * 60)
    print("  Smart Woodcutter — Calibration")
    print("=" * 60)
    print()
    print("Make sure your game window is open and visible.")
    print("At each step, move your mouse to the requested spot")
    print("and press ENTER in this terminal.")

    # ── 1. Game region ──────────────────────────────────────────
    prompt("STEP 1 — GAME WINDOW\n"
           "Move mouse to the TOP-LEFT corner of the game area.")
    tl = mouse_pos()
    print(f"    Recorded: {tl}")

    prompt("Move mouse to the BOTTOM-RIGHT corner of the game area.")
    br = mouse_pos()
    print(f"    Recorded: {br}")

    config["game_region"] = [tl[0], tl[1], br[0] - tl[0], br[1] - tl[1]]
    print(f"    → game_region = {config['game_region']}")

    # ── 2. Minimap ──────────────────────────────────────────────
    prompt("STEP 2 — MINIMAP\n"
           "Move mouse to the CENTER of the minimap\n"
           "(the white player dot).")
    mm_c = mouse_pos()
    print(f"    Center: {mm_c}")

    prompt("Move mouse to the EDGE of the minimap circle.")
    mm_e = mouse_pos()
    mm_r = int(((mm_c[0] - mm_e[0]) ** 2 + (mm_c[1] - mm_e[1]) ** 2) ** 0.5)
    print(f"    Radius: {mm_r} px")

    config["minimap"] = {"center": mm_c, "radius": mm_r}

    # ── 3. Inventory ────────────────────────────────────────────
    prompt("STEP 3 — INVENTORY\n"
           "Move mouse to the CENTER of the FIRST inventory slot\n"
           "(top-left slot, row 1 col 1).")
    inv1 = mouse_pos()
    print(f"    Slot 1: {inv1}")

    prompt("Move mouse to the CENTER of the SECOND slot in row 1\n"
           "(the slot directly to the right).")
    inv2 = mouse_pos()
    slot_w = inv2[0] - inv1[0]

    prompt("Move mouse to the CENTER of the first slot in ROW 2\n"
           "(directly below the first slot).")
    inv_r2 = mouse_pos()
    slot_h = inv_r2[1] - inv1[1]
    print(f"    Slot size: {slot_w} x {slot_h}")

    prompt("Hover over an EMPTY inventory slot background.")
    empty_col = sample_color()

    config["inventory"] = {
        "top_left": inv1,
        "slot_width": slot_w,
        "slot_height": slot_h,
        "cols": 4,
        "rows": 7,
        "empty_color": empty_col,
    }

    # ── 4. Colors ───────────────────────────────────────────────
    print("\n--- Color Calibration ---")

    prompt("STEP 4a — TREE TRUNK\n"
           "Hover over a tree TRUNK (the brown/dark part) in the game world.")
    tree_col = sample_color()

    prompt("STEP 4b — TREE CANOPY / LEAVES\n"
           "Hover over the LEAVES / CANOPY (the green part) of a tree.")
    canopy_col = sample_color()

    prompt("STEP 5 — MINIMAP TREE ICON\n"
           "Hover over a green tree area on the minimap.")
    mm_tree_col = sample_color()

    prompt("STEP 6 — MINIMAP BANK ICON\n"
           "Hover over the bank icon (usually a $ or gold dot)\n"
           "on the minimap.")
    mm_bank_col = sample_color()

    prompt("STEP 7 — BANK BOOTH\n"
           "Hover over the bank booth in the game world.\n"
           "(Walk to the bank first if you need to.)")
    bank_col = sample_color()

    config["colors"] = {
        "tree_trunk": tree_col,
        "tree_canopy": canopy_col,
        "minimap_tree": mm_tree_col,
        "minimap_bank": mm_bank_col,
        "bank_booth": bank_col,
    }

    config["tolerances"] = {
        "tree_trunk": 30,
        "tree_canopy": 35,
        "minimap_tree": 40,
        "minimap_bank": 40,
        "bank_booth": 30,
    }

    # ── 5. Deposit-all button ───────────────────────────────────
    prompt("STEP 8 — DEPOSIT ALL BUTTON\n"
           "Open the bank and move mouse to the\n"
           "'Deposit Inventory' / 'Deposit All' button.")
    config["deposit_all_pos"] = mouse_pos()
    print(f"    Recorded: {config['deposit_all_pos']}")

    # ── Save ────────────────────────────────────────────────────
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    print()
    print("=" * 60)
    print(f"  Saved to {CONFIG_PATH}")
    print("=" * 60)
    print()
    print("Next step:  python smart_woodcutter.py")
    print()
    print("Tip: if detection is shaky you can edit bot_config.json")
    print("and tweak the tolerance values (higher = more lenient).")


if __name__ == "__main__":
    calibrate()
