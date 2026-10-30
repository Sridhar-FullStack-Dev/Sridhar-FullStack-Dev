#!/usr/bin/env python3
"""
Prepare the photo/avatar for clean ASCII conversion:
  1. Remove background (rembg) so the subject is isolated
  2. Bilateral-smooth surface texture while keeping lines sharp
  3. Tone stretch over subject so skin lands near bright and features stay dark
  4. Darken lines / edge ridges
  5. Composite onto white and crop square

Output: source-prepped.png (grayscale), consumed by make_ascii_svg.py.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
INP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "source-photo.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "source-prepped.png")

LINE_WEIGHT = 0.6

if not os.path.exists(INP):
    print(f"Error: {INP} not found. Place a photo at source-photo.png first.", file=sys.stderr)
    sys.exit(1)

def get_cutout(inp_path):
    try:
        from rembg import remove
        return remove(Image.open(inp_path).convert("RGBA"))
    except Exception:
        # Fallback to local onnxruntime using cached bria-rmbg model
        for p in [
            "/Users/sridhar/.cache/uv/archive-v0/zTYG50rUHY6DOwmD",
            os.path.expanduser("~/.cache/uv/archive-v0/zTYG50rUHY6DOwmD"),
        ]:
            if os.path.exists(p) and p not in sys.path:
                sys.path.append(p)
        import onnxruntime as ort

        model_path = os.path.expanduser("~/.rembg/models/bria-rmbg/bria-rmbg.onnx")
        if not os.path.exists(model_path):
            raise RuntimeError(f"Model not found at {model_path}")

        img = Image.open(inp_path).convert("RGB")
        w, h = img.size
        resized = img.resize((1024, 1024), Image.Resampling.LANCZOS)
        ary = np.array(resized).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        norm = (ary - mean) / std
        tensor = np.expand_dims(norm.transpose(2, 0, 1), 0)

        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        sess = ort.InferenceSession(model_path, sess_options=opts)
        outs = sess.run(None, {sess.get_inputs()[0].name: tensor})
        pred = outs[0][:, 0, :, :]
        pred = (pred - pred.min()) / max(1e-6, (pred.max() - pred.min()))
        mask_np = (pred[0] * 255).astype(np.uint8)
        mask = Image.fromarray(mask_np, mode="L").resize((w, h), Image.Resampling.LANCZOS)

        cut = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        cut.paste(img, mask=mask)
        return cut

# 1. cut out subject
cut = get_cutout(INP)
rgb = np.array(cut.convert("RGB"))
alpha = np.array(cut.split()[-1])
gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

# 2. smooth texture, preserve edges
smooth = gray
for _ in range(3):
    smooth = cv2.bilateralFilter(smooth, 9, 40, 9)

# 3. tone stretch
lo, hi = np.percentile(smooth[alpha > 128], [2, 92])
tone = np.clip((smooth.astype(np.float32) - lo) / max(1.0, (hi - lo)), 0, 1)

# 4. darken contours & ridges
fine = cv2.GaussianBlur(smooth, (0, 0), 1.5).astype(np.float32)
coarse = cv2.GaussianBlur(smooth, (0, 0), 6).astype(np.float32)
lines = np.clip((coarse - fine) / 40.0, 0, 1)
out = np.clip(tone - LINE_WEIGHT * lines, 0, 1) * 255

# 5. composite onto pure white and square crop
mask = cv2.GaussianBlur(alpha.astype(np.float32) / 255.0, (0, 0), 1.0)
out = out * mask + 255.0 * (1.0 - mask)

ys, xs = np.where(alpha > 20)
if len(xs) > 0 and len(ys) > 0:
    side = max(xs.max() - xs.min(), ys.max() - ys.min()) + 60
    cx, cy = (xs.min() + xs.max()) // 2, (ys.min() + ys.max()) // 2
    canvas = np.full((side, side), 255, np.uint8)
    x0, y0 = cx - side // 2, cy - side // 2
    sx0, sy0 = max(x0, 0), max(y0, 0)
    sx1, sy1 = min(x0 + side, out.shape[1]), min(y0 + side, out.shape[0])
    canvas[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = out[sy0:sy1, sx0:sx1].astype(np.uint8)
    out = canvas

Image.fromarray(out.astype(np.uint8), mode="L").save(OUT)
print("wrote prepped photo to", OUT)
