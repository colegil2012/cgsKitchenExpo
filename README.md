# CGS Kitchen Expo Board — Vue display for cgsKitchen

Standalone kitchen order board for the food truck, built as a static web app
that runs in the **same Chromium-kiosk-on-a-Pi** pattern as the driver unit
and the POS. It is a **read-only** expo display: a wall-mounted TV showing
in-flight orders moving Paid -> In Kitchen -> Ready. It does not ring up,
advance, or cancel anything — the POS owns every transition. Built for a
**Pi Zero 2 W** driving an HDMI screen.

## Why this architecture

The driver kiosk and the POS already run Chromium fullscreen on labwc, loading
a local web app. This board reuses that exact stack — another Pi provisioned
the same way, only the launched URL differs. No new device class, one
provisioning playbook. The board is **standalone**: it only consumes cgsKitchen
endpoints, holds no local state worth persisting, and writes nothing back. New
data needs become new endpoints in cgsKitchen, not coupling into this app.

It is deliberately **read-only**. The POS (and its kitchen tab) is the single
writer of order status; a second device that could also advance orders would
be shared mutable state where a stale, late tap is wrong. This display just
mirrors `GET /api/orders/active` and lets the line cooks see the queue at a
glance. If a write surface is ever wanted here, it becomes a new device role,
not a quiet capability bolted onto a wall TV.

## Authentication

Every request sends the `X-API-Key` header (set from `VITE_API_KEY`, which must
match the backend `app.api-key`). The only exception is the health probe, which
is unauthenticated. The orders read lives on the backend's API-key filter chain
(`/api/**`), same as the POS — there is no public, keyless endpoint. Vite
inlines `VITE_*` vars at build time, so changing `.env` requires a rebuild, not
just a refresh.

## What it talks to

All endpoints are on the cgsKitchen backend. "On drop" describes what happens
on a connectivity loss.

| Action | Endpoint | On drop |
|---|---|---|
| Active kitchen orders | `GET /api/orders/active` | last-known board stays up; polls when online |
| Health probe | `GET /actuator/health` | — (this *is* the connectivity check) |

No new server endpoints are required; both are already what the POS calls.

## Features

### The board
Three columns — **Paid -> In Kitchen -> Ready** — backed by
`GET /api/orders/active`, polled every 10s. Orders are grouped by `status` and
sorted oldest-first within each column, so the first ticket paid is the first
ticket worked. When the server stops returning an order (advanced to a terminal
state, or cancelled from the POS) it simply drops off the board on the next
poll. Terminal states never appear here because `/active` excludes them.

### Ticket aging
Each ticket shows a short order number (last 4 of the order id), its line
items, and a live age timer driven by a single shared clock. Tickets in Paid
and In Kitchen warm to amber at 6 minutes and pulse red at 12 minutes, a
passive alarm so nothing sits forgotten. Ready tickets stay cool — once it's
up, age no longer matters.

### Connectivity behaviour
A header status dot shows Live (green) or Reconnecting (red, blinking). On a
drop the board keeps the last good data on screen rather than blanking the
kitchen, and silently resumes when the next poll succeeds.

## Why read-only (no transitions here)

The POS README spells out the rule: status changes are shared mutable state
where a stale, late-replayed action would be wrong, so they are online-only and
single-writer. This board honours that by simply not having a write path. The
backend transition matrix remains the source of truth; the only thing that
advances an order is the POS hitting `POST /api/orders/{id}/status`. The board
finds out on its next 10s poll.

## Project layout

```
src/
  api/client.ts            fetch wrapper (X-API-Key) + fetchActiveOrders + heartbeat
  lib/config.ts            Vite env config + HEARTBEAT_PATH + POLL_MS
  types/order.ts           OrderView contract + BoardColumn helpers
  stores/board.ts          polls active orders, groups by column, status dot
  components/BoardColumn.vue   one column header + its ticket stack
  components/OrderTicket.vue   a ticket: number, items, age, heat state
  App.vue                  board shell: top bar (brand/clock/status) + 3 columns
  main.ts                  entry
  styles.css               theme tokens + global kiosk styles (cursor: none)
```

## Develop

```bash
npm install
cp .env.example .env       # set VITE_API_BASE_URL, VITE_API_KEY
npm run dev                # http://localhost:5173
```

`VITE_API_KEY` must match the backend `app.api-key`. For local backend dev,
set `API_KEY` and add `http://localhost:5173` to `CORS_ORIGINS` in the
cgsKitchen run config. `npm run build` typechecks (vue-tsc) then emits `dist/`.

### Environment variables

- `VITE_API_BASE_URL` — backend base, e.g. `http://192.168.1.50:8080`
- `VITE_API_KEY` — must match backend `app.api-key`
- `VITE_POLL_MS` — board refresh interval (default 10000)

## Deploy to the Pi kiosk

The build output is plain static files with **relative** asset paths
(`base: './'`), so it loads via `file://` exactly like the driver dashboard
and the POS. Two options:

**A. Mirror the driver unit (recommended).** Provision a Pi Zero 2 W with the
same buildout doc (labwc + systemd autologin + `update.sh` git pull). Build and
commit `dist/`, or have `update.sh` run `npm ci && npm run build` after the
pull. Point `launch.sh` at the built file:

```bash
exec chromium \
  --kiosk --noerrdialogs --disable-infobars --no-first-run \
  --ozone-platform=wayland --password-store=basic \
  --enable-features=UseOzonePlatform \
  --app=file:///home/druid-mobile/celtech-kitchen-board/dist/index.html
```

**B. Serve from the network** and point `--app=` at the URL instead. Simpler
rebuilds, but then the kiosk needs connectivity to load the shell.

Notes for the Zero 2 W: Chromium is heavy on this board, but the app ships tiny
(~29 KB gzipped JS, no images) and only polls on a timer, so it idles
comfortably. `cursor: none` is set so no pointer shows on the wall TV. There is
no touch input — this is display-only.

## Offline-readiness checklist (do before relying on it cold)

1. **Self-host fonts.** `styles.css` pulls Archivo and Space Mono from Google
   Fonts, which needs network on first paint. Vendor the woff2 files and swap
   for a local `@font-face`. System-ui fallbacks already prevent a hard fail.
2. **API reachable on the LAN IP.** Keep `VITE_API_BASE_URL` pointed at the
   backend's LAN IP if serving the shell over the network. Option A (file://)
   makes the shell itself network-independent; only the data polls need the LAN.

## Production hardening notes

- The API key ships in the built bundle. Fine for one trusted kiosk on a
  private network; revisit (per-device key / backend proxy) before any broader
  rollout. Same posture as the POS.
- Read-only by construction, so there is no last-write-wins concern here — the
  board can never clobber another device's change because it makes none.

## Roadmap

- **Push instead of poll.** If cgsKitchen grows an SSE/WebSocket order stream,
  swap the 10s poll for a subscription so the board updates the instant the POS
  advances a ticket.
- **Bump-bar / KDS input (separate role).** If line cooks should advance orders
  from here, that is a new device role with its own write path and the same
  online-only transition rules as the POS — not a capability added to this
  display.
- **Self-hosted fonts** for full cold-start independence (see checklist).
- **Branding.** Logo on the top bar, favicon.