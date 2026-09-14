#!/usr/bin/env python3
"""Assemble the final report: template + body + inlined screenshots -> out dir + zip.

usage:
  build_report.py --body WORK/report/body.html --images WORK/report/img \
                  --out ~/example-com-usability-report --title "Audit example.com" \
                  --lang it [--findings WORK/findings] [--no-zip]

Produces:
  <out>/report.html          standalone page (doctype, head, CSS, body, images as data URIs)
  <out>/screenshot/*.jpg     the images used, as separate files
  <out>/findings/*.json      copied when --findings is given
  <out>.zip                  the folder zipped, unless --no-zip

Fails loudly (exit 1) if a {{IMG:...}} placeholder has no file, or if the body still
contains a placeholder after inlining.
"""
import argparse
import base64
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "report-template.html")
IMG_RE = re.compile(r"\{\{IMG:([^}]+)\}\}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", required=True)
    ap.add_argument("--images", required=True, help="directory holding the cropped images")
    ap.add_argument("--out", required=True, help="output directory (created); the zip is <out>.zip")
    ap.add_argument("--title", required=True)
    ap.add_argument("--lang", required=True, help="BCP-47 code for <html lang>, e.g. it, fr, en")
    ap.add_argument("--findings", help="directory of findings JSON to copy alongside")
    ap.add_argument("--no-zip", action="store_true")
    a = ap.parse_args()

    out = os.path.abspath(os.path.expanduser(a.out))
    body = open(a.body, encoding="utf-8").read()
    template = open(TEMPLATE, encoding="utf-8").read()

    used = []
    missing = []

    def inline(m: re.Match) -> str:
        name = m.group(1).strip()
        path = os.path.join(a.images, name)
        if not os.path.isfile(path):
            missing.append(name)
            return m.group(0)
        used.append(name)
        ext = name.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
        data = base64.b64encode(open(path, "rb").read()).decode()
        return f"data:{mime};base64,{data}"

    body_inlined = IMG_RE.sub(inline, body)
    if missing:
        sys.exit(f"missing images for placeholders: {', '.join(missing)}")
    if IMG_RE.search(body_inlined):
        sys.exit("placeholders left after inlining")

    page = (template.replace("{{LANG}}", a.lang)
                    .replace("{{TITLE}}", a.title)
                    .replace("{{BODY}}", body_inlined))

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "report.html"), "w", encoding="utf-8") as f:
        f.write(page)

    shot_dir = os.path.join(out, "screenshot")
    os.makedirs(shot_dir, exist_ok=True)
    for name in sorted(set(used)):
        shutil.copy2(os.path.join(a.images, name), os.path.join(shot_dir, name))

    if a.findings and os.path.isdir(a.findings):
        fdir = os.path.join(out, "findings")
        os.makedirs(fdir, exist_ok=True)
        for fn in os.listdir(a.findings):
            if fn.endswith(".json") and not fn.startswith("_"):
                shutil.copy2(os.path.join(a.findings, fn), os.path.join(fdir, fn))

    size_kb = os.path.getsize(os.path.join(out, "report.html")) // 1024
    print(f"report: {out}/report.html ({size_kb} KB, {len(set(used))} images)")

    if not a.no_zip:
        zip_base = out  # shutil adds .zip
        if os.path.exists(zip_base + ".zip"):
            os.remove(zip_base + ".zip")
        root_dir, base_name = os.path.split(out)
        shutil.make_archive(zip_base, "zip", root_dir=root_dir, base_dir=base_name)
        print(f"zip: {zip_base}.zip ({os.path.getsize(zip_base + '.zip') // 1024} KB)")


if __name__ == "__main__":
    main()
