#!/usr/bin/env python3
"""Crop, scale and compress a screenshot for the report.

usage:
  crop.py SRC OUT_DIR NAME [--box L,T,R,B] [--maxw PX] [--quality Q] [--top PX]

  --box     crop box in source pixels (left,top,right,bottom)
  --top     shortcut: keep only the first PX rows (mobile "first screens")
  --maxw    scale down so the width is at most PX (never scales up)
  --quality JPEG quality, default 78

Prints: NAME WxH BYTES
"""
import argparse
import os
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: pip install pillow")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out_dir")
    ap.add_argument("name", help="output file name, .jpg is appended if missing")
    ap.add_argument("--box", help="left,top,right,bottom in source pixels")
    ap.add_argument("--top", type=int, help="keep only the first N pixel rows")
    ap.add_argument("--maxw", type=int, help="max output width in pixels")
    ap.add_argument("--quality", type=int, default=78)
    a = ap.parse_args()

    im = Image.open(a.src)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    if a.box:
        l, t, r, b = (int(v) for v in a.box.split(","))
        im = im.crop((max(0, l), max(0, t), min(im.width, r), min(im.height, b)))
    elif a.top:
        im = im.crop((0, 0, im.width, min(im.height, a.top)))
    if a.maxw and im.width > a.maxw:
        im = im.resize((a.maxw, round(im.height * a.maxw / im.width)), Image.LANCZOS)

    os.makedirs(a.out_dir, exist_ok=True)
    name = a.name if a.name.lower().endswith((".jpg", ".jpeg")) else a.name + ".jpg"
    path = os.path.join(a.out_dir, name)
    im.save(path, "JPEG", quality=a.quality, optimize=True)
    print(name, f"{im.width}x{im.height}", os.path.getsize(path))


if __name__ == "__main__":
    main()
