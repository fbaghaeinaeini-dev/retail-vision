const SUGGESTIONS = [
  "Show me the zones",
  "Which area is busiest?",
  "Summary of key metrics",
  "Customer flow patterns",
];

/**
 * Clickable suggestion chips shown in the welcome message.
 * Each chip triggers a chat message via onSelect.
 */
export default function SuggestionChips({ onSelect }) {
  return (
    <div className="flex flex-wrap gap-2 mt-3">
      {SUGGESTIONS.map((text) => (
        <button
          key={text}
          onClick={() => onSelect?.(text)}
          className="px-3 py-1.5 text-xs font-medium rounded-full border border-accent-orange/30 bg-accent-orange/10 text-accent-orange hover:bg-accent-orange/20 hover:border-accent-orange/50 transition-colors cursor-pointer"
        >
          {text}
        </button>
      ))}
    </div>
  );
}
