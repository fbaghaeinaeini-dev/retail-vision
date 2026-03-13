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
