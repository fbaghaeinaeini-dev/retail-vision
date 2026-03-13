"""Quick debug: test chat endpoint locally."""
import asyncio, json, os, sys
sys.path.insert(0, ".")

from api.chat_server import create_app, _call_vlm_agent
from api.chat_prompt import build_system_prompt, summarize_report

report_path = "dashboard/public/data/report.json"
with open(report_path) as f:
    report = json.load(f)

api_key = os.environ.get("OPENROUTER_API_KEY", "")
model = "qwen/qwen3.5-9b-a3b"

print(f"API key present: {bool(api_key)} (len={len(api_key)})")
print(f"Model: {model}")
print(f"Zones: {len(report.get('zones', {}))}")

summary = summarize_report(report)
prompt = build_system_prompt(summary)
print(f"System prompt: {len(prompt)} chars")
print("---SUMMARY---")
print(summary)
print("---END---")

if not api_key:
    print("ERROR: No OPENROUTER_API_KEY set!")
    sys.exit(1)

print("\nTesting VLM call with 'list all zones'...")
messages = [{"role": "user", "content": "list all zones"}]

result = asyncio.run(_call_vlm_agent(api_key, model, prompt, messages, report))
print(f"\nResult text: {result.get('text', '')[:200]}")
print(f"Visualizations: {len(result.get('visualizations', []))}")
print(f"Actions: {result.get('actions', [])}")
