# -*- coding: utf-8 -*-
"""从 Planetary Computer 下载 Sentinel-2 L2A 指定波段，多线程分块下载，断点续传"""
import json
import os
import sys
import time
import threading
import requests
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
RAW = PROJECT / "原始数据" / "哨兵2号影像"
LOG = PROJECT / "日志与清单"
RAW.mkdir(parents=True, exist_ok=True)
LOG.mkdir(parents=True, exist_ok=True)

SCENES = [
    "S2A_MSIL2A_20191211T030121_R032_T49QGE_20201003T032515",  # 2019 冬 云量1.1%（南半部）
    "S2A_MSIL2A_20191211T030121_R032_T49QGF_20201003T032516",  # 2019 冬 云量2.4%（北半部）
    "S2B_MSIL2A_20241219T030029_R032_T49QGE_20241219T045947",  # 2024 冬 云量0.05%（南半部）
    "S2B_MSIL2A_20241219T030029_R032_T49QGF_20241219T045947",  # 2024 冬 云量0.008%（北半部）
]
BANDS = ["SCL", "B02", "B03", "B04", "B08", "B11", "B12"]
THREADS = 8
CHUNK = 4 * 1024 * 1024


def get_signed_href(collection, href, tries=6):
    for i in range(tries):
        r = requests.get(
            "https://planetarycomputer.microsoft.com/api/sas/v1/token/" + collection,
            params={"href": href}, timeout=90)
        if r.status_code == 200:
            return href + "?" + r.json()["token"]
        if r.status_code == 429 and i < tries - 1:
            wait = 3 * (2 ** i)
            print(f"  限流(429)，{wait}s 后重试...")
            time.sleep(wait)
            continue
        r.raise_for_status()


def fetch_item(scene_id):
    url = f"https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-2-l2a/items/{scene_id}"
    r = requests.get(url, timeout=90)
    r.raise_for_status()
    return r.json()


def download_part(url, start, end, out, lock, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, headers={"Range": f"bytes={start}-{end}"},
                             timeout=120, stream=True)
            r.raise_for_status()
            data = r.content
            with lock:
                with open(out, "r+b") as f:
                    f.seek(start)
                    f.write(data)
            return len(data)
        except Exception as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def download_file(url, dest, threads=THREADS):
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
    done = [0]
    lock = threading.Lock()
    parts = []
    step = (total + threads - 1) // threads
    for i in range(threads):
        s = i * step
        if s >= total:
            break
        parts.append((s, min(s + step - 1, total - 1)))
    t0 = time.time()
    threads_list = []
    for s, e in parts:
        t = threading.Thread(target=lambda a, b: download_part(url, a, b, tmp, lock),
                             args=(s, e))
        t.start()
        threads_list.append(t)
    for t in threads_list:
        t.join()
    dt = time.time() - t0
    os.replace(tmp, dest)
    print(f"  完成 {dest.name}: {total/1e6:.1f} MB, {total/dt/1e6:.2f} MB/s")
    return True


def main():
    manifest = []
    for sid in SCENES:
        print(f"== {sid[:29]}...")
        try:
            item = fetch_item(sid)
        except Exception as e:
            print(f"  获取条目失败: {e}")
            continue
        outdir = RAW / sid
        outdir.mkdir(parents=True, exist_ok=True)
        for b in BANDS:
            href = item["assets"][b]["href"]
            dest = outdir / (b + ".tif")
            if dest.exists():
                continue
            try:
                url = get_signed_href("sentinel-2-l2a", href)
                download_file(url, dest)
                manifest.append({"scene": sid, "band": b,
                                 "bytes": dest.stat().st_size,
                                 "url": href})
            except Exception as e:
                print(f"  {b} 下载失败: {e}")
            time.sleep(1)
    mf = RAW / "download_manifest.json"
    with open(mf, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"\n清单已写入 {mf}，共 {len(manifest)} 个文件")


if __name__ == "__main__":
    main()
