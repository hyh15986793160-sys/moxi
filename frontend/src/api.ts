import type { GameState, JoinResult, LeaveResult, PingResult, RoomPeek } from './types'

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    })
  } catch {
    throw new ApiError('网络断了，检查一下连接', 0)
  }

  if (!res.ok) {
    let detail = `请求失败（${res.status}）`
    try {
      const body = (await res.json()) as { detail?: unknown }
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* 响应不是 JSON，就用默认文案 */
    }
    throw new ApiError(detail, res.status)
  }

  return (await res.json()) as T
}

export const api = {
  createRoom: () => request<JoinResult>('/rooms', { method: 'POST' }),

  joinRoom: (code: string) =>
    request<JoinResult>(`/rooms/${encodeURIComponent(code)}/join`, { method: 'POST' }),

  /** 邀请链接落地前先探一下：房间还在不在、还有没有空位。 */
  peekRoom: (code: string) => request<RoomPeek>(`/rooms/${encodeURIComponent(code)}/peek`),

  getState: (code: string, playerId: string) =>
    request<GameState>(
      `/rooms/${encodeURIComponent(code)}?player_id=${encodeURIComponent(playerId)}`,
    ),

  /** 心跳：20 秒一次，既给座位续命，也用来发现"我已经不在房间里了"。 */
  ping: (code: string, playerId: string) =>
    request<PingResult>(
      `/rooms/${encodeURIComponent(code)}/ping?player_id=${encodeURIComponent(playerId)}`,
    ),

  submitWord: (code: string, playerId: string, word: string) =>
    request<GameState>(`/rooms/${encodeURIComponent(code)}/words`, {
      method: 'POST',
      body: JSON.stringify({ player_id: playerId, word }),
    }),

  /** 「这两个词算不算同一个意思」的表态。 */
  judge: (code: string, playerId: string, same: boolean) =>
    request<GameState>(`/rooms/${encodeURIComponent(code)}/judge`, {
      method: 'POST',
      body: JSON.stringify({ player_id: playerId, same }),
    }),

  /** 主动离开：腾出座位，房间空了服务端会直接销毁。 */
  leave: (code: string, playerId: string) =>
    request<LeaveResult>(`/rooms/${encodeURIComponent(code)}/leave`, {
      method: 'POST',
      body: JSON.stringify({ player_id: playerId }),
    }),

  nextRound: (code: string, playerId: string) =>
    request<GameState>(`/rooms/${encodeURIComponent(code)}/next`, {
      method: 'POST',
      body: JSON.stringify({ player_id: playerId }),
    }),

  restart: (code: string, playerId: string) =>
    request<GameState>(`/rooms/${encodeURIComponent(code)}/restart`, {
      method: 'POST',
      body: JSON.stringify({ player_id: playerId }),
    }),
}
