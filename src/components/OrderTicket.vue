<script setup lang="ts">
import {computed} from 'vue';
import type {OrderView, BoardColumn} from '../types/order';

const props = defineProps<{order: OrderView; column: BoardColumn; now: number}>();

// Short ticket id — last 4 of the order id, uppercased.
const ticket = computed(() => props.order.id.slice(-4).toUpperCase());

const ageMin = computed(() => {
  const created = new Date(props.order.createdAt).getTime();
  return Math.max(0, Math.floor((props.now - created) / 60000));
});

// Tickets sitting too long glow hotter — a passive kitchen alarm.
const heat = computed(() => {
  if (props.column === 'READY') return 'cool';
  if (ageMin.value >= 12) return 'hot';
  if (ageMin.value >= 6) return 'warm';
  return 'fresh';
});
</script>

<template>
  <article class="ticket" :data-heat="heat">
    <header class="ticket__head">
      <span class="ticket__no">#{{ ticket }}</span>
      <span class="ticket__age">{{ ageMin }}m</span>
    </header>
    <ul class="ticket__items">
      <li v-for="(it, i) in order.items" :key="i" class="line">
        <span class="line__qty">{{ it.quantity }}&times;</span>
        <span class="line__name">{{ it.name }}</span>
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
  gap: 0.3rem;
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
.ticket__foot {
  margin-top: 0.6rem;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--ink-dim);
}
</style>
