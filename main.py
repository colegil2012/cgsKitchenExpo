#!/usr/bin/env python3
"""
main.py — Expo board entry point (framebuffer renderer).

No pygame, no SDL, no EGL, no GPU. Renders with Pillow and writes the
resulting image straight to /dev/fb0.

CPU discipline: the API poll runs on a background thread, and we only
re-render when there is a reason to. A full 1366x768 Pillow frame is cheap;
we cap it at 2 FPS normally, 8 FPS while a ticket is pulsing red.
"""
import sys
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "common"))

from config import Config                      # noqa: E402
from api import ApiPoller                      # noqa: E402
from framebuffer import Framebuffer, hide_cursor   # noqa: E402
from expo_board import ExpoBoard, age_minutes, heat_for, COLUMNS   # noqa: E402


def any_hot(orders, now_ts):
    for o in orders or []:
        st = str(o.get("status") or "").upper()
        if st in COLUMNS and heat_for(st, age_minutes(o, now_ts)) == "hot":
            return True
    return False


def main():
    cfg = Config(role="expo")
    for p in cfg.validate():
        print(f"CONFIG ERROR: {p}", file=sys.stderr)

    hide_cursor()
    fb = Framebuffer(rotate=cfg.rotate)
    cw, ch = fb.canvas_size
    print(f"framebuffer: {fb.width}x{fb.height} @ {fb.bpp}bpp "
          f"(stride {fb.stride}) rotate={fb.rotate} canvas={cw}x{ch}", flush=True)

    board = ExpoBoard((cw, ch))
    poller = ApiPoller(cfg)
    poller.start()

    try:
        while True:
            now = time.time()
            orders = poller.data or []
            fb.show(board.render(orders, poller.online, now))
            time.sleep(0.125 if any_hot(orders, now) else 0.5)
    except KeyboardInterrupt:
        pass
    finally:
        poller.stop()
        fb.close()


if __name__ == "__main__":
    main()
