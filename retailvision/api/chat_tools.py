"""Agentic tool definitions and executor for RetailVision chat.

Defines the tools that the VLM agent can call during a multi-turn
conversation to query zone data, flow transitions, and summary stats.
"""

from __future__ import annotations

import json
from typing import Any

from api import data_tools


# ── Tool specifications (JSON Schema format) ─────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "query_zones",
        "description": (
            "Query, sort, filter, and limit zones. Returns zone data sorted "
            "by the chosen metric. Use for ranking questions ('top 3 busiest'), "
            "filtered queries ('all cafes'), or sorted listings."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "description": (
                        "Metric to sort by. Options: total_visits, "
                        "unique_visitors, avg_dwell_seconds, "
                        "median_dwell_seconds, p95_dwell_seconds, "
                        "avg_occupancy, max_occupancy, return_rate, "
                        "density_people_per_m2_hr, area_m2."
                    ),
                    "default": "total_visits",
                },
                "order": {
                    "type": "string",
                    "enum": ["desc", "asc"],
                    "default": "desc",
                },
                "limit": {
                    "type": "integer",
                    "description": (
                        "Max zones to return. Match the user's request "
                        "exactly: 'top 3' → 3, 'top 1' → 1, 'only 2' → 2."
                    ),
                },
                "zone_type": {
                    "type": "string",
                    "description": (
                        "Filter by zone type: cafe, kiosk, restaurant, "
                        "seating_area, shop, corridor, fast_food"
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_zone_detail",
        "description": (
            "Get full details for a specific zone: all metrics, VLM "
            "description, polygon coordinates, objects, signage, and "
            "spatial data. Use when user asks about a specific zone."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "zone_id": {
                    "type": "string",
                    "description": "Zone ID, e.g. 'zone_001'",
                },
            },
            "required": ["zone_id"],
        },
    },
    {
        "name": "search_zones",
        "description": (
            "Search zones by name (case-insensitive substring match). "
            "Use when user mentions a zone by name and you need its ID."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search string to match against names",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_flow_data",
        "description": (
            "Get customer flow/transition data between zones. Returns "
            "transition counts and probabilities. Optionally filter to "
            "transitions involving a specific zone."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "zone_id": {
                    "type": "string",
                    "description": "Optional: filter to transitions involving this zone",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_summary_stats",
        "description": (
            "Get aggregate statistics: total zones, total visits, "
            "average dwell time, busiest zone, and zone type breakdown."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


def execute_tool(name: str, params: dict, report: dict) -> Any:
    """Execute a named tool and return JSON-serializable results."""

    if name == "query_zones":
        return data_tools.query_zones(
            report,
            sort_by=params.get("sort_by", "total_visits"),
            order=params.get("order", "desc"),
            limit=params.get("limit"),
            zone_type=params.get("zone_type"),
        )

    if name == "get_zone_detail":
        result = data_tools.get_zone_detail(report, params.get("zone_id", ""))
        if result is None:
            return {"error": f"Zone '{params.get('zone_id')}' not found"}
        return result

    if name == "search_zones":
        return data_tools.search_zones_by_name(report, params.get("query", ""))

    if name == "get_flow_data":
        return data_tools.get_flow_data(report, params.get("zone_id"))

    if name == "get_summary_stats":
        return data_tools.get_summary_stats(report)

    return {"error": f"Unknown tool: {name}"}


def get_tool_names() -> list[str]:
    """Return list of available tool names."""
    return [t["name"] for t in TOOLS]
