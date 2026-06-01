import {defineStore} from 'pinia';
import {ref, computed, onScopeDispose} from 'vue';
import {fetchActiveOrders, ApiError} from '../api/client';
import {POLL_MS} from '../lib/config';
import type {OrderView, BoardColumn} from '../types/order';
import {BOARD_COLUMNS} from '../types/order';

/**
 * Read-only kitchen board state. Polls GET /api/orders/active on an interval
 * and exposes orders grouped into the three working columns. This board never
 * mutates orders — the POS / KDS controller owns transitions. If the server
 * stops returning an order (advanced to a terminal state, or cancelled) it
 * simply drops off the board on the next poll.
 */
export const useBoardStore = defineStore('board', () => {
  const orders = ref<OrderView[]>([]);
  const loading = ref(false);
  const online = ref(true);
  const lastUpdated = ref<number | null>(null);
  const errorMsg = ref<string | null>(null);

  let timer: ReturnType<typeof setInterval> | null = null;
  let inFlight: AbortController | null = null;

  const byColumn = computed<Record<BoardColumn, OrderView[]>>(() => {
    const groups = {PAID: [], IN_KITCHEN: [], READY: []} as Record<
      BoardColumn,
      OrderView[]
    >;
    for (const o of orders.value) {
      const col = o.status as BoardColumn;
      if (col in groups) groups[col].push(o);
    }
    // Oldest first within each column — first paid, first cooked.
    for (const col of BOARD_COLUMNS) {
      groups[col].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    }
    return groups;
  });

  const counts = computed<Record<BoardColumn, number>>(() => ({
    PAID: byColumn.value.PAID.length,
    IN_KITCHEN: byColumn.value.IN_KITCHEN.length,
    READY: byColumn.value.READY.length,
  }));

  async function refresh() {
    inFlight?.abort();
    inFlight = new AbortController();
    loading.value = true;
    try {
      orders.value = await fetchActiveOrders(inFlight.signal);
      online.value = true;
      errorMsg.value = null;
      lastUpdated.value = Date.now();
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      online.value = false;
      errorMsg.value =
        err instanceof ApiError
          ? `Server error ${err.status}`
          : 'Cannot reach server';
      // Keep the last good board on screen rather than blanking the kitchen.
    } finally {
      loading.value = false;
    }
  }

  function start() {
    if (timer) return;
    refresh();
    timer = setInterval(refresh, POLL_MS);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    inFlight?.abort();
  }

  onScopeDispose(stop);

  return {
    orders,
    loading,
    online,
    lastUpdated,
    errorMsg,
    byColumn,
    counts,
    start,
    stop,
    refresh,
  };
});
