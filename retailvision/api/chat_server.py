"""FastAPI chat server for RetailVision analytics.

Implements a ReAct-style agentic loop where the VLM can call data
query tools across multiple turns before producing a final answer.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import os

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse

from api.chat_prompt import VIZ_TYPES, build_system_prompt, summarize_report
from api.chat_tools import execute_tool, get_tool_names
from api.session_store import SessionStore

logger = logging.getLogger(__name__)

# Maximum tool-calling turns before forcing a final answer
MAX_AGENT_TURNS = 5

# Shared HTTP client for connection reuse (avoids TCP+TLS per request)
_http_client: httpx.AsyncClient | None = None


async def _get_http_client() -> httpx.AsyncClient:
    """Return a shared HTTP client with connection pooling."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10, read=120, write=10, pool=10),
        )
    return _http_client


# ── Request / response models ──────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


# ── App factory ────────────────────────────────────────────────

def create_app(
    report_path: str | Path,
    openrouter_api_key: str = "",
    vlm_model: str = "qwen/qwen3.5-9b",
    video_path: str = "E:/Agentic-path/2026-03-05_04-00-00_fixed.mp4",
    supabase_url: str = "",
    supabase_anon_key: str = "",
    static_dir: str = "",
) -> FastAPI:
    """Return a fully configured FastAPI application."""

    app = FastAPI(title="RetailVision Chat API")

    # CORS — allow everything during development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Supabase JWT auth (protects /api/* except /api/health) ───
    _supabase_url = supabase_url or os.environ.get(
        "SUPABASE_URL", "https://otjczdatmzdwhnsnnduh.supabase.co"
    )
    _allowed_domain = "ipsotek.com"
    _anon_key = supabase_anon_key or os.environ.get(
        "SUPABASE_ANON_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im90amN6ZGF0bXpkd2huc25uZHVoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMyNzA2ODcsImV4cCI6MjA4ODg0NjY4N30.b6FPvA2lkAzhILlDijtlpWw7FnxMmk2oKiKS_QT5GaM",
    )

    @app.middleware("http")
    async def supabase_auth_gate(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or path in ("/api/health", "/api/video"):
            return await call_next(request)
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        token = auth_header[7:]
        try:
            client = await _get_http_client()
            resp = await client.get(
                f"{_supabase_url}/auth/v1/user",
                headers={"Authorization": f"Bearer {token}", "apikey": _anon_key},
            )
            if resp.status_code != 200:
                return JSONResponse({"error": "invalid token"}, status_code=401)
            user = resp.json()
            email = user.get("email", "")
            if not email.lower().endswith(f"@{_allowed_domain}"):
                return JSONResponse({"error": "unauthorized domain"}, status_code=403)
        except Exception:
            return JSONResponse({"error": "auth verification failed"}, status_code=401)
        return await call_next(request)

    # ── shared state stored on app instance ────────────────────
    report_path = Path(report_path)
    with open(report_path) as f:
        report_data: dict = json.load(f)

    store = SessionStore()
    report_summary = summarize_report(report_data)
    system_prompt = build_system_prompt(report_summary)

    # Stash on app for testing convenience
    app.state.store = store
    app.state.report = report_data
    app.state.openrouter_api_key = openrouter_api_key
    app.state.vlm_model = vlm_model
    app.state.system_prompt = system_prompt
    app.state.video_path = video_path

    # ── endpoints ──────────────────────────────────────────────

    @app.get("/api/health")
    async def health():
        meta = report_data.get("meta", {})
        return {
            "status": "ok",
            "video_id": meta.get("video_id", "unknown"),
            "n_zones": len(report_data.get("zones", {})),
        }

    @app.get("/api/report")
    async def get_report():
        return report_data

    @app.get("/api/video")
    async def stream_video(request: Request):
        """Stream video file with HTTP range request support."""
        vpath = Path(video_path)
        if not vpath.exists():
            return StreamingResponse(
                iter([b"Video file not found"]),
                status_code=404,
                media_type="text/plain",
            )

        file_size = vpath.stat().st_size
        range_header = request.headers.get("range")

        if range_header:
            # Parse range header: "bytes=start-end"
            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                end = min(end, file_size - 1)
                chunk_size = end - start + 1

                def iter_range():
                    with open(vpath, "rb") as f:
                        f.seek(start)
                        remaining = chunk_size
                        while remaining > 0:
                            read_size = min(remaining, 1024 * 1024)  # 1MB chunks
                            data = f.read(read_size)
                            if not data:
                                break
                            remaining -= len(data)
                            yield data

                return StreamingResponse(
                    iter_range(),
                    status_code=206,
                    media_type="video/mp4",
                    headers={
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Accept-Ranges": "bytes",
                        "Content-Length": str(chunk_size),
                    },
                )

        # No range header — stream entire file
        def iter_file():
            with open(vpath, "rb") as f:
                while True:
                    data = f.read(1024 * 1024)
                    if not data:
                        break
                    yield data

        return StreamingResponse(
            iter_file(),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
            },
        )

    @app.post("/api/chat")
    async def chat(req: ChatRequest):
        # 1. session
        session_id = req.session_id
        if not session_id or store.get(session_id) is None:
            video_id = report_data.get("meta", {}).get("video_id", "unknown")
            session_id = store.create(video_id)

        store.add_message(session_id, "user", req.message)

        # 2. SSE stream with real-time agent events
        async def event_generator():
            yield {"data": json.dumps({"session_id": session_id})}

            if not openrouter_api_key:
                yield {"data": json.dumps({"type": "text", "content": "No API key configured."})}
                yield {"data": "[DONE]"}
                return

            full_text = ""
            try:
                async for event in _stream_vlm_agent(
                    openrouter_api_key,
                    vlm_model,
                    system_prompt,
                    store.get(session_id)["messages"],
                    report_data,
                ):
                    if event.get("type") == "text":
                        full_text += event.get("content", "")
                    yield {"data": json.dumps(event)}
            except Exception as exc:
                logger.exception("Agent error for session %s", session_id)
                yield {"data": json.dumps({
                    "type": "error",
                    "content": f"Server error: {exc}",
                })}

            store.add_message(session_id, "assistant", full_text)
            yield {"data": "[DONE]"}

        return EventSourceResponse(
            event_generator(),
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Static file serving (production build) ─────────────────
    if static_dir:
        static_path = Path(static_dir)
        if static_path.is_dir():
            # Serve data files (report.json, images)
            data_dir = static_path / "data"
            if data_dir.is_dir():
                app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")

            # Serve /assets via StaticFiles mount (correct MIME types, CF-compatible)
            assets_dir = static_path / "assets"
            if assets_dir.is_dir():
                app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

            # SPA catch-all: serve index.html for all non-API, non-asset routes
            _index_html = (static_path / "index.html").read_text()

            @app.get("/{full_path:path}")
            async def spa_catchall(request: Request, full_path: str):
                # Try serving static file first (for non-mounted paths like favicon)
                file = static_path / full_path
                if full_path and file.is_file():
                    import mimetypes
                    ct = mimetypes.guess_type(str(file))[0] or "application/octet-stream"
                    return StreamingResponse(open(file, "rb"), media_type=ct)
                return HTMLResponse(
                    _index_html,
                    headers={"Cache-Control": "no-transform"},
                )

            logger.info("Serving static files from %s", static_path)

    return app


# ── Agentic VLM caller (streaming) ────────────────────────────

async def _stream_vlm_agent(
    api_key: str,
    model: str,
    system_prompt: str,
    messages: list[dict],
    report: dict,
):
    """Async generator: runs agent loop, yields SSE event dicts.

    Tool-call turns use non-streaming (need full JSON to parse action).
    Final answer turn streams text token-by-token from OpenRouter.
    Yields tool_status events during tool calls for UI feedback.
    """
    tool_names = set(get_tool_names())

    oai_messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]
    for m in messages:
        oai_messages.append({"role": m["role"], "content": m["content"]})

    last_parsed: dict[str, Any] = {}
    t_agent_start = time.perf_counter()

    for turn in range(MAX_AGENT_TURNS):
        if turn == MAX_AGENT_TURNS - 1:
            oai_messages.append({
                "role": "user",
                "content": (
                    "You have used all available tool turns. "
                    "Produce your final_answer now using the data you have."
                ),
            })

        t0 = time.perf_counter()

        # ── Stream tokens — separate reasoning from content ──
        raw_content = ""       # everything the model outputs (for think detection)
        full_content = ""      # clean JSON only (after stripping <think>)
        action_detected = None
        last_text_len = 0
        text_streamed = False
        thinking_notified = False
        in_think_block = False # track <think> in content field

        token_count = 0
        async for kind, token in _llm_call_streaming(api_key, model, oai_messages):
            token_count += 1
            if token_count <= 3 or token_count % 50 == 0:
                logger.debug("Turn %d token #%d kind=%s len=%d", turn, token_count, kind, len(token))

            if kind == "reasoning":
                # Model is in <think> phase — notify frontend once
                if not thinking_notified:
                    logger.info("Turn %d: model entered reasoning phase", turn)
                    yield {"type": "tool_status", "tool": "thinking", "message": "Reasoning..."}
                    thinking_notified = True
                continue

            # kind == "content" — could be <think> or actual JSON
            raw_content += token

            # ── Handle <think> blocks in content field ──
            # Some models put thinking in content, not reasoning
            if not in_think_block and "<think>" in raw_content and "</think>" not in raw_content:
                in_think_block = True
                if not thinking_notified:
                    yield {"type": "tool_status", "tool": "thinking", "message": "Reasoning..."}
                    thinking_notified = True
                continue
            if in_think_block:
                if "</think>" in raw_content:
                    # Think block complete — extract only post-think content
                    in_think_block = False
                    after_think = re.sub(
                        r"<think>.*?</think>", "", raw_content, flags=re.DOTALL
                    ).strip()
                    full_content = after_think
                else:
                    # Still inside think block — skip
                    continue
            else:
                full_content += token

            # ── Detect action type early from partial JSON ──
            if action_detected is None:
                am = re.search(r'"action"\s*:\s*"([^"]*)"', full_content)
                if am:
                    action_detected = am.group(1)

            # ── Stream text progressively if this is a final_answer ──
            if action_detected == "final_answer":
                tm = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)', full_content)
                if tm:
                    current_len = len(tm.group(1))
                    if current_len > last_text_len:
                        delta_raw = tm.group(1)[last_text_len:]
                        delta = delta_raw.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                        if not text_streamed:
                            logger.info("Turn %d: text streaming started at token #%d", turn, token_count)
                        yield {"type": "text", "content": delta}
                        text_streamed = True
                        last_text_len = current_len

        logger.info("Turn %d: %d tokens, content_len=%d, text_streamed=%s", turn, token_count, len(full_content), text_streamed)
        t_llm = time.perf_counter() - t0
        parsed = _parse_vlm_json(full_content)
        last_parsed = parsed

        action = parsed.get("action")
        logger.info(
            "Turn %d: action=%s  llm_call=%.1fs  response_len=%d",
            turn, action, t_llm, len(full_content),
        )

        # ── Final answer ──────────────────────────────────────
        if action == "final_answer":
            logger.info("Agent done: %d turns, total=%.1fs", turn + 1, time.perf_counter() - t_agent_start)
            # If text wasn't streamed (parsing issue), send it now
            if not text_streamed:
                text = parsed.get("text", "")
                if text:
                    yield {"type": "text", "content": text}
            for viz in parsed.get("visualizations", []):
                yield {"type": "visualization", "visualization": viz}
            primary = parsed.get("primary_viz", "")
            if primary:
                yield {"type": "primary_viz", "viz_type": primary}
            for act in parsed.get("actions", []):
                yield {"type": "action", "action": act}
            return

        # ── UI action (set_theme, set_viz_size) ─────────────
        ui_action_types = {"set_theme", "set_viz_size"}
        if action in ui_action_types:
            value = parsed.get("value", "")
            text = parsed.get("text", "")
            if not text:
                label = action.replace("set_", "").replace("_", " ")
                text = f"Done! Switched {label} to **{value}**."
            yield {"type": "text", "content": text}
            yield {"type": "action", "action": {"type": action, "value": value}}
            return

        # ── Visualization type used as action ─────────────────
        viz_type_set = set(VIZ_TYPES)
        if action in viz_type_set:
            viz = {k: v for k, v in parsed.items() if k != "action"}
            viz["type"] = action
            text = parsed.get("text", "")
            if text:
                yield {"type": "text", "content": text}
            yield {"type": "visualization", "visualization": viz}
            return

        # ── Tool call ─────────────────────────────────────────
        if action and action in tool_names:
            # Tell frontend a tool is running
            _tool_labels = {
                "query_zones": "Querying zones...",
                "get_zone_detail": "Loading zone details...",
                "search_zones": "Searching zones...",
                "get_flow_data": "Analyzing traffic flow...",
                "get_summary_stats": "Fetching summary stats...",
            }
            yield {
                "type": "tool_status",
                "tool": action,
                "message": _tool_labels.get(action, f"Running {action}..."),
            }

            action_input = parsed.get("action_input", {})
            try:
                t_tool = time.perf_counter()
                tool_result = execute_tool(action, action_input, report)
                result_text = json.dumps(tool_result, default=str)
                logger.info(
                    "  tool=%s  exec=%.3fs  result_len=%d",
                    action, time.perf_counter() - t_tool, len(result_text),
                )
                if len(result_text) > 8000:
                    result_text = result_text[:8000] + "... (truncated)"
            except Exception as exc:
                result_text = json.dumps({"error": str(exc)})

            oai_messages.append({"role": "assistant", "content": full_content})
            oai_messages.append({
                "role": "user",
                "content": (
                    f"Tool '{action}' returned:\n{result_text}\n\n"
                    "Respond with final_answer now. Use the data above to populate "
                    "your text and visualization data arrays. Do not call another tool "
                    "unless you need different data."
                ),
            })
            continue

        # ── No action field / unknown action ──────────────────
        # If text was already streamed progressively, don't dump raw JSON
        if not text_streamed:
            text = parsed.get("text", "")
            if text:
                yield {"type": "text", "content": text}
        # Try to recover visualizations even from partial/truncated JSON
        vizzes = parsed.get("visualizations", [])
        if not vizzes:
            vizzes = _extract_partial_vizzes(full_content)
        for viz in vizzes:
            yield {"type": "visualization", "visualization": viz}
        primary = parsed.get("primary_viz", "")
        if primary:
            yield {"type": "primary_viz", "viz_type": primary}
        return

    # Exhausted turns
    text = last_parsed.get("text", "I processed your request but ran out of reasoning steps.")
    yield {"type": "text", "content": text}


async def _llm_call_streaming(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    max_retries: int = 2,
):
    """Streaming LLM call to OpenRouter with retry for transient errors.

    Yields ``(kind, text)`` tuples where *kind* is ``"reasoning"``
    (Qwen ``<think>`` tokens) or ``"content"`` (actual JSON output).
    """
    import asyncio

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.1,
        "stream": True,
    }

    client = await _get_http_client()
    last_err = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = 2 ** attempt  # 2s, 4s
            logger.warning("LLM call retry %d/%d after %.0fs", attempt, max_retries, wait)
            await asyncio.sleep(wait)

        try:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120.0,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content") or ""
                        # OpenRouter uses "reasoning"; some providers use "reasoning_content"
                        reasoning = (
                            delta.get("reasoning")
                            or delta.get("reasoning_content")
                            or ""
                        )
                        if content:
                            yield ("content", content)
                        elif reasoning:
                            yield ("reasoning", reasoning)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                return  # success — exit retry loop

        except httpx.HTTPStatusError as exc:
            last_err = exc
            if exc.response.status_code in (429, 502, 503, 504) and attempt < max_retries:
                logger.warning("LLM transient error %d: %s", exc.response.status_code, exc)
                continue
            raise
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last_err = exc
            if attempt < max_retries:
                logger.warning("LLM connection error: %s", exc)
                continue
            raise


async def _llm_call(
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
) -> str:
    """Non-streaming LLM call (kept for fallback). Returns full content."""
    full = ""
    async for kind, token in _llm_call_streaming(api_key, model, messages):
        if kind == "content":
            full += token
    return full


def _parse_vlm_json(text: str) -> dict[str, Any]:
    """Extract JSON from VLM output.

    Handles:
    - Qwen <think>...</think> tags (strips them)
    - Markdown code fences
    - Raw JSON
    - Brace extraction as last resort
    """
    # 1. Strip Qwen think tags
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if not cleaned:
        cleaned = text.strip()

    # 2. Try stripping markdown code fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL)
    candidate = fenced.group(1).strip() if fenced else cleaned

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            parsed.setdefault("actions", [])
            return parsed
    except json.JSONDecodeError:
        pass

    # 3. Find first { … } block (greedy)
    brace = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if brace:
        try:
            parsed = json.loads(brace.group(0))
            if isinstance(parsed, dict):
                parsed.setdefault("actions", [])
                return parsed
        except json.JSONDecodeError:
            pass

    return {"text": text, "visualizations": [], "actions": []}


def _extract_partial_vizzes(content: str) -> list[dict]:
    """Best-effort extraction of visualization objects from truncated JSON.

    When max_tokens truncates the response mid-JSON, the main parser fails.
    This scans for complete {"type": "...", ...} objects within the
    visualizations array.
    """
    vizzes = []
    # Find the visualizations array start
    m = re.search(r'"visualizations"\s*:\s*\[', content)
    if not m:
        return vizzes
    rest = content[m.end():]
    # Try to find each complete JSON object in the array
    depth = 0
    start = None
    for i, ch in enumerate(rest):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                candidate = rest[start:i + 1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict) and obj.get("type"):
                        vizzes.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None
        elif ch == ']' and depth == 0:
            break
    return vizzes


