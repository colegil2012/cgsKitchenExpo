"""
display.py — initialise pygame straight onto the framebuffer.

THE BIG WIN OVER CHROMIUM:
The Zero 2 W was running labwc (a Wayland compositor) + Chromium (a full
browser: renderer process, GPU process, network service, zygotes...). That
stack needs hundreds of MB and pegged the CPU with software rendering.

Here we drive KMS/DRM directly via SDL2. No compositor, no browser, no JS
engine. Just a surface we blit text onto. Expect tens of MB, not hundreds.

Driver selection order:
  1. kmsdrm  — the target: direct to the display, no X/Wayland (Pi console)
  2. x11/wayland — if a desktop session happens to be running (dev convenience)
  3. dummy   — headless, for rendering preview PNGs on a build machine
"""
import os
import pygame


def init_display(width=None, height=None, headless=False):
    """Returns (surface, (w, h)). Fullscreen on the Pi; windowed if headless."""
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        size = (width or 1920, height or 1080)
        surface = pygame.display.set_mode(size)
        return surface, size

    # On the Pi console there is no DISPLAY/WAYLAND_DISPLAY — use KMSDRM.
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")

    pygame.display.init()

    if width and height:
        size = (width, height)
        surface = pygame.display.set_mode(size, pygame.FULLSCREEN)
    else:
        # Native resolution of the attached TV.
        info = pygame.display.Info()
        size = (info.current_w, info.current_h)
        surface = pygame.display.set_mode(size, pygame.FULLSCREEN)

    pygame.mouse.set_visible(False)   # customer-facing TV: no cursor
    return surface, size


def load_font(path, size, fallback_bold=False):
    """Load a TTF, falling back to a bundled default if the file is missing.

    Fonts are vendored into the repo (fonts/) so the board never depends on
    the network at boot — the same lesson as the Vue apps' 'self-host fonts'
    checklist item, but now it's mandatory rather than optional.
    """
    if path and os.path.exists(path):
        return pygame.font.Font(path, size)
    return pygame.font.SysFont("dejavusans", size, bold=fallback_bold)
