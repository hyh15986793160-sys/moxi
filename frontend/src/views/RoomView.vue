<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import Confetti from '../components/Confetti.vue'
import PlayerCard from '../components/PlayerCard.vue'
import QrCode from '../components/QrCode.vue'
import WaveMark from '../components/WaveMark.vue'
import { copyText } from '../clipboard'
import { inviteUrl } from '../invite'
import {
  busy,
  copyInviteLink,
  flashToast,
  goNextRound,
  judgeWords,
  leaveRoom,
  linkLost,
  restartGame,
  shareInvite,
  state,
  stopPolling,
  submitWord,
} from '../state'
import type { GameState, HistoryEntry, PlayerPhase } from '../types'

const g = computed(() => state.value as GameState)

const draft = ref('')
const inputEl = ref<HTMLInputElement | null>(null)
const showConfetti = ref(false)

const link = computed(() => inviteUrl(g.value.room_code))
// 系统分享面板只在触屏设备上才有意义（能直接选微信）；桌面上复制链接更顺手。
const canShare =
  typeof navigator !== 'undefined' &&
  typeof navigator.share === 'function' &&
  window.matchMedia('(pointer: coarse)').matches

const myIndex = computed<0 | 1>(() => (state.value?.me.slot === 1 ? 1 : 0))
const matched = computed(() => g.value.status === 'finished')
const judging = computed(() => g.value.status === 'judging')
const myVote = computed(() => g.value.judging.me)
const theirVote = computed(() => g.value.judging.opponent)

// ── 卡片阶段 ──────────────────────────────────────
const myPhase = computed<PlayerPhase>(() => {
  const s = g.value
  if (s.status === 'judging' || s.status === 'revealed' || s.status === 'finished') return 'revealed'
  if (s.status === 'waiting') return 'ghost'
  return s.me.submitted ? 'locked' : 'thinking'
})

const theirPhase = computed<PlayerPhase>(() => {
  const s = g.value
  if (!s.opponent.joined) return 'ghost'
  if (s.status === 'judging' || s.status === 'revealed' || s.status === 'finished') return 'revealed'
  return s.opponent.submitted ? 'locked' : 'thinking'
})

const myHint = computed(() => {
  switch (g.value.status) {
    case 'waiting':
      return '等待中'
    case 'input':
      return g.value.me.submitted ? '已锁定' : '该你了'
    default:
      return '已揭晓'
  }
})

const theirHint = computed(() => {
  const s = g.value
  if (!s.opponent.joined) return '还没进来'
  if (s.status === 'judging' || s.status === 'revealed' || s.status === 'finished') return '已揭晓'
  return s.opponent.submitted ? '已锁定' : '思考中'
})

const eyebrow = computed(() => {
  switch (g.value.status) {
    case 'waiting':
      return '等对方进场'
    case 'input':
      return g.value.me.submitted ? '等对方交卷' : '各写一个词'
    case 'judging':
      return '揭晓 · 等你判断'
    case 'revealed':
      return '揭晓 · 没撞上'
    default:
      return '揭晓 · 撞上了'
  }
})

const hitLine = computed(() => {
  const n = g.value.rounds_played
  const judged = g.value.reveal?.judged
  if (judged) return `第 ${n} 轮，你们把两个词判成了同一个`
  return n <= 1 ? '第一轮就想到一块去了' : `${n} 轮之后，你们写下了同一个词`
})

// ── 动作 ─────────────────────────────────────────
async function onSubmit() {
  const text = draft.value.trim()
  if (!text) return
  draft.value = ''
  const ok = await submitWord(text)
  if (!ok) draft.value = text // 没交上去就把内容还给用户
}

async function copyCode() {
  const code = g.value.room_code
  const ok = await copyText(code)
  flashToast(ok ? `房间码 ${code} 已复制` : `房间码：${code}`)
}

function copyLink() {
  void copyInviteLink(g.value.room_code)
}

function shareTo() {
  void shareInvite(g.value.room_code)
}

function mineOf(entry: HistoryEntry) {
  return entry.words[myIndex.value]
}

function theirsOf(entry: HistoryEntry) {
  return entry.words[myIndex.value === 0 ? 1 : 0]
}

/** ✓ 字面撞上，≈ 两人判定算同一个，× 没撞上，? 还在判定中 */
function markOf(entry: HistoryEntry) {
  if (!entry.matched) {
    // 正在商量的这一轮还没定论，先别急着打叉
    if (judging.value && entry.round === g.value.round) return '?'
    return '×'
  }
  return entry.judged ? '≈' : '✓'
}

function vote(same: boolean) {
  void judgeWords(same)
}

// ── 焦点与庆祝 ────────────────────────────────────
watch(
  () => [g.value.status, g.value.me.submitted] as const,
  async ([status, submitted]) => {
    if (status === 'input' && !submitted) {
      await nextTick()
      inputEl.value?.focus()
    }
  },
)

watch(
  () => g.value.status,
  (next, prev) => {
    if (next === 'finished' && prev !== 'finished') {
      showConfetti.value = true
      window.setTimeout(() => {
        showConfetti.value = false
      }, 2400)
    }
  },
  { immediate: true },
)

onUnmounted(stopPolling)
</script>

<template>
  <div class="room">
    <header class="bar">
      <div class="bar__brand">
        <span class="bar__wave"><WaveMark :aligned="matched" /></span>
        <span class="bar__name">摩西摩西</span>
      </div>
      <div class="bar__tools">
        <button class="chip" type="button" title="复制房间码" @click="copyCode">
          <span class="chip__key">房间</span>
          <span class="chip__val">{{ g.room_code }}</span>
          <span v-if="g.locked" class="chip__lock" title="房间已锁，新人进不来">已锁</span>
        </button>
        <button class="chip chip--quiet" type="button" @click="leaveRoom">离开</button>
      </div>
    </header>

    <p v-if="linkLost" class="offline">连接断开，正在重试…</p>

    <main class="table">
      <div class="table__inner">
        <p class="eyebrow">
          <span class="eyebrow__round">第 {{ g.round }} 轮</span>
          <span class="eyebrow__dot" />
          <span>{{ eyebrow }}</span>
        </p>

        <div class="board">
          <PlayerCard
            label="你"
            tone="me"
            :hint="myHint"
            :word="g.me.word"
            :phase="myPhase"
            :matched="matched"
            placeholder="已就位"
          />

          <div class="board__spine"><span class="board__node" /></div>

          <PlayerCard
            label="对方"
            tone="them"
            :hint="theirHint"
            :word="g.opponent.word"
            :phase="theirPhase"
            :matched="matched"
            placeholder="等你把邀请发过去"
          />
        </div>

        <section class="dock">
          <!-- 等第二个人：房间码 + 二维码 + 链接，三种发法随便挑 -->
          <div v-if="g.status === 'waiting'" class="invite">
            <p class="invite__title">把这一局发给对方</p>

            <div class="invite__panel">
              <div class="invite__side">
                <button class="invite__code" type="button" title="复制房间码" @click="copyCode">
                  {{ g.room_code }}
                </button>
                <p class="invite__hint">当面玩就念这 6 位，点一下复制</p>
              </div>

              <figure class="invite__qr">
                <QrCode :value="link" :size="104" />
                <figcaption>扫码加入</figcaption>
              </figure>
            </div>

            <div class="invite__actions">
              <button class="btn btn--primary" type="button" @click="copyLink">
                复制邀请链接
              </button>
              <button v-if="canShare" class="btn btn--ghost" type="button" @click="shareTo">
                发给好友
              </button>
            </div>

            <p class="invite__note">对方点开链接就直接进这一局了</p>
          </div>

          <!-- 该你写词 -->
          <form
            v-else-if="g.status === 'input' && !g.me.submitted"
            class="compose"
            @submit.prevent="onSubmit"
          >
            <input
              ref="inputEl"
              v-model="draft"
              class="compose__input"
              maxlength="24"
              autocomplete="off"
              placeholder="写一个词…"
              aria-label="本轮的词"
            />
            <button
              class="btn btn--primary compose__send"
              type="submit"
              :disabled="busy || !draft.trim()"
            >
              提交
            </button>
          </form>

          <!-- 已交，等对方 -->
          <div v-else-if="g.status === 'input'" class="wait">
            <span class="wait__pulse" />
            已锁定，等对方交卷
          </div>

          <!-- 揭晓：两个词不一样，但可能只是说法不同，让两个人自己判断 -->
          <div v-else-if="judging" class="result result--judge">
            <p class="result__title">算同一个意思吗？</p>
            <p class="result__sub">
              字面不同，但可能只是叫法不一样。<br />
              说「算」要两个人都点头，说「不算」直接进下一轮。
            </p>

            <div v-if="myVote === null" class="verdict">
              <button class="btn btn--gold" type="button" :disabled="busy" @click="vote(true)">
                算同一个
              </button>
              <button class="btn btn--ghost" type="button" :disabled="busy" @click="vote(false)">
                不算
              </button>
            </div>

            <div v-else class="verdict verdict--waiting">
              <p class="verdict__mine">{{ myVote ? '你说了算同一个' : '你说了不算' }}</p>
              <p class="verdict__peer">
                {{ theirVote === null ? '等对方表态…' : theirVote ? '对方也说算同一个' : '对方觉得不算' }}
              </p>
            </div>
          </div>

          <!-- 揭晓：没撞上 -->
          <div v-else-if="g.status === 'revealed'" class="result">
            <p class="result__title">差一点</p>
            <p class="result__sub">两个念头，再来一次</p>
            <button class="btn btn--primary" type="button" :disabled="busy" @click="goNextRound">
              下一轮
            </button>
          </div>

          <!-- 揭晓：撞上了 -->
          <div v-else class="result result--hit">
            <p class="result__title">同频</p>
            <p class="result__sub">{{ hitLine }}</p>
            <button class="btn btn--gold" type="button" :disabled="busy" @click="restartGame">
              再来一局
            </button>
          </div>
        </section>

        <ol v-if="g.history.length" class="history">
          <li
            v-for="entry in g.history"
            :key="entry.round"
            class="history__item"
            :class="{
              'is-hit': entry.matched,
              'is-pending': judging && !entry.matched && entry.round === g.round,
            }"
          >
            <span class="history__no">{{ entry.round }}</span>
            <span class="history__word">{{ mineOf(entry) }}</span>
            <span class="history__sep">/</span>
            <span class="history__word">{{ theirsOf(entry) }}</span>
            <span class="history__mark">{{ markOf(entry) }}</span>
          </li>
        </ol>
      </div>
    </main>

    <Confetti v-if="showConfetti" />
  </div>
</template>

<style scoped>
.room {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
}

/* ── 顶栏 ─────────────────────────────────────── */
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px clamp(16px, 4vw, 40px);
}

.bar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bar__wave {
  width: 54px;
  opacity: 0.85;
}

.bar__name {
  font-size: 14px;
  letter-spacing: 0.34em;
  color: var(--ink-2);
}

.bar__tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
  -webkit-tap-highlight-color: transparent;
}

.chip:hover {
  border-color: var(--line-strong);
  background: rgba(255, 255, 255, 0.08);
}

.chip__key {
  font-size: 11px;
  letter-spacing: 0.1em;
  color: var(--ink-3);
}

.chip__val {
  font-family: var(--mono);
  font-size: 13px;
  letter-spacing: 0.16em;
  color: var(--ink);
}

.chip__lock {
  padding: 1px 7px;
  border-radius: 999px;
  background: rgba(255, 211, 122, 0.13);
  font-size: 10.5px;
  letter-spacing: 0.08em;
  color: rgba(255, 230, 171, 0.92);
}

.chip--quiet {
  font-size: 13px;
  color: var(--ink-3);
}

/* ── 主体 ─────────────────────────────────────── */
.table {
  flex: 1;
  display: flex;
  width: 100%;
  max-width: 780px;
  margin: 0 auto;
  padding: 16px 20px;
}

/* 内容比视口矮时上下均分留白（居中），比视口高时 auto 退化为 0 从顶部开始，
   不会像 justify-content:center 那样把上半截裁掉。 */
.table__inner {
  width: 100%;
  margin: auto;
}

.eyebrow {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 0 0 clamp(22px, 4.4vh, 40px);
  font-size: 12.5px;
  letter-spacing: 0.16em;
  color: var(--ink-3);
}

.eyebrow__round {
  color: var(--ink-2);
}

.eyebrow__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--ink-3);
}

.board {
  display: grid;
  grid-template-columns: 1fr 56px 1fr;
  align-items: stretch;
}

.board__spine {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.board__spine::before {
  content: '';
  position: absolute;
  top: 14%;
  bottom: 14%;
  width: 1px;
  background: linear-gradient(180deg, transparent, var(--line-strong), transparent);
}

.board__node {
  position: relative;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ink-3);
  box-shadow: 0 0 0 5px rgba(255, 255, 255, 0.035);
}

/* ── 操作区 ───────────────────────────────────── */
.dock {
  margin-top: clamp(26px, 5vh, 44px);
}

.compose {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 520px;
  margin: 0 auto;
  padding: 7px 7px 7px 22px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.045);
  transition:
    border-color 0.25s ease,
    box-shadow 0.3s ease;
}

.compose:focus-within {
  border-color: rgba(99, 230, 255, 0.45);
  box-shadow:
    0 0 0 5px rgba(99, 230, 255, 0.07),
    0 20px 50px -34px rgba(99, 230, 255, 0.9);
}

.compose__input {
  flex: 1;
  min-width: 0;
  padding: 10px 0;
  border: none;
  outline: none;
  background: none;
  font-size: 18px;
  color: var(--ink);
}

.compose__input::placeholder {
  color: var(--ink-3);
}

.compose__send {
  padding: 12px 26px;
  font-size: 14.5px;
}

.wait {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 18px;
  font-size: 14.5px;
  letter-spacing: 0.07em;
  color: var(--ink-2);
}

.wait__pulse {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--cyan);
  animation: halo 1.9s ease-out infinite;
}

@keyframes halo {
  0% {
    box-shadow: 0 0 0 0 rgba(99, 230, 255, 0.5);
  }
  70% {
    box-shadow: 0 0 0 15px rgba(99, 230, 255, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(99, 230, 255, 0);
  }
}

.invite {
  text-align: center;
  animation: rise 0.5s cubic-bezier(0.2, 0.8, 0.3, 1) both;
}

.invite__title {
  margin: 0 0 16px;
  font-size: 12.5px;
  letter-spacing: 0.16em;
  color: var(--ink-3);
}

.invite__panel {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  max-width: 460px;
  margin: 0 auto;
  padding: 18px 22px;
  border: 1px dashed rgba(255, 255, 255, 0.18);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.022);
}

.invite__side {
  flex: 1;
  min-width: 0;
  text-align: center;
}

.invite__code {
  display: block;
  width: 100%;
  padding: 2px 4px;
  border: none;
  background: none;
  font-family: var(--mono);
  font-size: 24px;
  letter-spacing: 0.34em;
  text-indent: 0.34em;
  color: var(--ink);
  cursor: pointer;
  transition: color 0.25s ease;
}

.invite__code:hover {
  color: #d8f8ff;
}

.invite__hint {
  margin: 8px 0 0;
  font-size: 11.5px;
  color: #7d87a6;
}

.invite__qr {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.invite__qr figcaption {
  font-size: 10.5px;
  letter-spacing: 0.16em;
  color: var(--ink-3);
}

.invite__actions {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 18px;
}

.invite__actions .btn {
  padding: 12px 24px;
  font-size: 14px;
}

.invite__note {
  margin: 12px 0 0;
  font-size: 11.5px;
  letter-spacing: 0.04em;
  color: #7d87a6;
}

.result {
  text-align: center;
  animation: rise 0.45s cubic-bezier(0.2, 0.8, 0.3, 1) both;
}

.result__title {
  margin: 0;
  font-size: 28px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-indent: 0.16em;
  color: var(--ink);
}

.result--hit .result__title {
  font-size: clamp(38px, 8vw, 52px);
  letter-spacing: 0.24em;
  text-indent: 0.24em;
  color: #ffe6ab;
  text-shadow: 0 0 44px rgba(255, 211, 122, 0.5);
}

.result__sub {
  margin: 12px 0 24px;
  font-size: 13px;
  letter-spacing: 0.08em;
  color: var(--ink-2);
}

/* ── 判定：算不算同一个意思 ───────────────────── */
.result--judge .result__title {
  font-size: clamp(22px, 5.4vw, 28px);
  letter-spacing: 0.1em;
  text-indent: 0.1em;
}

.result--judge .result__sub {
  line-height: 1.9;
}

.verdict {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}

.verdict .btn {
  min-width: 132px;
  padding: 13px 26px;
  font-size: 14.5px;
}

/* 投完票：把自己和对方的选择都摆出来，别让人对着屏幕猜 */
.verdict--waiting {
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.verdict__mine {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0.08em;
  color: var(--ink);
}

.verdict__peer {
  margin: 0;
  font-size: 12.5px;
  letter-spacing: 0.06em;
  color: var(--ink-3);
}

/* ── 历史 ─────────────────────────────────────── */
.history {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin: 46px 0 0;
  padding: 0;
  list-style: none;
}

.history__item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 13px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.028);
  font-size: 12.5px;
  color: var(--ink-3);
}

.history__item.is-hit {
  border-color: rgba(255, 211, 122, 0.34);
  background: rgba(255, 211, 122, 0.07);
}

.history__no {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink-2);
  opacity: 0.8;
}

.history__word {
  color: var(--ink-2);
}

.is-hit .history__word {
  color: #ffe6ab;
}

.history__sep {
  color: var(--ink-3);
  opacity: 0.9;
}

.history__mark {
  font-size: 12px;
  line-height: 1;
}

.history__item:not(.is-hit) .history__mark {
  color: var(--rose);
  opacity: 0.85;
}

.history__item.is-pending .history__mark {
  color: var(--ink-2);
  opacity: 0.9;
}

.history__item.is-hit .history__mark {
  color: var(--gold);
}

/* ── 断线提示 ─────────────────────────────────── */
.offline {
  position: fixed;
  inset: 0 0 auto;
  z-index: 50;
  margin: 0;
  padding: 7px;
  text-align: center;
  font-size: 12.5px;
  letter-spacing: 0.08em;
  background: rgba(255, 139, 158, 0.16);
  color: #ffd2d9;
  backdrop-filter: blur(10px);
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
}

/* ── 移动端：两张卡改成上下叠 ─────────────────── */
@media (max-width: 720px) {
  .board {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .board__spine {
    height: 34px;
  }

  .board__spine::before {
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    width: auto;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--line-strong), transparent);
  }

  .bar__name {
    font-size: 12px;
    letter-spacing: 0.28em;
  }

  .bar__wave {
    width: 42px;
  }

  .chip__key {
    display: none;
  }
}

/* 窄屏：邀请区收紧，二维码缩一点，按钮占满一行 */
@media (max-width: 560px) {
  .invite__panel {
    gap: 16px;
    padding: 14px 16px;
  }

  .invite__code {
    font-size: 19px;
    letter-spacing: 0.26em;
    text-indent: 0.26em;
  }

  .invite__qr .qr {
    width: 86px;
    height: 86px;
  }

  .invite__actions {
    flex-direction: column;
  }

  .invite__actions .btn {
    width: 100%;
  }
}
</style>
