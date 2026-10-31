<script setup lang="ts">
import { onMounted } from 'vue'

import WaveMark from './components/WaveMark.vue'
import HomeView from './views/HomeView.vue'
import RoomView from './views/RoomView.vue'
import { errorMsg, restore, restoring, state } from './state'

onMounted(() => {
  void restore()
})
</script>

<template>
  <div class="shell">
    <div class="aurora" aria-hidden="true">
      <span class="aurora__blob aurora__blob--a" />
      <span class="aurora__blob aurora__blob--b" />
      <span class="aurora__glow" />
      <span class="aurora__grid" />
    </div>

    <div v-if="restoring" class="boot">
      <div class="boot__wave"><WaveMark /></div>
    </div>
    <RoomView v-else-if="state" />
    <HomeView v-else />

    <Transition name="toast">
      <div v-if="errorMsg" class="toast" role="status">{{ errorMsg }}</div>
    </Transition>
  </div>
</template>

<style scoped>
.shell {
  position: relative;
  min-height: 100vh;
  min-height: 100dvh;
}

.boot {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  min-height: 100vh;
  min-height: 100dvh;
}

.boot__wave {
  width: 180px;
  opacity: 0.75;
  animation: breathe 1.6s ease-in-out infinite;
}

@keyframes breathe {
  0%,
  100% {
    opacity: 0.45;
  }
  50% {
    opacity: 0.9;
  }
}
</style>
