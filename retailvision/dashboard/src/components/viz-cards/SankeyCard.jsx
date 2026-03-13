import { useMemo } from "react";
import { sankey, sankeyLinkHorizontal } from "d3-sankey";
import { getZoneColor } from "../../lib/colors";

export default function SankeyCard({ config, report, onZoneClick }) {
  const filterZone = config?.filter_zone || null;
  const title = config?.title || "Customer Flow";
  const transitions = report?.flow?.transitions || [];

  const sankeyResult = useMemo(() => {
    if (!transitions.length) return null;

    let filtered = transitions.filter(
      (t) => t.from_zone !== t.to_zone && t.count > 0
    );

    if (filterZone) {
      filtered = filtered.filter(
        (t) => t.from_zone === filterZone || t.to_zone === filterZone
      );
    }

    const sorted = [...filtered]
      .sort((a, b) => b.count - a.count)
      .slice(0, 15);

    if (sorted.length < 2) return null;

    const sourceZones = new Set();
    const targetZones = new Set();
    sorted.forEach((t) => {
      sourceZones.add(t.from_zone);
      targetZones.add(t.to_zone);
    });

    const zones = report?.zones || {};
    const srcList = [...sourceZones];
    const tgtList = [...targetZones];
    const nodes = [
      ...srcList.map((id) => ({
        id: id + "_src",
        zoneId: id,
        name: (zones[id]?.business_name || id).slice(0, 10),
        type: zones[id]?.zone_type || "unknown",
        side: "source",
      })),
      ...tgtList.map((id) => ({
        id: id + "_tgt",
        zoneId: id,
        name: (zones[id]?.business_name || id).slice(0, 10),
        type: zones[id]?.zone_type || "unknown",
        side: "target",
      })),
    ];

    const idxMap = {};
    nodes.forEach((n, i) => {
      idxMap[n.id] = i;
    });

    const links = sorted
      .map((t) => ({
        source: idxMap[t.from_zone + "_src"],
        target: idxMap[t.to_zone + "_tgt"],
        value: t.count,
      }))
      .filter(
        (l) =>
          l.source !== undefined &&
          l.target !== undefined &&
          l.source !== l.target
      );

    if (!links.length) return null;

    const W = 400;
    const H = Math.max(160, Math.max(srcList.length, tgtList.length) * 24);

    try {
      const layout = sankey()
        .nodeWidth(10)
        .nodePadding(8)
        .nodeSort(null)
        .extent([
          [1, 5],
          [W - 1, H - 5],
        ]);

      const result = layout({
        nodes: nodes.map((n) => ({ ...n })),
        links: links.map((l) => ({ ...l })),
      });

      return { ...result, width: W, height: H };
    } catch {
      return null;
    }
  }, [transitions, filterZone, report?.zones]);

  if (!sankeyResult) {
    return (
      <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
        <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)]">
          <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
            {title}
          </h4>
        </div>
        <div className="p-3 text-center">
          <p className="text-text-secondary text-xs">Not enough flow data</p>
        </div>
      </div>
    );
  }

  const { nodes, links, width, height } = sankeyResult;

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)] flex items-center justify-between">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          Customer Flow
        </h4>
        <span className="text-[9px] font-mono text-text-secondary">
          {links.length} flows
        </span>
      </div>
      <div className="p-3" style={{ height: 200 }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-full"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* Links */}
          {links.map((link, i) => {
            const srcNode = nodes[link.source.index ?? link.source];
            const color = getZoneColor(srcNode?.type);
            return (
              <path
                key={i}
                d={sankeyLinkHorizontal()(link)}
                fill="none"
                stroke={color}
                strokeOpacity={0.25}
                strokeWidth={Math.max(link.width, 1.5)}
              >
                <title>
                  {srcNode?.name} → {nodes[link.target.index ?? link.target]?.name}: {link.value}
                </title>
              </path>
            );
          })}

          {/* Nodes */}
          {nodes.map((node, i) => {
            const color = getZoneColor(node.type);
            const nh = Math.max((node.y1 || 0) - (node.y0 || 0), 3);
            const isSource = node.side === "source";

            return (
              <g key={i}>
                <rect
                  x={node.x0}
                  y={node.y0}
                  width={(node.x1 || 0) - (node.x0 || 0)}
                  height={nh}
                  fill={color}
                  fillOpacity={0.8}
                  rx={2}
                />
                <text
                  x={isSource ? (node.x1 || 0) + 4 : (node.x0 || 0) - 4}
                  y={((node.y0 || 0) + (node.y1 || 0)) / 2}
                  textAnchor={isSource ? "start" : "end"}
                  dominantBaseline="middle"
                  fill="#a8a8b8"
                  fontSize={8}
                  fontFamily="DM Sans, sans-serif"
                >
                  {node.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
