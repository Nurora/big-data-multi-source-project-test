# -*- coding: utf-8 -*-
"""佛山 Landsat C2 L2 采集脚本（仿照中山 05_download_landsat.py，改为自动检索）
数据源：微软 Planetary Computer STAC API（landsat-c2-l2，USGS 数据）
检索逻辑：按佛山市 bbox，在 2019 与 2024 两个冬季窗口内取云量最低的
          前 N 景下载 7 个波段（跨传感器验证用）。
用法:
  python 05_download_landsat_foshan.py                # 两年、每年前 2 景
  python 05_download_landsat_foshan.py --year 2019
  python 05_download_landsat_foshan.py --limit 1
  python 05_download_landsat_foshan.py --dry-run
"""
import argparse
import json
import sys
import threading
import time
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parent.parent
RAW = PROJECT / "原始数据" / "Landsat影像"
RAW.mkdir(parents=True, exist_ok=True)

STAC_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2"

CITY_BBOX = [112.3925, 22.6422, 113.3934, 23.5734]  # 佛山市
WINDOWS = {
    2019: ("2019-11-20T00:00:00Z", "2019-12-31T23:59:59Z"),
    2024: ("2024-11-20T00:00:00Z", "2024-12-31T23:59:59Z"),
}
BANDS = ["blue", "green", "red", "nir08", "swir16", "swir22", "qa_pixel"]
THREADS = 8
MAX_CLOUD = 20.0


def get_signed_href(href, tries=6):
    for i in range(tries):
        r = requests.get(SAS_TOKEN, params={"href": href}, timeout=90)
        if r.status_code == 200:
            return href + "?" + r.json()["token"]
        if r.status_code == 429 and i < tries - 1:
            wait = 3 * (2 ** i)
            print(f"  限流(429)，{wait}s 后重试...")
            time.sleep(wait)
            continue
        r.raise_for_status()


def search_scenes(year, limit):
    t0, t1 = WINDOWS[year]
    payload = {
        "collections": ["landsat-c2-l2"],
        "bbox": CITY_BBOX,
        "datetime": f"{t0}/{t1}",
        "query": {"eo:cloud_cover": {"lt": MAX_CLOUD}},
        "limit": 50,
    }
    r = requests.post(STAC_SEARCH, json=payload, timeout=120)
    r.raise_for_status()
    feats = r.json()["features"]
    feats.sort(key=lambda f: f["properties"]["eo:cloud_cover"])
    return feats[:limit]


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
    import os
    tmp = dest.with_suffix(dest.suffix + ".part")
    if dest.exists():
        print(f"  已存在，跳过: {dest.name}")
        return True
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
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, choices=[2019, 2024], default=None)
    ap.add_argument("--limit", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    years = [args.year] if args.year else [2019, 2024]

    manifest = []
    for year in years:
        print(f"\n== 检索 {year} 年冬季窗口 ==")
        feats = search_scenes(year, args.limit)
        for f in feats:
            sid = f["id"]
            cc = f["properties"]["eo:cloud_cover"]
            dt = f["properties"]["datetime"][:10]
            print(f"  {sid} 云量 {cc}% 日期 {dt}")
            if args.dry_run:
                continue
            item_url = (f"https://planetarycomputer.microsoft.com/api/stac/v1/"
                        f"collections/landsat-c2-l2/items/{sid}")
            item = requests.get(item_url, timeout=90).json()
            outdir = RAW / sid
            outdir.mkdir(exist_ok=True)
            for b in BANDS:
                try:
                    url = get_signed_href(item["assets"][b]["href"])
                    ok = download_file(url, outdir / (b + ".tif"))
                    if ok:
                        manifest.append({"scene": sid, "band": b,
                                         "bytes": (outdir / (b + ".tif")).stat().st_size,
                                         "url": item["assets"][b]["href"]})
                except Exception as e:
                    print(f"  {b} 下载失败: {e}")
                time.sleep(1)
    if not args.dry_run:
        mf = RAW / "download_manifest_foshan_landsat.json"
        with open(mf, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"\n清单已写入 {mf}，共 {len(manifest)} 个文件")


if __name__ == "__main__":
    main()
