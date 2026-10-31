/**
 * 全局对局状态。
 *
 * 这个游戏只有一个"页面级"状态，没必要上 pinia；
 * 一个模块级的 ref + 一组函数足够，组件直接 import。
 */

import { ref } from 'vue'

import { ApiError, api } from './api'
import { copyText } from './clipboard'
import { CODE_LEN, clearInviteFromLocation, extractRoomCode, inviteUrl } from './invite'
import type { GameState } from './types'

// 身份存 sessionStorage 而不是 localStorage：
// 一人两个标签页试玩时，两个标签页必须是两个玩家。sessionStorage 按标签页隔离，
// 刷新仍然保留；服务端还会接管超时未心跳的座位，所以关掉再开也能回到原座位。
const STORAGE_KEY = 'moxi.session.v1'
const POLL_INTERVAL = 900
/** 心跳周期，和服务端 HEARTBEAT_INTERVAL 对齐。 */
const HEARTBEAT_INTERVAL = 20_000

interface Session {
  roomCode: string
  playerId: string
}

export const state = ref<GameState | null>(null)
export const errorMsg = ref<string | null>(null)
export const busy = ref(false)
export const linkLost = ref(false)

/** 本地存着房间时才先压住首页，避免刷新时闪一下首页再跳回来。 */
export const restoring = ref(readSession() !== null)

let session: Session | null = null
let pollTimer: ReturnType<typeof setTimeout> | null = null
let heartbeatTimer: ReturnType<typeof setInterval> | null = null
let polling = false
let failStreak = 0
let errorTimer: ReturnType<typeof setTimeout> | null = null

function readSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<Session>
    if (typeof parsed.roomCode === 'string' && typeof parsed.playerId === 'string') {
      return { roomCode: parsed.roomCode, playerId: parsed.playerId }
    }
  } catch {
    /* 存的东西坏了就当没有 */
  }
  return null
}

function writeSession(next: Session | null) {
  session = next
  try {
    if (next) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* 隐私模式下 sessionStorage 可能不可写，忽略即可 */
  }
}

export function flashToast(message: string) {
  errorMsg.value = message
  if (errorTimer) clearTimeout(errorTimer)
  errorTimer = setTimeout(() => {
    errorMsg.value = null
  }, 3200)
}




function describe(err: unknown): string {
  if (err instanceof ApiError) return err.message
  return '出了点问题，再试一次'
}

function scheduleNextPoll() {
  if (!polling) return
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = setTimeout(pollOnce, POLL_INTERVAL)
}

/** 座位没了（房间被销毁、或者太久没动静被回收）：收摊回首页。 */
function handleSeatGone(message = '你已不在这个房间里了，回首页重新开一局吧') {
  stopPolling()
  writeSession(null)
  state.value = null
  flashToast(message)
}

async function pollOnce() {
  if (!polling || !session) return

  // 正在提交时跳过这一拍，用提交接口自己返回的状态，避免旧数据覆盖新数据。
  if (busy.value) {
    scheduleNextPoll()
    return
  }

  try {
    state.value = await api.getState(session.roomCode, session.playerId)
    failStreak = 0
    linkLost.value = false
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      stopPolling()
      writeSession(null)
      state.value = null
      flashToast('这一局已经不在了，回首页重新开一局吧')
      return
    }
    failStreak += 1
    if (failStreak >= 2) linkLost.value = true
  }

  scheduleNextPoll()
}

/**
 * 心跳：每 20 秒问一次"我还在这个房间吗"。
 *
 * 它和轮询是两条独立的生命线——轮询负责同步牌面，心跳只负责证明座位还有人。
 * 分开的好处是：某一拍轮询卡住（比如正在提交、请求慢），不会连带把座位判死。
 * 页面切回前台时立刻补一次，顺手把后台被浏览器压住的定时器追回来。
 */
async function heartbeatOnce() {
  const current = session
  if (!current) return
  try {
    await api.ping(current.roomCode, current.playerId)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      handleSeatGone()
    }
    // 网络抖一下就等下一拍，交给轮询那边的"连接断开"提示去说
  }
}

function startHeartbeat() {
  if (heartbeatTimer) return
  heartbeatTimer = setInterval(() => {
    void heartbeatOnce()
  }, HEARTBEAT_INTERVAL)
}

function stopHeartbeat() {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer)
    heartbeatTimer = null
  }
}

/** 切回前台立刻补一拍，别等下一个 20 秒。 */
function wakeUp() {
  if (document.visibilityState !== 'visible') return
  if (!session) return
  void heartbeatOnce()
  if (polling && !busy.value) void pollOnce()
}

if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', wakeUp)
}

export function startPolling() {
  if (polling) return
  polling = true
  failStreak = 0
  startHeartbeat()
  scheduleNextPoll()
}

export function stopPolling() {
  polling = false
  stopHeartbeat()
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

/** 刷新页面后用本地存的房间号回到牌桌。 */
export async function restore() {
  const saved = readSession()
  if (!saved) {
    restoring.value = false
    return
  }
  try {
    state.value = await api.getState(saved.roomCode, saved.playerId)
    writeSession(saved)
    // 已经在局里了，地址栏里的邀请码就多余了。
    clearInviteFromLocation()
    startPolling()
  } catch {
    writeSession(null)
  } finally {
    restoring.value = false
  }
}

export async function createRoom() {
  if (busy.value) return
  busy.value = true
  try {
    const res = await api.createRoom()
    writeSession({ roomCode: res.room_code, playerId: res.player_id })
    state.value = res.state
    startPolling()
  } catch (err) {
    flashToast(describe(err))
  } finally {
    busy.value = false
  }
}

/**
 * 加入房间。参数可以是 6 位房间码，也可以是好友发来的整条邀请链接。
 * 返回是否真的进去了——邀请落地页要靠它决定要不要提示错误。
 */
export async function joinRoom(raw: string): Promise<boolean> {
  const clean = extractRoomCode(raw)
  if (clean.length !== CODE_LEN) {
    flashToast('房间码是 6 位')
    return false
  }
  if (busy.value) return false
  busy.value = true
  try {
    const res = await api.joinRoom(clean)
    writeSession({ roomCode: res.room_code, playerId: res.player_id })
    state.value = res.state
    clearInviteFromLocation()
    startPolling()
    return true
  } catch (err) {
    const e = err as ApiError
    if (e.status === 404) flashToast('没有这个房间，检查一下房间码')
    else if (e.status === 409) flashToast('这个房间已经坐满了，让房主另开一局')
    else flashToast(describe(err))
    return false
  } finally {
    busy.value = false
  }
}

export async function submitWord(word: string): Promise<boolean> {
  if (!session || busy.value) return false
  const text = word.trim()
  if (!text) {
    flashToast('先写一个词')
    return false
  }
  busy.value = true
  try {
    state.value = await api.submitWord(session.roomCode, session.playerId, text)
    return true
  } catch (err) {
    flashToast(describe(err))
    // 状态可能过期了（比如对方已经开了下一轮），立刻同步一次。
    void pollOnce()
    return false
  } finally {
    busy.value = false
  }
}

export async function goNextRound() {
  if (!session || busy.value) return
  busy.value = true
  try {
    state.value = await api.nextRound(session.roomCode, session.playerId)
  } catch (err) {
    flashToast(describe(err))
    void pollOnce()
  } finally {
    busy.value = false
  }
}

/**
 * 「猪」和「小猪」算不算同一个意思？
 *
 * 说"不算"一票否决，立刻进入下一轮；说"算"要两个人都点头。
 * 服务端只在 JUDGING 阶段接受这个操作，所以重复点也不会出事。
 */
export async function judgeWords(same: boolean) {
  if (!session || busy.value) return
  busy.value = true
  try {
    state.value = await api.judge(session.roomCode, session.playerId, same)
  } catch (err) {
    flashToast(describe(err))
    void pollOnce()
  } finally {
    busy.value = false
  }
}

export async function restartGame() {
  if (!session || busy.value) return
  busy.value = true
  try {
    state.value = await api.restart(session.roomCode, session.playerId)
  } catch (err) {
    flashToast(describe(err))
    void pollOnce()
  } finally {
    busy.value = false
  }
}

/** 复制这一局的邀请链接（不是房间码）。 */
export async function copyInviteLink(code: string): Promise<void> {
  const link = inviteUrl(code)
  const ok = await copyText(link)
  flashToast(ok ? '邀请链接已复制，发给对方就行' : `邀请码：${code}`)
}

/** 手机上有系统分享面板就用它（能直接发到微信），没有就退回复制。 */
export async function shareInvite(code: string): Promise<void> {
  const url = inviteUrl(code)
  const nav = navigator as Navigator & {
    share?: (data: ShareData) => Promise<void>
  }

  if (typeof nav.share === 'function') {
    try {
      await nav.share({
        title: '摩西摩西 · 两个人各写一个词',
        text: `来一局摩西摩西，房间码 ${code}`,
        url,
      })
      return
    } catch (err) {
      // 用户自己点了取消，不是错误
      if ((err as DOMException | undefined)?.name === 'AbortError') return
    }
  }

  await copyInviteLink(code)
}

/**
 * 离开房间。
 *
 * 先告诉服务端"我走了"：座位立刻腾出来，最后一个人走的时候房间就地销毁，
 * 不用等两分半的心跳超时。请求发出去就不管了，失败了也不影响本地退出。
 */
export function leaveRoom() {
  const current = session
  stopPolling()
  writeSession(null)
  state.value = null
  linkLost.value = false
  errorMsg.value = null
  clearInviteFromLocation()

  if (current) {
    void api.leave(current.roomCode, current.playerId).catch(() => {
      /* 房间可能早就没了，无所谓 */
    })
  }
}
