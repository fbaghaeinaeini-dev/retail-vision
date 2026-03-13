import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import VizChip from "./VizChip";
import SuggestionChips from "./SuggestionChips";

/**
 * Strip markdown tables from text (lines starting with | or |---).
 * Tables belong in data_table visualizations, not inline text.
 */
function stripMarkdownTables(text) {
  if (!text) return text;
  return text
    .split('\n')
    .filter(line => !/^\s*\|/.test(line))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/** Tailwind-styled markdown components for chat bubbles */
const mdComponents = {
  h1: ({ children }) => (
    <h1 className="text-base font-bold text-text-primary mt-3 mb-1 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-[15px] font-bold text-text-primary mt-2.5 mb-1 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-text-primary mt-2 mb-0.5 first:mt-0">{children}</h3>
  ),
  h4: ({ children }) => (
    <h4 className="text-[13px] font-semibold text-text-secondary mt-1.5 mb-0.5 first:mt-0">{children}</h4>
  ),
  p: ({ children }) => (
    <p className="mb-1.5 last:mb-0">{children}</p>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-text-primary">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-text-secondary">{children}</em>
  ),
  ul: ({ children }) => (
    <ul className="list-disc list-inside mb-1.5 space-y-0.5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="list-decimal list-inside mb-1.5 space-y-0.5">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-sm">{children}</li>
  ),
  code: ({ children, className }) => {
    const isBlock = className?.includes('language-');
    return isBlock ? (
      <pre className="bg-bg-primary rounded-md px-3 py-2 my-1.5 overflow-x-auto text-xs font-mono">
        <code>{children}</code>
      </pre>
    ) : (
      <code className="bg-bg-primary rounded px-1 py-0.5 text-xs font-mono text-accent-cyan">{children}</code>
    );
  },
  hr: () => (
    <hr className="border-border my-2" />
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-accent-cyan/40 pl-3 my-1.5 text-text-secondary italic">
      {children}
    </blockquote>
  ),
};

/**
 * Renders a single chat message (user or assistant).
 *
 * User messages are right-aligned with org-name label and initials avatar.
 * AI messages are left-aligned with Vision AI avatar and may contain
 * embedded visualization cards.
 */

export default function ChatMessage({
  message,
  orgName = "You",
  report,
  onSuggestionSelect,
  onRetry,
  onZoneClick,
  onVizFocus,
  isWelcome = false,
}) {
  const isUser = message.role === "user";

  // Extract initials from orgName
  const initials = orgName
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  // Prepare content — strip tables from AI messages with visualizations
  const content = !isUser && message.visualizations?.length
    ? stripMarkdownTables(message.content)
    : message.content;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`flex gap-3 px-4 py-3 isolate ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* Avatar */}
      {isUser ? (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent-orange flex items-center justify-center">
          <span className="text-[10px] font-bold text-white leading-none">
            {initials}
          </span>
        </div>
      ) : (
        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent-orange/20 border border-accent-orange/30 flex items-center justify-center">
          <span className="text-[6px] font-bold text-accent-orange leading-tight text-center whitespace-pre">
            {"Vision\nAI"}
          </span>
        </div>
      )}

      {/* Message body */}
      <div
        className={`flex flex-col min-w-0 flex-1 ${isUser ? "items-end" : "items-start"}`}
      >
        {/* Label */}
        <span className="text-[10px] text-text-secondary font-medium mb-1 px-1">
          {isUser ? orgName : "Vision AI"}
        </span>

        {/* Content bubble */}
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed break-words overflow-hidden max-w-[85%] ${
            isUser
              ? "bg-bg-hover text-text-primary rounded-tr-sm"
              : message.error
                ? "bg-accent-red/10 text-accent-red border border-accent-red/20 rounded-tl-sm"
                : "bg-bg-card border border-border text-text-primary rounded-tl-sm"
          }`}
        >
          {isUser ? (
            content
          ) : (
            <ReactMarkdown components={mdComponents}>
              {content || ""}
            </ReactMarkdown>
          )}

          {/* Retry button for error messages */}
          {message.error && onRetry && (
            <button
              onClick={onRetry}
              className="mt-2 text-xs text-accent-red hover:text-accent-red/80 underline cursor-pointer"
            >
              Retry
            </button>
          )}
        </div>

        {/* Suggestion chips for welcome message */}
        {isWelcome && !isUser && onSuggestionSelect && (
          <SuggestionChips onSelect={onSuggestionSelect} />
        )}

        {/* Viz chips — clickable links to gallery */}
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
      </div>
    </motion.div>
  );
}
