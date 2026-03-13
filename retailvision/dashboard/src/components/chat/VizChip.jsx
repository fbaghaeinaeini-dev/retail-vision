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
