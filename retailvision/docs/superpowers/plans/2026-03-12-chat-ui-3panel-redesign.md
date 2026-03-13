# Chat UI 3-Panel Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the RetailVision chat UI from a 2-panel layout into a gallery-centric 3-panel layout with resizable chat, central media gallery, and collapsible examples marquee.

**Architecture:** Gallery-centric approach (Option B). Chat on left (resizable), media gallery center (dominant, prev/next navigation), examples marquee right (collapsible toggle tab). All visualizations render full-size in the gallery; chat shows clickable viz chips. Includes zone map zoom fix, back navigation, and shared constants.

**Tech Stack:** React 19, React Router 7.13, Tailwind CSS 4, Framer Motion 12, Vite 6.2

**Spec:** `docs/superpowers/specs/2026-03-12-chat-ui-3panel-redesign.md`

---

## Chunk 1: Foundation — Constants, Bug Fixes, VizChip

### Task 1: Create shared constants file

**Files:**
- Create: `dashboard/src/lib/constants.js`

- [ ] **Step 1: Create the constants file with VIZ_TYPES metadata**

```javascript
// dashboard/src/lib/constants.js

export const VIZ_TYPES = {
  zone_map:     { icon: '🗺️', label: 'Zone Map — Camera View' },
  zone_map_bev: { icon: '🏗️', label: 'Zone Map — Bird\'s Eye' },
  zone_detail:  { icon: '📍', label: 'Zone Detail' },
  bar_chart:    { icon: '📊', label: 'Bar Chart' },
  sankey:       { icon: '🔀', label: 'Flow Diagram' },
  temporal:     { icon: '⏱️', label: 'Temporal Pattern' },
  kpi_cards:    { icon: '📈', label: 'KPI Cards' },
  data_table:   { icon: '📋', label: 'Data Table' },
  heatmap_image:{ icon: '🔥', label: 'Heatmap' },
  video_player: { icon: '🎥', label: 'Video Player' },
};

/** All viz type keys as a Set (replaces old PANEL_VIZ_TYPES) */
export const ALL_VIZ_TYPES = new Set(Object.keys(VIZ_TYPES));

/** Get display label for a viz type, with fallback */
export function getVizLabel(type) {
  return VIZ_TYPES[type]?.label || type.replace(/_/g, ' ');
}

/** Get icon for a viz type */
export function getVizIcon(type) {
  return VIZ_TYPES[type]?.icon || '📊';
}
```

- [ ] **Step 2: Verify file was created**

Run: `ls dashboard/src/lib/constants.js`
Expected: File exists

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/lib/constants.js
git commit -m "feat: add shared VIZ_TYPES constants with icon/label metadata"
```

---

### Task 2: Fix zone map zoom interaction bugs

**Files:**
- Modify: `dashboard/src/components/viz-cards/ZoneMapCard.jsx`

- [ ] **Step 1: Fix pan sensitivity — divide deltas by zoom**

In `ZoneMapCard.jsx`, find the `handlePointerMove` function (~lines 64-68). The current code uses raw deltas:

```javascript
// Current (broken at zoom > 1):
const dx = e.clientX - panStart.current.x;
const dy = e.clientY - panStart.current.y;
setPan({ x: panOrigin.current.x + dx, y: panOrigin.current.y + dy });
```

Replace with zoom-compensated deltas:

```javascript
const dx = (e.clientX - panStart.current.x) / zoom;
const dy = (e.clientY - panStart.current.y) / zoom;
setPan({ x: panOrigin.current.x + dx, y: panOrigin.current.y + dy });
```

- [ ] **Step 2: Fix tooltip positioning — divide offsets by zoom**

In `handlePolygonMouseEnter` (~lines 131-143), the tooltip position is calculated from the SVG bounding rect. The x/y offsets need to be divided by zoom:

Find the tooltip position calculation (something like):
```javascript
const rect = e.currentTarget.closest('svg').getBoundingClientRect();
const x = e.clientX - rect.left;
const y = e.clientY - rect.top;
```

Change to:
```javascript
const rect = e.currentTarget.closest('svg').getBoundingClientRect();
const x = (e.clientX - rect.left) / zoom;
const y = (e.clientY - rect.top) / zoom;
```

- [ ] **Step 3: Remove hardcoded maxHeight: 250**

Find line ~164 with `style={{ maxHeight: 250, ... }}`. Change to remove the maxHeight constraint so the component fills its gallery container:

```javascript
// Before:
style={{ maxHeight: 250, cursor: zoom > 1 ? "grab" : "default" }}

// After:
style={{ cursor: zoom > 1 ? "grab" : "default" }}
```

- [ ] **Step 3b: Fix tooltip X-position clamp**

The tooltip positioning (~line 318) has a hardcoded `Math.min(tooltip.x + 8, 250)` that clamps the tooltip X to 250px — this was tied to the old maxHeight. Now that the card fills the gallery, use the container width instead. Find the tooltip style and change the 250 clamp to use the container's clientWidth (or just remove the clamp and let CSS `overflow: hidden` handle it).

- [ ] **Step 4: Verify the app still builds**

Run: `cd dashboard && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/viz-cards/ZoneMapCard.jsx
git commit -m "fix: zone map tooltip positioning and pan sensitivity at zoom > 1x

Divide pointer coordinate deltas by zoom factor in handlePointerMove
and handlePolygonMouseEnter. Remove hardcoded maxHeight: 250 so the
card can fill the gallery container."
```

---

### Task 3: Create VizChip component

**Files:**
- Create: `dashboard/src/components/chat/VizChip.jsx`

- [ ] **Step 1: Create the VizChip component**

```jsx
// dashboard/src/components/chat/VizChip.jsx
import { getVizIcon, getVizLabel } from '../../lib/constants';

export default function VizChip({ vizType, vizId, onClick }) {
  const icon = getVizIcon(vizType);
  const label = getVizLabel(vizType);

  return (
    <button
      onClick={() => onClick?.(vizId)}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 mt-2
        rounded-full border border-accent-cyan/30 bg-accent-cyan/5
        text-[11px] text-accent-cyan hover:bg-accent-cyan/10
        hover:border-accent-cyan/50 transition-all cursor-pointer
        group"
    >
      <span>{icon}</span>
      <span className="truncate max-w-[140px]">{label}</span>
      <span className="text-accent-cyan/50 group-hover:text-accent-cyan transition-colors">→</span>
    </button>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd dashboard && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/chat/VizChip.jsx
git commit -m "feat: add VizChip component for clickable viz links in chat"
```

---

### Task 4: Update ChatMessage to use VizChip instead of inline vizs

**Files:**
- Modify: `dashboard/src/components/chat/ChatMessage.jsx`

- [ ] **Step 1: Replace inline viz rendering with VizChip**

In `ChatMessage.jsx`:

1. Remove the `PANEL_VIZ_TYPES` constant (line 26)
2. Remove the `VizCard` import
3. Add `VizChip` import:
   ```javascript
   import VizChip from './VizChip';
   ```

4. Remove `filterPanelVizs` and `vizSize` props from the component signature. Keep `onSuggestionSelect` (used by welcome message's SuggestionChips).

5. Add `onVizFocus` to the component props. The full updated signature:
```javascript
export default function ChatMessage({
  message,
  orgName = "You",
  report,
  onSuggestionSelect,  // kept — used by SuggestionChips for welcome message
  onRetry,
  onZoneClick,
  onVizFocus,          // new — navigates gallery to clicked viz
  isWelcome = false,
  // filterPanelVizs removed
  // vizSize removed
}) {
```

6. Replace the visualization rendering block (~lines 108-121). Find the entire `{!isUser && (() => { ... })()}` IIFE that maps over visualizations. Replace with:

```jsx
{!isUser && message.visualizations?.length > 0 && (
  <div className="flex flex-wrap gap-1.5 mt-1">
    {message.visualizations.map((viz, vi) => (
      <VizChip
        key={vi}
        vizType={viz.type}
        vizId={`viz-${message.id}-${viz.type}-${vi}`}
        onClick={onVizFocus}
      />
    ))}
  </div>
)}
```

Note: the vizId format `viz-${message.id}-${viz.type}-${vi}` matches the gallery's viz collection ID format so clicking a chip navigates to the correct viz.

- [ ] **Step 2: Verify build**

Run: `cd dashboard && npm run build`
Expected: May show warnings about unused props in ChatPage (filterPanelVizs) — that's fine, we'll fix ChatPage in a later task.

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/chat/ChatMessage.jsx
git commit -m "feat: replace inline viz cards with VizChip links in chat messages

All visualization types now show as clickable pills that navigate
the gallery. Removes PANEL_VIZ_TYPES duplication and VizCard import."
```

---

### Task 5: Update VizCard — remove size classes, fill container

**Files:**
- Modify: `dashboard/src/components/chat/VizCard.jsx`

- [ ] **Step 1: Simplify VizCard to fill its parent**

1. Remove the `SIZE_CLASSES` constant (lines 16-20)
2. Remove the `size` prop from the component
3. Change the wrapper div from using `SIZE_CLASSES[size]` to a simple full-size container:

**IMPORTANT**: The current VizCard accepts `viz` prop (the full visualization object) and passes it as `config={viz}` to CardComponents. All 10 card components expect `config` to be the full viz object (containing `type`, `data`, `highlight_zones`, etc. at the top level). We keep the same prop shape — just rename the external prop for clarity:

```jsx
export default function VizCard({ viz, report, onZoneClick }) {
  const CardComponent = CARD_MAP[viz?.type];
  if (!CardComponent) return null;

  return (
    <Suspense fallback={<VizSkeleton />}>
      <div className="w-full h-full overflow-hidden">
        <CardComponent config={viz} report={report} onZoneClick={onZoneClick} />
      </div>
    </Suspense>
  );
}
```

The change from the current VizCard is only: remove SIZE_CLASSES, remove `size` prop, change wrapper div to `w-full h-full`. The `viz` prop and `config={viz}` pass-through stays identical.

- [ ] **Step 2: Verify build**

Run: `cd dashboard && npm run build`
Expected: Build succeeds. Warnings about unused `size` prop in ChatPage are expected (fixed later).

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/chat/VizCard.jsx
git commit -m "refactor: remove VizCard size classes, fill parent container

Gallery will provide sizing via its absolutely-positioned container.
VizCard now renders at 100% width/height of its parent."
```

---

## Chunk 2: Layout Components — ResizeHandle, ExamplesPanel, MediaGallery

### Task 6: Create ResizeHandle component

**Files:**
- Create: `dashboard/src/components/layout/ResizeHandle.jsx`

- [ ] **Step 1: Create the layout directory and ResizeHandle**

```jsx
// dashboard/src/components/layout/ResizeHandle.jsx
import { useCallback, useRef } from 'react';

export default function ResizeHandle({ onResize, onResizeEnd }) {
  const dragging = useRef(false);

  const handlePointerDown = useCallback((e) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handlePointerMove = (moveEvent) => {
      if (dragging.current) {
        onResize(moveEvent.clientX);
      }
    };

    const handlePointerUp = () => {
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('pointermove', handlePointerMove);
      document.removeEventListener('pointerup', handlePointerUp);
      onResizeEnd?.();
    };

    document.addEventListener('pointermove', handlePointerMove);
    document.addEventListener('pointerup', handlePointerUp);
  }, [onResize, onResizeEnd]);

  return (
    <div
      onPointerDown={handlePointerDown}
      className="w-1 shrink-0 cursor-col-resize bg-border hover:bg-accent-cyan/50
        transition-colors group flex items-center justify-center"
    >
      <div className="w-0.5 h-8 rounded-full bg-text-secondary/30
        group-hover:bg-accent-cyan/70 transition-colors" />
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd dashboard && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/layout/ResizeHandle.jsx
git commit -m "feat: add ResizeHandle component with pointer-event-based dragging"
```

---

### Task 7: Create ExamplesPanel component

**Files:**
- Create: `dashboard/src/components/layout/ExamplesPanel.jsx`

- [ ] **Step 1: Create ExamplesPanel with collapse/expand toggle**

```jsx
// dashboard/src/components/layout/ExamplesPanel.jsx
import PromptShowcase from '../chat/PromptShowcase';

export default function ExamplesPanel({ isOpen, onToggle, onSend }) {
  return (
    <div
      className="shrink-0 border-l border-border bg-card flex flex-col
        transition-[width] duration-200 ease-out overflow-hidden"
      style={{ width: isOpen ? 240 : 32 }}
    >
      {isOpen ? (
        <>
          {/* Expanded header */}
          <div className="flex items-center justify-between px-3 py-2
            border-b border-border bg-viz-header shrink-0">
            <span className="text-[11px] font-medium text-accent-amber">
              EXAMPLES
            </span>
            <button
              onClick={onToggle}
              className="text-text-secondary hover:text-text-primary
                text-xs transition-colors"
            >
              ◂
            </button>
          </div>
          {/* Content with fade-in */}
          {/* NOTE: PromptShowcase accepts `onSelect` prop, not `onSend` */}
          <div className="flex-1 overflow-hidden animate-[fadeIn_150ms_50ms_ease-out_both]">
            <PromptShowcase onSelect={onSend} />
          </div>
        </>
      ) : (
        /* Collapsed tab */
        <button
          onClick={onToggle}
          className="flex-1 flex items-center justify-center cursor-pointer
            hover:bg-hover transition-colors"
        >
          <span
            className="text-[11px] font-medium text-accent-amber tracking-wider"
            style={{ writingMode: 'vertical-rl' }}
          >
            EXAMPLES ▸
          </span>
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add the fadeIn keyframe to index.css**

In `dashboard/src/index.css`, add after the existing `marquee-scroll` keyframe:

```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

- [ ] **Step 3: Verify build**

Run: `cd dashboard && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/components/layout/ExamplesPanel.jsx dashboard/src/index.css
git commit -m "feat: add ExamplesPanel with collapsible toggle and fade animation"
```

---

### Task 8: Create MediaGallery component

**Files:**
- Create: `dashboard/src/components/gallery/MediaGallery.jsx`

- [ ] **Step 1: Create the gallery directory and MediaGallery component**

```jsx
// dashboard/src/components/gallery/MediaGallery.jsx
import { useCallback, useEffect, useRef } from 'react';
import VizCard from '../chat/VizCard';
import { getVizLabel } from '../../lib/constants';

export default function MediaGallery({
  vizList,
  activeIndex,
  onNavigate,
  report,
  onZoneClick,
  emptyImageSrc,
}) {
  const containerRef = useRef(null);
  const total = vizList.length;
  const activeViz = vizList[activeIndex] || null;

  // Keyboard navigation
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'ArrowLeft' && activeIndex > 0) {
      onNavigate(activeIndex - 1);
    } else if (e.key === 'ArrowRight' && activeIndex < total - 1) {
      onNavigate(activeIndex + 1);
    }
  }, [activeIndex, total, onNavigate]);

  // Focus on click for keyboard nav
  const handleFocus = () => containerRef.current?.focus();

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onClick={handleFocus}
      className="flex-1 min-w-[400px] flex flex-col bg-primary
        outline-none relative"
    >
      {/* Gallery header */}
      <div className="flex items-center justify-between px-4 py-2
        border-b border-border bg-viz-header shrink-0">
        <span className="text-[12px] font-medium text-accent-cyan truncate">
          {activeViz ? getVizLabel(activeViz.type) : 'Media Gallery'}
        </span>
        {total > 0 && (
          <span className="text-[11px] text-text-secondary ml-2 shrink-0"
            aria-live="polite">
            {activeIndex + 1} / {total}
          </span>
        )}
      </div>

      {/* Gallery content area */}
      <div className="flex-1 relative overflow-hidden">
        {total === 0 ? (
          /* Empty state */
          <div className="absolute inset-0 flex flex-col items-center
            justify-center opacity-60">
            {emptyImageSrc && (
              <img
                src={emptyImageSrc}
                alt="Store camera view"
                className="max-w-[60%] max-h-[60%] object-contain rounded-lg
                  border border-border mb-4"
              />
            )}
            <p className="text-text-secondary text-sm">
              Ask a question to generate visualizations
            </p>
          </div>
        ) : (
          /* Active viz with crossfade */
          vizList.map((viz, i) => (
            <div
              key={viz.id}
              className="absolute inset-0 p-4 transition-opacity duration-150"
              style={{
                opacity: i === activeIndex ? 1 : 0,
                zIndex: i === activeIndex ? 1 : 0,
                pointerEvents: i === activeIndex ? 'auto' : 'none',
              }}
            >
              <div className="w-full h-full">
                <VizCard
                  viz={viz.data}
                  report={report}
                  onZoneClick={onZoneClick}
                />
              </div>
            </div>
          ))
        )}

        {/* Prev/Next arrows — only show if more than 1 viz */}
        {total > 1 && (
          <>
            <button
              onClick={(e) => { e.stopPropagation(); onNavigate(activeIndex - 1); }}
              disabled={activeIndex === 0}
              className="absolute left-3 top-1/2 -translate-y-1/2 z-10
                w-10 h-10 rounded-full bg-bg-card/70 border border-border
                flex items-center justify-center text-text-primary
                hover:bg-bg-hover hover:border-accent-cyan/30
                disabled:opacity-20 disabled:cursor-default
                transition-all backdrop-blur-sm"
              aria-label="Previous visualization"
            >
              ◀
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onNavigate(activeIndex + 1); }}
              disabled={activeIndex >= total - 1}
              className="absolute right-3 top-1/2 -translate-y-1/2 z-10
                w-10 h-10 rounded-full bg-bg-card/70 border border-border
                flex items-center justify-center text-text-primary
                hover:bg-bg-hover hover:border-accent-cyan/30
                disabled:opacity-20 disabled:cursor-default
                transition-all backdrop-blur-sm"
              aria-label="Next visualization"
            >
              ▶
            </button>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd dashboard && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add dashboard/src/components/gallery/MediaGallery.jsx
git commit -m "feat: add MediaGallery component with prev/next nav and crossfade"
```

---

## Chunk 3: ChatPage Rewrite — Wire Everything Together

### Task 9: Rewrite ChatPage with 3-panel layout

This is the largest task. It rewires the entire page layout.

**Files:**
- Modify: `dashboard/src/pages/ChatPage.jsx`

- [ ] **Step 1: Update imports**

At the top of ChatPage.jsx, update imports:

1. Change React import to: `import { useState, useEffect, useRef, useCallback } from "react";` (add `useCallback`, remove `useMemo` which is no longer needed)
2. Change router import from `import { Link } from "react-router-dom"` to `import { Link, useLocation, useNavigate } from "react-router-dom";` (keep `Link` for Dashboard link which stays in header)
3. Remove `import PromptShowcase from "../components/chat/PromptShowcase";` (now inside ExamplesPanel)
4. Remove `import VizCard from "../components/chat/VizCard";` (now inside MediaGallery)
5. Remove `const PANEL_VIZ_TYPES = ...` constant (line 15)
6. Remove `getChatVizs` function (dead code, lines 83-86)
7. Remove `panelViz` useMemo block (lines 70-80)
8. Add new imports:

```javascript
import ResizeHandle from '../components/layout/ResizeHandle';
import ExamplesPanel from '../components/layout/ExamplesPanel';
import MediaGallery from '../components/gallery/MediaGallery';
```

**Keep unchanged:** `useReport`, `useChat`, `useAuth`, `ChatInput`, `ChatMessage`, `ThinkingIndicator` imports. Also keep: `LS_KEY`, theme state, vizSize state, lastActions effect, orgName state, meta variables.

- [ ] **Step 2: Add new state and viz collection logic**

After the existing `useChat` and `useReport` hooks, add:

```javascript
const navigate = useNavigate();
const location = useLocation();

// Gallery state
const [vizList, setVizList] = useState([]);
const [activeVizIndex, setActiveVizIndex] = useState(0);
const [userBrowsing, setUserBrowsing] = useState(false);

// Panel state
const [chatWidth, setChatWidth] = useState(() =>
  parseInt(localStorage.getItem('retailvision-chat-width')) || 320
);
const [examplesOpen, setExamplesOpen] = useState(() =>
  localStorage.getItem('retailvision-examples-panel') === 'open'  // defaults to collapsed (spec requirement)
);
```

- [ ] **Step 3: Add viz collection effect**

```javascript
// Collect visualizations from messages into gallery
useEffect(() => {
  const collected = [];
  messages.forEach((msg, msgIdx) => {
    if (msg.role !== 'assistant' || !msg.visualizations?.length) return;
    msg.visualizations.forEach((viz, vizIdx) => {
      if (!viz.type) return; // SSE safety: skip partial entries (don't check viz.data — most viz types don't have it)
      const id = `viz-${msg.id}-${viz.type}-${vizIdx}`;
      if (!collected.find(v => v.id === id)) {
        collected.push({
          id,
          type: viz.type,
          data: viz,          // store the FULL viz object — CardComponents expect config={viz} with type, title, highlight_zones, etc. at the top level
          messageIndex: msgIdx,
        });
      }
    });
  });
  setVizList(collected);
  if (!userBrowsing && collected.length > 0) {
    setActiveVizIndex(collected.length - 1);
  }
}, [messages, userBrowsing]);
```

- [ ] **Step 4: Add handler functions**

```javascript
// Gallery navigation
const handleGalleryNavigate = useCallback((index) => {
  setActiveVizIndex(index);
  setUserBrowsing(true);
}, []);

// Reset userBrowsing when user sends a message
const handleSend = useCallback((text) => {
  setUserBrowsing(false);
  sendMessage(text);
}, [sendMessage]);

// Zone click — uses handleSend (not sendMessage) so userBrowsing resets
function handleZoneClick(zoneId) {
  handleSend(`Tell me about zone ${zoneId}`);
}

// VizChip click — focus gallery on that viz
const handleVizFocus = useCallback((vizId) => {
  const idx = vizList.findIndex(v => v.id === vizId);
  if (idx !== -1) {
    setActiveVizIndex(idx);
    setUserBrowsing(true);
  }
}, [vizList]);

// Chat panel resize
const handleResize = useCallback((clientX) => {
  const newWidth = Math.min(Math.max(clientX, 280), window.innerWidth * 0.5);
  setChatWidth(newWidth);
}, []);

const handleResizeEnd = useCallback(() => {
  localStorage.setItem('retailvision-chat-width', String(chatWidth));
}, [chatWidth]);

// Examples panel toggle
const handleToggleExamples = useCallback(() => {
  setExamplesOpen(prev => {
    const next = !prev;
    localStorage.setItem('retailvision-examples-panel', next ? 'open' : 'collapsed');
    return next;
  });
}, []);

// Clear chat — also reset gallery
const handleNewChat = useCallback(() => {
  clearChat();
  setVizList([]);
  setActiveVizIndex(0);
  setUserBrowsing(false);
}, [clearChat]);

// Back navigation
const handleBack = useCallback(() => {
  if (location.key !== 'default') {
    navigate(-1);
  } else {
    navigate('/dashboard');
  }
}, [navigate, location.key]);

// Escape key: collapse examples panel
useEffect(() => {
  const handler = (e) => {
    if (e.key === 'Escape' && examplesOpen) {
      handleToggleExamples();
    }
  };
  document.addEventListener('keydown', handler);
  return () => document.removeEventListener('keydown', handler);
}, [examplesOpen, handleToggleExamples]);
```

- [ ] **Step 5: Replace the JSX layout**

Replace the entire `return (...)` block with the complete new layout below. This is the full JSX — copy it exactly.

**What stays unchanged from current code:** Header structure (logo, metadata, orgName input, Dashboard link, user email, sign out). Theme/vizSize/lastActions effects. OrgName persistence. Auto-scroll effect (but scrolls `chatScrollRef`).

**What's new:** Back button in header, `handleNewChat` on New Chat button, 3-panel body layout, `handleSend` everywhere instead of `sendMessage`, `onVizFocus` on ChatMessage, `onSuggestionSelect={handleSend}` on welcome message.

```jsx
return (
  <div className="flex flex-col h-screen bg-bg-primary">
    {/* ── Header ─────────────────────────────────────────── */}
    <header className="flex items-center gap-3 px-4 py-3 bg-bg-card border-b border-border shrink-0">
      {/* Back button */}
      <button
        onClick={handleBack}
        className="text-text-secondary hover:text-accent-cyan text-xs transition-colors mr-1"
      >
        ← Back
      </button>

      {/* Logo */}
      <img src="/ipsotek-logo.png" alt="Ipsotek" className="h-8 object-contain" />
      <div className="w-px h-5.5 bg-border" />

      {/* Title + meta */}
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-semibold text-text-primary truncate">RetailVision AI</span>
        <span className="text-[10px] text-text-secondary font-mono truncate">
          {videoId} &middot; {sceneType} &middot; {nZones} zones &middot; {durationMin} min
        </span>
      </div>

      <div className="flex-1" />

      {/* Editable org name — same as current (lines 122-145) */}
      <div className="flex items-center gap-1.5 bg-bg-card border border-border rounded-lg px-2.5 py-1.5">
        <input
          type="text"
          value={orgName}
          onChange={(e) => setOrgName(e.target.value)}
          className="bg-transparent text-xs text-text-primary w-32 outline-none placeholder:text-text-secondary"
          placeholder="Organization name"
        />
        <svg className="w-3 h-3 text-text-secondary flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
        </svg>
      </div>

      {/* Dashboard link — kept as Link */}
      <Link to="/dashboard" className="text-xs text-accent-cyan hover:text-accent-cyan/80 transition-colors whitespace-nowrap">
        Dashboard &#8599;
      </Link>

      {/* New Chat — uses handleNewChat to also reset gallery */}
      <button
        onClick={handleNewChat}
        className="text-xs px-3 py-1.5 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-text-secondary transition-colors cursor-pointer"
      >
        New Chat
      </button>

      {/* User email + Sign out — same as current */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] text-text-secondary truncate max-w-[140px]">{session?.user?.email}</span>
        <button onClick={signOut} className="text-[10px] px-2 py-1 rounded-md border border-border text-text-secondary hover:text-accent-red hover:border-accent-red/30 transition-colors cursor-pointer">
          Sign out
        </button>
      </div>
    </header>

    {/* ── Main 3-panel body ──────────────────────────────── */}
    <div className="flex-1 flex min-h-0">
      {/* ── Chat Panel (left) ───────────────────────────── */}
      <div
        className="shrink-0 flex flex-col border-r border-border bg-bg-card"
        style={{ width: chatWidth, minWidth: 280 }}
      >
        {/* Message scroll area */}
        <div ref={chatScrollRef} className="flex-1 overflow-y-auto">
          <div className="py-4">
            {/* Welcome message */}
            <ChatMessage
              message={{
                id: "welcome",
                role: "assistant",
                content: loading
                  ? "Initializing analytics engine..."
                  : `Welcome to **RetailVision AI** — your intelligent agentic analytics platform.\n\nI've completed analysis of camera **${videoId}**, identifying **${nZones} distinct zones** across this environment.\n\nHow can I assist you?`,
                visualizations: [],
              }}
              orgName={orgName}
              report={report}
              onSuggestionSelect={handleSend}
              onZoneClick={handleZoneClick}
              onVizFocus={handleVizFocus}
              isWelcome={!loading}
            />

            {/* Conversation messages */}
            {messages.map((msg, idx) => {
              const retryFn = msg.error
                ? () => {
                    const lastUserMsg = messages.slice(0, idx).reverse().find((m) => m.role === "user");
                    if (lastUserMsg) handleSend(lastUserMsg.content);
                  }
                : undefined;

              return (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  orgName={orgName}
                  report={report}
                  onRetry={retryFn}
                  onZoneClick={handleZoneClick}
                  onVizFocus={handleVizFocus}
                />
              );
            })}

            {/* Thinking indicator */}
            {isLoading && <ThinkingIndicator />}
          </div>
        </div>

        {/* Input bar */}
        <div className="bg-bg-card border-t border-border shrink-0 p-3">
          <ChatInput onSend={handleSend} disabled={isLoading} />
        </div>
      </div>

      {/* ── Resize Handle ───────────────────────────────── */}
      <ResizeHandle onResize={handleResize} onResizeEnd={handleResizeEnd} />

      {/* ── Media Gallery (center, dominant) ─────────────── */}
      <MediaGallery
        vizList={vizList}
        activeIndex={activeVizIndex}
        onNavigate={handleGalleryNavigate}
        report={report}
        onZoneClick={handleZoneClick}
        emptyImageSrc={report?.config?.reference_frame
          ? `/api/reference-frame/${report.config.reference_frame}` : null}
      />

      {/* ── Examples Panel (right, collapsible) ──────────── */}
      <ExamplesPanel
        isOpen={examplesOpen}
        onToggle={handleToggleExamples}
        onSend={handleSend}
      />
    </div>
  </div>
);
```

- [ ] **Step 6: Verify build**

Run: `cd dashboard && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 7: Manual smoke test**

Run: `cd dashboard && npm run dev`

Verify in browser:
1. 3-panel layout renders: chat left, gallery center, examples right
2. Chat messages appear in left panel
3. Gallery shows empty state initially
4. Examples panel toggle works (click tab to expand/collapse)
5. Resize handle between chat and gallery works
6. Back button appears in header

- [ ] **Step 8: Commit**

```bash
git add dashboard/src/pages/ChatPage.jsx
git commit -m "feat: rewrite ChatPage with 3-panel gallery-centric layout

- Chat panel (left, resizable) with VizChip links
- Media gallery (center, dominant) with prev/next navigation
- Examples marquee (right, collapsible toggle)
- Back button using location.key for robust navigation
- Viz collection from messages with SSE safety guards
- Gallery auto-focus with userBrowsing suppression
- Panel widths persisted to localStorage"
```

---

## Chunk 4: Polish, Responsive, and Final Cleanup

### Task 10: Add responsive drawer behavior for narrow viewports

**Files:**
- Modify: `dashboard/src/pages/ChatPage.jsx`
- Modify: `dashboard/src/index.css`

- [ ] **Step 1: Add responsive state and media query**

In ChatPage, add:

```javascript
const [isMobile, setIsMobile] = useState(window.innerWidth < 1024);
const [drawerOpen, setDrawerOpen] = useState(false);

useEffect(() => {
  const mq = window.matchMedia('(max-width: 1023px)');
  const handler = (e) => setIsMobile(e.matches);
  mq.addEventListener('change', handler);
  return () => mq.removeEventListener('change', handler);
}, []);
```

- [ ] **Step 2: Wrap chat panel with responsive conditional**

For the chat panel section in the JSX, conditionally render as either inline or drawer:

```jsx
{isMobile ? (
  <>
    {/* Floating chat toggle button */}
    <button
      onClick={() => setDrawerOpen(true)}
      className="fixed top-16 left-3 z-30 w-10 h-10 rounded-full
        bg-bg-card border border-border flex items-center justify-center
        text-accent-cyan hover:bg-bg-hover transition-colors"
      aria-label="Open chat"
    >
      💬
    </button>
    {/* Drawer backdrop + panel */}
    {drawerOpen && (
      <div className="fixed inset-0 z-40" onClick={() => setDrawerOpen(false)}>
        <div className="absolute inset-0 bg-black/30" />
        <div
          className="absolute left-0 top-0 bottom-0 z-50 w-[320px] max-w-[85vw]
            flex flex-col bg-card border-r border-border shadow-2xl
            animate-[slideIn_200ms_ease-out]"
          onClick={e => e.stopPropagation()}
        >
          {/* Same chat content as desktop */}
        </div>
      </div>
    )}
  </>
) : (
  /* Desktop: inline chat panel + resize handle */
  <>
    <div style={{ width: chatWidth, minWidth: 280 }} className="shrink-0 flex flex-col border-r border-border bg-card">
      {/* ... chat content ... */}
    </div>
    <ResizeHandle onResize={handleResize} onResizeEnd={handleResizeEnd} />
  </>
)}
```

- [ ] **Step 3: Add slideIn keyframe to index.css**

```css
@keyframes slideIn {
  from { transform: translateX(-100%); }
  to { transform: translateX(0); }
}
```

- [ ] **Step 4: Auto-collapse examples on mobile**

In the ExamplesPanel section, pass `isOpen={isMobile ? false : examplesOpen}` and disable the toggle on mobile, or simply hide it:

```jsx
{!isMobile && (
  <ExamplesPanel
    isOpen={examplesOpen}
    onToggle={handleToggleExamples}
    onSend={handleSend}
  />
)}
```

- [ ] **Step 5: Verify build and test at narrow viewport**

Run: `cd dashboard && npm run build && npm run dev`

Test: Resize browser to < 1024px width.
Expected: Chat becomes floating drawer, examples hidden, gallery fills width.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/pages/ChatPage.jsx dashboard/src/index.css
git commit -m "feat: add responsive drawer mode for chat panel on narrow viewports

Below 1024px: chat becomes a floating drawer with backdrop,
examples panel auto-hides, gallery fills viewport width."
```

---

### Task 11: Clean up dead code and unused imports

**Files:**
- Modify: `dashboard/src/pages/ChatPage.jsx`
- Modify: `dashboard/src/components/chat/ChatMessage.jsx`

- [ ] **Step 1: Verify no unused imports or dead code remain**

In ChatPage.jsx, ensure:
- No `PANEL_VIZ_TYPES` constant
- No `getChatVizs` function
- No `panelViz` useMemo
- No `VizCard` import
- No `PromptShowcase` import
- No `filterPanelVizs` prop passed to ChatMessage
- No `vizSize` prop passed to ChatMessage
- `useMemo` removed from React import (replaced by `useCallback`)
- `Link` still imported (used by Dashboard link in header)
- `handleSend` used everywhere instead of direct `sendMessage` calls
- `handleNewChat` used on New Chat button instead of `clearChat`

In ChatMessage.jsx, ensure:
- No `PANEL_VIZ_TYPES` constant
- No `VizCard` import
- No `filterPanelVizs` prop in component signature
- No `vizSize` prop in component signature
- `onVizFocus` prop is used and passed to VizChip onClick
- `onSuggestionSelect` prop is kept (used by SuggestionChips)

In VizCard.jsx, ensure:
- No `SIZE_CLASSES` constant
- No `size` prop
- `viz` prop kept (same shape as before)
- Wrapper div uses `w-full h-full overflow-hidden`

- [ ] **Step 2: Verify full build**

Run: `cd dashboard && npm run build`
Expected: Clean build with no warnings about unused variables

- [ ] **Step 3: Final smoke test**

Run: `cd dashboard && npm run dev`

Full test checklist:
1. Chat panel renders on left, messages display correctly
2. Welcome message shows with suggestion chips — clicking a chip sends a message
3. Sending a message triggers SSE streaming
4. When a viz arrives, it appears in the gallery AND a VizChip appears in chat
5. Gallery shows correct counter (1/1, then 2/2 after second viz, etc.)
6. Single viz: arrows hidden, counter shows "1 / 1"
7. Multiple vizs: Prev/Next arrows visible and functional
8. VizChip in chat — clicking it navigates gallery to that viz
9. Arrow keys navigate gallery when focused (click gallery first)
10. Escape key collapses examples panel when open
11. Resize handle adjusts chat width, width persists on page reload
12. Narrow chat panel (drag to 280px): messages wrap, chips stack
13. Examples panel toggle works, collapsed/expanded state persists on reload
14. Back button navigates to dashboard (or browser back if history exists)
15. New Chat clears messages AND gallery (gallery shows empty state again)
16. Zone map: tooltip positions correctly when zoomed to 2x+
17. Zone map: pan feels proportional at all zoom levels
18. Zone map: clicking a zone sends "Tell me about zone X" message
19. At < 1024px width: chat drawer slides in/out, examples hidden, gallery fills

- [ ] **Step 4: Commit**

```bash
git add dashboard/src/pages/ChatPage.jsx dashboard/src/components/chat/ChatMessage.jsx
git commit -m "chore: clean up dead code from 2-panel layout migration

Remove PANEL_VIZ_TYPES, getChatVizs, panelViz useMemo, unused
VizCard/PromptShowcase imports, and filterPanelVizs prop."
```

---

## Task Dependency Summary

```
Task 1 (constants)
  ↓
Task 2 (zone map fix) — independent of Task 1
Task 3 (VizChip) — depends on Task 1
  ↓
Task 4 (ChatMessage update) — depends on Task 3
Task 5 (VizCard simplify) — independent
Task 6 (ResizeHandle) — independent
Task 7 (ExamplesPanel) — independent
Task 8 (MediaGallery) — depends on Task 5
  ↓
Task 9 (ChatPage rewrite) — depends on Tasks 4, 6, 7, 8
  ↓
Task 10 (responsive) — depends on Task 9
  ↓
Task 11 (cleanup) — depends on Task 10
```

**Parallelizable groups:**
- Group A (can run in parallel): Tasks 2, 5, 6, 7
- Group B (after Task 1): Task 3 → Task 4
- Group C (after A+B): Task 8
- Group D (sequential): Task 9 → Task 10 → Task 11
