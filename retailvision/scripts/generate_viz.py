"""Generate tracking + pipeline visualizations from existing DB."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.process_video import _generate_tracking_viz

db_path = "output/real/tracks.db"
video_id = "55748ef61510"
video_path = "E:/Agentic-path/2026-03-05_04-00-00_fixed.mp4"
output_dir = Path("output/real")

print("Generating tracking visualizations...")
_generate_tracking_viz(db_path, video_id, video_path, output_dir, 45000, 25.0)
print("Done!")
