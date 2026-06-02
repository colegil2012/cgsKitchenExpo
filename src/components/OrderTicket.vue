<script setup lang="ts">
import {computed} from 'vue';
import type {OrderView, BoardColumn, OrderItemView} from '../types/order';

const props = defineProps<{order: OrderView; column: BoardColumn; now: number}>();

// Short ticket id — last 4 of the order id, uppercased. Null-safe.
const ticket = computed(() => (props.order.id ?? '????').slice(-4).toUpperCase());

const ageMin = computed(() => {
  const created = new Date(props.order.createdAt ?? Date.now()).getTime();
  if (Number.isNaN(created)) return 0;
  return Math.max(0, Math.floor((props.now - created) / 60000));
});

// Items array may be absent on malformed orders; treat as empty.
const items = computed<OrderItemView[]>(() => props.order.items ?? []);

// Tickets sitting too long glow hotter — a passive kitchen alarm.
const heat = computed(() => {
  if (props.column === 'READY') return 'cool';
  if (ageMin.value >= 12) return 'hot';
  if (ageMin.value >= 6) return 'warm';
  return 'fresh';
});

// The backend's POS flattening appends modifiers to the item name in
// parentheses, e.g. "Breakfast Boxty (Bacon, Cheddar)". Split that trailing
// "(...)" off so we can show the bare name on top and the modifiers stacked
// underneath. Returns [cleanName, parenContents|null]. Null-safe: a missing
// name yields ['', null] rather than throwing.
function splitName(raw: string | null | undefined): [string, string | null] {
  const s = (raw ?? '').trim();
  const m = s.match(/^(.*?)\s*\(([^()]*)\)\s*$/);
  if (m) return [m[1].trim(), m[2].trim()];
  return [s, null];
}

function displayName(it: OrderItemView): string {
  return splitName(it?.name)[0];
}

// Normalize one modifier entry to a label string. Handles plain strings and
// object shapes like {label} / {name} (in case the structured field carries
// objects). Strips a leading "+" so it doesn't double the CSS "+" prefix.
function modLabel(entry: unknown): string {
  let s = '';
  if (typeof entry === 'string') s = entry;
  else if (entry && typeof entry === 'object') {
    const o = entry as Record<string, unknown>;
    s = String(o.label ?? o.name ?? '');
  }
  return s.trim().replace(/^\+\s*/, '');
}

// Modifiers may arrive as the structured field (an array of label strings or
// {label} objects — the proper backend shape), as a legacy comma-separated
// string, or null. Fall back to the name's parenthetical only for old orders
// that were flattened into the name. Returns a clean label list, empties dropped.
function modList(it: OrderItemView): string[] {
  const raw = it?.modifiers;

  if (Array.isArray(raw)) {
    return raw.map(modLabel).filter(Boolean);
  }
  if (typeof raw === 'string' && raw.trim()) {
    return raw.split(',').map(modLabel).filter(Boolean);
  }
  // No structured/string modifiers — fall back to legacy name parenthetical.
  return (splitName(it?.name)[1] ?? '')
    .split(',')
    .map(modLabel)
    .filter(Boolean);
}
</script>

<template>
  <article class="ticket" :data-heat="heat">
    <header class="ticket__head">
      <span class="ticket__no">#{{ ticket }}</span>
      <span class="ticket__age">{{ ageMin }}m</span>
    </header>
    <ul class="ticket__items">
      <li v-for="(it, i) in items" :key="i" class="item">
        <div class="line">
          <span class="line__qty">{{ it.quantity }}&times;</span>
          <span class="line__name">{{ displayName(it) }}</span>
        </div>
        <ul v-if="modList(it).length" class="mods">
          <li v-for="(mod, m) in modList(it)" :key="m" class="mods__item">
            {{ mod }}
          </li>
        </ul>
      </li>
    </ul>
    <footer v-if="order.fulfillment" class="ticket__foot">
      {{ order.fulfillment }}
    </footer>
  </article>
</template>

<style scoped>
.ticket {
  background: var(--card);
  border-radius: 14px;
  padding: 0.85rem 1rem 0.95rem;
  border-left: 8px solid var(--accent);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
  break-inside: avoid;
}
.ticket[data-heat='warm'] {
  border-left-color: #f5a623;
}
.ticket[data-heat='hot'] {
  border-left-color: #ff3b30;
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    box-shadow: 0 4px 16px rgba(255, 59, 48, 0.25);
  }
  50% {
    box-shadow: 0 4px 28px rgba(255, 59, 48, 0.6);
  }
}
.ticket__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.55rem;
}
.ticket__no {
  font-family: var(--font-display);
  font-size: 1.9rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  color: var(--ink);
}
.ticket__age {
  font-family: var(--font-mono);
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--ink-dim);
}
.ticket[data-heat='hot'] .ticket__age {
  color: #ff5a4f;
}
.ticket__items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.item {
  display: flex;
  flex-direction: column;
}
.line {
  display: flex;
  gap: 0.5rem;
  font-size: 1.5rem;
  line-height: 1.2;
  color: var(--ink);
}
.line__qty {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--accent-text);
  min-width: 2.2ch;
}
.line__name {
  font-weight: 500;
}
/* Modifiers sit under the item name, indented to line up past the qty column. */
.mods {
  list-style: none;
  margin: 0.15rem 0 0;
  padding: 0;
  padding-left: 2.7ch; /* 2.2ch qty min-width + 0.5ch gap */
  display: flex;
  flex-direction: column;
  gap: 0.05rem;
}
.mods__item {
  font-size: 1rem;
  line-height: 1.25;
  font-weight: 400;
  color: var(--ink-dim);
}
.mods__item::before {
  content: '+ ';
  color: var(--accent-text);
}
.ticket__foot {
  margin-top: 0.6rem;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--ink-dim);
}
</style>