# -*- coding: utf-8 -*-
"""Landsat 与 Sentinel-2 建设用地交叉验证：
用 QA_PIXEL 云掩膜，计算 Landsat 建设用地掩膜（30m），
重采样到 S2 的 10m 网格，对比同区域同年的建设用地比例一致性"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

PROJECT = Path(__file__).resolve().parent.parent
RAW = PROJECT / "原始数据" / "Landsat影像"
CLEANED = PROJECT / "清洗数据"
cfg = json.load(open(PROJECT / "参数配置" / "thresholds.json", encoding="utf-8"))
EPSG = cfg["epsg"]
BT = cfg["built_thresholds"]

# Landsat Collection 2 Level-2 SR QA_PIXEL 位定义
QA_FILL = 1 << 0           # 填充/无效
QA_CIRRUS = 1 << 2         # 卷云
QA_CLOUD = 1 << 3          # 云
QA_SHADOW = 1 << 4         # 云影
QA_SNOW = 1 << 5           # 雪


def qa_clear(qa):
    bad = QA_FILL | QA_CLOUD | QA_SHADOW | QA_CIRRUS | QA_SNOW
    return (qa & bad) == 0


def main(scene_dir, s2_year):
    scene_dir = Path(scene_dir)
    bands = {}
    for b in ["blue", "green", "red", "nir08", "swir16", "swir22", "qa_pixel"]:
        p = scene_dir / f"{b}.tif"
        if not p.exists():
            sys.exit(f"缺少 {p}")
        with rasterio.open(p) as src:
            bands[b] = src.read(1).astype(np.float32)
            profile = src.profile

    qa = bands.pop("qa_pixel").astype(np.uint16)
    clear = qa_clear(qa)

    ndvi = (bands["nir08"] - bands["red"]) / (bands["nir08"] + bands["red"] + 1e-6)
    ndwi = (bands["green"] - bands["nir08"]) / (bands["green"] + bands["nir08"] + 1e-6)
    ndbi = (bands["swir16"] - bands["nir08"]) / (bands["swir16"] + bands["nir08"] + 1e-6)

    built = (ndbi > BT["NDBI_min"]) & (ndvi < BT["NDVI_max"]) & (ndwi < BT["NDWI_max"]) & clear
    cloud_frac = 1 - clear.mean()
    print(f"Landsat: 云/无效占比 {cloud_frac:.2%}，建设用地占比 {built.mean():.2%}")

    # 重采样到 S2 的 10m 网格（以 建设用地_{year}.tif 为参考）
    ref_path = CLEANED / f"建设用地_{s2_year}.tif"
    with rasterio.open(ref_path) as ref:
        dst_arr = np.zeros((ref.height, ref.width), dtype=np.uint8)
        dst_clear = np.zeros((ref.height, ref.width), dtype=np.uint8)
        reproject(
            source=built.astype(np.uint8),
            destination=dst_arr,
            src_transform=profile["transform"],
            src_crs=profile["crs"],
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=Resampling.nearest,
        )
        reproject(
            source=clear.astype(np.uint8),
            destination=dst_clear,
            src_transform=profile["transform"],
            src_crs=profile["crs"],
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=Resampling.nearest,
        )
        s2_arr = ref.read(1)

    # 仅比较两边都有效（无云）的区域
    both_valid = (s2_arr != 255) & (dst_clear == 1)
    agree = (dst_arr == s2_arr) & both_valid
    s2_built_frac = (s2_arr[both_valid] == 1).mean()
    l8_built_frac = (dst_arr[both_valid] == 1).mean()
    print(f"两边共同有效区域占比 {both_valid.mean():.2%}")
    print(f"共同有效区域内 S2 建设占比 {s2_built_frac:.2%}，Landsat 建设占比 {l8_built_frac:.2%}")
    print(f"像元级一致率 {agree[both_valid].mean():.2%}")

    out_arr = np.full(dst_arr.shape, 255, dtype=np.uint8)
    out_arr[dst_clear == 1] = dst_arr[dst_clear == 1]
    out = CLEANED / f"Landsat建设用地_{s2_year}.tif"
    with rasterio.open(ref_path) as ref:
        prof = ref.profile.copy()
        prof.update(dtype="uint8", nodata=255)
        with rasterio.open(out, "w", **prof) as dst:
            dst.write(out_arr, 1)
    print("已保存:", out)
    return s2_built_frac, l8_built_frac, agree[both_valid].mean()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("用法: python 06_landsat_validate.py <Landsat景目录> <S2年份>")
    main(sys.argv[1], int(sys.argv[2]))
