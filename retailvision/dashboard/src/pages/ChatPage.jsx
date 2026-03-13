import { useState, useEffect, useRef, useCallback } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useReport } from "../hooks/useReport";
import { useChat } from "../hooks/useChat";
import { useAuth } from "../contexts/AuthContext";
import ChatInput from "../components/chat/ChatInput";
import ChatMessage from "../components/chat/ChatMessage";
import ThinkingIndicator from "../components/chat/ThinkingIndicator";
import ResizeHandle from "../components/layout/ResizeHandle";
import ExamplesPanel from "../components/layout/ExamplesPanel";
import MediaGallery from "../components/gallery/MediaGallery";

const LS_KEY = "retailvision_org_name";

export default function ChatPage() {
  const { report, loading } = useReport();
  const { messages, isLoading, sendMessage, clearChat, lastActions, toolStatus, streamPhase } = useChat();
  const { session, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [orgName, setOrgName] = useState(
    () => localStorage.getItem(LS_KEY) || "Your Organization",
  );
  const chatScrollRef = useRef(null);

  // Theme state
  const [theme, setTheme] = useState(() => localStorage.getItem("retailvision_theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("retailvision_theme", theme);
  }, [theme]);

  // Process actions from useChat
  useEffect(() => {
    for (const action of lastActions) {
      if (action.type === "set_theme") setTheme(action.value);
    }
  }, [lastActions]);

  // Persist org name to localStorage
  useEffect(() => {
    localStorage.setItem(LS_KEY, orgName);
  }, [orgName]);

  // Auto-scroll to bottom when messages change, loading state changes,
  // or stream phase changes (e.g. "preparing results" indicator appears)
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTo({
        top: chatScrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages, isLoading, streamPhase]);

  // ── Gallery state ──────────────────────────────────────
  const [vizList, setVizList] = useState([]);
  const [activeVizIndex, setActiveVizIndex] = useState(0);
  const userBrowsingRef = useRef(false);

  // ── Panel state ────────────────────────────────────────
  const [chatWidth, setChatWidth] = useState(() =>
    parseInt(localStorage.getItem('retailvision-chat-width')) || 380
  );
  const [examplesOpen, setExamplesOpen] = useState(() =>
    localStorage.getItem('retailvision-examples-panel') === 'open'
  );

  // ── Responsive state ──────────────────────────────────
  const [isMobile, setIsMobile] = useState(window.innerWidth < 1024);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1023px)');
    const handler = (e) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // ── Collect visualizations from the LATEST assistant response only ──
  useEffect(() => {
    // Find the last assistant message that has visualizations
    let lastAssistant = null;
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === 'assistant' && msg.visualizations?.length) {
        lastAssistant = { msg, msgIdx: i };
        break;
      }
    }
    if (!lastAssistant) {
      setVizList([]);
      return;
    }
    const collected = [];
    lastAssistant.msg.visualizations.forEach((viz, vizIdx) => {
      if (!viz.type) return; // SSE safety: skip partial entries
      const id = `viz-${lastAssistant.msg.id}-${viz.type}-${vizIdx}`;
      if (!collected.find(v => v.id === id)) {
        collected.push({
          id,
          type: viz.type,
          data: viz,
          messageIndex: lastAssistant.msgIdx,
        });
      }
    });
    setVizList(collected);
    if (!userBrowsingRef.current && collected.length > 0) {
      // Auto-select the LLM-recommended primary visualization
      const primary = lastAssistant.msg.primaryViz;
      const primaryIdx = primary
        ? collected.findIndex(v => v.type === primary)
        : -1;
      setActiveVizIndex(primaryIdx >= 0 ? primaryIdx : 0);
    }
  }, [messages]);

  // ── Gallery navigation ─────────────────────────────────
  const handleGalleryNavigate = useCallback((index) => {
    setActiveVizIndex(index);
    userBrowsingRef.current = true;
  }, []);

  // Reset userBrowsing when user sends a message
  const handleSend = useCallback((text) => {
    userBrowsingRef.current = false;
    sendMessage(text);
  }, [sendMessage]);

  // Zone click — uses handleSend so userBrowsing resets
  function handleZoneClick(zoneId) {
    handleSend(`Tell me about zone ${zoneId}`);
  }

  // VizChip click — focus gallery on that viz
  const handleVizFocus = useCallback((vizId) => {
    const idx = vizList.findIndex(v => v.id === vizId);
    if (idx !== -1) {
      setActiveVizIndex(idx);
      userBrowsingRef.current = true;
    }
  }, [vizList]);

  // Chat panel resize
  const handleResize = useCallback((clientX) => {
    const newWidth = Math.min(Math.max(clientX, 280), window.innerWidth * 0.5);
    setChatWidth(newWidth);
  }, []);

  const handleResizeEnd = useCallback(() => {
    setChatWidth(current => {
      localStorage.setItem('retailvision-chat-width', String(current));
      return current;
    });
  }, []);

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
    userBrowsingRef.current = false;
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

  // Report metadata
  const meta = report?.meta || {};
  const nZones = report ? Object.keys(report.zones || {}).length : 0;
  const videoId = meta.video_id || "loading";
  const sceneType = meta.scene_type || "retail";
  const durationMin = meta.duration_min || meta.duration_minutes || 30;

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

        {/* Editable org name */}
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

        {/* Dashboard link */}
        <Link to="/dashboard" className="text-xs text-accent-cyan hover:text-accent-cyan/80 transition-colors whitespace-nowrap">
          Dashboard &#8599;
        </Link>

        {/* New Chat */}
        <button
          onClick={handleNewChat}
          className="text-xs px-3 py-1.5 rounded-lg border border-border text-text-secondary hover:text-text-primary hover:border-text-secondary transition-colors cursor-pointer"
        >
          New Chat
        </button>

        {/* User email + Sign out */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-text-secondary truncate max-w-[140px]">{session?.user?.email}</span>
          <button onClick={signOut} className="text-[10px] px-2 py-1 rounded-md border border-border text-text-secondary hover:text-accent-red hover:border-accent-red/30 transition-colors cursor-pointer">
            Sign out
          </button>
        </div>
      </header>

      {/* ── Main 3-panel body ──────────────────────────────── */}
      <div className="flex-1 flex min-h-0">
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
                    flex flex-col bg-bg-card border-r border-border shadow-2xl
                    animate-[slideIn_200ms_ease-out]"
                  onClick={e => e.stopPropagation()}
                >
                  {/* Message scroll area */}
                  <div ref={chatScrollRef} className="flex-1 overflow-y-auto">
                    <div className="py-4">
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
                      {isLoading && streamPhase !== "streaming" && streamPhase !== "idle" && (
                      <ThinkingIndicator streamPhase={streamPhase} toolStatus={toolStatus} />
                    )}
                    </div>
                  </div>
                  {/* Input bar inside drawer */}
                  <div className="bg-bg-card border-t border-border shrink-0 p-3">
                    <ChatInput onSend={handleSend} disabled={isLoading} />
                  </div>
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            {/* ── Chat Panel (left, desktop) ────────────────── */}
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
                  {isLoading && streamPhase !== "streaming" && streamPhase !== "idle" && (
                      <ThinkingIndicator streamPhase={streamPhase} toolStatus={toolStatus} />
                    )}
                </div>
              </div>

              {/* Input bar */}
              <div className="bg-bg-card border-t border-border shrink-0 p-3">
                <ChatInput onSend={handleSend} disabled={isLoading} />
              </div>
            </div>

            {/* ── Resize Handle ───────────────────────────────── */}
            <ResizeHandle onResize={handleResize} onResizeEnd={handleResizeEnd} />
          </>
        )}

        {/* ── Media Gallery (center, dominant) ─────────────── */}
        <MediaGallery
          vizList={vizList}
          activeIndex={activeVizIndex}
          onNavigate={handleGalleryNavigate}
          report={report}
          onZoneClick={handleZoneClick}
          emptyImageSrc={report?.config?.reference_frame
            ? `/data/${report.config.reference_frame}` : "/data/reference_frame.png"}
        />

        {/* ── Examples Panel (right, hidden on mobile) ──────── */}
        {!isMobile && (
          <ExamplesPanel
            isOpen={examplesOpen}
            onToggle={handleToggleExamples}
            onSend={handleSend}
          />
        )}
      </div>
    </div>
  );
}
