<script setup lang="ts">
import { computed } from 'vue'
import qrcode from 'qrcode-generator'

const props = withDefaults(defineProps<{ value: string; size?: number }>(), { size: 120 })

/** 二维码本身永远留白底、深色码点 —— 反色的码有些手机扫不出来。 */
const QUIET = 3

const grid = computed(() => {
  const qr = qrcode(0, 'M')
  qr.addData(props.value)
  qr.make()

  const count = qr.getModuleCount()
  let path = ''
  for (let row = 0; row < count; row += 1) {
    for (let col = 0; col < count; col += 1) {
      if (qr.isDark(row, col)) path += `M${col} ${row}h1v1h-1z`
    }
  }
  return { path, count }
})
</script>

<template>
  <svg
    class="qr"
    :width="size"
    :height="size"
    :viewBox="`${-QUIET} ${-QUIET} ${grid.count + QUIET * 2} ${grid.count + QUIET * 2}`"
    shape-rendering="crispEdges"
    role="img"
    aria-label="邀请二维码"
  >
    <rect :x="-QUIET" :y="-QUIET" :width="grid.count + QUIET * 2" :height="grid.count + QUIET * 2" fill="#eef2fa" />
    <path :d="grid.path" fill="#0a1020" />
  </svg>
</template>

<style scoped>
.qr {
  display: block;
  border-radius: 10px;
  /* 一点点冷光，让它从深色背景里浮起来而不是贴上去 */
  box-shadow: 0 12px 30px -18px rgba(0, 0, 0, 0.9);
  image-rendering: pixelated;
}
</style>
