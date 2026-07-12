"""
framebuffer.py — write pixels straight to /dev/fb0. No SDL, no EGL, no GPU.

WHY THIS EXISTS:
On the Pi Zero 2 W the VideoCore IV cannot give SDL a working EGL context
("EGL not initialized"), and this SDL build has no fbcon/directfb backends —
so *no* SDL backend can reach the screen. Chromium died on the same GPU wall.

The framebuffer cannot hit that wall: we mmap the kernel's framebuffer and
write bytes into it. The display controller scans those bytes out. There is
no GPU, no context, no driver negotiation.

ROTATION (menu board, portrait TV):
Because we render to a PIL image before blitting, rotation is free — no
kernel flags, no display-driver config. Set ROTATE=90 (or 270) in
/etc/celtech/env. The board is asked to draw at the *rotated* canvas size
(e.g. 768x1366 portrait) and the finished image is rotated to fit the panel's
native landscape framebuffer. Physically turn the TV 90 degrees to match.
"""
import mmap
import os
import numpy as np


class Framebuffer:
    def __init__(self, device="/dev/fb0", rotate=0):
        self.device = device
        self.rotate = int(rotate) % 360
        if self.rotate not in (0, 90, 180, 270):
            raise ValueError("ROTATE must be 0, 90, 180 or 270")

        # Native panel geometry (always the physical framebuffer).
        self.width, self.height = self._read_size()
        self.bpp = self._read_int("bits_per_pixel", 16)
        self.stride = self._read_int("stride", self.width * self.bpp // 8)

        if self.bpp not in (16, 32):
            raise RuntimeError(
                f"Unsupported framebuffer depth: {self.bpp}bpp "
                "(expected 16 (RGB565) or 32 (BGRA/XRGB))"
            )

        self._fd = os.open(self.device, os.O_RDWR)
        self._size = self.stride * self.height
        self._mm = mmap.mmap(self._fd, self._size, mmap.MAP_SHARED,
                             mmap.PROT_READ | mmap.PROT_WRITE)

    # ---- what size should the BOARD draw at? ---------------------------
    @property
    def canvas_size(self):
        """The size the renderer should draw at.

        At 90/270 this is the panel's dimensions SWAPPED — the board draws a
        tall portrait image, which we then rotate onto the landscape panel.
        """
        if self.rotate in (90, 270):
            return (self.height, self.width)      # e.g. 768 x 1366 portrait
        return (self.width, self.height)

    # ---- sysfs geometry -------------------------------------------------
    def _sysfs(self, name):
        return f"/sys/class/graphics/{os.path.basename(self.device)}/{name}"

    def _read_size(self):
        try:
            with open(self._sysfs("virtual_size")) as fh:
                w, h = fh.read().strip().split(",")
                return int(w), int(h)
        except Exception:
            return 1366, 768

    def _read_int(self, name, default):
        try:
            with open(self._sysfs(name)) as fh:
                return int(fh.read().strip())
        except Exception:
            return default

    # ---- blit -----------------------------------------------------------
    def show(self, pil_image):
        """Push a Pillow RGB image to the panel, rotating if configured."""
        if self.rotate:
            # expand=True so a 768x1366 portrait becomes 1366x768 landscape
            pil_image = pil_image.rotate(self.rotate, expand=True)

        if pil_image.size != (self.width, self.height):
            pil_image = pil_image.resize((self.width, self.height))
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        arr = np.asarray(pil_image, dtype=np.uint8)

        if self.bpp == 16:
            r = arr[:, :, 0].astype(np.uint16)
            g = arr[:, :, 1].astype(np.uint16)
            b = arr[:, :, 2].astype(np.uint16)
            packed = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            raw = packed.astype("<u2").tobytes()
            row_bytes = self.width * 2
        else:
            bgra = np.dstack([
                arr[:, :, 2], arr[:, :, 1], arr[:, :, 0],
                np.full(arr.shape[:2], 255, dtype=np.uint8),
            ])
            raw = bgra.tobytes()
            row_bytes = self.width * 4

        if row_bytes == self.stride:
            self._mm.seek(0)
            self._mm.write(raw)
        else:
            for y in range(self.height):
                self._mm.seek(y * self.stride)
                self._mm.write(raw[y * row_bytes:(y + 1) * row_bytes])

    def close(self):
        try:
            self._mm.close()
        finally:
            os.close(self._fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def hide_cursor():
    try:
        with open("/sys/class/graphics/fbcon/cursor_blink", "w") as fh:
            fh.write("0")
    except Exception:
        pass
