"""
config.py — runtime configuration for the CGS Kitchen native display boards.

IMPORTANT DIFFERENCE FROM THE VUE BUILD:
Vite inlined VITE_* vars at BUILD time, which is why update.sh had to run
`npm ci && npm run build` on the Pi after any env change. A Python app reads
its env at RUNTIME, so update.sh becomes a plain `git pull` + service restart.
No Node, no npm, no 50-second build, no 512MB memory wall.

Reads /etc/celtech/env (the same secrets file the kiosks already use) and
/etc/celtech/role (expo|menu).
"""
import os
import sys

ENV_FILE = "/etc/celtech/env"
ROLE_FILE = "/etc/celtech/role"


def _load_env_file(path=ENV_FILE):
    """Parse the shell-style /etc/celtech/env into a dict.

    The file is `KEY=value` lines (sourced by bash elsewhere), so we parse it
    directly rather than requiring it be exported into our process env. This
    keeps the systemd unit simple (no EnvironmentFile needed) and means a
    `systemctl restart` is enough to pick up an env change.
    """
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            # strip optional surrounding quotes
            val = val.strip().strip('"').strip("'")
            values[key.strip()] = val
    return values


def load_role(argv=None):
    """Role comes from argv[1] or /etc/celtech/role. Must be expo|menu."""
    argv = sys.argv if argv is None else argv
    role = argv[1].strip().lower() if len(argv) > 1 else ""
    if not role and os.path.exists(ROLE_FILE):
        with open(ROLE_FILE) as fh:
            role = fh.read().strip().lower()
    if role not in ("expo", "menu"):
        raise SystemExit(f"ERROR: role must be 'expo' or 'menu' (got '{role}')")
    return role


class Config:
    def __init__(self, role=None):
        env = _load_env_file()
        self.role = role or load_role()

        self.api_base_url = env.get("API_BASE_URL", "").rstrip("/")
        self.api_key = env.get("API_KEY", "")

        # Poll cadence mirrors the Vue apps: expo 10s, menu 30s.
        default_poll = 10 if self.role == "expo" else 30
        try:
            self.poll_seconds = int(env.get("POLL_SECONDS", default_poll))
        except ValueError:
            self.poll_seconds = default_poll

        self.board_title = env.get("BOARD_TITLE", "Menu")

        # Heartbeat endpoint (unauthenticated) for the connectivity indicator.
        self.health_path = "/actuator/health"

    @property
    def data_path(self):
        """The one endpoint each board reads. Same contract as the Vue apps."""
        return "/api/orders/active" if self.role == "expo" else "/api/menu/all"

    def validate(self):
        problems = []
        if not self.api_base_url:
            problems.append("API_BASE_URL is empty in /etc/celtech/env")
        if not self.api_key:
            problems.append("API_KEY is empty in /etc/celtech/env")
        return problems
