import { useRef, useState, useCallback } from "react";

/**
 * Categorized prompt examples with SVG icon identifiers.
 * Each prompt is clickable to send directly to the chat.
 */
const CATEGORIES = [
  {
    title: "Rankings & Insights",
    icon: "ranking",
    color: "accent-cyan",
    prompts: [
      "Top 3 busiest zones",
      "Which zone has the longest dwell time?",
      "Show bottom 5 by density",
      "Most popular cafes",
      "Top twenty zones by visits",
    ],
  },
  {
    title: "Zone Explorer",
    icon: "zone",
    color: "accent-orange",
    prompts: [
      "Tell me about zone 1",
      "What's happening at Xiaomi?",
      "Compare zone 1 vs zone 2",
      "Show all kiosks",
      "Details on the seating area",
    ],
  },
  {
    title: "Flow & Movement",
    icon: "flow",
    color: "accent-green",
    prompts: [
      "Show customer flow patterns",
      "Flow analysis for zone 3",
      "Top 5 flow transitions",
      "Where do visitors go after the cafe?",
    ],
  },
  {
    title: "Visual Analytics",
    icon: "visual",
    color: "accent-amber",
    prompts: [
      "Show me the busiest zone on the image",
      "Point out the top 3 busiest zones",
      "Highlight where visitors spend the most time",
      "Show me the least crowded areas",
      "Where is the highest foot traffic?",
      "Show heatmap",
      "Play the video footage",
    ],
  },
  {
    title: "Data & Reports",
    icon: "data",
    color: "accent-orange",
    prompts: [
      "List all zones with metrics",
      "Give me an overview",
      "Summary of key statistics",
      "Show all zone types",
    ],
  },
  {
    title: "Controls",
    icon: "settings",
    color: "accent-green",
    prompts: [
      "Switch to light mode",
      "Make graphs larger",
      "Compact view",
      "Dark mode",
    ],
  },
];

/** Inline SVG icons for each category */
const ICONS = {
  ranking: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path d="M10 2a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 2zM10 15a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 15zM10 7a3 3 0 100 6 3 3 0 000-6zM15.657 5.404a.75.75 0 10-1.06-1.06l-1.061 1.06a.75.75 0 001.06 1.06l1.06-1.06zM6.464 14.596a.75.75 0 10-1.06-1.06l-1.06 1.06a.75.75 0 001.06 1.06l1.06-1.06zM18 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 0118 10zM5 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 015 10zM14.596 15.657a.75.75 0 001.06-1.06l-1.06-1.061a.75.75 0 10-1.06 1.06l1.06 1.06zM5.404 6.464a.75.75 0 001.06-1.06l-1.06-1.06a.75.75 0 10-1.06 1.06l1.06 1.06z" />
    </svg>
  ),
  zone: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 00.281-.14c.186-.096.446-.24.757-.433.62-.384 1.445-.966 2.274-1.765C15.302 14.988 17 12.493 17 9A7 7 0 103 9c0 3.492 1.698 5.988 3.355 7.584a13.731 13.731 0 002.274 1.765 11.842 11.842 0 00.976.544l.062.029.018.008.006.003zM10 11.25a2.25 2.25 0 100-4.5 2.25 2.25 0 000 4.5z" clipRule="evenodd" />
    </svg>
  ),
  flow: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path fillRule="evenodd" d="M2.5 4A1.5 1.5 0 001 5.5V6h18v-.5A1.5 1.5 0 0017.5 4h-15zM19 8.5H1v6A1.5 1.5 0 002.5 16h15a1.5 1.5 0 001.5-1.5v-6zM3 13.25a.75.75 0 01.75-.75h1.5a.75.75 0 010 1.5h-1.5a.75.75 0 01-.75-.75zm4.75-.75a.75.75 0 000 1.5h3.5a.75.75 0 000-1.5h-3.5z" clipRule="evenodd" />
    </svg>
  ),
  visual: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path d="M1 4.75C1 3.784 1.784 3 2.75 3h14.5c.966 0 1.75.784 1.75 1.75v10.515a1.75 1.75 0 01-1.75 1.75h-1.5c-.078 0-.155-.005-.23-.015H4.48c-.075.01-.152.015-.23.015h-1.5A1.75 1.75 0 011 15.265V4.75zm3.75 8.744V14.5h10.5v-.756l-2.31-2.31a.75.75 0 00-.97-.07l-3.08 2.054-2.14-1.284a.75.75 0 00-.906.1L4.75 13.494z" />
    </svg>
  ),
  data: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path fillRule="evenodd" d="M.99 5.24A2.25 2.25 0 013.25 3h13.5A2.25 2.25 0 0119 5.25l.01 9.5A2.25 2.25 0 0116.76 17H3.26A2.25 2.25 0 011 14.75l-.01-9.5zm8.26 9.52v-3.5l-2.25.01v3.5l2.25-.01zm1.5 0l2.25.01v-3.5l-2.25-.01v3.5zm-1.5-5v-3.5l-2.25.01v3.5l2.25-.01zm1.5 0l2.25.01v-3.5l-2.25-.01v3.5z" clipRule="evenodd" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path fillRule="evenodd" d="M7.84 1.804A1 1 0 018.82 1h2.36a1 1 0 01.98.804l.331 1.652a6.993 6.993 0 011.929 1.115l1.598-.54a1 1 0 011.186.447l1.18 2.044a1 1 0 01-.205 1.251l-1.267 1.113a7.047 7.047 0 010 2.228l1.267 1.113a1 1 0 01.206 1.25l-1.18 2.045a1 1 0 01-1.187.447l-1.598-.54a6.993 6.993 0 01-1.929 1.115l-.33 1.652a1 1 0 01-.98.804H8.82a1 1 0 01-.98-.804l-.331-1.652a6.993 6.993 0 01-1.929-1.115l-1.598.54a1 1 0 01-1.186-.447l-1.18-2.044a1 1 0 01.205-1.251l1.267-1.114a7.05 7.05 0 010-2.227L1.821 7.773a1 1 0 01-.206-1.25l1.18-2.045a1 1 0 011.187-.447l1.598.54A6.992 6.992 0 017.51 3.456l.33-1.652zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
    </svg>
  ),
};

/** Color map for category accent borders and text */
const COLOR_MAP = {
  "accent-cyan": {
    border: "border-accent-cyan/20",
    bg: "bg-accent-cyan/5",
    text: "text-accent-cyan",
    hoverBg: "hover:bg-accent-cyan/10",
    hoverBorder: "hover:border-accent-cyan/40",
    dot: "bg-accent-cyan/40",
  },
  "accent-orange": {
    border: "border-accent-orange/20",
    bg: "bg-accent-orange/5",
    text: "text-accent-orange",
    hoverBg: "hover:bg-accent-orange/10",
    hoverBorder: "hover:border-accent-orange/40",
    dot: "bg-accent-orange/40",
  },
  "accent-green": {
    border: "border-accent-green/20",
    bg: "bg-accent-green/5",
    text: "text-accent-green",
    hoverBg: "hover:bg-accent-green/10",
    hoverBorder: "hover:border-accent-green/40",
    dot: "bg-accent-green/40",
  },
  "accent-amber": {
    border: "border-accent-amber/20",
    bg: "bg-accent-amber/5",
    text: "text-accent-amber",
    hoverBg: "hover:bg-accent-amber/10",
    hoverBorder: "hover:border-accent-amber/40",
    dot: "bg-accent-amber/40",
  },
};

/**
 * Enterprise prompt showcase with smooth vertical auto-scroll.
 *
 * Displays categorized example prompts in a marquee-style ticker
 * on the left panel. Pauses on hover; clicking sends to chat.
 */
export default function PromptShowcase({ onSelect }) {
  const [isPaused, setIsPaused] = useState(false);
  const scrollRef = useRef(null);

  const handleSelect = useCallback(
    (prompt) => {
      onSelect?.(prompt);
    },
    [onSelect],
  );

  const renderCategory = (cat, keyPrefix = "") => {
    const colors = COLOR_MAP[cat.color] || COLOR_MAP["accent-cyan"];
    return (
      <div key={`${keyPrefix}${cat.title}`} className="mb-4 px-1">
        {/* Category header */}
        <div className="flex items-center gap-2 mb-2 px-1">
          <span className={`${colors.dot} w-1.5 h-1.5 rounded-full shrink-0`} />
          <span className={`${colors.text} opacity-70`}>{ICONS[cat.icon]}</span>
          <span className="text-[10px] font-semibold text-text-secondary uppercase tracking-wider">
            {cat.title}
          </span>
        </div>
        {/* Prompt list */}
        <div className="flex flex-col gap-1.5">
          {cat.prompts.map((prompt) => (
            <button
              key={`${keyPrefix}${prompt}`}
              onClick={() => handleSelect(prompt)}
              className={`group text-left w-full px-3 py-2 rounded-lg border text-xs
                bg-bg-card ${colors.border} text-text-primary/80
                ${colors.hoverBg} ${colors.hoverBorder}
                hover:text-text-primary
                transition-all duration-200 cursor-pointer
                flex items-center gap-2`}
            >
              <svg
                className="w-3 h-3 text-text-secondary/40 group-hover:text-text-secondary/70 shrink-0 transition-colors"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                />
              </svg>
              <span className="leading-snug">{prompt}</span>
              <svg
                className="w-3 h-3 ml-auto text-text-secondary/0 group-hover:text-text-secondary/50 shrink-0 transition-all duration-200 group-hover:translate-x-0.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                />
              </svg>
            </button>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      {/* Fixed header */}
      <div className="px-4 pt-4 pb-3 shrink-0">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-6 h-6 rounded-md bg-accent-orange/15 border border-accent-orange/20 flex items-center justify-center">
            <svg
              className="w-3.5 h-3.5 text-accent-orange"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              strokeWidth={1.8}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"
              />
            </svg>
          </div>
          <div>
            <h3 className="text-xs font-semibold text-text-primary">
              Explore Analytics
            </h3>
            <p className="text-[9px] text-text-secondary">
              Click any prompt to get started
            </p>
          </div>
        </div>
        <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent mt-2" />
      </div>

      {/* Scrolling marquee area */}
      <div
        className="flex-1 overflow-hidden relative"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        {/* Top fade */}
        <div className="absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-bg-primary to-transparent z-10 pointer-events-none" />
        {/* Bottom fade */}
        <div className="absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-bg-primary to-transparent z-10 pointer-events-none" />

        <div
          ref={scrollRef}
          className="prompt-marquee"
          style={{ animationPlayState: isPaused ? "paused" : "running" }}
        >
          {/* First copy */}
          <div className="px-3 py-2">
            {CATEGORIES.map((cat) => renderCategory(cat, "a-"))}
          </div>
          {/* Duplicate for seamless loop */}
          <div className="px-3 py-2" aria-hidden="true">
            {CATEGORIES.map((cat) => renderCategory(cat, "b-"))}
          </div>
        </div>
      </div>

      {/* Pause indicator */}
      <div className="px-3 py-1.5 shrink-0">
        <div className="flex items-center justify-center gap-1.5">
          <span
            className={`w-1.5 h-1.5 rounded-full transition-colors duration-300 ${
              isPaused ? "bg-accent-amber" : "bg-accent-green/60 animate-pulse"
            }`}
          />
          <span className="text-[9px] text-text-secondary">
            {isPaused ? "Paused — hover to browse" : "Auto-scrolling"}
          </span>
        </div>
      </div>
    </div>
  );
}
