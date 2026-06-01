/**
 * Config from Vite env vars (set in `.env`, see `.env.example`). Same keys as
 * the POS so one provisioning convention covers every Pi on the network.
 *
 *   VITE_API_BASE_URL  e.g. http://192.168.1.50:8080
 *   VITE_API_KEY       must match the server's app.api-key
 *   VITE_POLL_MS       board refresh interval (default 4000)
 *
 * Vite inlines VITE_* vars at build time, so changing .env needs a rebuild.
 */
export const API_BASE_URL: string = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080'
).replace(/\/+$/, '');

export const API_KEY: string = import.meta.env.VITE_API_KEY ?? '';

export const POLL_MS: number = Number(import.meta.env.VITE_POLL_MS ?? 4000);

/** Unauthenticated health probe, same path the POS uses. */
export const HEARTBEAT_PATH = '/api/health';

if (!API_KEY) {
  // The orders endpoint is key-authed, so an empty key means a blank board.
  // eslint-disable-next-line no-console
  console.warn('[config] VITE_API_KEY is empty — /api/orders/active will 401.');
}
