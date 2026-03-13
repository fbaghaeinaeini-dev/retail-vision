# Chat-First Interface Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a ChatGPT-style conversational AI interface that replaces the scroll-based dashboard with a chat-first UI where Vision AI responds with text + embedded interactive visualization cards.

**Architecture:** FastAPI backend with session-based chat + SSE streaming, calling OpenRouter VLM (qwen3.5) for intent classification. React frontend with chat message feed and 9 embeddable visualization card types. Existing dashboard preserved as a separate route.

**Tech Stack:** FastAPI, httpx, SSE (sse-starlette), React 19, Tailwind 4, Recharts, D3-Sankey, Framer Motion, react-router-dom

---

## File Structure

### Backend (new files)
```
api/
  chat_server.py        # FastAPI app: /api/chat (SSE), /api/report, /api/health
  chat_prompt.py        # System prompt builder + report summarizer for VLM
  session_store.py      # In-memory session manager (history, metadata)
```

### Frontend (new files)
```
dashboard/src/
  pages/
    ChatPage.jsx        # Chat-first interface (main page)
    DashboardPage.jsx   # Existing dashboard (extracted from App.jsx)
  components/chat/
    ChatInput.jsx       # Input bar with send button + suggestion chips
    ChatMessage.jsx     # Single message renderer (AI or user)
    ThinkingIndicator.jsx  # Animated dots loading state
    VizCard.jsx         # Viz card router — dispatches to card type
  components/viz-cards/
    ZoneDetailCard.jsx  # Single zone detail card (new)
    DataTableCard.jsx   # Sortable data table (new)
    BarChartCard.jsx    # Compact bar chart (adapted from ZoneBarChart)
    SankeyCard.jsx      # Compact sankey (adapted from SankeyFlow)
    TemporalCard.jsx    # Compact temporal heatmap (adapted from TemporalHeatmap)
    ZoneMapCard.jsx     # Zone map perspective (adapted from ZoneMapPerspective)
    ZoneMapBEVCard.jsx  # BEV map (adapted from ZoneMapBEV)
    KPICard.jsx         # Compact KPI summary (adapted from KPIRibbon)
    HeatmapImageCard.jsx  # Static heatmap PNG display
  hooks/
    useChat.js          # Chat state, SSE connection, message management
```

### Modified files
```
dashboard/src/App.jsx           # Add react-router: /chat + /dashboard routes
dashboard/src/index.css         # Add Ipsotek orange theme color
dashboard/package.json          # Add react-router-dom dependency
dashboard/vite.config.js        # Add proxy for /api → FastAPI dev server
pyproject.toml                  # Add fastapi, uvicorn, sse-starlette
```

---

## Chunk 1: Backend — Session Store + Chat Prompt

### Task 1: Session Store

**Files:**
- Create: `api/__init__.py`
- Create: `api/session_store.py`
- Test: `tests/test_session_store.py`

- [ ] **Step 1: Write failing tests for session store**

Create `tests/test_session_store.py`:

```python
"""Tests for chat session store."""
import pytest
from api.session_store import SessionStore


class TestSessionStore:
    def test_create_session(self):
        store = SessionStore()
        sid = store.create("video_123")
        assert sid is not None
        session = store.get(sid)
        assert session is not None
        assert session["video_id"] == "video_123"
        assert session["messages"] == []

    def test_get_missing_session_returns_none(self):
        store = SessionStore()
        assert store.get("nonexistent") is None

    def test_add_message(self):
        store = SessionStore()
        sid = store.create("v1")
        store.add_message(sid, "user", "Hello")
        store.add_message(sid, "assistant", "Hi there")
        session = store.get(sid)
        assert len(session["messages"]) == 2
        assert session["messages"][0]["role"] == "user"
        assert session["messages"][1]["content"] == "Hi there"

    def test_message_history_limit(self):
        store = SessionStore(max_messages=4)
        sid = store.create("v1")
        for i in range(10):
            store.add_message(sid, "user", f"msg {i}")
        session = store.get(sid)
        assert len(session["messages"]) == 4
        assert session["messages"][0]["content"] == "msg 6"

    def test_delete_session(self):
        store = SessionStore()
        sid = store.create("v1")
        store.delete(sid)
        assert store.get(sid) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/Agentic-path/retailvision && conda run -n retailvision python -m pytest tests/test_session_store.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Create empty `api/__init__.py`**

Create `api/__init__.py` (empty file).

- [ ] **Step 4: Implement session store**

Create `api/session_store.py`:

```python
"""In-memory session store for chat conversations."""
from __future__ import annotations

import uuid
from datetime import datetime


class SessionStore:
    """Thread-safe in-memory session manager."""

    def __init__(self, max_messages: int = 20):
        self._sessions: dict[str, dict] = {}
        self._max_messages = max_messages

    def create(self, video_id: str) -> str:
        sid = uuid.uuid4().hex[:12]
        self._sessions[sid] = {
            "session_id": sid,
            "video_id": video_id,
            "created_at": datetime.utcnow().isoformat(),
            "messages": [],
        }
        return sid

    def get(self, session_id: str) -> dict | None:
        return self._sessions.get(session_id)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        if len(session["messages"]) > self._max_messages:
            session["messages"] = session["messages"][-self._max_messages:]

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd E:/Agentic-path/retailvision && conda run -n retailvision python -m pytest tests/test_session_store.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add api/__init__.py api/session_store.py tests/test_session_store.py
git commit -m "feat(chat): add in-memory session store"
```

---

### Task 2: Chat Prompt Builder

**Files:**
- Create: `api/chat_prompt.py`
- Test: `tests/test_chat_prompt.py`

- [ ] **Step 1: Write failing tests for prompt builder**

Create `tests/test_chat_prompt.py`:

```python
"""Tests for chat prompt builder."""
import json
import pytest
from api.chat_prompt import build_system_prompt, summarize_report


class TestReportSummarizer:
    def test_summarize_report_basic(self):
        report = {
            "meta": {"video_id": "v1", "scene_type": "indoor_food_court",
                     "duration_seconds": 1800, "n_zones": 3},
            "zones": {
                "z0": {"business_name": "Starbucks", "zone_type": "cafe", "area_m2": 12.5},
                "z1": {"business_name": "Subway", "zone_type": "restaurant", "area_m2": 18.0},
                "z2": {"business_name": "Corridor A", "zone_type": "corridor", "area_m2": 30.0},
            },
            "analytics": {
                "z0": {"total_visits": 50, "avg_dwell_seconds": 25.0, "density_people_per_m2_hr": 2.0},
                "z1": {"total_visits": 80, "avg_dwell_seconds": 47.0, "density_people_per_m2_hr": 4.5},
                "z2": {"total_visits": 120, "avg_dwell_seconds": 5.0, "density_people_per_m2_hr": 1.0},
            },
            "flow": {"transitions": [{"from_zone": "z0", "to_zone": "z1", "count": 15}]},
            "temporal": {"time_bin_seconds": 300},
            "spatial": {},
        }
        summary = summarize_report(report)
        assert "Starbucks" in summary
        assert "indoor_food_court" in summary
        assert "1800" in summary or "30" in summary  # duration

    def test_summarize_handles_empty_report(self):
        summary = summarize_report({"meta": {}, "zones": {}, "analytics": {},
                                     "flow": {}, "temporal": {}, "spatial": {}})
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestSystemPrompt:
    def test_build_system_prompt_contains_viz_types(self):
        prompt = build_system_prompt("test summary")
        assert "zone_map" in prompt
        assert "bar_chart" in prompt
        assert "sankey" in prompt
        assert "JSON" in prompt

    def test_build_system_prompt_includes_summary(self):
        prompt = build_system_prompt("MY_CUSTOM_SUMMARY")
        assert "MY_CUSTOM_SUMMARY" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd E:/Agentic-path/retailvision && conda run -n retailvision python -m pytest tests/test_chat_prompt.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement chat prompt builder**

Create `api/chat_prompt.py`:

```python
"""Chat prompt builder — constructs VLM system prompt from report data."""
from __future__ import annotations


def summarize_report(report: dict) -> str:
    """Condense report.json into a compact text summary for the VLM context."""
    meta = report.get("meta", {})
    zones = report.get("zones", {})
    analytics = report.get("analytics", {})
    flow = report.get("flow", {})
    temporal = report.get("temporal", {})

    lines = [
        f"Video: {meta.get('video_id', 'unknown')}",
        f"Scene: {meta.get('scene_type', 'unknown')}",
        f"Duration: {meta.get('duration_seconds', 0)}s",
        f"Zones: {len(zones)}",
        "",
        "Zone Details:",
    ]

    for zid, z in zones.items():
        a = analytics.get(zid, {})
        lines.append(
            f"  {zid}: {z.get('business_name', zid)} "
            f"(type={z.get('zone_type', '?')}, "
            f"area={z.get('area_m2', 0):.1f}m², "
            f"visits={a.get('total_visits', 0)}, "
            f"dwell={a.get('avg_dwell_seconds', 0):.1f}s, "
            f"density={a.get('density_people_per_m2_hr', 0):.1f}/m²/hr)"
        )

    transitions = flow.get("transitions", [])
    if transitions:
        lines.append("")
        lines.append(f"Flow: {len(transitions)} zone-to-zone transitions")
        top = sorted(transitions, key=lambda t: t.get("count", 0), reverse=True)[:5]
        for t in top:
            lines.append(f"  {t['from_zone']} → {t['to_zone']}: {t['count']} trips")

    if temporal.get("time_bin_seconds"):
        lines.append(f"\nTemporal: {temporal['time_bin_seconds']}s bins")

    return "\n".join(lines)


VIZ_TYPE_SCHEMA = """Available visualization types you can embed:
- zone_map: Camera perspective with zone polygons. Config: { highlight_zones?: string[] }
- zone_map_bev: Bird's eye view with density. Config: { highlight_zones?: string[] }
- zone_detail: Single zone card with metrics. Config: { zone_id: string }
- bar_chart: Metric comparison across zones. Config: { metric: "total_visits"|"avg_dwell_seconds"|"density_people_per_m2_hr", zones?: string[], sort_by?: "asc"|"desc" }
- sankey: Zone-to-zone flow diagram. Config: { filter_zone?: string }
- temporal: Time × zone heatmap. Config: { highlight_zone?: string }
- kpi_cards: Summary metric cards. Config: { metrics?: string[] }
- data_table: Sortable data table. Config: { columns: string[], sort_by?: string, filter?: object }
- heatmap_image: Density heatmap image. Config: {}"""


def build_system_prompt(report_summary: str) -> str:
    """Build the VLM system prompt with report context and viz schema."""
    return f"""You are Vision AI, an intelligent analytics assistant for retail CCTV scene analysis.
You are powered by Ipsotek, an Eviden business.

You have access to a fully analyzed video scene with zone discovery, customer tracking, and spatial analytics.

## Scene Data
{report_summary}

## Your Capabilities
1. **Navigation** — Show specific visualizations (zone maps, flow diagrams, heatmaps)
2. **Data Q&A** — Answer questions about zones, metrics, comparisons, rankings
3. **Live Analysis** — Filter zones by criteria, find patterns, compare metrics

## Response Format
You MUST respond with valid JSON in this exact format:
{{
  "thinking": "Brief internal reasoning (1 sentence)",
  "text": "Your response to the user in clear, professional language. Use specific numbers and zone names. Be concise but insightful.",
  "visualizations": [
    {{ "type": "<viz_type>", "config": {{ ... }} }}
  ]
}}

{VIZ_TYPE_SCHEMA}

## Rules
- Always include at least one visualization when the query relates to data
- Use zone IDs (e.g. "zone_0") in config, not business names
- For comparison queries, prefer bar_chart
- For "show me zones" or spatial queries, prefer zone_map
- For flow/path queries, prefer sankey
- For time-based queries, prefer temporal
- For "summary" or "overview", use kpi_cards
- For specific zone questions, use zone_detail
- For listing/ranking queries, use data_table
- Maximum 3 visualizations per response
- Keep text concise — let the visualizations do the heavy lifting
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd E:/Agentic-path/retailvision && conda run -n retailvision python -m pytest tests/test_chat_prompt.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add api/chat_prompt.py tests/test_chat_prompt.py
git commit -m "feat(chat): add prompt builder with report summarizer"
```

---

### Task 3: FastAPI Chat Server

**Files:**
- Create: `api/chat_server.py`
- Test: `tests/test_chat_server.py`
- Modify: `pyproject.toml` (add dependencies)

- [ ] **Step 1: Add Python dependencies**

Add to `pyproject.toml` dependencies:
```
fastapi>=0.115.0
uvicorn>=0.32.0
sse-starlette>=2.1.0
```

- [ ] **Step 2: Install dependencies**

Run: `cd E:/Agentic-path/retailvision && conda run -n retailvision pip install fastapi uvicorn sse-starlette`

- [ ] **Step 3: Write failing tests for chat server**

Create `tests/test_chat_server.py`:

```python
"""Tests for chat API server."""
import json
import pytest
from fastapi.testclient import TestClient
from api.chat_server import create_app


@pytest.fixture
def client(tmp_path):
    """Create test client with a mock report."""
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({
        "meta": {"video_id": "test_v1", "scene_type": "indoor_food_court",
                 "duration_seconds": 600, "n_zones": 2},
        "zones": {
            "zone_0": {"business_name": "Cafe A", "zone_type": "cafe", "area_m2": 10},
            "zone_1": {"business_name": "Shop B", "zone_type": "shop", "area_m2": 20},
        },
        "analytics": {
            "zone_0": {"total_visits": 30, "avg_dwell_seconds": 15, "density_people_per_m2_hr": 1.5},
            "zone_1": {"total_visits": 50, "avg_dwell_seconds": 8, "density_people_per_m2_hr": 2.0},
        },
        "flow": {"transitions": []},
        "temporal": {"time_bin_seconds": 300},
        "spatial": {},
    }))
    app = create_app(report_path=str(report_path), openrouter_api_key="")
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["video_id"] == "test_v1"


class TestReportEndpoint:
    def test_get_report(self, client):
        resp = client.get("/api/report")
        assert resp.status_code == 200
        data = resp.json()
        assert "zones" in data
        assert "zone_0" in data["zones"]


class TestChatEndpoint:
    def test_chat_without_api_key_returns_fallback(self, client):
        """Without an OpenRouter key, should return a structured fallback response."""
        resp = client.post("/api/chat", json={
            "message": "Show me the zones"
        })
        assert resp.status_code == 200
        # SSE response — read lines
        lines = resp.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert len(data_lines) > 0
        # Last data line should be the complete response
        last_data = json.loads(data_lines[-1].replace("data: ", ""))
        assert "text" in last_data
        assert "visualizations" in last_data

    def test_chat_creates_session(self, client):
        resp = client.post("/api/chat", json={"message": "hello"})
        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        last_data = json.loads(data_lines[-1].replace("data: ", ""))
        assert "session_id" in last_data

    def test_chat_with_session_id(self, client):
        # First request to create session
        resp1 = client.post("/api/chat", json={"message": "hello"})
        lines = resp1.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        sid = json.loads(data_lines[-1].replace("data: ", ""))["session_id"]
        # Second request with session
        resp2 = client.post("/api/chat", json={
            "message": "show zones", "session_id": sid
        })
        assert resp2.status_code == 200
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd E:/Agentic-path/retailvision && conda run -n retailvision python -m pytest tests/test_chat_server.py -v`
Expected: FAIL — ImportError

- [ ] **Step 5: Implement chat server**

Create `api/chat_server.py`:

```python
"""FastAPI chat server — SSE streaming endpoint for Vision AI chat."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from api.chat_prompt import build_system_prompt, summarize_report
from api.session_store import SessionStore


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


def create_app(
    report_path: str = "dashboard/public/data/report.json",
    openrouter_api_key: str = "",
    vlm_model: str = "qwen/qwen3.5-35b-a3b",
) -> FastAPI:
    app = FastAPI(title="RetailVision Chat API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Load report data
    report_file = Path(report_path)
    if report_file.exists():
        report = json.loads(report_file.read_text())
    else:
        report = {"meta": {}, "zones": {}, "analytics": {},
                  "flow": {}, "temporal": {}, "spatial": {}}

    summary = summarize_report(report)
    system_prompt = build_system_prompt(summary)
    sessions = SessionStore()
    api_key = openrouter_api_key

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "video_id": report.get("meta", {}).get("video_id", "unknown"),
            "n_zones": len(report.get("zones", {})),
        }

    @app.get("/api/report")
    def get_report():
        return report

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        # Get or create session
        sid = req.session_id
        if not sid or sessions.get(sid) is None:
            video_id = report.get("meta", {}).get("video_id", "unknown")
            sid = sessions.create(video_id)

        sessions.add_message(sid, "user", req.message)
        session = sessions.get(sid)

        async def event_stream():
            try:
                result = _call_vlm(
                    api_key, vlm_model, system_prompt,
                    session["messages"], req.message,
                )
            except Exception as e:
                logger.error(f"VLM call failed: {e}")
                result = _fallback_response(req.message, report)

            sessions.add_message(sid, "assistant", result.get("text", ""))
            result["session_id"] = sid
            yield {"data": json.dumps(result)}

        return EventSourceResponse(event_stream())

    return app


def _call_vlm(
    api_key: str,
    model: str,
    system_prompt: str,
    history: list[dict],
    message: str,
) -> dict:
    """Call OpenRouter VLM for chat response."""
    if not api_key:
        raise ValueError("No API key")

    messages = [{"role": "system", "content": system_prompt}]
    # Add conversation history (last 10 messages for context window)
    for msg in history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2048,
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]

    # Parse JSON response
    return _parse_vlm_response(text)


def _parse_vlm_response(text: str) -> dict:
    """Parse structured JSON from VLM response."""
    import re
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {"text": text, "visualizations": []}


def _fallback_response(message: str, report: dict) -> dict:
    """Generate a rule-based fallback when VLM is unavailable."""
    msg_lower = message.lower()
    zones = report.get("zones", {})
    analytics = report.get("analytics", {})

    viz = []
    text = ""

    if any(w in msg_lower for w in ["zone", "map", "layout", "where"]):
        viz.append({"type": "zone_map", "config": {}})
        text = f"Here's the zone map showing all {len(zones)} discovered zones."

    elif any(w in msg_lower for w in ["flow", "path", "move", "transition", "traffic"]):
        viz.append({"type": "sankey", "config": {}})
        text = "Here's the customer flow diagram showing zone-to-zone transitions."

    elif any(w in msg_lower for w in ["busy", "popular", "visit", "most"]):
        viz.append({"type": "bar_chart", "config": {"metric": "total_visits"}})
        if analytics:
            top_zid = max(analytics, key=lambda z: analytics[z].get("total_visits", 0))
            top_name = zones.get(top_zid, {}).get("business_name", top_zid)
            top_visits = analytics[top_zid].get("total_visits", 0)
            text = f"{top_name} is the busiest zone with {top_visits} total visits."
        else:
            text = "Here's the zone visit comparison."

    elif any(w in msg_lower for w in ["dwell", "stay", "linger", "time"]):
        viz.append({"type": "bar_chart", "config": {"metric": "avg_dwell_seconds"}})
        if analytics:
            top_zid = max(analytics, key=lambda z: analytics[z].get("avg_dwell_seconds", 0))
            top_name = zones.get(top_zid, {}).get("business_name", top_zid)
            top_dwell = analytics[top_zid].get("avg_dwell_seconds", 0)
            text = f"{top_name} has the highest dwell time at {top_dwell:.1f}s."
        else:
            text = "Here's the dwell time comparison."

    elif any(w in msg_lower for w in ["when", "hour", "time", "temporal", "peak"]):
        viz.append({"type": "temporal", "config": {}})
        text = "Here's the temporal occupancy pattern across all zones."

    elif any(w in msg_lower for w in ["summary", "overview", "key", "metric", "kpi"]):
        viz.append({"type": "kpi_cards", "config": {}})
        text = f"Here's the summary: {len(zones)} zones discovered across the scene."

    elif any(w in msg_lower for w in ["heat", "density", "cluster", "hotspot"]):
        viz.append({"type": "heatmap_image", "config": {}})
        text = "Here's the density heatmap showing where people cluster."

    elif any(w in msg_lower for w in ["list", "table", "all", "sort", "rank"]):
        viz.append({"type": "data_table", "config": {
            "columns": ["business_name", "zone_type", "total_visits", "avg_dwell_seconds"]
        }})
        text = f"Here's a table of all {len(zones)} zones with their metrics."

    else:
        viz.append({"type": "kpi_cards", "config": {}})
        viz.append({"type": "zone_map", "config": {}})
        text = f"I'm analyzing a scene with {len(zones)} zones. Here's an overview — ask me about specific zones, flow patterns, or metrics!"

    return {"text": text, "visualizations": viz}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd E:/Agentic-path/retailvision && conda run -n retailvision python -m pytest tests/test_chat_server.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add api/chat_server.py tests/test_chat_server.py pyproject.toml
git commit -m "feat(chat): add FastAPI chat server with SSE streaming"
```

---

## Chunk 2: Frontend — Chat Hook + Core Components

### Task 4: Install Frontend Dependencies + Config

**Files:**
- Modify: `dashboard/package.json`
- Modify: `dashboard/vite.config.js`
- Modify: `dashboard/src/index.css`

- [ ] **Step 1: Install react-router-dom**

Run: `cd E:/Agentic-path/retailvision/dashboard && npm install react-router-dom`

- [ ] **Step 2: Add Vite proxy for API**

In `dashboard/vite.config.js`, add proxy config to the `server` block:

```javascript
server: {
  port: 5173,
  open: true,
  proxy: {
    "/api": {
      target: "http://localhost:8000",
      changeOrigin: true,
    },
  },
},
```

- [ ] **Step 3: Add Ipsotek orange to theme**

In `dashboard/src/index.css`, add after the accent-red line:

```css
--color-accent-orange: #e8632b;
```

- [ ] **Step 4: Commit**

```bash
cd E:/Agentic-path/retailvision/dashboard && git add package.json package-lock.json vite.config.js src/index.css
git commit -m "feat(chat): add react-router, vite proxy, ipsotek orange theme"
```

---

### Task 5: useChat Hook

**Files:**
- Create: `dashboard/src/hooks/useChat.js`

- [ ] **Step 1: Create the chat hook**

Create `dashboard/src/hooks/useChat.js`:

```javascript
import { useState, useCallback, useRef } from "react";

/**
 * Chat state manager with SSE streaming support.
 *
 * Messages: [{ id, role: "user"|"assistant", content, visualizations?, timestamp }]
 */
export function useChat(report) {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const sessionIdRef = useRef(null);

  const sendMessage = useCallback(
    async (text) => {
      if (!text.trim() || isLoading) return;

      const userMsg = {
        id: Date.now().toString(),
        role: "user",
        content: text.trim(),
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setError(null);

      try {
        const body = { message: text.trim() };
        if (sessionIdRef.current) {
          body.session_id = sessionIdRef.current;
        }

        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!res.ok) {
          throw new Error(`Chat request failed: ${res.status}`);
        }

        // Read SSE stream
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";
        let result = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                result = data;
                if (data.session_id) {
                  sessionIdRef.current = data.session_id;
                }
                fullText = data.text || "";
              } catch {
                // Partial JSON, skip
              }
            }
          }
        }

        const aiMsg = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: fullText,
          visualizations: result?.visualizations || [],
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, aiMsg]);
      } catch (err) {
        setError(err.message);
        // Add error message to chat
        setMessages((prev) => [
          ...prev,
          {
            id: (Date.now() + 1).toString(),
            role: "assistant",
            content: "Sorry, I encountered an error. Please try again.",
            visualizations: [],
            error: true,
            timestamp: new Date().toISOString(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading]
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    sessionIdRef.current = null;
    setError(null);
  }, []);

  return { messages, isLoading, error, sendMessage, clearChat };
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/src/hooks/useChat.js
git commit -m "feat(chat): add useChat hook with SSE streaming"
```

---

### Task 6: Chat UI Components (Input, Message, Thinking)

**Files:**
- Create: `dashboard/src/components/chat/ChatInput.jsx`
- Create: `dashboard/src/components/chat/ChatMessage.jsx`
- Create: `dashboard/src/components/chat/ThinkingIndicator.jsx`
- Create: `dashboard/src/components/chat/SuggestionChips.jsx`

- [ ] **Step 1: Create ThinkingIndicator**

Create `dashboard/src/components/chat/ThinkingIndicator.jsx`:

```jsx
/**
 * Animated "Thinking" indicator with three pulsing dots.
 */
export default function ThinkingIndicator() {
  return (
    <div className="flex gap-2.5 max-w-[85%]">
      {/* Vision AI avatar */}
      <div className="w-8 h-8 rounded-full border-[1.5px] border-accent-orange/30 bg-accent-orange/10 flex items-center justify-center flex-shrink-0">
        <span className="text-accent-orange text-[6.5px] font-bold leading-none text-center">
          Vision
          <br />
          AI
        </span>
      </div>
      <div className="bg-bg-card rounded-xl rounded-tl-sm px-4 py-3 flex items-center gap-2.5">
        <div className="flex gap-1 items-center">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-orange animate-[pulse-dot_1.4s_ease-in-out_infinite]" />
          <span className="w-1.5 h-1.5 rounded-full bg-accent-orange animate-[pulse-dot_1.4s_ease-in-out_0.2s_infinite]" />
          <span className="w-1.5 h-1.5 rounded-full bg-accent-orange animate-[pulse-dot_1.4s_ease-in-out_0.4s_infinite]" />
        </div>
        <span className="text-accent-orange text-[11px] font-medium opacity-80">
          Thinking
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create SuggestionChips**

Create `dashboard/src/components/chat/SuggestionChips.jsx`:

```jsx
const SUGGESTIONS = [
  "Show me the zones",
  "Which area is busiest?",
  "Summary of key metrics",
  "Customer flow patterns",
];

/**
 * Clickable suggestion chips for common queries.
 */
export default function SuggestionChips({ onSelect }) {
  return (
    <div className="flex flex-wrap gap-1.5 mt-2.5">
      {SUGGESTIONS.map((text) => (
        <button
          key={text}
          onClick={() => onSelect(text)}
          className="px-2.5 py-1 text-[10px] text-accent-orange border border-accent-orange/25 bg-accent-orange/8 rounded-full hover:bg-accent-orange/15 transition-colors cursor-pointer"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create ChatInput**

Create `dashboard/src/components/chat/ChatInput.jsx`:

```jsx
import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";

/**
 * Chat input bar with send button.
 */
export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    if (!disabled) inputRef.current?.focus();
  }, [disabled]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end">
      <div className="flex-1 bg-bg-hover border border-border rounded-xl px-3.5 py-2.5 flex items-center">
        <input
          ref={inputRef}
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about zones, flow patterns, metrics..."
          disabled={disabled}
          className="flex-1 bg-transparent border-none outline-none text-text-primary text-sm placeholder:text-text-secondary/50 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="w-7 h-7 rounded-lg flex items-center justify-center transition-colors disabled:opacity-30"
          style={{ backgroundColor: disabled || !text.trim() ? "#4a5568" : "#e8632b" }}
        >
          <Send size={14} className="text-white" />
        </button>
      </div>
    </form>
  );
}
```

- [ ] **Step 4: Create ChatMessage**

Create `dashboard/src/components/chat/ChatMessage.jsx`:

```jsx
import { motion } from "framer-motion";
import SuggestionChips from "./SuggestionChips";
import VizCard from "./VizCard";

/**
 * Single chat message — AI (left) or user (right).
 */
export default function ChatMessage({ message, orgName, report, onSuggestionSelect, isWelcome }) {
  const isUser = message.role === "user";
  const initials = orgName
    ? orgName.split(/\s+/).map((w) => w[0]).join("").toUpperCase().slice(0, 2)
    : "U";

  if (isUser) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex gap-2.5 max-w-[70%] self-end flex-row-reverse"
      >
        <div className="w-8 h-8 rounded-full border-[1.5px] border-border bg-bg-hover flex items-center justify-center flex-shrink-0">
          <span className="text-accent-orange text-[11px] font-bold uppercase">
            {initials}
          </span>
        </div>
        <div>
          {orgName && (
            <div className="text-right mb-0.5">
              <span className="text-text-secondary text-[9px]">{orgName}</span>
            </div>
          )}
          <div className="bg-[#1e293b] rounded-xl rounded-tr-sm px-3.5 py-2.5">
            <p className="text-text-primary text-sm">{message.content}</p>
          </div>
        </div>
      </motion.div>
    );
  }

  // AI message
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-2.5 max-w-[90%]"
    >
      <div className="w-8 h-8 rounded-full border-[1.5px] border-accent-orange/30 bg-accent-orange/10 flex items-center justify-center flex-shrink-0">
        <span className="text-accent-orange text-[6.5px] font-bold leading-none text-center">
          Vision
          <br />
          AI
        </span>
      </div>
      <div className="bg-bg-card rounded-xl rounded-tl-sm px-3.5 py-3 flex-1">
        <div className="text-accent-orange text-[10px] font-semibold mb-1">
          Vision AI
        </div>
        <p className={`text-sm leading-relaxed ${message.error ? "text-accent-red" : "text-text-primary"}`}>
          {message.content}
        </p>

        {/* Embedded visualizations */}
        {message.visualizations?.map((viz, i) => (
          <div key={i} className="mt-2.5">
            <VizCard viz={viz} report={report} />
          </div>
        ))}

        {/* Suggestion chips on welcome message */}
        {isWelcome && onSuggestionSelect && (
          <SuggestionChips onSelect={onSuggestionSelect} />
        )}
      </div>
    </motion.div>
  );
}
```

- [ ] **Step 5: Create VizCard router (placeholder)**

Create `dashboard/src/components/chat/VizCard.jsx`:

```jsx
import { lazy, Suspense } from "react";

const CARD_MAP = {
  zone_map: lazy(() => import("../viz-cards/ZoneMapCard")),
  zone_map_bev: lazy(() => import("../viz-cards/ZoneMapBEVCard")),
  zone_detail: lazy(() => import("../viz-cards/ZoneDetailCard")),
  bar_chart: lazy(() => import("../viz-cards/BarChartCard")),
  sankey: lazy(() => import("../viz-cards/SankeyCard")),
  temporal: lazy(() => import("../viz-cards/TemporalCard")),
  kpi_cards: lazy(() => import("../viz-cards/KPICard")),
  data_table: lazy(() => import("../viz-cards/DataTableCard")),
  heatmap_image: lazy(() => import("../viz-cards/HeatmapImageCard")),
};

/**
 * Viz card router — lazy-loads the correct card component based on type.
 */
export default function VizCard({ viz, report }) {
  const CardComponent = CARD_MAP[viz.type];

  if (!CardComponent) {
    return (
      <div className="bg-bg-primary border border-border rounded-lg p-3 text-text-secondary text-xs">
        Unknown visualization: {viz.type}
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="bg-bg-primary border border-border rounded-lg p-4 animate-pulse">
          <div className="h-3 w-32 bg-border rounded mb-2" />
          <div className="h-24 bg-border/50 rounded" />
        </div>
      }
    >
      <CardComponent config={viz.config || {}} report={report} />
    </Suspense>
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/components/chat/
git commit -m "feat(chat): add core chat components — input, message, thinking, suggestions"
```

---

## Chunk 3: Visualization Cards (9 types)

### Task 7: Create All 9 Viz Card Components

**Files:**
- Create: `dashboard/src/components/viz-cards/BarChartCard.jsx`
- Create: `dashboard/src/components/viz-cards/ZoneDetailCard.jsx`
- Create: `dashboard/src/components/viz-cards/SankeyCard.jsx`
- Create: `dashboard/src/components/viz-cards/TemporalCard.jsx`
- Create: `dashboard/src/components/viz-cards/ZoneMapCard.jsx`
- Create: `dashboard/src/components/viz-cards/ZoneMapBEVCard.jsx`
- Create: `dashboard/src/components/viz-cards/KPICard.jsx`
- Create: `dashboard/src/components/viz-cards/DataTableCard.jsx`
- Create: `dashboard/src/components/viz-cards/HeatmapImageCard.jsx`

Each card receives `{ config, report }` props and renders a compact, dark-themed card suitable for inline chat embedding.

All cards follow this pattern:
```jsx
export default function XCard({ config, report }) {
  const data = /* extract from report based on config */;
  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          Card Title
        </h4>
      </div>
      <div className="p-3">
        {/* card content */}
      </div>
    </div>
  );
}
```

- [ ] **Step 1: Create BarChartCard** — Adapted from ZoneBarChart, compact for chat. Uses recharts BarChart with the metric from `config.metric`.

- [ ] **Step 2: Create ZoneDetailCard** — Single zone detail with crop image placeholder, name, type, area, visits, dwell, density. Uses `config.zone_id` to look up data.

- [ ] **Step 3: Create SankeyCard** — Adapted from SankeyFlow, compact. Optional `config.filter_zone` to highlight one zone's connections.

- [ ] **Step 4: Create TemporalCard** — Adapted from TemporalHeatmap, compact. Optional `config.highlight_zone`.

- [ ] **Step 5: Create ZoneMapCard** — Camera perspective view with zone polygons. Optional `config.highlight_zones`.

- [ ] **Step 6: Create ZoneMapBEVCard** — BEV view, compact. Optional `config.highlight_zones`.

- [ ] **Step 7: Create KPICard** — Compact KPI grid (2×2 or 1×4). Shows total zones, visits, avg dwell, peak density.

- [ ] **Step 8: Create DataTableCard** — New component. Sortable table with columns from `config.columns`. Click column header to sort.

- [ ] **Step 9: Create HeatmapImageCard** — Displays `/data/viz/detection_heatmap.png` or similar.

- [ ] **Step 10: Commit**

```bash
git add dashboard/src/components/viz-cards/
git commit -m "feat(chat): add 9 visualization card components for chat embedding"
```

---

## Chunk 4: Pages + Routing + Integration

### Task 8: Extract Dashboard to Page + Create Chat Page

**Files:**
- Create: `dashboard/src/pages/DashboardPage.jsx`
- Create: `dashboard/src/pages/ChatPage.jsx`
- Modify: `dashboard/src/App.jsx`
- Modify: `dashboard/src/main.jsx`

- [ ] **Step 1: Create DashboardPage** — Move existing App.jsx content into `DashboardPage.jsx`. Keep all imports, sections, refs, zone detail panel.

- [ ] **Step 2: Create ChatPage** — Full chat-first interface:
  - Header: Ipsotek logo, "RetailVision AI", video meta, editable org name, Dashboard link, New Chat
  - Chat stream: Welcome message + messages from `useChat()`
  - ThinkingIndicator when loading
  - ChatInput at bottom
  - Footer: "Powered by Ipsotek, an Eviden business · N zones · M min footage"

- [ ] **Step 3: Update App.jsx with routing** — Use react-router-dom:
  - `/` → redirects to `/chat`
  - `/chat` → ChatPage
  - `/dashboard` → DashboardPage

- [ ] **Step 4: Update main.jsx** — Wrap App in BrowserRouter.

- [ ] **Step 5: Verify dashboard build**

Run: `cd E:/Agentic-path/retailvision/dashboard && npx vite build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/pages/ dashboard/src/App.jsx dashboard/src/main.jsx
git commit -m "feat(chat): add chat page with routing, preserve dashboard"
```

---

### Task 9: Backend CLI Entry Point

**Files:**
- Create: `scripts/run_chat_server.py`

- [ ] **Step 1: Create CLI script**

Create `scripts/run_chat_server.py`:

```python
"""CLI to start the RetailVision Chat API server.

Usage:
    python -m scripts.run_chat_server --report dashboard/public/data/report.json
    python -m scripts.run_chat_server --openrouter-key sk-...
"""
import click
import uvicorn

from api.chat_server import create_app


@click.command()
@click.option("--report", default="dashboard/public/data/report.json", help="Path to report.json")
@click.option("--openrouter-key", envvar="OPENROUTER_API_KEY", default="", help="OpenRouter API key")
@click.option("--vlm-model", default="qwen/qwen3.5-35b-a3b", help="VLM model")
@click.option("--host", default="0.0.0.0", help="Host")
@click.option("--port", default=8000, type=int, help="Port")
def main(report, openrouter_key, vlm_model, host, port):
    """Start the RetailVision Chat API server."""
    app = create_app(
        report_path=report,
        openrouter_api_key=openrouter_key,
        vlm_model=vlm_model,
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/run_chat_server.py
git commit -m "feat(chat): add chat server CLI entry point"
```

---

### Task 10: Integration Testing + Polish

- [ ] **Step 1: Run all existing Python tests**

Run: `cd E:/Agentic-path/retailvision && conda run -n retailvision python -m pytest tests/ -v --tb=short`
Expected: All tests pass (70 existing + new chat tests)

- [ ] **Step 2: Build dashboard**

Run: `cd E:/Agentic-path/retailvision/dashboard && npx vite build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Manual smoke test**

Start backend: `conda run -n retailvision python -m scripts.run_chat_server`
Start frontend: `cd dashboard && npx vite`
Open: http://localhost:5173/chat

Verify:
- Welcome message with suggestion chips appears
- Clicking a chip sends the query
- ThinkingIndicator shows during loading
- Response appears with text + viz cards
- "Dashboard ↗" link navigates to /dashboard
- Editable org name updates initials live
- /dashboard shows the full legacy dashboard

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(chat): complete chat-first interface with 9 viz cards"
```
