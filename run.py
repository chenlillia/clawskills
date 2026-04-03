#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""facenamematchskill runner

Pipeline:
1) fetch pic list from photoplus (signed request)
2) download all images (avif)
3) OCR (easyocr) on bottom area to extract candidate names
4) select representative photo for each name

Note: This does NOT do face recognition. "matching" means the name text appears in the photo.
"""

import argparse
import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List

import requests


def sign_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Reproduce the site's signature logic."""
    t = int(time.time() * 1000)
    d = dict(params)
    d["_t"] = t
    parts = []
    for k in sorted(d.keys()):
        v = d[k]
        if v is None:
            continue
        parts.append(f"{k}={json.dumps(v, ensure_ascii=False)}")
    s = "&".join(parts).replace('"', "")
    d["_s"] = hashlib.md5((s + "laxiaoheiwu").encode("utf-8")).hexdigest()
    return d


def fetch_pics(activity_no: int) -> List[Dict[str, Any]]:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://live.photoplus.cn/live/pc/{activity_no}/",
    }
    params = {
        "activityNo": activity_no,
        "key": "",
        "isNew": None,
        "count": 1000,
        "page": 1,
        "size": 2000,
        "ppSign": "",
        "picUpIndex": "",
    }
    r = requests.get(
        "https://live.photoplus.cn/pic/list",
        params=sign_params(params),
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    obj = r.json()
    if not obj.get("success"):
        raise RuntimeError(obj)
    return obj["result"]["pics_array"]


def download_all(pics: List[Dict[str, Any]], out_dir: Path, workers: int = 16) -> None:
    img_dir = out_dir / "all_images"
    img_dir.mkdir(parents=True, exist_ok=True)

    def dl(i: int, p: Dict[str, Any]) -> None:
        url = p.get("big_img") or p.get("middle_img") or p.get("small_img")
        if not url:
            return
        if url.startswith("//"):
            url = "https:" + url
        fn = img_dir / f"img_{i:04d}.avif"
        if fn.exists() and fn.stat().st_size > 1024:
            return
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        fn.write_bytes(r.content)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(dl, i + 1, p) for i, p in enumerate(pics)]
        for _ in as_completed(futs):
            pass


def ocr_extract_names(out_dir: Path, mode: str) -> Dict[str, Dict[str, Any]]:
    # Lazy imports (OCR deps are heavy)
    import numpy as np
    import pillow_avif  # noqa
    from PIL import Image
    import easyocr

    if mode == "strict":
        conf_th = 0.85
    else:
        conf_th = 0.35  # loose

    name_re = re.compile(r"[\u4e00-\u9fff]{2,4}")
    stop_sub = [
        "组织",
        "研修",
        "领航",
        "签到",
        "致辞",
        "总结",
        "工区",
        "江湾",
        "公司",
        "集团",
        "课程",
        "学员",
        "嘉宾",
        "讲师",
        "主持",
        "字节",
        "跳动",
    ]

    reader = easyocr.Reader(["ch_sim", "en"], gpu=False)
    img_dir = out_dir / "all_images"
    imgs = sorted(img_dir.glob("img_*.avif"))

    best: Dict[str, Dict[str, Any]] = {}
    for p in imgs:
        im = Image.open(p).convert("RGB")
        w, h = im.size
        crop = im.crop((0, int(h * 0.45), w, h))
        crop = crop.resize((800, int(800 * crop.size[1] / crop.size[0])))
        arr = np.array(crop)
        try:
            res = reader.readtext(arr, detail=1)
        except Exception:
            continue
        for bbox, text, conf in res:
            conf = float(conf)
            if conf < conf_th:
                continue
            for m in name_re.findall(text):
                if any(s in m for s in stop_sub):
                    continue
                if m.endswith(("处", "区")):
                    continue
                prev = best.get(m)
                if (prev is None) or conf > prev["conf"]:
                    best[m] = {"conf": conf, "image": p.name, "source_text": text}

    (out_dir / "ocr_name_best.json").write_text(
        json.dumps(best, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return best


def build_selected(out_dir: Path, best: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    # convert representative images to jpg for doc usage
    import pillow_avif  # noqa
    from PIL import Image

    img_dir = out_dir / "all_images"
    sel_dir = out_dir / "selected_jpg"
    sel_dir.mkdir(exist_ok=True)

    selected = []
    for name in sorted(best.keys()):
        v = best[name]
        src = img_dir / v["image"]
        dst = sel_dir / f"{name}.jpg"
        im = Image.open(src).convert("RGB")
        w, h = im.size
        if w > 1600:
            im = im.resize((1600, int(1600 * h / w)))
        im.save(dst, quality=85)
        selected.append(
            {
                "name": name,
                "conf": v["conf"],
                "image_file": dst.name,
                "source_image": v["image"],
                "source_text": v["source_text"],
            }
        )

    (out_dir / "selected_people.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return selected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--activity", required=True, type=int)
    ap.add_argument("--mode", choices=["loose", "strict"], default="loose")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_dir = Path(args.out or f"photoplus_{args.activity}")
    out_dir.mkdir(parents=True, exist_ok=True)

    pics = fetch_pics(args.activity)
    (out_dir / "pics.json").write_text(
        json.dumps(pics, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    download_all(pics, out_dir)
    best = ocr_extract_names(out_dir, args.mode)
    build_selected(out_dir, best)

    print(f"done. names={len(best)} out={out_dir}")


if __name__ == "__main__":
    main()
