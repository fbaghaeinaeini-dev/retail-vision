"""In-memory session store for chat conversations."""

from __future__ import annotations

import uuid


class SessionStore:
    """Thread-local in-memory store for chat sessions.

    Each session holds a message history (list of {role, content} dicts)
    capped at *max_messages* entries.
    """

    def __init__(self, max_messages: int = 20) -> None:
        self.max_messages = max_messages
        self._sessions: dict[str, dict] = {}

    # ── public API ──────────────────────────────────────────────

    def create(self, video_id: str) -> str:
        """Create a new session for *video_id* and return its ID."""
        session_id = uuid.uuid4().hex[:12]
        self._sessions[session_id] = {
            "session_id": session_id,
            "video_id": video_id,
            "messages": [],
        }
        return session_id

    def get(self, session_id: str) -> dict | None:
        """Return the session dict or ``None`` if it does not exist."""
        return self._sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message and trim history to *max_messages*."""
        session = self._sessions.get(session_id)
        if session is None:
            return
        session["messages"].append({"role": role, "content": content})
        if len(session["messages"]) > self.max_messages:
            session["messages"] = session["messages"][-self.max_messages :]

    def delete(self, session_id: str) -> None:
        """Remove a session entirely."""
        self._sessions.pop(session_id, None)
