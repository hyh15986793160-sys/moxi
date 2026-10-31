"""对局接口。

一局游戏的全部交互都是普通 HTTP，前端用 900ms 轮询拿状态。
不用 WebSocket 的原因很实际：这台服务器上的 Nginx 已经有现成的
``/api/`` 转发，轮询到此为止，部署时一行配置都不用改。

另有一条 20 秒一次的心跳 ``/ping``：轮询负责"同步牌面"，
心跳负责"证明这个座位还有人"，两者分开以后，卡住一轮轮询
不会连带把座位判死。
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.game.store import MAX_WORD_LEN, GameError, store

router = APIRouter(tags=["game"])


class SubmitBody(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    word: str = Field(max_length=MAX_WORD_LEN, description="本轮的词")


class PlayerBody(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)


class JudgeBody(BaseModel):
    player_id: str = Field(min_length=1, max_length=64)
    same: bool = Field(description="这两个词算不算同一个意思")


@router.post("/rooms")
def create_room() -> dict:
    """开一局：建房间并成为 1 号位。"""
    room, player = store.create()
    return {
        "room_code": room.code,
        "player_id": player.id,
        "slot": player.slot,
        "state": room.view(player.id),
    }


@router.post("/rooms/{code}/join")
def join_room(code: str) -> dict:
    """加入房间，成为 2 号位。

    房间满了直接 409——这是"房间锁"：先坐进来的人不会被后来的人顶掉。
    想再进来只能带着原来的 player_id 回到自己的座位（刷新页面就走这条路）。
    """

    def action(room):
        player = room.join()
        return {
            "room_code": room.code,
            "player_id": player.id,
            "slot": player.slot,
            "state": room.view(player.id),
        }

    return store.with_room(code, action)


@router.get("/rooms/{code}/peek")
def peek_room(code: str) -> dict:
    """邀请链接落地前打听一下：房间还在吗？还有位子吗（是不是锁了）？

    不需要 player_id，所以放在 ``/rooms/{code}`` 之前，避免被它的必填参数挡住。
    """
    return store.with_room(code, lambda r: r.public_view())


@router.get("/rooms/{code}")
def get_state(code: str, player_id: str = Query(min_length=1, max_length=64)) -> dict:
    """轮询入口。对方的词在揭晓前不会出现在响应里。"""
    return store.with_room(code, lambda r: r.view(player_id))


@router.get("/rooms/{code}/ping")
def ping(code: str, player_id: str = Query(min_length=1, max_length=64)) -> dict:
    """心跳。前端每 20 秒打一次，座位靠它续命。

    座位已经没了会返回 404，前端据此提示"你已不在这个房间"，而不是继续空转。
    """
    return store.with_room(code, lambda r: r.ping(player_id))


@router.post("/rooms/{code}/words")
def submit_word(code: str, body: SubmitBody) -> dict:
    def action(room):
        room.submit(body.player_id, body.word)
        return room.view(body.player_id)

    return store.with_room(code, action)


@router.post("/rooms/{code}/judge")
def judge(code: str, body: JudgeBody) -> dict:
    """判定"这两个词算不算同一个意思"。说"不算"一票否决，说"算"要两边都点头。"""

    def action(room):
        room.judge(body.player_id, body.same)
        return room.view(body.player_id)

    return store.with_room(code, action)


@router.post("/rooms/{code}/next")
def next_round(code: str, body: PlayerBody) -> dict:
    def action(room):
        room.next_round(body.player_id)
        return room.view(body.player_id)

    return store.with_room(code, action)


@router.post("/rooms/{code}/restart")
def restart(code: str, body: PlayerBody) -> dict:
    def action(room):
        room.restart(body.player_id)
        return room.view(body.player_id)

    return store.with_room(code, action)


@router.post("/rooms/{code}/leave")
def leave(code: str, body: PlayerBody) -> dict:
    """主动离开：座位立刻腾出来；最后一个人走了，房间就地销毁。"""
    return store.leave(code, body.player_id)


@router.get("/stats", include_in_schema=False)
def stats() -> dict:
    return {"rooms_in_memory": store.count()}


__all__ = ["router", "GameError"]
