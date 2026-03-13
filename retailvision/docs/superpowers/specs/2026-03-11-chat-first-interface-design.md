# RetailVision AI — Chat-First Interface Design

**Date**: 2026-03-11
**Status**: Approved

## Overview

A ChatGPT-style conversational AI interface that replaces the existing scroll-based dashboard. Users type natural language questions, and Vision AI responds with narrative text + embedded interactive visualization cards. Powered by qwen3.5 via OpenRouter for intent classification and response generation.

## Architecture

```
┌─────────────────────────────────────┐
│       React Chat-First UI           │
│  Chat Feed + 9 Embedded Viz Cards   │
│         ▲  SSE streaming  ▲         │
└─────────┼─────────────────┼─────────┘
          │ POST /api/chat  │
          ▼                 │
┌─────────────────────────────────────┐
│       FastAPI Backend (thin)        │
│  Sessions (memory) + Intent Router  │
│  Data Query Layer (report.json)     │
│  OpenRouter VLM API (qwen3.5)      │
└─────────────────────────────────────┘
```

## Decisions

| Decision | Choice |
|----------|--------|
| VLM interaction | Approach C: Full conversational agent |
| Query scope | Tiers 1-3: Navigation, Data Q&A, Live Analysis |
| UI layout | D: Chat-first with embedded visualizations |
| Backend | B: Session-based with SSE streaming |
| Viz cards | 9 types (all except 3D scene) |

## Backend: `api/chat_server.py`

FastAPI server with:

- `POST /api/chat` — accepts `{ session_id, message }`, returns SSE stream
- `GET /api/report` — serves loaded report.json
- `GET /api/health` — health check

### Session Store

In-memory dict keyed by session ID:
- Conversation history (last 20 messages)
- Loaded report data reference
- Session metadata (created_at, video_id)

### VLM Intent Classification

System prompt instructs qwen3.5 to return structured JSON:

```json
{
  "thinking": "User wants to compare dwell times across zones...",
  "text": "Zone 5 (Subway) has the highest dwell time at 47.2s...",
  "visualizations": [
    { "type": "bar_chart", "metric": "avg_dwell_seconds", "zones": "all" },
    { "type": "zone_detail", "zone_id": "zone_005" }
  ]
}
```

### 9 Visualization Types

| Type | Config | Source Component |
|------|--------|-----------------|
| `zone_map` | `highlight_zones?` | ZoneMapPerspective |
| `zone_map_bev` | `highlight_zones?` | ZoneMapBEV |
| `zone_detail` | `zone_id` | ZoneDetailCard (new) |
| `bar_chart` | `metric, zones, sort_by?` | ZoneBarChart |
| `sankey` | `filter_zone?` | SankeyFlow |
| `temporal` | `highlight_zone?` | TemporalHeatmap |
| `kpi_cards` | `metrics?` | KPISummary (compact) |
| `data_table` | `columns, sort_by, filter?` | DataTable (new) |
| `heatmap_image` | — | Static PNG |

## Frontend: Chat-First UI

### Layout

- **Header**: Ipsotek logo (e:/logo.png) | divider | "RetailVision AI" + video meta | editable org name | Dashboard link | New Chat
- **Chat stream**: Scrollable message feed with AI (left) and User (right) messages
- **Input bar**: Rounded input, Ipsotek orange send button, footer "Powered by Ipsotek, an Eviden business · 15 zones · 30 min footage"

### Branding

- Ipsotek orange: `#e8632b`
- Vision AI avatar: Circle with "Vision AI" text, orange border
- User avatar: Circle with org initials in uppercase orange
- Suggestion chips: Orange-tinted
- Send button: Solid orange

### States

1. **Welcome**: AI greets with scene summary + 4 suggestion chips
2. **Loading**: Three animated orange dots + "Thinking" text, input dimmed
3. **Response**: Narrative text + 0-3 embedded viz cards
4. **Error**: Red-tinted message with retry button

### Organization Name

- Editable inline text field in header (pencil icon)
- Updates user avatar initials and message labels live
- Persisted to localStorage

### Existing Dashboard

- Accessible via "Dashboard ↗" link in header
- Kept as a separate route, not removed

## Data Flow

1. User types question → `POST /api/chat { session_id, message }`
2. Backend builds VLM prompt: system prompt (report summary) + conversation history + user message
3. VLM returns structured JSON via SSE stream
4. Frontend renders text progressively, then viz cards after stream completes
5. Conversation stored in session for context ("that zone", "compare with previous")

## File Structure

```
api/
  chat_server.py          # FastAPI server
  chat_prompt.py          # System prompt + report summarizer
  session_store.py        # In-memory session management

dashboard/src/
  App.jsx                 # Add routing: /chat (new default) + /dashboard (legacy)
  pages/
    ChatPage.jsx          # Chat-first interface
    DashboardPage.jsx     # Existing dashboard (moved from App.jsx)
  components/
    chat/
      ChatInput.jsx       # Input bar with send button
      ChatMessage.jsx     # Single message (AI or user)
      ThinkingIndicator.jsx # Animated dots loading
      SuggestionChips.jsx # Clickable query suggestions
      VizCard.jsx         # Viz card router (dispatches to specific card)
    viz-cards/
      ZoneDetailCard.jsx  # New: single zone detail
      DataTableCard.jsx   # New: sortable data table
      BarChartCard.jsx    # Adapted from ZoneBarChart
      SankeyCard.jsx      # Adapted from SankeyFlow
      TemporalCard.jsx    # Adapted from TemporalHeatmap
      ZoneMapCard.jsx     # Adapted from ZoneMapPerspective
      ZoneMapBEVCard.jsx  # Adapted from ZoneMapBEV
      KPICard.jsx         # Adapted from KPIRibbon
      HeatmapImageCard.jsx # Static PNG display
  hooks/
    useChat.js            # Chat state, SSE connection, message handling
```

## Testing

### Backend Tests
- `tests/test_chat_server.py` — API endpoints, session management, SSE streaming
- `tests/test_chat_prompt.py` — Report summarization, VLM prompt construction

### Frontend Tests
- Manual verification of all 9 viz card types
- Chat flow: send → thinking → response with viz
- Org name editing + persistence
- SSE reconnection on failure
- Dashboard link navigation

### Integration
- Full round-trip: user question → VLM → structured response → rendered viz cards
- Session continuity: follow-up questions reference previous context
