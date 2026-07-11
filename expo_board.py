"""
expo_board.py — native Expo (kitchen) board.

Faithful port of the Vue board's design:
  columns  PAID -> IN_KITCHEN -> READY, oldest-first within each
  ticket   #LAST4 + age, item lines (qty x name), modifiers indented beneath,
           fulfillment footer
  heat     READY = cool always; else >=12min HOT (red, pulsing),
           >=6min WARM (amber), else FRESH (column accent)
  colors   lifted from styles.css + BoardColumn.vue
"""
import os
import re
import time
import datetime
import pygame

# ---- palette (from styles.css / BoardColumn.vue) -----------------------
BG          = (0x0e, 0x25, 0x0e)   # --bg
CARD        = (0x16, 0x1b, 0x25)   # --card
INK         = (0xf4, 0xf6, 0xfb)   # --ink
INK_DIM     = (0x8b, 0x93, 0xa7)   # --ink-dim
BRAND       = (0xe6, 0xac, 0x00)   # --accent-brand

COL_ACCENT = {
    "PAID":       ((0x3b, 0x82, 0xf6), (0x93, 0xc5, 0xfd)),   # accent, accent-text
    "IN_KITCHEN": ((0xf5, 0xa6, 0x23), (0xfc, 0xd3, 0x4d)),
    "READY":      ((0x22, 0xc5, 0x5e), (0x86, 0xef, 0xac)),
}
HEAT_WARM = (0xf5, 0xa6, 0x23)
HEAT_HOT  = (0xff, 0x3b, 0x30)
HOT_AGE   = (0xff, 0x5a, 0x4f)

COLUMNS = ["PAID", "IN_KITCHEN", "READY"]
COLUMN_LABEL = {"PAID": "Paid", "IN_KITCHEN": "In Kitchen", "READY": "Ready"}

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


# ---- modifier / name normalization (ported from OrderTicket.vue) -------
_PAREN = re.compile(r"^(.*?)\s*\(([^()]*)\)\s*$")


def split_name(raw):
    """['Clean Name', 'paren contents'|None] — legacy flattened POS names."""
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
    """Structured array -> legacy comma string -> name parenthetical fallback."""
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
        # Backend sends ISO-8601; tolerate a trailing Z.
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
    def __init__(self, surface, size):
        self.surface = surface
        self.w, self.h = size
        s = self.h / 1080.0          # scale from the 1080p design baseline

        def A(px):   # Archivo (display)
            return pygame.font.Font(os.path.join(FONT_DIR, "Archivo.ttf"), max(10, int(px * s)))

        def M(px, bold=False):   # Space Mono
            name = "SpaceMono-Bold.ttf" if bold else "SpaceMono-Regular.ttf"
            return pygame.font.Font(os.path.join(FONT_DIR, name), max(10, int(px * s)))

        self.f_brand   = A(30)
        self.f_coltitle = A(30)
        self.f_colcount = M(24, bold=True)
        self.f_ticketno = A(32)
        self.f_age      = M(19)
        self.f_line     = A(25)
        self.f_qty      = M(23, bold=True)
        self.f_mod      = A(17)
        self.f_foot     = A(16)
        self.f_empty    = A(34)
        self.f_status   = A(17)

        self.s = s
        self.pad = int(28 * s)

    # ---- helpers ------------------------------------------------------
    def _rrect(self, rect, color, radius=None):
        pygame.draw.rect(self.surface, color, rect,
                         border_radius=radius if radius is not None else int(14 * self.s))

    def _text(self, font, txt, color, x, y):
        img = font.render(str(txt), True, color)
        self.surface.blit(img, (x, y))
        return img.get_width(), img.get_height()

    # ---- ticket -------------------------------------------------------
    def _ticket_height(self, order):
        """Measure before drawing so columns can lay out without overflow."""
        s = self.s
        h = int(12 * s)                      # top pad
        h += self.f_ticketno.get_height()    # head row
        h += int(10 * s)
        for it in order.get("items") or []:
            h += self.f_line.get_height() + int(3 * s)
            for _ in mod_list(it):
                h += self.f_mod.get_height() + int(1 * s)
            h += int(6 * s)
        if order.get("fulfillment"):
            h += int(8 * s) + self.f_foot.get_height()
        h += int(12 * s)                     # bottom pad
        return h

    def _draw_ticket(self, order, column, x, y, w, now_ts, pulse):
        s = self.s
        age = age_minutes(order, now_ts)
        heat = heat_for(column, age)
        accent, accent_text = COL_ACCENT[column]

        if heat == "warm":
            bar = HEAT_WARM
        elif heat == "hot":
            bar = HEAT_HOT
        else:
            bar = accent

        h = self._ticket_height(order)
        rect = pygame.Rect(int(x), int(y), int(w), int(h))

        # Hot tickets pulse: a red glow ring that breathes (the CSS keyframe).
        if heat == "hot":
            glow = int(90 + 90 * pulse)
            grect = rect.inflate(int(8 * s), int(8 * s))
            gs = pygame.Surface((grect.w, grect.h), pygame.SRCALPHA)
            pygame.draw.rect(gs, (*HEAT_HOT, glow), gs.get_rect(),
                             border_radius=int(16 * s))
            self.surface.blit(gs, grect.topleft)

        self._rrect(rect, CARD)
        # left accent bar (8px in CSS)
        bar_w = max(4, int(8 * s))
        bar_rect = pygame.Rect(rect.x, rect.y, bar_w, rect.h)
        pygame.draw.rect(self.surface, bar, bar_rect,
                         border_top_left_radius=int(14 * s),
                         border_bottom_left_radius=int(14 * s))

        ix = rect.x + bar_w + int(14 * s)
        iw = rect.w - (bar_w + int(28 * s))
        cy = rect.y + int(12 * s)

        # head: #LAST4  ....  12m
        tno = "#" + (str(order.get("id") or "????")[-4:]).upper()
        self._text(self.f_ticketno, tno, INK, ix, cy)
        age_col = HOT_AGE if heat == "hot" else INK_DIM
        aimg = self.f_age.render(f"{age}m", True, age_col)
        self.surface.blit(aimg, (rect.right - int(14 * s) - aimg.get_width(),
                                 cy + int(8 * s)))
        cy += self.f_ticketno.get_height() + int(10 * s)

        # items
        qty_w = int(self.f_qty.size("00x")[0])
        for it in order.get("items") or []:
            q = f"{it.get('quantity', 1)}x"
            self._text(self.f_qty, q, accent_text, ix, cy)
            name = split_name(it.get("name"))[0]
            name = self._ellipsize(self.f_line, name, iw - qty_w - int(8 * s))
            self._text(self.f_line, name, INK, ix + qty_w + int(8 * s), cy)
            cy += self.f_line.get_height() + int(3 * s)

            for m in mod_list(it):
                mx = ix + qty_w + int(8 * s)
                pw, _ = self._text(self.f_mod, "+ ", accent_text, mx, cy)
                mtxt = self._ellipsize(self.f_mod, m, iw - qty_w - int(20 * s) - pw)
                self._text(self.f_mod, mtxt, INK_DIM, mx + pw, cy)
                cy += self.f_mod.get_height() + int(1 * s)
            cy += int(6 * s)

        if order.get("fulfillment"):
            cy += int(2 * s)
            self._text(self.f_foot, str(order["fulfillment"]).upper(), INK_DIM, ix, cy)

        return h

    def _ellipsize(self, font, text, max_w):
        text = str(text)
        if font.size(text)[0] <= max_w:
            return text
        while text and font.size(text + "…")[0] > max_w:
            text = text[:-1]
        return text + "…" if text else ""

    # ---- full frame ---------------------------------------------------
    def draw(self, orders, online, now_ts):
        s = self.s
        self.surface.fill(BG)

        # ---- top bar: brand | clock | status dot ----
        bar_h = int(64 * s)
        self._text(self.f_brand, "CGS KITCHEN", BRAND, self.pad, int(16 * s))

        clock = time.strftime("%-I:%M %p", time.localtime(now_ts))
        cimg = self.f_brand.render(clock, True, INK)
        self.surface.blit(cimg, (self.w // 2 - cimg.get_width() // 2, int(16 * s)))

        dot_col = (0x22, 0xc5, 0x5e) if online else (0xff, 0x3b, 0x30)
        label = "LIVE" if online else "RECONNECTING"
        limg = self.f_status.render(label, True, INK_DIM)
        lx = self.w - self.pad - limg.get_width()
        self.surface.blit(limg, (lx, int(24 * s)))
        pygame.draw.circle(self.surface, dot_col,
                           (lx - int(16 * s), int(24 * s) + limg.get_height() // 2),
                           max(4, int(7 * s)))

        # ---- group orders by column, oldest first ----
        buckets = {c: [] for c in COLUMNS}
        for o in orders or []:
            st = str(o.get("status") or "").upper()
            if st in buckets:
                buckets[st].append(o)
        for c in COLUMNS:
            buckets[c].sort(key=lambda o: str(o.get("createdAt") or ""))

        # pulse phase for hot tickets (1.6s cycle, like the CSS animation)
        pulse = 0.5 * (1 + pygame.math.Vector2(1, 0).rotate(
            (now_ts % 1.6) / 1.6 * 360).x)

        # ---- three columns ----
        gap = int(20 * s)
        col_w = (self.w - self.pad * 2 - gap * 2) // 3
        top = bar_h + int(16 * s)

        for i, c in enumerate(COLUMNS):
            cx = self.pad + i * (col_w + gap)
            accent, accent_text = COL_ACCENT[c]

            # column head + 4px underline
            self._text(self.f_coltitle, COLUMN_LABEL[c].upper(), INK, cx, top)
            cnt = str(len(buckets[c]))
            cimg2 = self.f_colcount.render(cnt, True, accent_text)
            self.surface.blit(cimg2, (cx + col_w - cimg2.get_width() - int(8 * s),
                                      top + int(4 * s)))
            uy = top + self.f_coltitle.get_height() + int(8 * s)
            pygame.draw.rect(self.surface, accent,
                             pygame.Rect(cx, uy, col_w, max(2, int(4 * s))))

            # tickets
            ty = uy + int(16 * s)
            limit = self.h - int(20 * s)
            if not buckets[c]:
                eimg = self.f_empty.render("—", True, (40, 48, 40))
                self.surface.blit(eimg, (cx + col_w // 2 - eimg.get_width() // 2,
                                         ty + int(30 * s)))
                continue
            for o in buckets[c]:
                th = self._ticket_height(o)
                if ty + th > limit:
                    more = len(buckets[c]) - buckets[c].index(o)
                    self._text(self.f_foot, f"+{more} more", INK_DIM,
                               cx + int(4 * s), ty + int(4 * s))
                    break
                self._draw_ticket(o, c, cx, ty, col_w, now_ts, pulse)
                ty += th + int(12 * s)
