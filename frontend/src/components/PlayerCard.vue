<script setup lang="ts">
import type { PlayerPhase } from '../types'

withDefaults(
  defineProps<{
    label: string
    hint: string
    word: string | null
    phase: PlayerPhase
    tone: 'me' | 'them'
    matched?: boolean
    placeholder?: string
  }>(),
  { matched: false, placeholder: '还没进来' },
)
</script>

<template>
  <article
    class="card"
    :class="[`card--${tone}`, `card--${phase}`, { 'card--hit': matched }]"
  >
    <header class="card__top">
      <span class="card__label">{{ label }}</span>
      <span class="card__hint">
        <i class="card__dot" />
        {{ hint }}
      </span>
    </header>

    <div class="card__body">
      <Transition name="word" mode="out-in">
        <p v-if="word" :key="word" class="card__word">{{ word }}</p>

        <span v-else-if="phase === 'thinking'" key="thinking" class="card__dots">
          <i /><i /><i />
        </span>

        <span v-else-if="phase === 'locked'" key="sealed" class="card__sealed" />

        <p v-else key="ghost" class="card__ghost">{{ placeholder }}</p>
      </Transition>
    </div>
  </article>
</template>

<style scoped>
.card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 232px;
  padding: 22px 24px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.052), rgba(255, 255, 255, 0.014));
  overflow: hidden;
  transition:
    border-color 0.4s ease,
    box-shadow 0.5s ease,
    transform 0.5s cubic-bezier(0.2, 0.8, 0.3, 1);
}

/* 顶部一条高光，让卡片看起来是"有厚度的玻璃" */
.card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.42), transparent);
  opacity: 0.6;
}

.card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card__label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.2em;
  color: var(--ink-3);
  text-transform: uppercase;
}

.card__hint {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  color: var(--ink-3);
  white-space: nowrap;
  transition: color 0.3s ease;
}

.card__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ink-3);
  transition:
    background 0.3s ease,
    box-shadow 0.3s ease;
}

.card__body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 92px;
}

.card__word {
  margin: 0;
  font-size: clamp(24px, 3.4vw, 34px);
  font-weight: 600;
  line-height: 1.25;
  letter-spacing: 0.02em;
  text-align: center;
  word-break: break-word;
  text-wrap: balance;
}

.card__ghost {
  margin: 0;
  font-size: 14px;
  color: var(--ink-3);
  letter-spacing: 0.06em;
}

.card__sealed {
  width: 128px;
  height: 24px;
  border-radius: 7px;
  background: repeating-linear-gradient(
    118deg,
    rgba(255, 255, 255, 0.17) 0 9px,
    rgba(255, 255, 255, 0.05) 9px 18px
  );
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

.card__dots {
  display: inline-flex;
  gap: 10px;
}

.card__dots i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--ink-3);
  animation: blink 1.25s ease-in-out infinite;
}

.card__dots i:nth-child(2) {
  animation-delay: 0.16s;
}

.card__dots i:nth-child(3) {
  animation-delay: 0.32s;
}

@keyframes blink {
  0%,
  100% {
    opacity: 0.28;
    transform: translateY(0);
  }
  50% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

/* ── 座位色调 ─────────────────────────────── */
.card--me {
  background: linear-gradient(180deg, rgba(99, 230, 255, 0.055), rgba(255, 255, 255, 0.012));
  box-shadow: inset 0 0 60px -40px var(--cyan);
}

.card--me .card__label {
  color: rgba(99, 230, 255, 0.62);
}

.card--them {
  background: linear-gradient(180deg, rgba(177, 140, 255, 0.055), rgba(255, 255, 255, 0.012));
  box-shadow: inset 0 0 60px -40px var(--violet);
}

.card--them .card__label {
  color: rgba(177, 140, 255, 0.62);
}

/* ── 阶段 ─────────────────────────────────── */
.card--thinking .card__dot {
  background: var(--cyan);
  box-shadow: 0 0 10px var(--cyan);
  animation: pulse 1.4s ease-in-out infinite;
}

.card--locked {
  border-color: rgba(255, 255, 255, 0.13);
}

.card--locked .card__hint {
  color: var(--ink-2);
}

.card--locked .card__dot {
  background: var(--ink-2);
  box-shadow: none;
}

.card--locked .card__word {
  color: var(--ink-2);
  filter: blur(0.2px);
}

.card--revealed {
  border-color: var(--line-strong);
}

.card--revealed .card__hint {
  color: var(--ink-2);
}

.card--revealed.card--me {
  box-shadow:
    inset 0 0 80px -46px var(--cyan),
    0 20px 60px -40px rgba(99, 230, 255, 0.55);
}

.card--revealed.card--them {
  box-shadow:
    inset 0 0 80px -46px var(--violet),
    0 20px 60px -40px rgba(177, 140, 255, 0.5);
}

/* 撞上了：两张卡一起烧起来。
   写成 .card.card--hit 是为了压过上面 .card--revealed.card--me 的阴影。 */
.card.card--hit {
  border-color: rgba(255, 211, 122, 0.5);
  box-shadow:
    inset 0 0 90px -40px var(--gold),
    0 24px 70px -38px rgba(255, 211, 122, 0.7);
  transform: translateY(-3px);
}

.card--hit .card__word {
  color: #ffe6ab;
  text-shadow: 0 0 26px rgba(255, 211, 122, 0.55);
}

.card--hit .card__label,
.card--hit .card__hint {
  color: rgba(255, 230, 171, 0.8);
}

.card--hit .card__dot {
  background: var(--gold);
  box-shadow: 0 0 12px var(--gold);
}

@keyframes pulse {
  0%,
  100% {
    opacity: 0.45;
  }
  50% {
    opacity: 1;
  }
}

/* ── 词进出 ───────────────────────────────── */
.word-enter-active {
  transition:
    opacity 0.42s ease,
    filter 0.42s ease,
    transform 0.5s cubic-bezier(0.2, 0.8, 0.3, 1);
}

.word-leave-active {
  transition:
    opacity 0.16s ease,
    transform 0.16s ease;
}

.word-enter-from {
  opacity: 0;
  filter: blur(9px);
  transform: scale(0.9);
}

.word-leave-to {
  opacity: 0;
  transform: scale(0.97);
}

/* 手机上两张卡纵向叠放，压扁一点才放得下房间码和输入框 */
@media (max-width: 720px) {
  .card {
    min-height: 128px;
    padding: 15px 18px;
    gap: 8px;
  }

  .card__body {
    min-height: 54px;
  }

  .card__word {
    font-size: 24px;
  }

  .card__sealed {
    width: 104px;
    height: 20px;
  }
}
</style>
