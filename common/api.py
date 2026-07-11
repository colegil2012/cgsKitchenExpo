"""
api.py — polls cgsKitchen and holds last-known-good data.

Design mirrors the Vue boards' connectivity behaviour:
  - On a drop, KEEP the last good data on screen (never blank the board).
  - Expose an `online` flag so the UI can show a status dot / stale indicator.
  - Poll on a background thread so a slow request never stalls the render loop
    (this is what wedged Chromium's NetworkService — we keep IO off the
    drawing path entirely).

Uses only `requests` (tiny) rather than a browser's entire network stack.
"""
import threading
import time
import urllib.request
import urllib.error
import json
import ssl


class ApiPoller:
    def __init__(self, config, on_update=None):
        self.cfg = config
        self.on_update = on_update

        self._lock = threading.Lock()
        self._data = None          # last-known-good payload
        self._online = False
        self._last_success = 0.0
        self._stop = threading.Event()
        self._thread = None

        # Explicit TLS context; the boards talk to https://celtechgs.kitchen
        self._ssl_ctx = ssl.create_default_context()

    # ---- public accessors (thread-safe) ----------------------------------
    @property
    def data(self):
        with self._lock:
            return self._data

    @property
    def online(self):
        with self._lock:
            return self._online

    @property
    def seconds_since_success(self):
        with self._lock:
            if not self._last_success:
                return None
            return time.time() - self._last_success

    # ---- lifecycle -------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    # ---- internals -------------------------------------------------------
    def _fetch(self):
        url = self.cfg.api_base_url + self.cfg.data_path
        req = urllib.request.Request(url, method="GET")
        req.add_header("X-API-Key", self.cfg.api_key)
        req.add_header("Accept", "application/json")
        # Generous timeout: cellular can be slow. The render loop is on another
        # thread, so a slow poll never freezes the screen.
        with urllib.request.urlopen(req, timeout=20, context=self._ssl_ctx) as resp:
            body = resp.read()
        return json.loads(body.decode("utf-8"))

    def _run(self):
        while not self._stop.is_set():
            try:
                payload = self._fetch()
                with self._lock:
                    self._data = payload
                    self._online = True
                    self._last_success = time.time()
                if self.on_update:
                    try:
                        self.on_update(payload)
                    except Exception:
                        pass
            except Exception:
                # Network drop, DNS fail, 5xx, bad JSON — all treated the same:
                # go offline, KEEP the last good data on screen.
                with self._lock:
                    self._online = False

            # Sleep in small slices so stop() is responsive.
            waited = 0.0
            while waited < self.cfg.poll_seconds and not self._stop.is_set():
                time.sleep(0.25)
                waited += 0.25
