"""规则测试。跑 ::

    cd backend && pip install -r requirements-dev.txt && pytest -q
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.game.store import normalize_word
from app.main import app

client = TestClient(app)


def new_room():
    r = client.post("/api/rooms")
    assert r.status_code == 200
    data = r.json()
    return data["room_code"], data["player_id"]


def join(code):
    r = client.post(f"/api/rooms/{code}/join")
    assert r.status_code == 200
    return r.json()["player_id"]


def state(code, pid):
    r = client.get(f"/api/rooms/{code}", params={"player_id": pid})
    assert r.status_code == 200, r.text
    return r.json()


def submit(code, pid, word):
    r = client.post(f"/api/rooms/{code}/words", json={"player_id": pid, "word": word})
    assert r.status_code == 200, r.text
    return r.json()


def judge(code, pid, same):
    r = client.post(f"/api/rooms/{code}/judge", json={"player_id": pid, "same": same})
    assert r.status_code == 200, r.text
    return r.json()


def test_health():
    r = client.get("/api/health")
    assert r.json()["status"] == "ok"


def test_normalize_word():
    assert normalize_word("  Apple ") == "apple"
    assert normalize_word("ａｐｐｌｅ") == "apple"  # 全角转半角
    assert normalize_word("苹果 树") == "苹果树"      # 空格不参与比较
    assert normalize_word("苹果") != normalize_word("苹果树")


def test_room_waits_for_second_player():
    code, host = new_room()
    assert state(code, host)["status"] == "waiting"

    # 一个人时不能提交
    r = client.post(f"/api/rooms/{code}/words", json={"player_id": host, "word": "海"})
    assert r.status_code == 409

    guest = join(code)
    s = state(code, host)
    assert s["status"] == "input"
    assert s["opponent"]["joined"] is True
    assert s["opponent"]["submitted"] is False
    assert guest


def test_room_locks_once_full():
    """房间锁：人满了就是满了，第三个人进不来。"""
    code, _ = new_room()
    join(code)

    r = client.post(f"/api/rooms/{code}/join")
    assert r.status_code == 409
    assert "满" in r.json()["detail"]

    peek = client.get(f"/api/rooms/{code}/peek").json()
    assert peek["full"] is True
    assert peek["locked"] is True


def test_stale_seat_is_not_stolen_by_stranger():
    """核心修复：稍微掉线一会儿，座位也不会被后来的人顶掉。"""
    from app.game.store import store

    code, _ = new_room()
    join(code)

    # 模拟对方 10 秒没心跳——远没到回收线
    room = store.get(code)
    room.players[1].last_seen -= 10

    r = client.post(f"/api/rooms/{code}/join")
    assert r.status_code == 409  # 依然是满的，谁也不许顶

    # 房间没被搅乱
    assert len(store.get(code).players) == 2


def test_abandoned_seat_is_recycled_after_timeout():
    """真走了（超过 3 个心跳周期）才会被回收，并且是按"新的一局"重来。"""
    from app.game.store import SEAT_TIMEOUT, store

    code, host = new_room()
    guest = join(code)
    submit(code, host, "月亮")

    room = store.get(code)
    room.players[1].last_seen -= SEAT_TIMEOUT + 5

    # 任何一个请求都会顺手把死座位清掉
    s = state(code, host)
    assert s["status"] == "waiting"
    assert s["opponent"]["joined"] is False
    assert s["me"]["word"] is None  # 上一轮的提交跟着作废
    assert s["history"] == []

    # 现在有空位了，新人可以进来
    newcomer = join(code)
    assert newcomer != guest
    s = state(code, host)
    assert s["status"] == "input"
    assert s["round"] == 1
    # 被顶掉的旧身份立刻失效
    assert client.get(f"/api/rooms/{code}", params={"player_id": guest}).status_code == 404


def test_leave_frees_seat_and_destroys_empty_room():
    from app.game.store import store

    code, host = new_room()
    guest = join(code)

    r = client.post(f"/api/rooms/{code}/leave", json={"player_id": guest})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "players": 1, "destroyed": False}

    # 座位腾出来了，别人能进来
    newcomer = join(code)
    assert newcomer != guest

    # 还留着一个人，房间还在
    r = client.post(f"/api/rooms/{code}/leave", json={"player_id": host})
    assert r.json() == {"ok": True, "players": 1, "destroyed": False}

    # 最后一个人走，房间就地销毁
    r = client.post(f"/api/rooms/{code}/leave", json={"player_id": newcomer})
    assert r.json()["destroyed"] is True
    assert client.get(f"/api/rooms/{code}/peek").status_code == 404


def test_heartbeat_keeps_seat_and_reports_death():
    from app.game.store import SEAT_TIMEOUT, store

    code, host = new_room()

    r = client.get(f"/api/rooms/{code}/ping", params={"player_id": host})
    assert r.status_code == 200
    data = r.json()
    assert data["alive"] is True
    assert data["room_code"] == code
    assert data["next_ping_in"] == 20

    room = store.get(code)
    room.players[0].last_seen -= SEAT_TIMEOUT + 5

    # 座位没了，心跳要如实说"你已经不在了"，而不是继续假装活着
    r = client.get(f"/api/rooms/{code}/ping", params={"player_id": host})
    assert r.status_code == 404


def test_opponent_word_hidden_until_both_submit():
    """核心防作弊测试：先交的人拿不到后交的人的词。"""
    code, host = new_room()
    guest = join(code)

    client.post(f"/api/rooms/{code}/words", json={"player_id": host, "word": "月亮"})

    # 自己看得到自己的
    s = state(code, host)
    assert s["me"]["word"] == "月亮"
    assert s["me"]["submitted"] is True
    # 对方还没交，状态里不能有任何词
    assert s["opponent"]["submitted"] is False
    assert s["opponent"]["word"] is None
    assert s["reveal"] is None

    # 从对方视角看，也看不到 host 的词
    s2 = state(code, guest)
    assert s2["opponent"]["submitted"] is True
    assert s2["opponent"]["word"] is None
    assert "月亮" not in str(s2)


def test_mismatch_enters_judging_then_veto_moves_on():
    """词不一样不直接结束，先问一句"算不算同一个意思"。"""
    code, host = new_room()
    guest = join(code)

    submit(code, host, "月亮")
    s = submit(code, guest, "太阳")

    assert s["status"] == "judging"
    assert s["opponent"]["word"] == "月亮"
    assert s["reveal"] == {"round": 1, "words": ["月亮", "太阳"], "matched": False, "judged": False}
    assert s["judging"]["enabled"] is True
    assert s["judging"]["me"] is None

    # 判定阶段不能再交词
    r = client.post(f"/api/rooms/{code}/words", json={"player_id": host, "word": "x"})
    assert r.status_code == 409

    # 自己投完才能看到对方的选择
    s = judge(code, guest, False)
    assert s["status"] == "revealed"
    assert s["judging"]["me"] is False

    r = client.post(f"/api/rooms/{code}/next", json={"player_id": host})
    assert r.status_code == 200
    s = r.json()
    assert s["status"] == "input"
    assert s["round"] == 2
    assert s["me"]["submitted"] is False
    assert s["opponent"]["word"] is None
    assert len(s["history"]) == 1


def test_semantic_match_by_mutual_judgement():
    """猪 / 小猪：两个人都觉得算同一个，就按撞上结束。"""
    code, host = new_room()
    guest = join(code)

    submit(code, host, "猪")
    s = submit(code, guest, "小猪")
    assert s["status"] == "judging"

    # 一个人说"算"还不够
    s = judge(code, host, True)
    assert s["status"] == "judging"
    assert s["judging"]["me"] is True
    # 对方还没投，看不到我这票
    assert s["judging"]["opponent"] is None

    s = judge(code, guest, True)
    assert s["status"] == "finished"
    assert s["reveal"]["matched"] is True
    assert s["reveal"]["judged"] is True
    assert s["history"][-1] == {"round": 1, "words": ["猪", "小猪"], "matched": True, "judged": True}

    # 结束以后照常可以再来一局
    r = client.post(f"/api/rooms/{code}/restart", json={"player_id": guest})
    assert r.status_code == 200
    assert r.json()["status"] == "input"
    assert r.json()["history"] == []


def test_judge_is_rejected_outside_judging():
    code, host = new_room()
    join(code)
    r = client.post(f"/api/rooms/{code}/judge", json={"player_id": host, "same": True})
    assert r.status_code == 409


def test_match_finishes_game():
    code, host = new_room()
    guest = join(code)

    submit(code, host, "Apple")
    s = submit(code, guest, "ａｐｐｌｅ ")

    assert s["status"] == "finished"
    assert s["reveal"]["matched"] is True
    assert s["reveal"]["judged"] is False
    assert s["matched_round"] == 1

    # 结束后不能再交词，只能重开
    r = client.post(f"/api/rooms/{code}/words", json={"player_id": host, "word": "x"})
    assert r.status_code == 409

    r = client.post(f"/api/rooms/{code}/restart", json={"player_id": guest})
    assert r.status_code == 200
    s = r.json()
    assert s["status"] == "input"
    assert s["round"] == 1
    assert s["history"] == []


def test_peek_tells_seat_availability_without_leaking_words():
    """邀请链接落地页靠它判断能不能自动进房。"""
    code, host = new_room()

    r = client.get(f"/api/rooms/{code}/peek")
    assert r.status_code == 200
    data = r.json()
    assert data["room_code"] == code
    assert data["players"] == 1
    assert data["full"] is False
    assert data["locked"] is False
    assert data["status"] == "waiting"

    guest = join(code)
    data = client.get(f"/api/rooms/{code}/peek").json()
    assert data["players"] == 2
    assert data["full"] is True
    assert data["locked"] is True

    # 已经有人交了词，peek 也不能漏出去
    client.post(f"/api/rooms/{code}/words", json={"player_id": host, "word": "月亮"})
    text = client.get(f"/api/rooms/{code}/peek").text
    assert "月亮" not in text
    assert guest not in text

    assert client.get("/api/rooms/ZZZZZZ/peek").status_code == 404


def test_unknown_room_and_outsider():
    r = client.get("/api/rooms/ZZZZZZ", params={"player_id": "nobody"})
    assert r.status_code == 404

    code, _ = new_room()
    r = client.get(f"/api/rooms/{code}", params={"player_id": "nobody"})
    assert r.status_code == 404

    r = client.post(f"/api/rooms/{code}/join")
    assert r.status_code == 200


def test_word_validation():
    code, host = new_room()
    join(code)

    assert client.post(
        f"/api/rooms/{code}/words", json={"player_id": host, "word": "   "}
    ).status_code == 400
    assert client.post(
        f"/api/rooms/{code}/words", json={"player_id": host, "word": "x" * 25}
    ).status_code == 422  # pydantic 长度上限先拦住

    client.post(f"/api/rooms/{code}/words", json={"player_id": host, "word": "海"})
    # 同一轮不能交第二次
    r = client.post(f"/api/rooms/{code}/words", json={"player_id": host, "word": "山"})
    assert r.status_code == 409


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
