import cv2, sys
cap = cv2.VideoCapture(sys.argv[1])
fps = cap.get(cv2.CAP_PROP_FPS)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
dur = total / fps if fps > 0 else 0
print(f"Resolution: {w}x{h}")
print(f"FPS: {fps:.2f}")
print(f"Total frames: {total}")
print(f"Duration: {dur:.0f}s ({dur/60:.1f}min)")
cap.release()
