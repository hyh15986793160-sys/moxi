<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import WaveMark from '../components/WaveMark.vue'
import { ApiError, api } from '../api'
import { CODE_LEN, clearInviteFromLocation, extractRoomCode, inviteFromLocation } from '../invite'
import { busy, createRoom, joinRoom } from '../state'

const code = ref('')

/** 从邀请链接进来时，这里存着那个房间码。 */
const invited = ref<string | null>(null)
const inviteNote = ref<string | null>(null)
const checking = ref(false)
/** 打听过之后确认房间坐满了：这时候按钮就别让人点了。 */
const roomFull = ref(false)

watch(code, (value) => {
  // 直接粘整条邀请链接也能认出来
  const clean = extractRoomCode(value)
  if (clean !== value) code.value = clean
  // 换了一个房间码，之前"已满"的判断就作废
  if (clean !== invited.value) roomFull.value = false
})

const canJoin = computed(
  () => code.value.length === 6 && !busy.value && !checking.value && !roomFull.value,
)

function handleJoin() {
  if (!canJoin.value) return
  void joinRoom(code.value)
}

/**
 * 直接粘整条邀请链接：输入框只有 6 格，会被截成 "http:/"，
 * 所以在粘贴这一步就先从剪贴板里把房间码抠出来。
 */
function onPaste(event: ClipboardEvent) {
  const text = event.clipboardData?.getData('text') ?? ''
  const extracted = extractRoomCode(text)
  if (extracted.length !== CODE_LEN) return // 本来就只粘了 6 位，交给默认行为
  event.preventDefault()
  code.value = extracted
}

onMounted(() => {
  const invite = inviteFromLocation()
  if (!invite) return
  invited.value = invite
  code.value = invite
  void enterInvitedRoom(invite)
})

/**
 * 点开邀请链接：先探一眼房间，还有空位就直接进去，省掉一次点击。
 * 满了或者过期了，就把决定权还给用户。
 */
async function enterInvitedRoom(invite: string) {
  checking.value = true
  try {
    const peek = await api.peekRoom(invite)
    if (peek.full) {
      // 房间锁：满了就是满了，不会为了让你进来把先到的人踹走
      roomFull.value = true
      inviteNote.value = '这一局已经坐满了。让房主另开一局，或者等这个房间过期'
      return
    }
    roomFull.value = false
    inviteNote.value = null
    await joinRoom(invite)
  } catch (err) {
    inviteNote.value =
      err instanceof ApiError && err.status === 404
        ? '这个房间已经不在了，可能开得太久过期了'
        : '没连上服务器，稍后再点一次加入'
  } finally {
    checking.value = false
  }
}

function dismissInvite() {
  invited.value = null
  inviteNote.value = null
  code.value = ''
  clearInviteFromLocation()
}
</script>

<template>
  <div class="home">
    <div class="home__mark">
      <WaveMark />
    </div>

    <h1 class="wordmark">摩西摩西</h1>
    <p class="home__tagline">两个人，各写一个词<br />撞上了，就赢了</p>

    <!-- 从邀请链接进来：直接给一个「加入这一局」 -->
    <section v-if="invited" class="invite">
      <p class="invite__label">有人邀你入局</p>
      <p class="invite__code">{{ invited }}</p>
      <p v-if="inviteNote" class="invite__note">{{ inviteNote }}</p>
      <p v-else-if="checking" class="invite__note">正在进房间…</p>
      <div class="invite__actions">
        <button class="btn btn--primary" type="button" :disabled="!canJoin" @click="handleJoin">
          {{ roomFull ? '房间已满' : '加入这一局' }}
        </button>
        <button class="invite__quiet" type="button" @click="dismissInvite">先不玩</button>
      </div>
    </section>

    <template v-else>
      <button class="btn btn--primary home__cta" :disabled="busy" @click="createRoom">
        开一局
      </button>

      <div class="rule home__rule">或者加入</div>

      <form class="home__join" @submit.prevent="handleJoin">
        <input
          v-model="code"
          class="home__code"
          inputmode="text"
          autocomplete="off"
          autocapitalize="characters"
          spellcheck="false"
          maxlength="6"
          placeholder="房间码"
          aria-label="房间码"
          @paste="onPaste"
        />
        <button class="btn btn--ghost" type="submit" :disabled="!canJoin">加入</button>
      </form>
    </template>

    <p class="home__note">
      每轮各自写下想到的那个词，同时揭晓。<br />
      一样，立刻结束；不一样，你们可以自己判一句「算不算同一个意思」。
    </p>

    <footer class="legal">
      <p class="legal__line">
        一个纯娱乐的小游戏 · 不需要注册 · 不收集个人信息 · 房间数据只存在内存里，人走光就销毁
      </p>
      <details class="legal__more">
        <summary>免责声明</summary>
        <div class="legal__body">
          <p>
            本项目（摩西摩西 / moxi）是开源的娱乐玩具，按「现状」提供，不附带任何明示或暗示的担保，
            包括但不限于可用性、无中断、无错误或适用于特定用途。
          </p>
          <p>
            房间数据仅保存在服务进程的内存中：服务重启、房间闲置过期，或者房间内所有人离开后，
            数据就会消失，无法恢复。请不要用它传递任何重要或敏感内容。
          </p>
          <p>
            本服务不要求注册，也不主动收集姓名、手机号、邮箱等个人身份信息；
            但任何网络服务都不可避免地会产生访问日志（IP、时间、请求路径），
            这些日志仅用于排查故障与安全防护，不用于画像、营销或向第三方出售。
          </p>
          <p>
            因使用或无法使用本服务造成的任何直接或间接损失，包括但不限于数据丢失、游戏中止、
            情绪不适，作者不承担责任。请勿提交违法、侵权、骚扰或令人不适的内容；
            因用户输入内容引发的纠纷由发布者自行承担。
          </p>
          <p>
            如你在页面上看到不当内容，或希望删除某个房间的数据，请通过项目仓库的 Issue 联系作者。
          </p>
        </div>
      </details>
    </footer>
  </div>
</template>

<style scoped>
.home {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  max-width: 480px;
  min-height: 100vh;
  min-height: 100dvh;
  margin: 0 auto;
  padding: clamp(40px, 8vh, 80px) 24px;
  text-align: center;
  animation: rise 0.7s cubic-bezier(0.2, 0.8, 0.3, 1) both;
}

.home__mark {
  width: 236px;
  opacity: 0.92;
  margin-bottom: 4px;
}

.wordmark {
  margin: 0;
  /* 四个字的站名，字号比原来的两字版收一档，免得手机上撑破 */
  font-size: clamp(38px, 10.5vw, 62px);
  font-weight: 250;
  line-height: 1;
  letter-spacing: 0.1em;
  text-indent: 0.1em;
  white-space: nowrap;
  background: linear-gradient(180deg, #ffffff 0%, #b9c8e6 58%, #6b7d9e 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.home__tagline {
  margin: 18px 0 0;
  font-size: 15px;
  line-height: 1.85;
  color: var(--ink-2);
  letter-spacing: 0.06em;
}

.home__cta {
  margin-top: 40px;
  min-width: 200px;
  padding: 16px 34px;
  font-size: 16px;
}

.home__rule {
  width: 100%;
  margin: 38px 0 22px;
}

.home__join {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  max-width: 320px;
}

.home__code {
  flex: 1;
  min-width: 0;
  height: 52px;
  padding: 0 18px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.04);
  font-family: var(--mono);
  font-size: 17px;
  letter-spacing: 0.28em;
  text-align: center;
  text-indent: 0.28em;
  text-transform: uppercase;
  color: var(--ink);
  outline: none;
  transition:
    border-color 0.25s ease,
    box-shadow 0.25s ease;
}

.home__join .btn {
  height: 52px;
  padding: 0 26px;
}

.home__code::placeholder {
  font-family: var(--font);
  font-size: 14px;
  letter-spacing: 0.14em;
  text-indent: 0.14em;
  color: var(--ink-3);
}

.home__code:focus {
  border-color: rgba(99, 230, 255, 0.45);
  box-shadow: 0 0 0 4px rgba(99, 230, 255, 0.07);
}

.home__note {
  margin: 46px 0 0;
  font-size: 12.5px;
  line-height: 1.9;
  color: #8d97b5;
}

/* ── 免责声明 ─────────────────────────────────── */
.legal {
  margin-top: 34px;
  font-size: 11.5px;
  line-height: 1.85;
  color: #6b7494;
}

.legal__line {
  margin: 0;
}

.legal__more {
  margin-top: 10px;
}

.legal__more summary {
  display: inline-block;
  padding: 2px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 11.5px;
  letter-spacing: 0.08em;
  color: #7d87a6;
  cursor: pointer;
  list-style: none;
  transition: color 0.2s ease, border-color 0.2s ease;
}

.legal__more summary::-webkit-details-marker {
  display: none;
}

.legal__more summary:hover {
  color: var(--ink-2);
  border-color: rgba(255, 255, 255, 0.22);
}

.legal__body {
  margin-top: 14px;
  padding: 16px 18px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.022);
  text-align: left;
  animation: rise 0.35s ease both;
}

.legal__body p {
  margin: 0 0 10px;
}

.legal__body p:last-child {
  margin-bottom: 0;
}

/* ── 邀请落地 ─────────────────────────────────── */
.invite {
  width: 100%;
  max-width: 330px;
  margin-top: 36px;
  padding: 22px 24px 18px;
  border: 1px solid rgba(99, 230, 255, 0.2);
  border-radius: 20px;
  background:
    radial-gradient(120% 130% at 50% 0%, rgba(99, 230, 255, 0.1), transparent 62%),
    rgba(255, 255, 255, 0.03);
  box-shadow:
    0 30px 74px -54px rgba(99, 230, 255, 0.95),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  animation: rise 0.6s cubic-bezier(0.2, 0.8, 0.3, 1) both;
}

.invite__label {
  margin: 0;
  font-size: 11.5px;
  letter-spacing: 0.28em;
  text-indent: 0.28em;
  color: var(--cyan);
  opacity: 0.9;
}

.invite__code {
  margin: 14px 0 0;
  font-family: var(--mono);
  font-size: 26px;
  letter-spacing: 0.34em;
  text-indent: 0.34em;
  color: var(--ink);
}

.invite__note {
  margin: 12px 0 0;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--ink-2);
}

.invite__actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 20px;
}

.invite__actions .btn {
  width: 100%;
  padding: 14px 24px;
  font-size: 15px;
}

.invite__quiet {
  padding: 10px;
  border: none;
  background: none;
  font-size: 12.5px;
  letter-spacing: 0.1em;
  color: var(--ink-3);
  cursor: pointer;
  transition: color 0.2s ease;
}

.invite__quiet:hover {
  color: var(--ink-2);
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
}

@media (max-width: 420px) {
  .home__join {
    flex-direction: column;
    align-items: stretch;
    max-width: 300px;
  }

  .home__code {
    flex: none;
    width: 100%;
  }

  .home__join .btn {
    width: 100%;
  }
}
</style>
