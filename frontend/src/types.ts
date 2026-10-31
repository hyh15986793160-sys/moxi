export type RoomStatus = 'waiting' | 'input' | 'judging' | 'revealed' | 'finished'

/** 单张玩家卡片的视觉阶段 */
export type PlayerPhase = 'ghost' | 'thinking' | 'locked' | 'revealed'

export interface Peer {
  slot: number
  submitted: boolean
  word: string | null
}

export interface Reveal {
  round: number
  /** [1 号位的词, 2 号位的词]，固定按座位顺序 */
  words: [string, string]
  matched: boolean
  /** true 表示这轮是两人商量后"算同一个"，不是字面撞上 */
  judged: boolean
}

export interface HistoryEntry {
  round: number
  words: [string, string]
  matched: boolean
  judged: boolean
}

/** 判定阶段：两个词字面不同，等双方表态算不算同一个意思 */
export interface Judging {
  enabled: boolean
  /** null = 还没表态 */
  me: boolean | null
  /** 自己没表态前对方的选择是不可见的 */
  opponent: boolean | null
}

export interface GameState {
  room_code: string
  status: RoomStatus
  round: number
  max_players: number
  /** 人满即锁，新人进不来 */
  locked: boolean
  me: Peer
  opponent: { joined: boolean; submitted: boolean; word: string | null }
  reveal: Reveal | null
  judging: Judging
  history: HistoryEntry[]
  rounds_played: number
  matched_round: number | null
  heartbeat_seconds: number
}

/** 邀请落地页在进房前看到的房间概况：只有人数和状态，没有词。 */
export interface RoomPeek {
  room_code: string
  status: RoomStatus
  players: number
  max_players: number
  full: boolean
  locked: boolean
  round: number
}

export interface JoinResult {
  room_code: string
  player_id: string
  slot: number
  state: GameState
}

/** 心跳回执：只回答"你还在不在"。 */
export interface PingResult {
  alive: boolean
  room_code: string
  status: RoomStatus
  round: number
  players: number
  locked: boolean
  next_ping_in: number
}

export interface LeaveResult {
  ok: boolean
  players: number
  destroyed: boolean
}
