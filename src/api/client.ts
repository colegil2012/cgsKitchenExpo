import {API_BASE_URL, API_KEY, HEARTBEAT_PATH} from '../lib/config';
import type {OrderView} from '../types/order';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

interface RequestOpts {
  /** Send the X-API-Key header. Off for the health probe. */
  auth?: boolean;
  signal?: AbortSignal;
  timeoutMs?: number;
}

async function request<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const {auth = true, signal, timeoutMs = 8000} = opts;

  const headers: Record<string, string> = {Accept: 'application/json'};
  if (auth) {
    // Backend ApiKeyFilter accepts X-API-Key or Authorization: Bearer.
    headers['X-API-Key'] = API_KEY;
  }

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  if (signal) {
    signal.addEventListener('abort', () => ctrl.abort(), {once: true});
  }

  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'GET',
      headers,
      signal: ctrl.signal,
    });
    if (!res.ok) {
      let body: unknown;
      try {
        body = await res.json();
      } catch {
        /* ignore */
      }
      throw new ApiError(`GET ${path} failed`, res.status, body);
    }
    return (await res.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

/** GET /api/orders/active — every in-flight order for the kitchen board. */
export function fetchActiveOrders(signal?: AbortSignal): Promise<OrderView[]> {
  return request<OrderView[]>('/api/orders/active', {signal});
}

/** Lightweight connectivity probe (unauthenticated). */
export async function heartbeat(): Promise<boolean> {
  try {
    await request(HEARTBEAT_PATH, {auth: false, timeoutMs: 4000});
    return true;
  } catch {
    return false;
  }
}
