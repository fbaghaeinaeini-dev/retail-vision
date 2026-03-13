/**
 * Animated indicator shown while the AI is working.
 *
 * Phases (controlled by parent — hidden during "streaming"):
 * - thinking:  orange dots + "Thinking"  (LLM reasoning / waiting)
 * - preparing: green dots  + "Preparing results..."  (extracting vizzes)
 * - toolStatus present: green dots + "Using tools..."  (tool execution)
 */
export default function ThinkingIndicator({ streamPhase, toolStatus }) {
  const isPreparing = streamPhase === "preparing";
  const isTooling = !!toolStatus;
  const isGreen = isPreparing || isTooling;

  const label = isPreparing
    ? "Preparing results..."
    : isTooling
      ? "Using tools..."
      : "Thinking";

  const dotColor = isGreen ? "bg-emerald-400" : "bg-accent-orange";
  const textColor = isGreen ? "text-emerald-400" : "text-text-secondary";

  return (
    <div className="flex items-start gap-3 px-4 py-3">
      {/* Vision AI Avatar */}
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-accent-orange/20 border border-accent-orange/30 flex items-center justify-center">
        <span className="text-[6px] font-bold text-accent-orange leading-tight text-center whitespace-pre">
          {"Vision\nAI"}
        </span>
      </div>

      {/* Dots + label */}
      <div className="flex items-center gap-1.5 bg-bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3">
        <div
          className={`w-2 h-2 rounded-full ${dotColor}`}
          style={{ animation: "pulse-dot 1.4s ease-in-out infinite", animationDelay: "0s" }}
        />
        <div
          className={`w-2 h-2 rounded-full ${dotColor}`}
          style={{ animation: "pulse-dot 1.4s ease-in-out infinite", animationDelay: "0.2s" }}
        />
        <div
          className={`w-2 h-2 rounded-full ${dotColor}`}
          style={{ animation: "pulse-dot 1.4s ease-in-out infinite", animationDelay: "0.4s" }}
        />
        <span className={`ml-2 text-xs ${textColor}`}>{label}</span>
      </div>
    </div>
  );
}
