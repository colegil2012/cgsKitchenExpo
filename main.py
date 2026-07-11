#!/usr/bin/env python3
"""
main.py — Expo board entry point.

CPU discipline (the whole point of this rewrite):
  - The API poll runs on a background thread, so network never blocks drawing.
  - We redraw at ~2 FPS normally. Chromium was repainting continuously and
    pegging the CPU; a kitchen board does not need 60 FPS.
  - When a ticket is HOT we bump to ~12 FPS so the pulse animates smoothly,
    then drop back. Nothing else animates.
"""
import sys
import os
import time
import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))

from config import Config              # noqa: E402
from api import ApiPoller              # noqa: E402
from display import init_display       # noqa: E402
from expo_board import ExpoBoard, age_minutes, heat_for, COLUMNS   # noqa: E402


def any_hot(orders, now_ts):
    for o in orders or []:
        st = str(o.get("status") or "").upper()
        if st in COLUMNS and heat_for(st, age_minutes(o, now_ts)) == "hot":
            return True
    return False


def main():
    cfg = Config(role="expo")
    problems = cfg.validate()
    if problems:
        for p in problems:
            print(f"CONFIG ERROR: {p}", file=sys.stderr)

    pygame.init()
    surface, size = init_display()
    board = ExpoBoard(surface, size)

    poller = ApiPoller(cfg)
    poller.start()

    clock = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False

        now = time.time()
        orders = poller.data or []
        board.draw(orders, poller.online, now)
        pygame.display.flip()

        # Only spend CPU on animation when something is actually pulsing.
        clock.tick(12 if any_hot(orders, now) else 2)

    poller.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
