<script setup lang="ts">
// 撞词成功时的一次性爆发粒子。纯装饰，不参与布局。
const PALETTE = ['#ffd37a', '#ffe6ab', '#63e6ff', '#b18cff', '#ffffff']

const pieces = Array.from({ length: 52 }, (_, index) => {
  const angle = Math.random() * Math.PI * 2
  const distance = 120 + Math.random() * 330
  return {
    id: index,
    style: {
      '--x': `${Math.cos(angle) * distance}px`,
      '--y': `${Math.sin(angle) * distance * 1.2 + 90}px`,
      '--delay': `${Math.random() * 0.6}s`,
      '--size': `${4 + Math.random() * 7}px`,
      '--color': PALETTE[Math.floor(Math.random() * PALETTE.length)],
      '--spin': `${Math.random() * 720 - 360}deg`,
    } as Record<string, string>,
  }
})
</script>

<template>
  <div class="confetti" aria-hidden="true">
    <span v-for="piece in pieces" :key="piece.id" :style="piece.style" />
  </div>
</template>

<style scoped>
.confetti {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  /* 把爆发点抬到牌桌区域，而不是屏幕正中 */
  padding-bottom: clamp(120px, 26vh, 250px);
  pointer-events: none;
  overflow: hidden;
}

.confetti span {
  position: absolute;
  width: var(--size);
  height: var(--size);
  border-radius: 2px;
  background: var(--color);
  opacity: 0;
  animation: burst 1.7s var(--delay) cubic-bezier(0.16, 0.72, 0.34, 1) forwards;
}

@keyframes burst {
  0% {
    opacity: 0;
    transform: translate3d(0, 0, 0) scale(0.3) rotate(0deg);
  }
  12% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translate3d(var(--x), var(--y), 0) scale(1) rotate(var(--spin));
  }
}
</style>
