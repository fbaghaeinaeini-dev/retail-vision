// dashboard/src/components/layout/ExamplesPanel.jsx
import PromptShowcase from '../chat/PromptShowcase';

export default function ExamplesPanel({ isOpen, onToggle, onSend }) {
  return (
    <div
      className="shrink-0 border-l border-border bg-bg-card flex flex-col
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
            hover:bg-bg-hover transition-colors"
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
