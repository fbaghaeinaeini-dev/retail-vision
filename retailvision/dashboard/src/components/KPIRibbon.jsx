import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  Users,
  MapPin,
  Clock,
  Activity,
  TrendingUp,
  Eye,
  Crosshair,
  Layers,
} from "lucide-react";
import { formatDuration, formatNumber } from "../lib/colors";

/**
 * Animated count-up hook. Animates from 0 to targetValue over `duration` ms.
 */
function useCountUp(targetValue, duration = 1200) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef(null);
  const startRef = useRef(null);

  useEffect(() => {
    if (typeof targetValue !== "number" || isNaN(targetValue)) {
      setDisplay(0);
      return;
    }

    startRef.current = performance.now();
    const start = 0;
    const end = targetValue;

    function tick(now) {
      const elapsed = now - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = start + (end - start) * eased;

      setDisplay(current);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [targetValue, duration]);

  return display;
}

function KPICard({
  icon: Icon,
  label,
  value,
  rawValue,
  sub,
  colorClass,
  colorHex,
  delay = 0,
  formatter,
}) {
  const animatedVal = useCountUp(rawValue ?? 0, 1200);

  // Format the animated value
  const displayValue =
    rawValue !== undefined && formatter
      ? formatter(animatedVal)
      : value;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4, ease: "easeOut" }}
      className="bg-bg-card border border-border rounded-xl px-4 py-3 flex items-center gap-3 hover:border-border/80 transition-colors"
    >
      <div
        className="p-2 rounded-lg"
        style={{ backgroundColor: `${colorHex}15` }}
      >
        <Icon className="w-5 h-5" style={{ color: colorHex }} />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] text-text-secondary uppercase tracking-wider font-semibold">
          {label}
        </p>
        <p className="text-xl font-mono font-semibold text-text-primary tabular-nums">
          {displayValue}
        </p>
        {sub && (
          <p className="text-[10px] text-text-secondary truncate">{sub}</p>
        )}
      </div>
    </motion.div>
  );
}

export default function KPIRibbon({ zones, analytics, meta }) {
  const zoneCount = Object.keys(zones).length;

  // Aggregate analytics
  let totalVisits = 0;
  let totalDwell = 0;
  let dwellCount = 0;
  let peakDensity = 0;

  for (const zid of Object.keys(analytics)) {
    const a = analytics[zid];
    totalVisits += a?.total_visits || 0;
    if (a?.avg_dwell_seconds > 0) {
      totalDwell += a.avg_dwell_seconds;
      dwellCount++;
    }
    peakDensity = Math.max(peakDensity, a?.density_people_per_m2_hr || 0);
  }

  const avgDwell = dwellCount > 0 ? totalDwell / dwellCount : 0;
  const qualityScore = meta.validation_metrics?.overall_score || 0;
  const coverage = meta.validation_metrics?.coverage_pct || 0;
  const nTracks = meta.n_tracks || 0;
  const duration = meta.duration_seconds || 0;

  const strategyProfile = meta?.strategy_profile || meta?.llm_chosen_params?.strategy_profile || "general";

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-8 gap-3">
      <KPICard
        icon={MapPin}
        label="Zones"
        value={zoneCount}
        rawValue={zoneCount}
        formatter={(v) => Math.round(v)}
        sub={meta.calibration_method?.replace(/_/g, " ") || ""}
        colorHex="#00d4ff"
        delay={0}
      />
      <KPICard
        icon={Users}
        label="Total Visits"
        value={formatNumber(totalVisits)}
        rawValue={totalVisits}
        formatter={(v) => formatNumber(Math.round(v))}
        sub={`across ${zoneCount} zones`}
        colorHex="#ff9500"
        delay={0.05}
      />
      <KPICard
        icon={Clock}
        label="Avg Dwell"
        value={formatDuration(avgDwell)}
        rawValue={avgDwell}
        formatter={(v) => formatDuration(v)}
        sub="mean across zones"
        colorHex="#00ff88"
        delay={0.1}
      />
      <KPICard
        icon={Activity}
        label="Peak Density"
        value={`${peakDensity.toFixed(1)}`}
        rawValue={peakDensity}
        formatter={(v) => v.toFixed(1)}
        sub="people/m\u00B2/hr"
        colorHex="#ff3366"
        delay={0.15}
      />
      <KPICard
        icon={TrendingUp}
        label="Quality"
        value={`${(qualityScore * 100).toFixed(0)}%`}
        rawValue={qualityScore * 100}
        formatter={(v) => `${Math.round(v)}%`}
        sub={meta.quality_passed ? "QA passed" : "QA failed"}
        colorHex={meta.quality_passed ? "#00ff88" : "#ff3366"}
        delay={0.2}
      />
      <KPICard
        icon={Crosshair}
        label="Coverage"
        value={`${(coverage * 100).toFixed(0)}%`}
        rawValue={coverage * 100}
        formatter={(v) => `${Math.round(v)}%`}
        sub="scene area covered"
        colorHex="#b366ff"
        delay={0.25}
      />
      <KPICard
        icon={Eye}
        label="Duration"
        value={formatDuration(duration)}
        rawValue={duration}
        formatter={(v) => formatDuration(v)}
        sub={nTracks ? `${formatNumber(nTracks)} tracks` : meta.scene_type?.replace(/_/g, " ") || ""}
        colorHex="#ffc233"
        delay={0.3}
      />
      <KPICard
        icon={Layers}
        label="Strategy"
        value={strategyProfile}
        sub="analysis profile"
        colorHex="#b366ff"
        delay={0.35}
      />
    </div>
  );
}
