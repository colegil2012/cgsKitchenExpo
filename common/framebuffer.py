"""
framebuffer.py — write pixels straight to /dev/fb0. No SDL, no EGL, no GPU.

WHY THIS EXISTS:
On the Pi Zero 2 W the VideoCore IV cannot give SDL a working EGL context
("EGL not initialized"), and this SDL build has no fbcon/directfb backends —
so *no* SDL backend can reach the screen. Chromium died on the same GPU wall.

The framebuffer cannot hit that wall: we mmap the kernel's framebuffer and
write bytes into it. The display controller scans those bytes out. There is
no GPU, no context, no driver negotiation. It is the oldest and dumbest way
to put pixels on a screen, and for a text board it is exactly right.

Reads geometry from sysfs rather than assuming, then converts Pillow's
RGB888 image to the panel's native format (RGB565 on this hardware).
"""
import mmap
import os
import numpy as np


class Framebuffer:
    def __init__(self, device="/dev/fb0"):
        self.device = device
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
        self._mm = mmap.mmap(self._fd, self._size,
                             mmap.MAP_SHARED,
                             mmap.PROT_READ | mmap.PROT_WRITE)

    # ---- sysfs geometry -----------------------------------------------
    def _sysfs(self, name):
        node = os.path.basename(self.device)          # fb0
        return f"/sys/class/graphics/{node}/{name}"

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

    # ---- blit ----------------------------------------------------------
    def show(self, pil_image):
        """Push a Pillow RGB image to the panel."""
        if pil_image.size != (self.width, self.height):
            pil_image = pil_image.resize((self.width, self.height))
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        arr = np.asarray(pil_image, dtype=np.uint8)          # H x W x 3

        if self.bpp == 16:
            # RGB888 -> RGB565: r>>3 <<11 | g>>2 <<5 | b>>3
            r = arr[:, :, 0].astype(np.uint16)
            g = arr[:, :, 1].astype(np.uint16)
            b = arr[:, :, 2].astype(np.uint16)
            packed = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            raw = packed.astype("<u2").tobytes()
            row_bytes = self.width * 2
        else:
            # 32bpp: kernel expects BGRA/XRGB little-endian
            bgra = np.dstack([
                arr[:, :, 2], arr[:, :, 1], arr[:, :, 0],
                np.full(arr.shape[:2], 255, dtype=np.uint8),
            ])
            raw = bgra.tobytes()
            row_bytes = self.width * 4

        # Respect stride: the panel's rows may be padded wider than the image.
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
    """Stop the console text cursor blinking over the board."""
    try:
        with open("/sys/class/graphics/fbcon/cursor_blink", "w") as fh:
            fh.write("0")
    except Exception:
        pass          # not fatal; the buildout also sets vt.global_cursor_default=0
