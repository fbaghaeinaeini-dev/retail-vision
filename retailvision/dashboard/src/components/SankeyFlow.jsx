import { useMemo, useState } from "react";
import { sankey, sankeyLinkHorizontal } from "d3-sankey";
import { getZoneColor, formatZoneTypeLabel } from "../lib/colors";

/**
 * Sankey diagram showing zone-to-zone customer flows.
 *
 * Key fixes:
 * - d3-sankey cannot handle circular links (A->B and B->A).
 *   Solution: merge bidirectional flows into the dominant direction,
 *   and append "_src"/"_dst" suffixes to create a DAG.
 * - Limits to top N transitions to avoid clutter.
 * - Falls back to an arc diagram if Sankey layout fails.
 */
export default function SankeyFlow({ flow, zones }) {
  const transitions = flow?.transitions || [];
  const topPaths = flow?.top_paths || [];
  const [hoveredLink, setHoveredLink] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);

  // Process and build Sankey data
  const sankeyResult = useMemo(() => {
    if (!transitions.length) return null;

    // Take top 20 transitions by count to reduce clutter
    const sorted = [...transitions]
      .filter((t) => t.from_zone !== t.to_zone && t.count > 0)
      .sort((a, b) => b.count - a.count)
      .slice(0, 20);

    if (!sorted.length) return null;

    // To handle circular links, we create a bipartite graph:
    // Each zone appears as both a "source" node (left) and a "target" node (right)
    // This guarantees no cycles.
    const sourceZones = new Set();
    const targetZones = new Set();
    sorted.forEach((t) => {
      sourceZones.add(t.from_zone);
      targetZones.add(t.to_zone);
    });

    // Build node list: sources first, then targets
    const srcList = [...sourceZones];
    const tgtList = [...targetZones];
    const nodes = [
      ...srcList.map((id) => ({
        id: id + "_src",
        zoneId: id,
        name: zones[id]?.business_name || id,
        type: zones[id]?.zone_type || "unknown",
        side: "source",
      })),
      ...tgtList.map((id) => ({
        id: id + "_tgt",
        zoneId: id,
        name: zones[id]?.business_name || id,
        type: zones[id]?.zone_type || "unknown",
        side: "target",
      })),
    ];

    const idxMap = {};
    nodes.forEach((n, i) => {
      idxMap[n.id] = i;
    });

    const links = sorted.map((t) => ({
      source: idxMap[t.from_zone + "_src"],
      target: idxMap[t.to_zone + "_tgt"],
      value: t.count,
      fromZone: t.from_zone,
      toZone: t.to_zone,
    }));

    // Validate all indices exist
    const validLinks = links.filter(
      (l) => l.source !== undefined && l.target !== undefined && l.source !== l.target
    );

    if (!validLinks.length) return null;

    const W = 650;
    const H = Math.max(280, Math.max(srcList.length, tgtList.length) * 30);

    try {
      const layout = sankey()
        .nodeWidth(14)
        .nodePadding(10)
        .nodeSort(null)
        .extent([
          [1, 5],
          [W - 1, H - 5],
        ]);

      const result = layout({
        nodes: nodes.map((n) => ({ ...n })),
        links: validLinks.map((l) => ({ ...l })),
      });

      return { ...result, width: W, height: H };
    } catch (err) {
      console.warn("Sankey layout failed:", err);
      return null;
    }
  }, [transitions, zones]);

  // Fallback: arc diagram data
  const arcData = useMemo(() => {
    if (sankeyResult) return null;
    if (!transitions.length) return null;

    const sorted = [...transitions]
      .filter((t) => t.from_zone !== t.to_zone && t.count > 0)
      .sort((a, b) => b.count - a.count)
      .slice(0, 15);

    if (!sorted.length) return null;

    const zoneIds = new Set();
    sorted.forEach((t) => {
      zoneIds.add(t.from_zone);
      zoneIds.add(t.to_zone);
    });
    const idList = [...zoneIds];
    const posMap = {};
    const nodeW = 600;
    const spacing = nodeW / (idList.length + 1);
    idList.forEach((id, i) => {
      posMap[id] = (i + 1) * spacing;
    });

    let maxCount = 0;
    sorted.forEach((t) => {
      if (t.count > maxCount) maxCount = t.count;
    });

    return {
      nodes: idList.map((id) => ({
        id,
        x: posMap[id],
        name: zones[id]?.business_name || id,
        type: zones[id]?.zone_type || "unknown",
      })),
      links: sorted.map((t) => {
        const x1 = posMap[t.from_zone];
        const x2 = posMap[t.to_zone];
        const mid = (x1 + x2) / 2;
        const radius = Math.abs(x2 - x1) / 2;
        return {
          from: t.from_zone,
          to: t.to_zone,
          count: t.count,
          path: `M ${x1} 200 A ${radius} ${radius} 0 0 ${x1 < x2 ? 1 : 0} ${x2} 200`,
          thickness: 1 + (t.count / maxCount) * 6,
          fromType: zones[t.from_zone]?.zone_type || "unknown",
        };
      }),
      width: nodeW,
      height: 300,
    };
  }, [transitions, zones, sankeyResult]);

  // No data at all
  if (!sankeyResult && !arcData) {
    return (
      <div className="bg-bg-card border border-border rounded-xl p-6 text-center">
        <p className="text-text-secondary text-sm">No flow data available</p>
        <p className="text-text-secondary text-[10px] mt-1 font-mono">
          {transitions.length} transitions found but could not be visualized
        </p>
      </div>
    );
  }

  // Render Sankey
  if (sankeyResult) {
    const { nodes, links, width, height } = sankeyResult;

    return (
      <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Customer Flow
          </h3>
          <span className="text-[10px] font-mono text-text-secondary">
            {transitions.length} transitions &middot; top {Math.min(links.length, 20)}
          </span>
        </div>
        <div className="p-2 overflow-x-auto">
          <svg
            viewBox={`0 0 ${width} ${height}`}
            className="w-full"
            style={{ minHeight: 220 }}
          >
            {/* Column headers */}
            <text
              x={8}
              y={4}
              fill="#6e6e82"
              fontSize={9}
              fontFamily="JetBrains Mono, monospace"
              fontWeight="600"
            >
              FROM
            </text>
            <text
              x={width - 8}
              y={4}
              fill="#6e6e82"
              fontSize={9}
              fontFamily="JetBrains Mono, monospace"
              fontWeight="600"
              textAnchor="end"
            >
              TO
            </text>

            {/* Links */}
            {links.map((link, i) => {
              const srcNode = nodes[link.source.index || link.source];
              const tgtNode = nodes[link.target.index || link.target];
              const color = getZoneColor(srcNode?.type);
              const isHovered = hoveredLink === i;
              const isNodeHovered =
                hoveredNode !== null &&
                (srcNode?.zoneId === hoveredNode || tgtNode?.zoneId === hoveredNode);

              return (
                <path
                  key={i}
                  d={sankeyLinkHorizontal()(link)}
                  fill="none"
                  stroke={color}
                  strokeOpacity={isHovered ? 0.7 : isNodeHovered ? 0.5 : 0.2}
                  strokeWidth={Math.max(link.width, 1.5)}
                  onMouseEnter={() => setHoveredLink(i)}
                  onMouseLeave={() => setHoveredLink(null)}
                  className="cursor-pointer transition-opacity"
                >
                  <title>
                    {srcNode?.name} &rarr; {tgtNode?.name}: {link.value} people
                  </title>
                </path>
              );
            })}

            {/* Nodes */}
            {nodes.map((node, i) => {
              const color = getZoneColor(node.type);
              const nh = Math.max((node.y1 || 0) - (node.y0 || 0), 3);
              const isHovered = hoveredNode === node.zoneId;
              const isSource = node.side === "source";

              // Truncate long names
              const shortName = (node.name || "").length > 16
                ? node.name.slice(0, 14) + ".."
                : node.name;

              return (
                <g
                  key={i}
                  onMouseEnter={() => setHoveredNode(node.zoneId)}
                  onMouseLeave={() => setHoveredNode(null)}
                  className="cursor-pointer"
                >
                  <rect
                    x={node.x0}
                    y={node.y0}
                    width={(node.x1 || 0) - (node.x0 || 0)}
                    height={nh}
                    fill={color}
                    fillOpacity={isHovered ? 1 : 0.8}
                    rx={2}
                  />
                  <text
                    x={isSource ? (node.x1 || 0) + 5 : (node.x0 || 0) - 5}
                    y={((node.y0 || 0) + (node.y1 || 0)) / 2}
                    textAnchor={isSource ? "start" : "end"}
                    dominantBaseline="middle"
                    fill={isHovered ? "#e8e8ec" : "#a8a8b8"}
                    fontSize={10}
                    fontFamily="DM Sans, sans-serif"
                    fontWeight={isHovered ? "600" : "400"}
                  >
                    {shortName}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Top paths */}
        {topPaths.length > 0 && (
          <div className="px-4 py-2.5 border-t border-border">
            <p className="text-[10px] text-text-secondary uppercase tracking-wider mb-1.5 font-semibold">
              Top Paths
            </p>
            <div className="flex flex-wrap gap-2">
              {topPaths.slice(0, 6).map((p, i) => {
                const fromColor = getZoneColor(zones[p.from_zone]?.zone_type);
                return (
                  <span
                    key={i}
                    className="text-[11px] font-mono bg-bg-hover px-2 py-0.5 rounded border border-border inline-flex items-center gap-1"
                  >
                    <span
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ backgroundColor: fromColor }}
                    />
                    {zones[p.from_zone]?.business_name || p.from_zone}
                    <span className="text-text-secondary">&rarr;</span>
                    {zones[p.to_zone]?.business_name || p.to_zone}
                    <span className="text-accent-cyan ml-1">
                      {p.count}
                    </span>
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>
    );
  }

  // Render Arc diagram fallback
  if (arcData) {
    return (
      <div className="bg-bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
            Customer Flow
          </h3>
          <span className="text-[10px] font-mono text-text-secondary">
            Arc diagram &middot; {arcData.links.length} flows
          </span>
        </div>
        <div className="p-2 overflow-x-auto">
          <svg
            viewBox={`0 0 ${arcData.width} ${arcData.height}`}
            className="w-full"
            style={{ minHeight: 200 }}
          >
            {/* Arcs */}
            {arcData.links.map((l, i) => (
              <path
                key={i}
                d={l.path}
                fill="none"
                stroke={getZoneColor(l.fromType)}
                strokeOpacity={0.3}
                strokeWidth={l.thickness}
              >
                <title>
                  {zones[l.from]?.business_name || l.from} &rarr;{" "}
                  {zones[l.to]?.business_name || l.to}: {l.count}
                </title>
              </path>
            ))}

            {/* Nodes */}
            {arcData.nodes.map((n) => {
              const color = getZoneColor(n.type);
              return (
                <g key={n.id}>
                  <circle cx={n.x} cy={200} r={6} fill={color} />
                  <text
                    x={n.x}
                    y={220}
                    fill="#e8e8ec"
                    fontSize={9}
                    fontFamily="DM Sans, sans-serif"
                    textAnchor="middle"
                    transform={`rotate(45, ${n.x}, 220)`}
                  >
                    {(n.name || "").slice(0, 12)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>
    );
  }

  return null;
}
