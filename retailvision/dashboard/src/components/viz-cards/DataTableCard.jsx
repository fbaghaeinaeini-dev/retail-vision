import { useMemo, useState } from "react";
import { formatDuration } from "../../lib/colors";

const DEFAULT_COLUMNS = [
  { key: "business_name", label: "Zone" },
  { key: "zone_type", label: "Type" },
  { key: "total_visits", label: "Visits" },
  { key: "avg_dwell_seconds", label: "Avg Dwell" },
];

const COLUMN_DEFS = {
  business_name: { label: "Zone", format: (v) => v || "—" },
  zone_type: { label: "Type", format: (v) => (v || "unknown").replace(/_/g, " ") },
  total_visits: { label: "Visits", format: (v) => v ?? 0, numeric: true },
  avg_dwell_seconds: { label: "Avg Dwell", format: (v) => formatDuration(v || 0), numeric: true },
  density_people_per_m2_hr: { label: "Density", format: (v) => (v || 0).toFixed(1), numeric: true },
  area_m2: { label: "Area (m²)", format: (v) => (v || 0).toFixed(1), numeric: true },
};

export default function DataTableCard({ config, report, onZoneClick }) {
  const vlmData = config?.data || null;
  const vlmColumns = config?.columns || null;
  const title = config?.title || "Zone Data";
  const limit = config?.limit || null;

  // Determine columns
  const columns = useMemo(() => {
    if (vlmData && vlmColumns) {
      // VLM-provided columns: array of {key, label} objects
      return vlmColumns.map((col) => {
        if (typeof col === "string") {
          return { key: col, label: COLUMN_DEFS[col]?.label || col };
        }
        return { key: col.key, label: col.label || COLUMN_DEFS[col.key]?.label || col.key };
      });
    }
    if (config?.columns && !vlmData) {
      // Old format: columns as array of strings
      return config.columns.map((key) => ({
        key,
        label: COLUMN_DEFS[key]?.label || key,
      }));
    }
    return DEFAULT_COLUMNS;
  }, [vlmData, vlmColumns, config?.columns]);

  const defaultSortBy = config?.sort_by || (vlmData ? null : "total_visits");
  const [sortKey, setSortKey] = useState(defaultSortBy);
  const [sortAsc, setSortAsc] = useState(false);

  // Determine rows
  const rows = useMemo(() => {
    // VLM-provided data
    if (vlmData && Array.isArray(vlmData)) {
      const items = vlmData.map((row, i) => ({
        ...row,
        zone_id: row.zone_id || null,
        _idx: i,
      }));
      return limit ? items.slice(0, limit) : items;
    }

    // Compute from report (existing behavior)
    const zones = report?.zones || {};
    const analytics = report?.analytics || {};

    const computed = Object.entries(zones).map(([zid, z]) => {
      const a = analytics[zid] || {};
      return {
        zone_id: zid,
        business_name: z.business_name || zid,
        zone_type: z.zone_type || "unknown",
        area_m2: z.area_m2 || 0,
        total_visits: a.total_visits || 0,
        avg_dwell_seconds: a.avg_dwell_seconds || 0,
        density_people_per_m2_hr: a.density_people_per_m2_hr || 0,
      };
    });
    return limit ? computed.slice(0, limit) : computed;
  }, [report, vlmData, limit]);

  const sortedRows = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => {
      const va = a[sortKey] ?? "";
      const vb = b[sortKey] ?? "";
      if (typeof va === "number" && typeof vb === "number") {
        return sortAsc ? va - vb : vb - va;
      }
      const cmp = String(va).localeCompare(String(vb));
      return sortAsc ? cmp : -cmp;
    });
  }, [rows, sortKey, sortAsc]);

  function handleSort(key) {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  }

  function formatCell(key, value) {
    const def = COLUMN_DEFS[key];
    return def?.format ? def.format(value) : String(value ?? "");
  }

  // Determine which column key represents the zone name (for clickable cells)
  const zoneNameKeys = new Set(["business_name", "name", "zone_name", "label"]);
  const firstCol = columns.length > 0 ? columns[0].key : null;

  function isZoneNameCell(colKey) {
    return zoneNameKeys.has(colKey) || colKey === firstCol;
  }

  return (
    <div className="bg-bg-primary border border-border rounded-lg overflow-hidden">
      <div className="px-3 py-1.5 border-b border-border bg-[var(--color-viz-header)] flex items-center justify-between">
        <h4 className="text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
          {title}
        </h4>
        <span className="text-[9px] font-mono text-text-secondary">
          {rows.length} rows
        </span>
      </div>
      <div className="overflow-auto" style={{ maxHeight: 250 }}>
        <table className="w-full text-[10px]">
          <thead>
            <tr className="border-b border-border">
              {columns.map((col) => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  className="px-2 py-1.5 text-left text-text-secondary font-semibold uppercase tracking-wider cursor-pointer hover:text-text-primary select-none whitespace-nowrap"
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="ml-0.5 text-accent-cyan">
                      {sortAsc ? "\u25B2" : "\u25BC"}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, i) => (
              <tr
                key={row.zone_id || row._idx || i}
                className={`border-b border-border/30 ${
                  i % 2 === 0 ? "bg-transparent" : "bg-[#0a0a12]/50"
                }`}
              >
                {columns.map((col) => {
                  const clickable = isZoneNameCell(col.key) && onZoneClick && row.zone_id;
                  return (
                    <td
                      key={col.key}
                      className={`px-2 py-1 font-mono text-text-primary whitespace-nowrap ${
                        COLUMN_DEFS[col.key]?.numeric ? "text-right tabular-nums" : ""
                      } ${clickable ? "cursor-pointer hover:text-accent-orange transition-colors" : ""}`}
                      onClick={clickable ? () => onZoneClick(row.zone_id) : undefined}
                    >
                      {formatCell(col.key, row[col.key])}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
