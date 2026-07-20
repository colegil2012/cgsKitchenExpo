"""
expo_board.py — Expo (kitchen) board, rendered with Pillow.

Same design as the Vue board (and the same rules ported from OrderTicket.vue /
BoardColumn.vue) — only the drawing primitives changed from pygame to Pillow,
because SDL cannot reach the screen on this hardware.

  columns  PAID -> IN_KITCHEN -> READY, oldest-first within each
  ticket   #LAST4 + age, item lines (qty x name), modifiers indented, footer
  heat     READY = cool always; else >=12min HOT (red, pulsing),
           >=6min WARM (amber), else FRESH (column accent)
"""
import os
import re
import time
import datetime
from PIL import Image, ImageDraw, ImageFont

# ---- palette (styles.css / BoardColumn.vue) ---------------------------
BG       = (0x0e, 0x25, 0x0e)
CARD     = (0x16, 0x1b, 0x25)
INK      = (0xf4, 0xf6, 0xfb)
INK_DIM  = (0x8b, 0x93, 0xa7)
BRAND    = (0xe6, 0xac, 0x00)
EMPTY    = (40, 48, 40)

COL_ACCENT = {
    "PAID":       ((0x3b, 0x82, 0xf6), (0x93, 0xc5, 0xfd)),
    "IN_KITCHEN": ((0xf5, 0xa6, 0x23), (0xfc, 0xd3, 0x4d)),
    "READY":      ((0x22, 0xc5, 0x5e), (0x86, 0xef, 0xac)),
}
HEAT_WARM = (0xf5, 0xa6, 0x23)
HEAT_HOT  = (0xff, 0x3b, 0x30)
HOT_AGE   = (0xff, 0x5a, 0x4f)
LIVE      = (0x22, 0xc5, 0x5e)
DEAD      = (0xff, 0x3b, 0x30)

COLUMNS = ["PAID", "IN_KITCHEN", "READY"]
COLUMN_LABEL = {"PAID": "PAID", "IN_KITCHEN": "IN KITCHEN", "READY": "READY"}

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

_PAREN = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(ASSET_DIR, "logo.png")

# ---- rules ported from OrderTicket.vue --------------------------------
def split_name(raw):
    s = (raw or "").strip()
    m = _PAREN.match(s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return s, None


def _mod_label(entry):
    if isinstance(entry, str):
        s = entry
    elif isinstance(entry, dict):
        s = str(entry.get("label") or entry.get("name") or "")
    else:
        s = ""
    return re.sub(r"^\+\s*", "", s.strip())


def mod_list(item):
    raw = item.get("modifiers")
    if isinstance(raw, list):
        return [m for m in (_mod_label(e) for e in raw) if m]
    if isinstance(raw, str) and raw.strip():
        return [m for m in (_mod_label(p) for p in raw.split(",")) if m]
    paren = split_name(item.get("name"))[1] or ""
    return [m for m in (_mod_label(p) for p in paren.split(",")) if m]


def age_minutes(order, now_ts):
    created = order.get("createdAt")
    if not created:
        return 0
    try:
        dt = datetime.datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return max(0, int((now_ts - dt.timestamp()) // 60))
    except Exception:
        return 0


def heat_for(column, age_min):
    if column == "READY":
        return "cool"
    if age_min >= 12:
        return "hot"
    if age_min >= 6:
        return "warm"
    return "fresh"


class ExpoBoard:
    def __init__(self, size):
        self.w, self.h = size
        s = self.h / 1080.0
        # On a 768p panel a straight 1080p scale makes kitchen text small;
        # lift it so line cooks can read the board across the truck.
        s = max(s, 0.78)
        self.s = s

        def A(px):
            return ImageFont.truetype(os.path.join(FONT_DIR, "Archivo.ttf"),
                                      max(10, int(px * s)))

        def M(px, bold=False):
            f = "SpaceMono-Bold.ttf" if bold else "SpaceMono-Regular.ttf"
            return ImageFont.truetype(os.path.join(FONT_DIR, f),
                                      max(10, int(px * s)))

        self.f_brand    = A(28)
        self.f_coltitle = A(28)
        self.f_colcount = M(22, bold=True)
        self.f_ticketno = A(30)
        self.f_age      = M(18)
        self.f_line     = A(23)
        self.f_qty      = M(21, bold=True)
        self.f_mod      = A(16)
        self.f_foot     = A(15)
        self.f_empty    = A(30)
        self.f_status   = A(15)

        self.pad = int(22 * s)

        self.logo = None
        if os.path.exists(LOGO_PATH):
            logo = Image.open(LOGO_PATH).convert("RGBA")
            target_h = int(36 * s)
            ratio = target_h / logo.height
            self.logo = logo.resize(
                (max(1, int(logo.width * ratio)), target_h), Image.LANCZOS)


    # ---- text helpers --------------------------------------------------
    def _tw(self, d, font, text):
        return d.textbbox((0, 0), str(text), font=font)[2]

    def _th(self, font):
        a, desc = font.getmetrics()
        return a + desc

    def _ellipsize(self, d, font, text, max_w):
        text = str(text)
        if self._tw(d, font, text) <= max_w:
            return text
        while text and self._tw(d, font, text + "…") > max_w:
            text = text[:-1]
        return (text + "…") if text else ""

    # ---- ticket --------------------------------------------------------
    def _ticket_height(self, d, order):
        s = self.s
        h = int(10 * s) + self._th(self.f_ticketno) + int(8 * s)
        for it in order.get("items") or []:
            h += self._th(self.f_line) + int(2 * s)
            for _ in mod_list(it):
                h += self._th(self.f_mod) + int(1 * s)
            h += int(5 * s)
        if order.get("fulfillment"):
            h += int(6 * s) + self._th(self.f_foot)
        return h + int(10 * s)

    def _draw_ticket(self, d, order, column, x, y, w, now_ts, pulse):
        s = self.s
        age = age_minutes(order, now_ts)
        heat = heat_for(column, age)
        accent, accent_text = COL_ACCENT[column]
        bar = {"warm": HEAT_WARM, "hot": HEAT_HOT}.get(heat, accent)

        h = self._ticket_height(d, order)
        r = int(10 * s)

        # hot tickets pulse: a red ring that breathes
        if heat == "hot":
            k = int(2 + 3 * pulse)
            d.rounded_rectangle([x - k, y - k, x + w + k, y + h + k],
                                radius=r + k, outline=HEAT_HOT, width=max(1, int(2 * s)))

        d.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=CARD)
        bw = max(4, int(7 * s))
        d.rounded_rectangle([x, y, x + bw + r, y + h], radius=r, fill=bar)
        d.rectangle([x + bw, y, x + bw + r, y + h], fill=CARD)

        ix = x + bw + int(12 * s)
        iw = w - (bw + int(24 * s))
        cy = y + int(10 * s)

        tno = "#" + (str(order.get("id") or "????")[-4:]).upper()
        d.text((ix, cy), tno, font=self.f_ticketno, fill=INK)
        acol = HOT_AGE if heat == "hot" else INK_DIM
        atxt = f"{age}m"
        d.text((x + w - int(12 * s) - self._tw(d, self.f_age, atxt), cy + int(6 * s)),
               atxt, font=self.f_age, fill=acol)
        cy += self._th(self.f_ticketno) + int(8 * s)

        qw = self._tw(d, self.f_qty, "00x") + int(8 * s)
        for it in order.get("items") or []:
            d.text((ix, cy), f"{it.get('quantity', 1)}x",
                   font=self.f_qty, fill=accent_text)
            nm = self._ellipsize(d, self.f_line,
                                 split_name(it.get("name"))[0], iw - qw)
            d.text((ix + qw, cy), nm, font=self.f_line, fill=INK)
            cy += self._th(self.f_line) + int(2 * s)

            for m in mod_list(it):
                mx = ix + qw
                d.text((mx, cy), "+", font=self.f_mod, fill=accent_text)
                pw = self._tw(d, self.f_mod, "+ ")
                mt = self._ellipsize(d, self.f_mod, m, iw - qw - pw - int(6 * s))
                d.text((mx + pw, cy), mt, font=self.f_mod, fill=INK_DIM)
                cy += self._th(self.f_mod) + int(1 * s)
            cy += int(5 * s)

        if order.get("fulfillment"):
            cy += int(2 * s)
            d.text((ix, cy), str(order["fulfillment"]).upper(),
                   font=self.f_foot, fill=INK_DIM)
        return h

    # ---- frame ---------------------------------------------------------
    def render(self, orders, online, now_ts):
        img = Image.new("RGB", (self.w, self.h), BG)
        d = ImageDraw.Draw(img)
        s = self.s

        # top bar
        bx, by = self.pad, int(12 * s)
        if self.logo:
            # RGBA paste needs the alpha channel as the mask
            img.paste(self.logo, (bx, by), self.logo)
            bx += self.logo.width + int(8 * s)
        d.text((bx, by), "Expo", font=self.f_brand, fill=BRAND)
        clock = time.strftime("%-I:%M %p", time.localtime(now_ts))
        d.text((self.w // 2 - self._tw(d, self.f_brand, clock) // 2, int(12 * s)),
               clock, font=self.f_brand, fill=INK)

        lbl = "LIVE" if online else "RECONNECTING"
        lw = self._tw(d, self.f_status, lbl)
        lx = self.w - self.pad - lw
        ly = int(18 * s)
        d.text((lx, ly), lbl, font=self.f_status, fill=INK_DIM)
        rr = max(3, int(5 * s))
        ccy = ly + self._th(self.f_status) // 2
        d.ellipse([lx - int(14 * s) - rr, ccy - rr, lx - int(14 * s) + rr, ccy + rr],
                  fill=(LIVE if online else DEAD))

        bar_h = int(12 * s) + self._th(self.f_brand) + int(14 * s)

        # bucket + sort
        buckets = {c: [] for c in COLUMNS}
        for o in orders or []:
            st = str(o.get("status") or "").upper()
            if st in buckets:
                buckets[st].append(o)
        for c in COLUMNS:
            buckets[c].sort(key=lambda o: str(o.get("createdAt") or ""))

        # pulse phase (~1.6s cycle)
        import math
        pulse = 0.5 * (1 + math.sin((now_ts % 1.6) / 1.6 * 2 * math.pi))

        gap = int(14 * s)
        col_w = (self.w - self.pad * 2 - gap * 2) // 3
        top = bar_h

        for i, c in enumerate(COLUMNS):
            cx = self.pad + i * (col_w + gap)
            accent, accent_text = COL_ACCENT[c]

            d.text((cx, top), COLUMN_LABEL[c], font=self.f_coltitle, fill=INK)
            cnt = str(len(buckets[c]))
            d.text((cx + col_w - self._tw(d, self.f_colcount, cnt), top + int(4 * s)),
                   cnt, font=self.f_colcount, fill=accent_text)
            uy = top + self._th(self.f_coltitle) + int(6 * s)
            d.rectangle([cx, uy, cx + col_w, uy + max(2, int(3 * s))], fill=accent)

            ty = uy + int(14 * s)
            limit = self.h - int(12 * s)

            if not buckets[c]:
                em = "—"
                d.text((cx + col_w // 2 - self._tw(d, self.f_empty, em) // 2,
                        ty + int(24 * s)), em, font=self.f_empty, fill=EMPTY)
                continue

            for idx, o in enumerate(buckets[c]):
                th = self._ticket_height(d, o)
                if ty + th > limit:
                    more = len(buckets[c]) - idx
                    d.text((cx + int(4 * s), ty + int(2 * s)), f"+{more} more",
                           font=self.f_foot, fill=INK_DIM)
                    break
                self._draw_ticket(d, o, c, cx, ty, col_w, now_ts, pulse)
                ty += th + int(10 * s)

        return img
