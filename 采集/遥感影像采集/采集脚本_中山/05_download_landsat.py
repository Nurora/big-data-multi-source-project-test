# -*- coding: utf-8 -*-
"""从 Planetary Computer 下载中山 Landsat C2 L2 影像（跨传感器验证用）
用法: python scripts/05_download_landsat.py <scene_id>
默认下载 2019-12-24 LE07（云量3%）与 2024 年相近日期一景"""
import json
import os
import sys
import time
import threading
import requests
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
RAW = PROJECT / "原始数据" / "Landsat影像"
RAW.mkdir(parents=True, exist_ok=True)

# Landsat L2 SR 关键波段: blue green red nir swir16 swir22 + QA_PIXEL
BANDS = ["blue", "green", "red", "nir08", "swir16", "swir22", "qa_pixel"]
THREADS = 8
CHUNK = 4 * 1024 * 1024


def get_signed_href(collection, href):
    r = requests.get(
        "https://planetarycomputer.microsoft.com/api/sas/v1/token/" + collection,
        params={"href": href}, timeout=90)
    r.raise_for_status()
    return href + "?" + r.json()["token"]


def fetch_item(scene_id):
    url = f"https://planetarycomputer.microsoft.com/api/stac/v1/collections/landsat-c2-l2/items/{scene_id}"
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    return r.json()


def download_part(url, start, end, out, lock, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, headers={"Range": f"bytes={start}-{end}"},
                             timeout=180, stream=True)
            r.raise_for_status()
            with lock:
                with open(out, "r+b") as f:
                    f.seek(start)
                    f.write(r.content)
            return
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def download_file(url, dest):
    tmp = dest.with_suffix(dest.suffix + ".part")
    if dest.exists():
        print(f"  已存在，跳过: {dest.name}")
        return
    r = requests.head(url, timeout=90)
    total = int(r.headers.get("Content-Length", 0))
    if total == 0:
        raise RuntimeError("无法获取文件大小")
    if not tmp.exists():
        with open(tmp, "wb") as f:
            f.truncate(total)
    lock = threading.Lock()
    step = (total + THREADS - 1) // THREADS
    ts = []
    for i in range(THREADS):
        s = i * step
        if s >= total:
            break
        e = min(s + step - 1, total - 1)
        t = threading.Thread(target=download_part, args=(url, s, e, tmp, lock))
        t.start()
        ts.append(t)
    for t in ts:
        t.join()
    os.replace(tmp, dest)
    print(f"  完成 {dest.name}: {total/1e6:.1f} MB")


def main(scene_id):
    print(f"== {scene_id}")
    item = fetch_item(scene_id)
    outdir = RAW / scene_id
    outdir.mkdir(exist_ok=True)
    for b in BANDS:
        href = item["assets"][b]["href"]
        url = get_signed_href("landsat-c2-l2", href)
        download_file(url, outdir / f"{b}.tif")
        time.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("用法: python 05_download_landsat.py <scene_id>")
    main(sys.argv[1])
