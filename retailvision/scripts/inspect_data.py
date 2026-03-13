"""Inspect report.json data structure."""
import json

r = json.load(open("dashboard/public/data/report.json"))

z = list(r["zones"].values())[0]
print("=== ZONE KEYS ===")
print(list(z.keys()))
print()
print("=== SAMPLE ZONE ===")
print(json.dumps(z, indent=2, default=str)[:2000])
print()

a = list(r["analytics"].values())[0]
print("=== ANALYTICS KEYS ===")
print(list(a.keys()))
print()
print("=== SAMPLE ANALYTICS ===")
print(json.dumps(a, indent=2, default=str)[:1000])
print()

print("=== FLOW KEYS ===")
print(list(r.get("flow", {}).keys()))
print()

print("=== TEMPORAL KEYS ===")
print(list(r.get("temporal", {}).keys()))
print()

print("=== SPATIAL KEYS ===")
print(list(r.get("spatial", {}).keys()))
print()

print("=== ALL ZONE IDS + NAMES ===")
for zid, zdata in r["zones"].items():
    name = zdata.get("business_name", "?")
    ztype = zdata.get("zone_type", "?")
    a = r.get("analytics", {}).get(zid, {})
    visits = a.get("total_visits", 0)
    dwell = a.get("avg_dwell_seconds", 0)
    print(f"  {zid}: {name} ({ztype}) visits={visits} dwell={dwell:.1f}s")

print()
print("=== POLYGON DATA? ===")
z0 = list(r["zones"].values())[0]
if "polygon" in z0:
    print(f"polygon keys: {list(z0['polygon'].keys()) if isinstance(z0['polygon'], dict) else 'array'}")
    print(f"polygon sample: {str(z0['polygon'])[:300]}")
elif "polygon_px" in z0:
    print(f"polygon_px sample: {str(z0['polygon_px'])[:300]}")
else:
    poly_keys = [k for k in z0.keys() if "poly" in k.lower() or "coord" in k.lower() or "bbox" in k.lower()]
    print(f"Polygon-like keys: {poly_keys}")
    for pk in poly_keys:
        print(f"  {pk}: {str(z0[pk])[:200]}")
