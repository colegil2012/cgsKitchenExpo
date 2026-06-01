<script setup lang="ts">
import type {OrderView, BoardColumn} from '../types/order';
import {COLUMN_LABEL} from '../types/order';
import OrderTicket from './OrderTicket.vue';

defineProps<{
  column: BoardColumn;
  orders: OrderView[];
  now: number;
}>();
</script>

<template>
  <section class="col" :data-col="column">
    <header class="col__head">
      <h2 class="col__title">{{ COLUMN_LABEL[column] }}</h2>
      <span class="col__count">{{ orders.length }}</span>
    </header>
    <div class="col__body">
      <OrderTicket
        v-for="o in orders"
        :key="o.id"
        :order="o"
        :column="column"
        :now="now"
      />
      <p v-if="orders.length === 0" class="col__empty">—</p>
    </div>
  </section>
</template>

<style scoped>
.col {
  display: flex;
  flex-direction: column;
  min-height: 0;
  --accent: #6b7280;
  --accent-text: #cbd5e1;
}
.col[data-col='PAID'] {
  --accent: #3b82f6;
  --accent-text: #93c5fd;
}
.col[data-col='IN_KITCHEN'] {
  --accent: #f5a623;
  --accent-text: #fcd34d;
}
.col[data-col='READY'] {
  --accent: #22c55e;
  --accent-text: #86efac;
}
.col__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 1rem;
  border-bottom: 4px solid var(--accent);
  margin-bottom: 0.9rem;
}
.col__title {
  font-family: var(--font-display);
  font-size: 1.75rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--ink);
  margin: 0;
}
.col__count {
  font-family: var(--font-mono);
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--accent-text);
  background: rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  min-width: 2.4ch;
  text-align: center;
  padding: 0.1rem 0.5rem;
}
.col__body {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  overflow-y: auto;
  padding: 0 0.5rem 1rem 0.25rem;
}
.col__body::-webkit-scrollbar {
  width: 6px;
}
.col__body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}
.col__empty {
  text-align: center;
  font-size: 2rem;
  color: rgba(255, 255, 255, 0.12);
  margin-top: 1.5rem;
}
</style>
