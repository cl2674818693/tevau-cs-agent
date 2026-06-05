"""Verify SSE stream stops promptly when cancel_evt is set (simulating client disconnect)."""
import asyncio

from ai_engine.api import chat as chat_api


async def test_stream_ai_turn_stops_on_cancel_evt(monkeypatch):
    """cancel_evt.set() during runtime yield → _stream_ai_turn returns with message_stop(cancelled)."""
    yielded_count = 0

    async def fake_run_turn(**kwargs):  # noqa: ANN003
        for _ in range(100):
            yield {"type": "text", "text": "x"}
            await asyncio.sleep(0.01)

    # 替换 runtime.run_turn 避免真打 LLM
    monkeypatch.setattr(chat_api.runtime, "run_turn", fake_run_turn)
    # publish_conversation_event 是 no-op 替身（避免依赖 staff_conversations bus）
    monkeypatch.setattr(chat_api, "publish_conversation_event", lambda *a, **k: None)

    # 屏蔽 att_dao.get_attachment 调用（attachment_ids=[] 不触发，保险）
    cancel_evt = asyncio.Event()

    async def drive():
        nonlocal yielded_count
        cancelled_frame_seen = False
        async for frame in chat_api._stream_ai_turn(
            conversation_id=1, user_type="c", subject_id="U1",
            message="hi", client_message_id=None,
            cancel_evt=cancel_evt, attachment_ids=[], ui_locale=None,
        ):
            yielded_count += 1
            if yielded_count == 2:
                cancel_evt.set()
            # data 帧里包含 "cancelled" 即认为 cancel 路径走到了
            if "cancelled" in str(frame):
                cancelled_frame_seen = True
                return cancelled_frame_seen
        return cancelled_frame_seen

    seen = await asyncio.wait_for(drive(), timeout=2.0)
    assert seen, "cancel_evt set during streaming should yield a cancelled message_stop frame"
    assert yielded_count < 50, f"should stop early after cancel; got {yielded_count} frames"


async def test_watch_disconnect_sets_cancel_evt_when_request_disconnected():
    """_watch_disconnect polls is_disconnected; True → cancel_evt.set()."""
    cancel_evt = asyncio.Event()

    class _Req:
        client = type("c", (), {"host": "127.0.0.1"})()
        async def is_disconnected(self):
            return True

    task = asyncio.create_task(chat_api._watch_disconnect(_Req(), cancel_evt))
    await asyncio.wait_for(cancel_evt.wait(), timeout=1.0)
    assert cancel_evt.is_set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_watch_disconnect_exits_when_cancel_evt_set():
    """cancel_evt 已 set 时 _watch_disconnect 自然退出，不持续轮询。"""
    cancel_evt = asyncio.Event()
    cancel_evt.set()

    class _Req:
        client = type("c", (), {"host": "127.0.0.1"})()
        async def is_disconnected(self):
            return False

    await asyncio.wait_for(chat_api._watch_disconnect(_Req(), cancel_evt), timeout=1.0)
    # 没超时即通过


async def test_watch_disconnect_fast_exit_on_external_set():
    """cancel_evt 外部 set 时 watcher 应立刻返回，不空转 0.25s。"""
    cancel_evt = asyncio.Event()

    class _Req:
        client = type("c", (), {"host": "127.0.0.1"})()
        async def is_disconnected(self):
            return False

    task = asyncio.create_task(chat_api._watch_disconnect(_Req(), cancel_evt))
    await asyncio.sleep(0.02)  # 让 watcher 进入 wait_for
    cancel_evt.set()
    # 期望 <100ms 内退出（vs 旧 sleep 实现的 ~250ms）
    await asyncio.wait_for(task, timeout=0.1)
