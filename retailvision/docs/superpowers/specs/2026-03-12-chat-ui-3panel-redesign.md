# Chat UI 3-Panel Redesign — Design Spec

**Date**: 2026-03-12
**Status**: Approved
**Approach**: Gallery-Centric with Prev/Next Navigation (Option B)

## Overview

Redesign the RetailVision chat interface from a 2-panel layout (left: viz+examples, right: chat) into a 3-panel gallery-centric layout: Chat (left) | Media Gallery (center, dominant) | Examples Marquee (right, collapsible). Fix zone map zoom interaction bug, add back navigation, and resolve PANEL_VIZ_TYPES duplication.

## Goals

1. Media/visualizations are the focal point — large, centered, interactive
2. Users can browse all conversation visualizations via prev/next gallery
3. Chat and examples panels are secondary — resizable and collapsible
4. Zone map interactions work correctly at all zoom levels
5. Proper navigation between dashboard and chat pages

## Non-Goals

- Multi-viz simultaneous display (side-by-side comparisons)
- Thumbnail filmstrip (decided against in approach selection)
- Chat session history / multi-conversation support
- Mobile-first responsive design (tablet/small laptop covered, phone not)

---

## 1. Panel Layout Architecture

### Structure

```
┌─────────────────────────────────────────────────────────────┐
│  ← Back  │  Logo  │  Metadata  │  OrgName  │  New Chat  │  │
├──────────┬────────────────────────────────────┬─────────────┤
│          │                                    │ E           │
│  Chat    ║  Media Gallery                     │ X           │
│  Panel   ║  (prev/next arrows)                │ A           │
│          ║                                    │ M           │
│          ║     ┌──────────────────┐           │ P           │
│  [msgs]  ║     │                  │    ◀  ▶   │ L           │
│          ║     │   Active Viz     │           │ E           │
│          ║     │   (full size)    │   2 / 5   │ S           │
│          ║     │                  │           │ ▸           │
│          ║     └──────────────────┘           │             │
│          ║                                    │             │
│ [input]  ║                                    │             │
└──────────╨────────────────────────────────────┴─────────────┘
  320px      flex-1 (fills remaining)             32px collapsed
  min:280px  min:400px                            240px expanded
```

### Panel Specifications

| Panel | Default Width | Min Width | Resizable | Collapsible |
|-------|-------------|-----------|-----------|-------------|
| Chat | 320px | 280px | Yes (drag handle on right edge) | No |
| Media Gallery | flex-1 | 400px | Auto-expands to fill | No |
| Examples Marquee | 240px (expanded) / 32px (collapsed) | — | No | Yes (toggle tab) |

### Resize Handle

- Single vertical drag handle between Chat and Media panels
- Visual: 4px wide, subtle border color, changes to accent-cyan on hover
- Cursor: `col-resize`
- Behavior: Dragging adjusts Chat panel width. Media absorbs remaining space. Chat width clamped to [280px, 50% of viewport].
- Chat width persisted to localStorage.

### Responsive Behavior (< 1024px viewport)

- Chat becomes a floating drawer: absolute positioned over the left side of Media, with backdrop shadow
- Drawer width: 320px (same as default), max 85vw
- Toggle via a chat icon button (fixed position, top-left of media area)
- Backdrop: semi-transparent overlay (`bg-black/30`), clicking it dismisses the drawer
- z-index layering: backdrop (z-40) < drawer (z-50) < gallery nav arrows (z-30, behind drawer)
- Examples panel auto-collapses to the 32px tab
- Media fills 100% viewport width
- Drawer slides in/out with 200ms ease transition
- Input bar stays inside the drawer (not accessible outside it)

---

## 2. Media Gallery Component

### New Component: `MediaGallery.jsx`

Central gallery that collects and displays all visualizations from the conversation.

### Visualization Collection

- Maintains a flat ordered array: `vizList: Array<{ id, type, data, messageIndex }>`
- Each time an assistant message contains a `visualization` payload, it's appended to `vizList`
- `id` is auto-generated (`viz-{messageIndex}-{type}`) for stable identity
- `messageIndex` links back to the originating chat message

### Navigation

- **Prev/Next arrows**: Large circular semi-transparent buttons (40px diameter), overlaid on left/right edges of the media area. Visible on hover, always visible on touch devices.
- **Counter**: Top-right of gallery header, displays `{current} / {total}` (e.g., "2 / 5")
- **Keyboard**: Left/Right arrow keys when gallery is focused. Gallery receives focus on click.
- **Chat linkage**: Clicking a viz chip in a chat message calls `gallery.goTo(vizId)` to navigate to that specific visualization.

### Auto-Focus Behavior

- When a new viz streams in from SSE, gallery auto-navigates to it (shows latest)
- If user has manually navigated to a different viz (clicked prev/next), set `userBrowsing = true`
- While `userBrowsing === true`, suppress auto-focus
- Reset `userBrowsing = false` when the user sends a new message

### Rendering

- Gallery wraps each viz card component, passing full available `width` and `height` as props
- Viz cards render at the gallery's full content area (minus header and padding)
- All viz types render here: zone_map, zone_map_bev, video_player, bar_chart, sankey, temporal, kpi_cards, data_table, heatmap_image, zone_detail
- Transition between vizs: crossfade with absolute positioning. Gallery content area uses `position: relative` with fixed dimensions. Each viz card is `position: absolute; inset: 0` so vizs of different sizes stack without layout jumps. Active viz: `opacity: 1; z-index: 1`. Previous viz: `opacity: 0; z-index: 0`. Transition: 150ms opacity ease.

### Empty State

- Before any vizs exist, display the reference frame image (`reference_frame.png` from report config)
- Subtle centered text: "Ask a question to generate visualizations"
- Muted styling (opacity 0.6)

### Gallery Header

- Left: Viz type label (e.g., "Zone Map — Camera View")
- Right: Counter ("2 / 5")
- Background: `bg-viz-header` (#141420)

---

## 3. Chat Panel Redesign

### Layout

- Moves from right side to left side
- Default 320px width, min 280px
- Full height minus header
- Flex column: message scroll area (flex-1) + input bar (pinned bottom)

### Message Rendering Changes

- **Text content**: Renders as today (markdown bold, etc.)
- **Visualizations in messages**: ALL viz types are replaced with a **viz link chip** instead of inline rendering:
  ```
  [🗺️ Zone Map — Camera View  →]
  ```
- Chip styling: rounded pill, 1px accent border, icon + label + arrow, hover: subtle glow + pointer cursor
- Clicking a chip: calls `onVizFocus(vizId)` which navigates the gallery
- This eliminates the current `filterPanelVizs` logic — no vizs render inline anymore

### Viz Link Chip Component: `VizChip.jsx`

```
Props:
  - vizType: string (zone_map, bar_chart, etc.)
  - label: string (human-readable name)
  - vizId: string (gallery reference)
  - onClick: (vizId) => void
```

- Icon mapping: zone_map → 🗺️, bar_chart → 📊, video_player → 🎥, heatmap_image → 🔥, sankey → 🔀, temporal → ⏱️, kpi_cards → 📈, data_table → 📋, zone_detail → 📍, zone_map_bev → 🏗️
- Compact: ~32px height, fits inline with text flow

### Welcome Message

- Suggestion chips remain (compact, fit narrow panel)
- No inline viz display

### Input Bar

- Same functionality as today
- Full width within panel (no max-width constraint)
- Footer metadata (scene type, zones count, analytics) moves to the global header bar

---

## 4. Examples Marquee Panel

### Collapsed State (default on first visit)

- 32px wide vertical tab on the right edge of the viewport
- Rotated text: "EXAMPLES ▸" in accent-amber (#ff9500)
- Background: bg-card (#12121a) with left border
- Clicking anywhere on the tab expands the panel

### Expanded State

- 240px wide
- Contains the existing PromptShowcase component (7 categories, vertical marquee, pause on hover, clickable prompts)
- Toggle arrow flips: "◂ EXAMPLES" in header
- Close by clicking the toggle arrow or the tab area

### Animation

- Width transition: 200ms ease-out
- Content fades in after width animation completes (50ms delay + 150ms opacity)
- Prevents content flash during expansion

### State Persistence

- Collapsed/expanded state saved to `localStorage` key: `retailvision-examples-panel`
- Restored on mount

---

## 5. Bug Fixes

### Fix #1: Zone Map Interaction Breaks on Zoom

**File**: `dashboard/src/components/viz-cards/ZoneMapCard.jsx`

**Root Cause**: Two coordinate-related bugs when zoomed:
1. **Tooltip positioning** (`handlePolygonMouseEnter`, ~lines 135-140): Calculates position relative to the SVG bounding rect but does NOT divide by zoom factor, causing the tooltip to appear at the wrong offset when zoomed in.
2. **Pan sensitivity** (`handlePointerMove`, ~lines 64-68): Uses raw `clientX` deltas without accounting for the scale factor, causing pan movement to feel too fast/slow at higher zoom levels.

Note: `handlePolygonClick` itself just receives a `zoneId` string and calls `onZoneClick(zoneId)` — it does NOT use coordinates. The browser's own hit-testing for SVG polygon click/hover events correctly accounts for CSS transforms, so polygon clicks themselves still work. The bugs are in the tooltip and pan handlers.

**Fix Strategy**:
1. **Tooltip fix**: In `handlePolygonMouseEnter`, divide the computed x/y offsets by the current `zoom` factor so the tooltip tracks the polygon correctly at all zoom levels.
2. **Pan fix**: In `handlePointerMove`, divide `clientX/clientY` deltas by `zoom` so pan sensitivity matches the visual scale: `setPanX(prev => prev + deltaX / zoom)`.
3. Optionally, use the SVG element's `getScreenCTM().inverse()` with `createSVGPoint()` for a more robust screen→SVG coordinate mapping.

**Testing**: Verify tooltip appears over the correct polygon and pan moves at expected speed at zoom levels 1x, 2x, 3x, 5x.

### Fix #2: No Back Button

**Files**: `dashboard/src/pages/ChatPage.jsx`, potentially `DashboardPage`

**Fix**:
- Add `← Back` button in ChatPage header, left of the logo
- Implementation: `useNavigate()` from react-router. On click: check `location.key !== 'default'` (React Router sets key to `'default'` when there's no prior in-app navigation). If a previous in-app entry exists, `navigate(-1)`. Otherwise, `navigate('/dashboard')`. This avoids the unreliable `window.history.length` which counts all session entries including external sites.
- Style: text button with accent-cyan color, hover underline
- Add matching `← Back to Chat` button on DashboardPage

### Fix #3: PANEL_VIZ_TYPES Duplication

**Current**: `PANEL_VIZ_TYPES` set defined in both `ChatPage.jsx` and `ChatMessage.jsx`

**Fix**:
- Create `dashboard/src/lib/constants.js`
- Export `VIZ_TYPES` object with type metadata (icon, label, etc.)
- Import everywhere instead of local definitions
- In the new design, this becomes the single source of truth for viz type → icon mapping used by `VizChip`

---

## 6. State Management

### New State in ChatPage

```javascript
// Gallery state
const [vizList, setVizList] = useState([])        // All vizs collected from messages
const [activeVizIndex, setActiveVizIndex] = useState(0)  // Currently displayed viz
const [userBrowsing, setUserBrowsing] = useState(false)  // Manual navigation flag

// Panel state
const [chatWidth, setChatWidth] = useState(() =>
  parseInt(localStorage.getItem('retailvision-chat-width')) || 320
)
const [examplesOpen, setExamplesOpen] = useState(() =>
  localStorage.getItem('retailvision-examples-panel') !== 'collapsed'
)
```

### Viz Collection Logic

- `useEffect` watches `messages` array
- On change, scans for new/changed visualizations and appends to `vizList`
- Each viz entry: `{ id, type, data, messageIndex, label }`
- **SSE safety**: Only process a message's visualizations when the visualization array is non-empty and contains fully-formed entries (has `type` and `data` fields). Skip partially-streamed entries to avoid duplicates or errors during SSE accumulation.
- Dedup by `id` (`viz-{messageIndex}-{type}`) to prevent re-adding on re-renders
- If `!userBrowsing`, auto-set `activeVizIndex` to last item

### New Chat Reset

- When `clearChat()` is called (New Chat button), reset `vizList` to `[]` and `activeVizIndex` to `0`
- Gallery returns to the empty state (reference frame image)

### Panel Width Persistence

- `chatWidth` saved to localStorage on drag-end (debounced, not on every pixel)
- `examplesOpen` saved to localStorage on toggle

---

## 7. Component Tree (New)

```
ChatPage
├── Header
│   ├── BackButton (new)
│   ├── Logo
│   ├── Metadata (moved from footer)
│   ├── OrgName
│   ├── NewChatButton
│   └── Auth
├── PanelLayout (new)
│   ├── ChatPanel (resizable)
│   │   ├── MessageList
│   │   │   ├── ChatMessage (with VizChip instead of inline vizs)
│   │   │   │   └── VizChip (new — clickable viz link)
│   │   │   └── ThinkingIndicator
│   │   └── ChatInput
│   ├── ResizeHandle (new)
│   ├── MediaGallery (new)
│   │   ├── GalleryHeader (type label + counter)
│   │   ├── GalleryContent (active viz card, full size)
│   │   │   └── VizCard (existing, passed full dimensions)
│   │   └── NavArrows (prev/next overlay)
│   └── ExamplesPanel (new wrapper)
│       ├── CollapsedTab (vertical "EXAMPLES ▸")
│       └── ExpandedContent
│           └── PromptShowcase (existing)
```

### New Files

| File | Purpose |
|------|---------|
| `src/components/layout/PanelLayout.jsx` | 3-panel flex container with resize logic |
| `src/components/layout/ResizeHandle.jsx` | Draggable resize handle |
| `src/components/gallery/MediaGallery.jsx` | Gallery with nav, viz collection, rendering |
| `src/components/gallery/NavArrows.jsx` | Prev/next overlay buttons |
| `src/components/chat/VizChip.jsx` | Clickable viz link pill |
| `src/components/layout/ExamplesPanel.jsx` | Collapsible wrapper for PromptShowcase |
| `src/lib/constants.js` | Shared viz type metadata (icons, labels, types) |

### Modified Files

| File | Changes |
|------|---------|
| `ChatPage.jsx` | New layout structure, gallery state, viz collection, remove old 2-panel layout |
| `ChatMessage.jsx` | Replace inline viz rendering with VizChip components |
| `VizCard.jsx` | Remove `SIZE_CLASSES` map and `size` prop. Gallery renders viz cards inside an absolutely-positioned container that fills available space. VizCard no longer wraps in a sized div — it just renders the lazy-loaded component which fills its parent via CSS (`width: 100%; height: 100%`). |
| `ZoneMapCard.jsx` | Fix tooltip positioning (divide by zoom) and pan sensitivity (divide deltas by zoom). Remove hardcoded `maxHeight: 250` (line 164) so the card fills the gallery. Use `ResizeObserver` to recalculate dimensions when gallery resizes. |
| `App.jsx` | No changes needed |
| `index.css` | Add resize handle styles, panel transition styles |

---

## 8. Edge Cases

- **No visualizations yet**: Gallery shows reference frame with prompt text
- **Single visualization**: Arrows hidden, counter shows "1 / 1"
- **Rapid viz streaming**: Only collect vizs with fully-formed `type` + `data` fields. Dedup by viz `id` to prevent re-adds.
- **Very narrow chat panel (280px)**: Long messages wrap naturally, chips stack vertically if needed
- **Zone map at full gallery size**: Must recalculate viewBox/dimensions on gallery resize. Use ResizeObserver.
- **Examples panel toggle during resize**: Transition width, gallery auto-adjusts via flex-1
- **Browser back from dashboard**: Navigates correctly to chat with state preserved (React Router handles this)
- **Dead code cleanup**: Remove `getChatVizs` function in ChatPage.jsx (defined but never called)
- **Keyboard accessibility**: Gallery receives focus on click and via Tab. Left/Right arrows navigate vizs. Escape collapses examples panel if open. Gallery counter uses `aria-live="polite"` for screen reader announcements on viz change.
