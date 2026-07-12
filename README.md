# cgsKitchenExpo

Kitchen order board for the CGS Kitchen food truck. Runs on a **Raspberry Pi Zero 2 W** wired to an HDMI TV, and shows live orders as they move `PAID → IN_KITCHEN → READY`.

It is a read-only display. It never writes to the backend — the POS drives all state changes; this board just reflects them.

---

## Architecture

**Python + Pillow, drawing straight to the Linux framebuffer (`/dev/fb0`).**

No browser. No compositor. No GPU. No Node.

```
cgsKitchen (Spring, DigitalOcean)
        │  GET /api/orders/active   [X-API-Key]
        ▼
   ApiPoller (background thread)
        │  OrderView[]
        ▼
   ExpoBoard.render()  →  PIL.Image
        │
        ▼
   Framebuffer.show()  →  mmap → /dev/fb0  →  TV
```

### Why not a browser?

This board was originally a Vue app in Chromium, matching the POS. **On a 512MB Zero 2 W that does not work.** Chromium could not get a GPU context (`EGL_BAD_ATTRIBUTE`), fell back to software rendering, and then ate the board alive: 84MB RAM free, swap 77% consumed, the renderer at 143% CPU and the network process pegged at 102% — which wedged its own network layer and left the screen blank.

### Why not SDL/pygame?

Tried second, also dead. The VideoCore IV cannot give SDL an EGL context either (`pygame.error: EGL not initialized`), and Pi OS's SDL ships no `fbcon`/`directfb` fallback — probing every backend leaves only `offscreen`, which renders to memory and displays nothing.

### Why the framebuffer works

We `mmap` the kernel's framebuffer and write bytes into it; the display controller scans them out. **No GPU is involved at any point**, so there is no context to fail to acquire. It is the oldest and dumbest way to put pixels on a screen, and for a text board it is exactly right.

---

## Layout

```
main.py             entry point: poll loop + framebuffer blit
expo_board.py       the renderer (columns, tickets, aging heat)
preview.py          dev tool — render to PNG instead of the framebuffer
common/
  config.py         reads /etc/celtech/env at RUNTIME
  api.py            background poller, last-known-good on drop
  framebuffer.py    mmap /dev/fb0, RGB565/BGRA packing, rotation
fonts/              vendored TTFs (Archivo, Space Mono) — committed on purpose
deploy/
  cgs-expo.service  systemd unit
requirements.txt    Pillow + numpy. That's it.
update.sh           git pull + systemctl restart
```

---

## Configuration

All config lives in **`/etc/celtech/env`** on the device and is read **at runtime** — change it and restart the service; there is no build step.

```ini
API_BASE_URL=https://celtechgs.kitchen
API_KEY=<the backend's API key>

# optional
POLL_SECONDS=10      # default 10 for expo
ROTATE=0             # 0 | 90 | 180 | 270 — for a TV turned on its side
```

`/etc/celtech/role` contains `expo`.

> **Runtime config is the quiet win.** The old Vue build inlined `VITE_*` at *build* time, so changing a key meant `npm ci && npm run build` **on the Pi** — a 50-second, memory-guarded ordeal that needed a 1GB swapfile. Now it's `systemctl restart`.

---

## What it renders

Three columns, oldest-first within each: **Paid**, **In Kitchen**, **Ready**.

Each ticket shows the last 4 of the order id, an age timer, item lines (`2x Shepherd's Fries`), modifiers indented beneath, and the fulfillment type.

**Aging heat** (ported from the original `OrderTicket.vue`):

| Age | State | Treatment |
|---|---|---|
| < 6 min | fresh | column accent bar |
| ≥ 6 min | warm | amber bar |
| ≥ 12 min | hot | red bar + pulsing ring |
| any, in READY | cool | always calm — it's done |

**Modifiers** are normalized from three shapes, in order: the structured array (`[{label, priceDeltaCents}]`), a legacy comma-delimited string, or a parenthetical in the item name (`Boxty (Bacon, Cheddar)`) — so old flattened tickets still render.

**Connectivity**: a green `LIVE` dot, or red `RECONNECTING`. On a network drop the board **keeps the last known orders on screen** rather than blanking — a blank board in a kitchen is worse than a stale one.

---

## Running

### On the Pi

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py expo
```

It prints the panel geometry before drawing — that line is your proof it found the framebuffer:

```
framebuffer: 1366x768 @ 16bpp (stride 2732) rotate=0 canvas=1366x768
```

Then install the service:

```bash
sudo cp deploy/cgs-expo.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cgs-expo.service
```

The user must be in the **`video`** group (that's who owns `/dev/fb0`):

```bash
sudo usermod -aG video druid && sudo reboot
```

### On a dev laptop

`main.py` **will not run** on a desktop machine — the compositor owns `/dev/fb0` and you'll get `PermissionError`. That's correct, not a bug. Use `preview.py`, which runs the *same* renderer and writes a PNG:

```bash
./preview.py expo --demo --show      # fake data, no backend needed
./preview.py expo --show             # live, against /etc/celtech/env
./preview.py expo --watch            # re-render every few seconds
./preview.py expo --size 1366x768    # match the Pi's panel exactly
```

What you see in the PNG is pixel-for-pixel what the TV shows.

---

## Updating

```bash
./update.sh expo
```

Fetches `main`, resets to it, and restarts the service. **No npm, no build, no swap** — the whole thing takes a couple of seconds.

---

## Gotchas

**Seeing "Hello from the pygame community"?** You're running old code. The framebuffer version imports no pygame at all. Check `grep -c pygame main.py` (must be `0`) and that `common/framebuffer.py` exists while `common/display.py` does not.

**Zero 2 W is 2.4GHz-only.** It has no 5GHz radio. If the SSID isn't broadcasting 2.4GHz, the unit silently never appears on the network.

**Reimaged?** `ssh-keygen -R druid-expo.local` — new host keys.

**Text too small?** The board scales from a 1080p baseline with a floor (`max(h/1080, 0.78)`). Raise the floor in `ExpoBoard.__init__` if the kitchen reads it from a distance.

**Provision on bench WiFi**, not the truck's cellular router. The old Vue stack burned ~5GB of SIM data on `npm ci` across two buildouts. This one downloads ~20MB once and then uses a few KB per poll.

---

## Backend contract

`GET /api/orders/active` → `OrderView[]`, header `X-API-Key`.

```ts
OrderView {
  id: string
  status: 'PAID' | 'IN_KITCHEN' | 'READY'
  fulfillment: string
  items: OrderItemView[]      // { name, quantity, modifiers? }
  createdAt: string           // ISO-8601; drives the age timer
}
```

Terminal states never appear in `/active`, so the board doesn't handle them.
