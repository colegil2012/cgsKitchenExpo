<script setup lang="ts">
import {ref, onMounted, onUnmounted} from 'vue';
import {storeToRefs} from 'pinia';
import {useBoardStore} from './stores/board';
import {BOARD_COLUMNS} from './types/order';
import BoardColumn from './components/BoardColumn.vue';
import logoUrl from './assets/header_logo.png';

const store = useBoardStore();
const {byColumn, online} = storeToRefs(store);

// A shared "now" ticking once a second drives every ticket's age without each
// card holding its own timer.
const now = ref(Date.now());
const clock = ref('');
let tick: ReturnType<typeof setInterval> | null = null;

function fmtClock(d: Date) {
  return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}

onMounted(() => {
  store.start();
  const d = new Date();
  clock.value = fmtClock(d);
  tick = setInterval(() => {
    const t = new Date();
    now.value = t.getTime();
    clock.value = fmtClock(t);
  }, 1000);
});

onUnmounted(() => {
  store.stop();
  if (tick) clearInterval(tick);
});
</script>

<template>
  <div class="board">
    <header class="board__bar">
      <div class="board__brand">
        <img :src="logoUrl" class="board__brand-logo" alt="Logo" />
        <h1 class="board__brand-title">EXPO</h1>
      </div>
      <div class="board__status">
        <span class="dot" :class="online ? 'dot--ok' : 'dot--down'" />
        <span class="board__net">{{ online ? 'Online' : 'Reconnecting' }}</span>
        <span class="board__clock">{{ clock }}</span>
      </div>
    </header>

    <main class="board__grid">
      <BoardColumn
        v-for="col in BOARD_COLUMNS"
        :key="col"
        :column="col"
        :orders="byColumn[col]"
        :now="now"
      />
    </main>
  </div>
</template>

<style scoped>
.board {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(
      120% 80% at 50% -10%,
      rgba(59, 130, 246, 0.08),
      transparent 60%
    ),
    var(--bg);
  overflow: hidden;
}
.board__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.7rem 1.6rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.board__brand {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.board__brand-logo {
  height: 2.3rem;
  width: auto;
}
.board__brand-title {
  color: var(--accent-brand);
  font-family: var(--font-display);
  font-size: 1.7rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  margin: 0;
}
.board__status {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}
.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
.dot--ok {
  background: #22c55e;
  box-shadow: 0 0 10px #22c55e;
}
.dot--down {
  background: #ff3b30;
  box-shadow: 0 0 10px #ff3b30;
  animation: blink 1s steps(2) infinite;
}
@keyframes blink {
  50% {
    opacity: 0.3;
  }
}
.board__net {
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: var(--ink-dim);
}
.board__clock {
  font-family: var(--font-mono);
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--ink);
  margin-left: 0.6rem;
}
.board__grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.1rem;
  padding: 1.1rem 1.3rem 0;
  min-height: 0;
}
</style>
