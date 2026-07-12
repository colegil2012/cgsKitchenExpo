#!/usr/bin/env python3
"""
preview.py — run a board WITHOUT a framebuffer (for a dev laptop).

The Pi writes frames to /dev/fb0. On a desktop machine that device is owned
by the compositor (and you likely aren't in the `video` group), so
`main.py` fails with PermissionError — correctly. This renders the same
frame and either saves it to a PNG or opens it in your image viewer.

Uses the real Config + ApiPoller + board renderer, so what you see is exactly
what the panel gets.

    ./preview.py expo                    # one frame -> preview.png
    ./preview.py expo --size 1366x768    # match the Pi's panel
    ./preview.py expo --show             # open it in the default viewer
    ./preview.py expo --watch            # re-render every poll, live
    ./preview.py expo --demo             # fake data, no backend needed
"""
import argparse
import os
import sys
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "common"))

from config import Config          # noqa: E402
from api import ApiPoller          # noqa: E402


def _demo_orders():
    def iso(m):
        return (datetime.datetime.now(datetime.timezone.utc)
                - datetime.timedelta(minutes=m)).isoformat()
    return [
        {"id": "6a44f9c1aa02b8e1", "status": "PAID", "fulfillment": "PICKUP",
         "createdAt": iso(2), "items": [
             {"name": "Shepherd's Fries", "quantity": 2,
              "modifiers": ["Meat: Beef", "Cheese: Beer cheese"]},
             {"name": "Lamb Gyro", "quantity": 1, "modifiers": ["Sauce: Mint"]}]},
        {"id": "9c31ffaa1102bd77", "status": "IN_KITCHEN", "fulfillment": "PICKUP",
         "createdAt": iso(14), "items": [
             {"name": "Irish Nachos", "quantity": 3,
              "modifiers": ["Cheese: Beer cheese", "No jalapeno"]}]},
        {"id": "44ba99f120de8871", "status": "READY", "fulfillment": "PICKUP",
         "createdAt": iso(21), "items": [
             {"name": "Fish & Chips", "quantity": 2, "modifiers": ["Tartar"]}]},
    ]


def _demo_menu():
    def ch(l, d=0, av=True):
        return {"label": l, "priceDeltaCents": d, "available": av}
    return [
        {"categoryId": "c1", "categoryName": "Boxty & Fries", "sortOrder": 1,
         "name": "Shepherd's Fries", "priceCents": 1200, "available": True,
         "description": "Hand-cut fries, slow-braised lamb, beer cheese.",
         "badgeLabel": "Most Loved", "badgeColor": "gold",
         "optionGroups": [{"label": "Cheese", "available": True, "choices": [
             ch("Cheddar"), ch("Beer cheese", 100, av=False)]}]},
        {"categoryId": "c1", "categoryName": "Boxty & Fries", "sortOrder": 2,
         "name": "Irish Nachos", "priceCents": 1100, "available": False,
         "optionGroups": []},
        {"categoryId": "c2", "categoryName": "Drinks", "sortOrder": 3,
         "name": "Barry's Tea", "priceCents": 250, "available": True,
         "optionGroups": []},
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("role", choices=["expo", "menu"])
    ap.add_argument("--size", default="1366x768",
                    help="panel size, e.g. 1366x768 (default: the Pi's panel)")
    ap.add_argument("--out", default="preview.png")
    ap.add_argument("--show", action="store_true", help="open in image viewer")
    ap.add_argument("--watch", action="store_true", help="re-render continuously")
    ap.add_argument("--demo", action="store_true",
                    help="use fake data (no backend / no /etc/celtech/env needed)")
    args = ap.parse_args()

    w, h = (int(v) for v in args.size.lower().split("x"))

    if args.role == "expo":
        from expo_board import ExpoBoard
        board = ExpoBoard((w, h))
    else:
        from menu_board import MenuBoard
        from main import group_sections          # reuse the real grouping
        board = MenuBoard((w, h), title="Menu")

    if args.demo:
        data = _demo_orders() if args.role == "expo" else _demo_menu()
        payload, online = data, True
        poller = None
    else:
        cfg = Config(role=args.role)
        for p in cfg.validate():
            print(f"CONFIG WARNING: {p}", file=sys.stderr)
        poller = ApiPoller(cfg)
        poller.start()
        print("polling…", cfg.api_base_url + cfg.data_path)
        time.sleep(2)                            # let the first poll land

    def frame():
        if poller:
            raw, on = (poller.data or []), poller.online
        else:
            raw, on = payload, online
        if args.role == "expo":
            return board.render(raw, on, time.time())
        from main import group_sections
        return board.render(group_sections(raw), on, time.time())

    try:
        if args.watch:
            print("Ctrl+C to stop; re-rendering…")
            while True:
                frame().save(args.out)
                print(f"  wrote {args.out} "
                      f"(online={poller.online if poller else True})")
                time.sleep(3)
        else:
            img = frame()
            img.save(args.out)
            print(f"wrote {args.out} ({img.size[0]}x{img.size[1]})")
            if args.show:
                img.show()
    except KeyboardInterrupt:
        pass
    finally:
        if poller:
            poller.stop()


if __name__ == "__main__":
    main()
