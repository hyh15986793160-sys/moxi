<script setup lang="ts">
withDefaults(defineProps<{ aligned?: boolean }>(), { aligned: false })

// 一段周期 80 的正弦波；开头必须先有 Q，后面的 T 才有控制点可镜像。
const WAVE = [
  'M0 36 Q20 12 40 36',
  ...Array.from({ length: 5 }, (_, i) => `T${(i + 2) * 40} 36`),
].join(' ')
</script>

<template>
  <svg class="wave" :class="{ 'wave--aligned': aligned }" viewBox="0 0 240 72" aria-hidden="true">
    <path class="wave__line wave__line--a" :d="WAVE" vector-effect="non-scaling-stroke" />
    <path class="wave__line wave__line--b" :d="WAVE" vector-effect="non-scaling-stroke" />
  </svg>
</template>

<style scoped>
.wave {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}

.wave__line {
  fill: none;
  /* 线宽按屏幕像素算，否则缩到 50px 宽时线会细得看不见 */
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-dasharray: 6 10;
  animation: flow 1.6s linear infinite;
}

.wave__line--a {
  stroke: rgba(99, 230, 255, 0.85);
  filter: drop-shadow(0 0 6px rgba(99, 230, 255, 0.45));
  transform: translateY(-6px);
  transition:
    transform 0.7s cubic-bezier(0.2, 0.8, 0.3, 1),
    stroke 0.7s ease,
    filter 0.7s ease;
}

.wave__line--b {
  stroke: rgba(177, 140, 255, 0.75);
  transform: translateY(6px);
  animation-direction: reverse;
  transition:
    transform 0.7s cubic-bezier(0.2, 0.8, 0.3, 1),
    stroke 0.7s ease,
    filter 0.7s ease;
}

/* 同频：两条波收拢成一条，并转为金色 */
.wave--aligned .wave__line--b {
  transform: translateY(0);
  stroke: rgba(255, 211, 122, 0.9);
}

.wave--aligned .wave__line--a {
  transform: translateY(0);
  stroke: rgba(255, 211, 122, 0.95);
  filter: drop-shadow(0 0 10px rgba(255, 211, 122, 0.55));
}

@keyframes flow {
  to {
    stroke-dashoffset: -32;
  }
}
</style>
