import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";

/**
 * Chat input bar with text field and send button.
 * Submits on Enter (but not Shift+Enter). Disables when `disabled` is true.
 */
export default function ChatInput({ onSend, disabled = false }) {
  const [text, setText] = useState("");
  const inputRef = useRef(null);

  // Auto-focus when not disabled
  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus();
    }
  }, [disabled]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = text.trim().length > 0 && !disabled;

  return (
    <div className="flex items-center gap-2 p-3 border-t border-border bg-bg-card">
      <input
        ref={inputRef}
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={disabled ? "Waiting for response..." : "Ask Vision AI about your analytics..."}
        className="flex-1 bg-bg-primary border border-border rounded-lg px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:border-accent-orange/50 focus:ring-1 focus:ring-accent-orange/20 transition-colors disabled:opacity-50"
      />
      <button
        onClick={handleSubmit}
        disabled={!canSend}
        className={`flex-shrink-0 p-2.5 rounded-lg transition-colors ${
          canSend
            ? "bg-accent-orange text-white hover:bg-accent-orange/80 cursor-pointer"
            : "bg-bg-hover text-text-secondary cursor-not-allowed"
        }`}
      >
        <Send className="w-4 h-4" />
      </button>
    </div>
  );
}
