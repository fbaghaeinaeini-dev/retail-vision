"""Quick test: inspect SSA model output format."""
import replicate, os, io, cv2
from PIL import Image

# Set REPLICATE_API_TOKEN in your environment or .env file
# os.environ["REPLICATE_API_TOKEN"] = "your-token-here"
assert os.environ.get("REPLICATE_API_TOKEN"), "Set REPLICATE_API_TOKEN env var"

frame = cv2.imread("output/pipeline_run12/debug/extract_reference_frame__reference_frame.png")
pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
buf = io.BytesIO()
pil.save(buf, format="JPEG", quality=85)
buf.seek(0)

print("Running SSA with output_json=True...")
output = replicate.run(
    "cjwbw/semantic-segment-anything:b2691db53f2d96add0051a4a98e7a3861bd21bf5972031119d344d956d2f8256",
    input={"image": buf, "output_json": True},
)

print(f"Output type: {type(output)}")
print(f"Dict keys: {list(output.keys())}")

# Read JSON output
json_out = output["json_out"]
raw = json_out.read()
print(f"JSON size: {len(raw)} bytes")

import json
data = json.loads(raw)
if isinstance(data, list):
    print(f"JSON is a list of {len(data)} items")
    for item in data[:3]:
        print(f"  keys={list(item.keys()) if isinstance(item, dict) else type(item)}")
        if isinstance(item, dict):
            for k, v in item.items():
                val_str = str(v)[:100] if not isinstance(v, (list, dict)) else f"[{type(v).__name__} len={len(v)}]"
                print(f"    {k}: {val_str}")
elif isinstance(data, dict):
    print(f"JSON is a dict with keys: {list(data.keys())}")
else:
    print(f"JSON is {type(data)}")
