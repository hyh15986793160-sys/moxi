"""房间状态存储与游戏规则。

设计要点（README 里有更长的说明）：

* 全部状态放内存，单进程单锁。这个游戏一局的并发量极小，
  用不上 Redis；容器重启丢房间是可以接受的代价。
* **视图裁剪发生在服务端**：对方还没提交时，他的词根本不会离开
  这个模块，前端拿不到，也就无从作弊。
* 比较用规范化后的词，展示用原始输入。
* **房间是一次性的**：人满即锁，谁也顶不掉谁；人走光即销毁。
"""

from __future__ import annotations

import re
import secrets
import threading
import time
import unicodedata
from dataclasses import dataclass, field

# 房间码字符集去掉了 I/O/0/1，避免口头念房间号时听错。
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LEN = 6

MAX_PLAYERS = 2
MAX_WORD_LEN = 24
ROOM_IDLE_TTL = 6 * 3600  # 6 小时没人动过就回收

# 前端每 20 秒心跳一次。正常情况下三拍不来就算走了——
# 但浏览器会把后台标签页的定时器压到一分钟一次，所以放宽到
# 2.5 分钟，免得把「切出去回个微信」的人误判成掉线。
# 注意回收是"作废"，不是"让给后来的人坐"，后者会让先来的人被人顶掉。
SEAT_TIMEOUT = 150.0
HEARTBEAT_INTERVAL = 20  # 秒，同时写给前端，改这里就两端一起变

STATUS_WAITING = "waiting"    # 还差一个人
STATUS_INPUT = "input"        # 双方都可以提交
STATUS_JUDGING = "judging"    # 两边词不一样，但可能语义相近，等双方表态
STATUS_REVEALED = "revealed"  # 已判定不同，等谁点下一轮
STATUS_FINISHED = "finished"  # 撞上了，游戏结束


class GameError(Exception):
    """可预期的业务错误，路由层会翻译成 4xx。"""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def normalize_word(raw: str) -> str:
    """把词压成用来比较的形状。

    规则刻意写死在这里而不是散落到前端，两边永远一致：
    全角转半角、去掉所有空白、英文不分大小写。
    这样 "Apple" 和 "ａｐｐｌｅ " 算同一个词，但 "苹果" 和 "苹果树" 不算
    ——后者交给「算不算同一个」的人工判定。
    """
    text = unicodedata.normalize("NFKC", raw)
    text = re.sub(r"\s+", "", text)
    return text.casefold()


@dataclass(slots=True)
class Player:
    id: str
    slot: int
    joined_at: float
    last_seen: float


@dataclass(slots=True)
class RoundResult:
    index: int
    words: tuple[str, str]
    matched: bool
    # True 表示这一轮是两个人商量后「算同一个」，不是字面撞上。
    judged: bool = False


@dataclass(slots=True)
class Room:
    code: str
    created_at: float
    last_active: float
    players: list[Player] = field(default_factory=list)
    status: str = STATUS_WAITING
    round_index: int = 1
    # 当前轮：player_id -> (原始输入, 规范化后的词)
    pending: dict[str, tuple[str, str]] = field(default_factory=dict)
    # 判定阶段：player_id -> 是否认为两个词是同一个意思
    votes: dict[str, bool] = field(default_factory=dict)
    history: list[RoundResult] = field(default_factory=list)

    # -- 小工具 -------------------------------------------------------
    @property
    def full(self) -> bool:
        return len(self.players) >= MAX_PLAYERS

    def player(self, player_id: str) -> Player:
        for p in self.players:
            if p.id == player_id:
                return p
        raise GameError("你已不在这个房间（座位超时或被释放了）", 404)

    def opponent_of(self, slot: int) -> Player | None:
        for p in self.players:
            if p.slot != slot:
                return p
        return None

    def _free_slot(self) -> int:
        """挑一个空座位。有人中途离开时，补的是他腾出来的那一个。"""
        taken = {p.slot for p in self.players}
        for slot in range(MAX_PLAYERS):
            if slot not in taken:
                return slot
        raise GameError("房间已经满了", 409)

    def _touch(self) -> None:
        self.last_active = time.time()

    def _reset_pairing(self) -> None:
        """两个人凑不齐了：本轮作废，历史清空，回到等人状态。

        不做这一步的话，新人坐进来会看到上一对玩家的战绩，
        或者对方的词一提交就自动结算——都不是他参与过的一局。
        """
        self.pending.clear()
        self.votes.clear()
        self.history.clear()
        self.round_index = 1
        self.status = STATUS_WAITING

    # -- 入场 / 离场 ---------------------------------------------------
    def join(self) -> Player:
        """坐下。房间满了就直接拒绝，绝不顶替已有的人。"""
        self._touch()
        now = time.time()

        if self.full:
            raise GameError("房间已经满了（房间锁已生效）", 409)

        player = Player(
            id=secrets.token_urlsafe(12),
            slot=self._free_slot(),
            joined_at=now,
            last_seen=now,
        )
        self.players.append(player)
        if self.full:
            self.status = STATUS_INPUT
            # 新的一对，从第一轮开始算。
            self.pending.clear()
            self.votes.clear()
            self.history.clear()
            self.round_index = 1
        return player

    def leave(self, player_id: str) -> None:
        """主动离开：座位立刻腾出来，不等心跳超时。"""
        self._touch()
        player = self.player(player_id)
        self.players = [p for p in self.players if p.id != player_id]
        self.pending.pop(player_id, None)
        self.votes.pop(player_id, None)
        self._reset_pairing()

    def sweep(self, now: float) -> bool:
        """把太久没心跳的座位回收掉。返回 True 表示这个房间该销毁了。"""
        if now - self.last_active > ROOM_IDLE_TTL:
            return True

        alive = [p for p in self.players if now - p.last_seen <= SEAT_TIMEOUT]
        if len(alive) != len(self.players):
            dropped = {p.id for p in self.players} - {p.id for p in alive}
            self.players = alive
            for pid in dropped:
                self.pending.pop(pid, None)
                self.votes.pop(pid, None)
            if self.players:
                self._reset_pairing()
            else:
                return True
        return False

    # -- 规则 ---------------------------------------------------------
    def submit(self, player_id: str, raw_word: str) -> None:
        self._touch()
        player = self.player(player_id)
        player.last_seen = time.time()

        if self.status == STATUS_WAITING:
            raise GameError("还在等另一个人进房间", 409)
        if self.status == STATUS_JUDGING:
            raise GameError("先判断上一轮的两个词算不算同一个", 409)
        if self.status == STATUS_REVEALED:
            raise GameError("这一轮已经揭晓了，先开下一轮", 409)
        if self.status == STATUS_FINISHED:
            raise GameError("这局已经结束了，点「再来一局」吧", 409)
        if player_id in self.pending:
            raise GameError("这一轮你已经提交过了", 409)

        stripped = raw_word.strip()
        if not stripped:
            raise GameError("写一个词再提交", 400)
        if len(stripped) > MAX_WORD_LEN:
            raise GameError(f"最多 {MAX_WORD_LEN} 个字", 400)
        if not normalize_word(stripped):
            raise GameError("不能只提交空白", 400)

        self.pending[player_id] = (stripped, normalize_word(stripped))

        if len(self.pending) == MAX_PLAYERS:
            self._settle()

    def _settle(self) -> None:
        """双方都交了，判定本轮结果。

        字面一样直接结束；不一样就进判定阶段——
        给两个人一个说"猪和小猪算一个意思"的机会。
        """
        first, second = self.players[0], self.players[1]
        word_a = self.pending[first.id][0]
        word_b = self.pending[second.id][0]
        matched = self.pending[first.id][1] == self.pending[second.id][1]
        self.history.append(
            RoundResult(index=self.round_index, words=(word_a, word_b), matched=matched)
        )
        if matched:
            self.status = STATUS_FINISHED
            return

        self.votes.clear()
        self.status = STATUS_JUDGING

    def judge(self, player_id: str, same: bool) -> None:
        """判定"这两个词算不算同一个意思"。

        规则很简单：说"不算"的人一票否决，立刻进入下一轮；
        说"算"需要两边都点头。这样既给了商量的余地，
        也不会因为一方迟迟不表态把房间卡死。
        """
        self._touch()
        player = self.player(player_id)
        player.last_seen = time.time()

        if self.status != STATUS_JUDGING:
            raise GameError("现在没有需要判断的回合", 409)

        self.votes[player_id] = same

        if not same:
            self.status = STATUS_REVEALED
            return

        # 全员都投了"算同一个"
        if len(self.votes) == MAX_PLAYERS and all(self.votes.values()):
            if self.history:
                self.history[-1].matched = True
                self.history[-1].judged = True
            self.status = STATUS_FINISHED

    def next_round(self, player_id: str) -> None:
        self._touch()
        self.player(player_id).last_seen = time.time()
        if self.status != STATUS_REVEALED:
            raise GameError("现在还不能开下一轮", 409)
        self.round_index += 1
        self.pending.clear()
        self.votes.clear()
        self.status = STATUS_INPUT

    def restart(self, player_id: str) -> None:
        self._touch()
        self.player(player_id).last_seen = time.time()
        if self.status != STATUS_FINISHED:
            raise GameError("这局还没结束", 409)
        self.round_index = 1
        self.pending.clear()
        self.votes.clear()
        self.history.clear()
        self.status = STATUS_INPUT

    def ping(self, player_id: str) -> dict:
        """心跳：只做两件事——续命，并告诉对方"你还在这个房间里"。"""
        player = self.player(player_id)
        now = time.time()
        player.last_seen = now
        self._touch()
        return {
            "alive": True,
            "room_code": self.code,
            "status": self.status,
            "round": self.round_index,
            "players": len(self.players),
            "locked": self.full,
            "next_ping_in": HEARTBEAT_INTERVAL,
        }

    # -- 视图 ---------------------------------------------------------
    def public_view(self) -> dict:
        """给"还没进房间的人"看的信息：只有房间活着没有、还有没有位子。

        不含任何人的词，也不含玩家 id —— 邀请链接落地页会先调它，
        确认房间还在、还有空位，再决定要不要自动进房。
        """
        self._touch()
        return {
            "room_code": self.code,
            "status": self.status,
            "players": len(self.players),
            "max_players": MAX_PLAYERS,
            "full": self.full,
            "locked": self.full,
            "round": self.round_index,
        }

    def view(self, player_id: str) -> dict:
        self._touch()
        me = self.player(player_id)
        me.last_seen = time.time()
        opp = self.opponent_of(me.slot)

        my_entry = self.pending.get(me.id)
        visible = self.status in (
            STATUS_JUDGING,
            STATUS_REVEALED,
            STATUS_FINISHED,
        )

        payload: dict = {
            "room_code": self.code,
            "status": self.status,
            "round": self.round_index,
            "max_players": MAX_PLAYERS,
            "locked": self.full,
            "me": {
                "slot": me.slot,
                "submitted": my_entry is not None,
                # 自己的词随时可见，只是提交后锁住不能改。
                "word": my_entry[0] if my_entry else None,
            },
            "opponent": {
                "joined": opp is not None,
                "submitted": opp is not None and opp.id in self.pending,
                # 未揭晓前这里永远是 None —— 前端拿不到对方的词。
                "word": None,
            },
            "reveal": None,
            "judging": {
                "enabled": self.status == STATUS_JUDGING,
                # None = 还没表态
                "me": self.votes.get(me.id),
                # 自己没表态前看不到对方的选择，免得被带着走
                "opponent": (
                    self.votes.get(opp.id)
                    if opp is not None
                    and me.id in self.votes
                    and self.status == STATUS_JUDGING
                    else None
                ),
            },
            "history": [
                {
                    "round": r.index,
                    "words": list(r.words),
                    "matched": r.matched,
                    "judged": r.judged,
                }
                for r in self.history
            ],
            "rounds_played": len(self.history),
            "matched_round": next(
                (r.index for r in self.history if r.matched), None
            ),
            "heartbeat_seconds": HEARTBEAT_INTERVAL,
        }

        if visible and opp is not None:
            opp_entry = self.pending.get(opp.id)
            payload["opponent"]["word"] = opp_entry[0] if opp_entry else None
            last = self.history[-1] if self.history else None
            if last is not None:
                payload["reveal"] = {
                    "round": last.index,
                    "words": list(last.words),
                    "matched": last.matched,
                    "judged": last.judged,
                }

        return payload


class RoomStore:
    """进程内的房间表。所有入口都走锁，省得想并发。"""

    def __init__(self) -> None:
        self._rooms: dict[str, Room] = {}
        self._lock = threading.Lock()

    def _sweep_locked(self) -> None:
        """回收超时座位、销毁空房间。每次操作前顺手做一遍，够用了。"""
        now = time.time()
        dead = [code for code, room in self._rooms.items() if room.sweep(now)]
        for code in dead:
            self._rooms.pop(code, None)

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))
            if code not in self._rooms:
                return code

    def create(self) -> tuple[Room, Player]:
        with self._lock:
            self._sweep_locked()
            now = time.time()
            room = Room(code=self._new_code(), created_at=now, last_active=now)
            self._rooms[room.code] = room
            return room, room.join()

    def _get_locked(self, code: str) -> Room:
        room = self._rooms.get(code.upper())
        if room is None:
            raise GameError("房间不存在或已过期", 404)
        return room

    def get(self, code: str) -> Room:
        with self._lock:
            self._sweep_locked()
            return self._get_locked(code)

    def with_room(self, code: str, action) -> object:
        """在锁里对某个房间做一次操作，避免手写 try/finally。"""
        with self._lock:
            self._sweep_locked()
            room = self._get_locked(code)
            return action(room)

    def leave(self, code: str, player_id: str) -> dict:
        """离开房间。最后一个人走了，房间立刻从表里删掉。"""
        with self._lock:
            self._sweep_locked()
            room = self._get_locked(code)
            room.leave(player_id)
            if not room.players:
                self._rooms.pop(room.code, None)
                return {"ok": True, "players": 0, "destroyed": True}
            return {"ok": True, "players": len(room.players), "destroyed": False}

    def count(self) -> int:
        with self._lock:
            self._sweep_locked()
            return len(self._rooms)


store = RoomStore()
