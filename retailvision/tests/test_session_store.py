"""Tests for the in-memory session store."""

from api.session_store import SessionStore


class TestSessionStore:
    """SessionStore unit tests."""

    def test_create_returns_id(self):
        store = SessionStore()
        sid = store.create("vid_001")
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_get_existing_session(self):
        store = SessionStore()
        sid = store.create("vid_001")
        session = store.get(sid)
        assert session is not None
        assert session["video_id"] == "vid_001"
        assert session["session_id"] == sid
        assert session["messages"] == []

    def test_get_missing_returns_none(self):
        store = SessionStore()
        assert store.get("nonexistent") is None

    def test_add_message(self):
        store = SessionStore()
        sid = store.create("vid_001")
        store.add_message(sid, "user", "hello")
        store.add_message(sid, "assistant", "hi there")
        msgs = store.get(sid)["messages"]
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi there"}

    def test_history_limit(self):
        store = SessionStore(max_messages=4)
        sid = store.create("vid_001")
        for i in range(10):
            store.add_message(sid, "user", f"msg_{i}")
        msgs = store.get(sid)["messages"]
        assert len(msgs) == 4
        # Should keep the last 4 messages (msg_6 .. msg_9)
        assert msgs[0]["content"] == "msg_6"
        assert msgs[1]["content"] == "msg_7"
        assert msgs[2]["content"] == "msg_8"
        assert msgs[3]["content"] == "msg_9"

    def test_delete(self):
        store = SessionStore()
        sid = store.create("vid_001")
        store.delete(sid)
        assert store.get(sid) is None

    def test_delete_nonexistent_is_noop(self):
        store = SessionStore()
        store.delete("ghost")  # should not raise
