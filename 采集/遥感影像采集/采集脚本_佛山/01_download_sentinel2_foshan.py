# -*- coding: utf-8 -*-
"""佛山哨兵二号 L2A 采集脚本（仿照中山 01_download_sentinel2.py，改为自动检索）
数据源：微软 Planetary Computer STAC API（sentinel-2-l2a，CC BY 4.0）
检索逻辑：按佛山市行政区划 bbox，在 2019 与 2024 两个冬季窗口内，
          对每颗覆盖瓦片自动选取云量最低的一景；多线程分块下载、断点续传。
用法:
  python 01_download_sentinel2_foshan.py                 # 两年、两颗核心瓦片（QFF+QGF）
  python 01_download_sentinel2_foshan.py --year 2019     # 只下 2019 年
  python 01_download_sentinel2_foshan.py --tiles T49QFF  # 只下指定瓦片
  python 01_download_sentinel2_foshan.py --dry-run       # 只检索打印，不下载
"""
import argparse
import json
import re
import sys
import threading
import time
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parent.parent
RAW = PROJECT / "原始数据" / "哨兵2号影像"
RAW.mkdir(parents=True, exist_ok=True)

STAC_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a"

# 佛山市范围（行政区划 guangdong_440000_full.json，adcode=440600）
CITY_BBOX = [112.3925, 22.6422, 113.3934, 23.5734]

# 两个冬季对比窗口（与中山试跑口径一致：2019 冬 vs 2024 冬）
WINDOWS = {
    2019: ("2019-11-20T00:00:00Z", "2019-12-31T23:59:59Z"),
    2024: ("2024-11-20T00:00:00Z", "2024-12-31T23:59:59Z"),
}
# 覆盖佛山的核心瓦片（实测重叠：QFF≈2861 km²、QGF≈2311 km²；QFG/QGG 为边角可加）
DEFAULT_TILES = ["T49QFF", "T49QGF"]
BANDS = ["SCL", "B02", "B03", "B04", "B08", "B11", "B12"]
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


def search_scenes(year):
    t0, t1 = WINDOWS[year]
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": CITY_BBOX,
        "datetime": f"{t0}/{t1}",
        "query": {"eo:cloud_cover": {"lt": MAX_CLOUD}},
        "limit": 100,
    }
    r = requests.post(STAC_SEARCH, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["features"]


def pick_best_per_tile(features, tiles):
    best = {}
    for f in features:
        m = re.search(r"T\d{2}[A-Z]{3}", f["id"])
        tile = m.group(0)
        if tile not in tiles:
            continue
        cc = f["properties"]["eo:cloud_cover"]
        if tile not in best or cc < best[tile][1]:
            best[tile] = (f["id"], cc, f["properties"]["datetime"][:10])
    return best


def download_part(url, start, end, out, lock, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, headers={"Range": f"bytes={start}-{end}"},
                             timeout=120, stream=True)
            r.raise_for_status()
            data = r.content
            # 严格校验：必须是 206 且字节数与请求区间一致，否则视为坏块重试
            if r.status_code != 206 or len(data) != end - start + 1:
                raise RuntimeError(f"Range 响应异常: status={r.status_code} len={len(data)}")
            with lock:
                with open(out, "r+b") as f:
                    f.seek(start)
                    f.write(data)
            return
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def download_file(url, dest):
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
    os_replace(tmp, dest)
    print(f"  完成 {dest.name}: {total/1e6:.1f} MB")
    return True


def os_replace(tmp, dest):
    import os
    os.replace(tmp, dest)


def verify_band(path):
    """下载后完整性校验：读左上、中部、右下三块数据，全部成功才算通过"""
    import rasterio
    with rasterio.open(path) as src:
        h, w = src.shape
        for r0, c0 in [(0, 0), (h // 2, w // 2), (max(0, h - 60), max(0, w - 60))]:
            src.read(1, window=((r0, min(r0 + 50, h)), (c0, min(c0 + 50, w))))
    return True


def download_single(url, dest):
    """单线程整文件下载（分块下载失败后的兜底路径，无 Range 更稳）"""
    import os
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(1024 * 1024):
            f.write(chunk)
    os.replace(tmp, dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, choices=[2019, 2024], default=None)
    ap.add_argument("--tiles", type=str, default=",".join(DEFAULT_TILES))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    tiles = [t.strip() for t in args.tiles.split(",") if t.strip()]
    years = [args.year] if args.year else [2019, 2024]

    manifest = []
    for year in years:
        print(f"\n== 检索 {year} 年冬季窗口（瓦片 {', '.join(tiles)}）==")
        feats = search_scenes(year)
        best = pick_best_per_tile(feats, tiles)
        for tile, (sid, cc, dt) in sorted(best.items()):
            print(f"  {tile}: {sid} 云量 {cc}% 日期 {dt}")
            if args.dry_run:
                continue
            item_url = (f"https://planetarycomputer.microsoft.com/api/stac/v1/"
                        f"collections/sentinel-2-l2a/items/{sid}")
            item = requests.get(item_url, timeout=90).json()
            outdir = RAW / sid
            outdir.mkdir(exist_ok=True)
            for b in BANDS:
                try:
                    dest = outdir / (b + ".tif")
                    url = get_signed_href(item["assets"][b]["href"])
                    ok = download_file(url, dest)
                    if ok and not verify_band(dest):
                        print(f"  {b} 校验失败，删除后单线程重下")
                        dest.unlink()
                        url = get_signed_href(item["assets"][b]["href"])
                        download_single(url, dest)
                        verify_band(dest)
                    if ok:
                        manifest.append({"scene": sid, "band": b,
                                         "bytes": dest.stat().st_size,
                                         "url": item["assets"][b]["href"]})
                except Exception as e:
                    print(f"  {b} 下载失败: {e}")
                time.sleep(1)
    if not args.dry_run:
        mf = RAW / "download_manifest_foshan.json"
        with open(mf, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        print(f"\n清单已写入 {mf}，共 {len(manifest)} 个文件")


if __name__ == "__main__":
    main()
