# -*- coding: utf-8 -*-
"""佛山市试跑管线（仿照中山 02_process_zhongshan.py）：
云掩膜 -> 指数计算 -> 建设用地变化 -> 5km 网格空间面板
输入：原始数据/哨兵2号影像/ 下佛山两颗瓦片（QFF+QGF）2019/2024 各一景；
      原始数据/行政区划/guangdong_440000_full.json（按 adcode=440600 取佛山市界）
输出：清洗数据/植被指数_佛山_{year}.tif、建设用地_佛山_{year}.tif、
      有效像元_佛山_{year}.tif、建设用地变化_佛山_2019至2024.tif；
      融合数据/空间面板_佛山_5km网格.csv
用法：python 02_process_foshan.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
import geopandas as gpd
import pandas as pd

PROJECT = Path(__file__).resolve().parent.parent
RAW = PROJECT / "原始数据" / "哨兵2号影像"
RAW_D7 = PROJECT / "原始数据" / "行政区划"
CLEANED = PROJECT / "清洗数据"
INTEGRATED = PROJECT / "融合数据"
CLEANED.mkdir(exist_ok=True)
INTEGRATED.mkdir(exist_ok=True)

cfg = json.load(open(PROJECT / "参数配置" / "thresholds.json", encoding="utf-8"))
EPSG = cfg["epsg"]
GRID_KM = cfg["grid_km"]
BT = cfg["built_thresholds"]
VALID_SCL = set(cfg["valid_scl_classes"])

# 佛山市行政代码（440600），覆盖中山配置中的 city_adcode
CITY_ADCODE = 440600

# 佛山横跨两颗卫星瓦片：QFF 西部（三水/高明）+ QGF 东部（禅城/南海/顺德），需拼接
SCENES = {
    2019: ["S2A_MSIL2A_20191211T030121_R032_T49QFF_20201003T032516",
           "S2A_MSIL2A_20191211T030121_R032_T49QGF_20201003T032516"],
    2024: ["S2B_MSIL2A_20241229T030029_R032_T49QFF_20241229T045836",
           "S2B_MSIL2A_20241219T030029_R032_T49QGF_20241219T045947"],
}


def get_city_geom():
    gdf = gpd.read_file(RAW_D7 / "guangdong_440000_full.json")
    city = gdf[gdf["adcode"] == CITY_ADCODE].iloc[0]
    gser = gpd.GeoSeries([city.geometry], crs="EPSG:4326").to_crs(f"EPSG:{EPSG}")
    return gser[0]


def get_common_grid(city_geom, dst_res=10, pad_m=2000):
    """以城市范围（而不是单颗瓦片）确定统一 10m 目标网格"""
    geom = gpd.GeoSeries([city_geom], crs=f"EPSG:{EPSG}").buffer(pad_m)[0]
    minx, miny, maxx, maxy = geom.bounds
    x0 = np.floor(minx / dst_res) * dst_res
    y1 = np.ceil(maxy / dst_res) * dst_res
    w = int(np.ceil((maxx - x0) / dst_res)) + 1
    h = int(np.ceil((y1 - miny) / dst_res)) + 1
    dst_transform = rasterio.Affine(dst_res, 0, x0, 0, -dst_res, y1)
    return dst_transform, (h, w)


def read_band_on_grid(path, dst_transform, shape, dst_crs):
    """把任意波段读取并重投影到统一 10m 网格上（逐块重投影，避免大网格内存溢出）"""
    from rasterio.windows import Window, transform as win_transform
    arr = np.zeros(shape, dtype=np.float32)
    step = 2048
    with rasterio.open(path) as src:
        for r0 in range(0, shape[0], step):
            h = min(step, shape[0] - r0)
            dst_win = Window(0, r0, shape[1], h)
            wt = win_transform(dst_win, dst_transform)
            chunk = np.zeros((h, shape[1]), dtype=np.float32)
            reproject(
                source=rasterio.band(src, 1),
                destination=chunk,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=wt,
                dst_crs=f"EPSG:{dst_crs}",
                resampling=Resampling.bilinear,
            )
            arr[r0:r0 + h, :] = chunk
    return arr


def compute_indices_tile(scene_dir, dst_transform, shape):
    """单颗瓦片在公共网格上计算 (ndvi, ndwi, ndbi, valid)"""
    bands = {}
    for b in ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"]:
        p = scene_dir / f"{b}.tif"
        if not p.exists():
            raise FileNotFoundError(f"缺少波段 {p}")
        bands[b] = read_band_on_grid(p, dst_transform, shape, EPSG)

    ndvi = (bands["B08"] - bands["B04"]) / (bands["B08"] + bands["B04"] + 1e-6)
    ndwi = (bands["B03"] - bands["B08"]) / (bands["B03"] + bands["B08"] + 1e-6)
    ndbi = (bands["B11"] - bands["B08"]) / (bands["B11"] + bands["B08"] + 1e-6)

    scl_int = np.round(bands["SCL"]).astype(np.int16)
    valid = np.isin(scl_int, list(VALID_SCL))
    valid &= np.isfinite(ndvi) & np.isfinite(ndwi) & np.isfinite(ndbi)
    return ndvi, ndwi, ndbi, valid


def compute_indices_mosaic(scene_dirs, city_geom):
    """多颗瓦片拼接：公共网格上逐瓦片计算指数，按有效掩膜合并（先到先得）"""
    dst_transform, shape = get_common_grid(city_geom)
    out = None
    for d in scene_dirs:
        print(f"    瓦片 {d.name[:29]}...")
        ndvi, ndwi, ndbi, valid = compute_indices_tile(d, dst_transform, shape)
        if out is None:
            out = {"ndvi": ndvi, "ndwi": ndwi, "ndbi": ndbi, "valid": valid}
        else:
            cur = {"ndvi": ndvi, "ndwi": ndwi, "ndbi": ndbi}
            take = valid & ~out["valid"]
            for k in cur:
                out[k] = np.where(take, cur[k], out[k])
            out["valid"] = out["valid"] | valid
    return out["ndvi"], out["ndwi"], out["ndbi"], out["valid"], dst_transform


def save_geotiff(path, arr, transform, crs, dtype="float32", nodata=-9999):
    profile = {
        "driver": "GTiff", "height": arr.shape[0], "width": arr.shape[1],
        "count": 1, "dtype": dtype, "transform": transform,
        "crs": f"EPSG:{crs}", "nodata": nodata, "compress": "lzw",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(dtype), 1)


def main():
    city_geom = get_city_geom()
    print(f"佛山市边界已加载（EPSG:{EPSG}）")

    built = {}
    valid_years = {}
    for year, sids in SCENES.items():
        print(f"\n== 处理 {year} 年（{len(sids)} 颗瓦片拼接）")
        ndvi, ndwi, ndbi, valid, t = compute_indices_mosaic(
            [RAW / sid for sid in sids], city_geom)

        cloud_frac = 1 - valid.mean()
        print(f"  栅格 {ndvi.shape[1]}x{ndvi.shape[0]}，云/无效像元占比 {cloud_frac:.1%}")

        bmask = (ndbi > BT["NDBI_min"]) & (ndvi < BT["NDVI_max"]) & (ndwi < BT["NDWI_max"]) & valid
        built[year] = bmask.astype(np.uint8)
        valid_years[year] = valid

        save_geotiff(CLEANED / f"植被指数_佛山_{year}.tif", ndvi.astype(np.float32), t, EPSG)
        save_geotiff(CLEANED / f"建设用地_佛山_{year}.tif", built[year], t, EPSG, dtype="uint8", nodata=255)
        save_geotiff(CLEANED / f"有效像元_佛山_{year}.tif", valid.astype(np.uint8), t, EPSG, dtype="uint8", nodata=255)
        print(f"  已保存 ndvi/built/valid {year}")

    b19, b24 = built[2019], built[2024]
    valid_both = valid_years[2019] & valid_years[2024]
    change = np.full(b24.shape, 255, dtype=np.uint8)
    change[(b24 == 1) & (b19 == 0) & valid_both] = 1   # 新增建设
    change[(b24 == 0) & (b19 == 1) & valid_both] = 2   # 减少建设
    change[(b24 == 1) & (b19 == 1) & valid_both] = 3   # 稳定建设
    change[(b24 == 0) & (b19 == 0) & valid_both] = 0   # 稳定非建设
    save_geotiff(CLEANED / "建设用地变化_佛山_2019至2024.tif", change, t, EPSG, dtype="uint8", nodata=255)

    # ---- 5km 网格聚合 ----
    res = 10.0
    cell_px = int(GRID_KM * 1000 / res)
    h, w = b24.shape
    ncols = int(np.ceil(w / cell_px))
    nrows = int(np.ceil(h / cell_px))

    def cell_ids(mask):
        rows, cols = np.nonzero(mask)
        cids = (rows // cell_px) * ncols + (cols // cell_px)
        return cids

    c19 = cell_ids(b19 == 1)
    c24 = cell_ids(b24 == 1)
    cnew = cell_ids(change == 1)
    call = cell_ids(change != 255)

    cnt19 = np.bincount(c19, minlength=nrows * ncols)
    cnt24 = np.bincount(c24, minlength=nrows * ncols)
    cntnew = np.bincount(cnew, minlength=nrows * ncols)
    cntall = np.bincount(call, minlength=nrows * ncols)

    panel = pd.DataFrame({
        "grid_row": np.repeat(np.arange(nrows), ncols),
        "grid_col": np.tile(np.arange(ncols), nrows),
        "built_px_2019": cnt19,
        "built_px_2024": cnt24,
        "new_built_px": cntnew,
        "valid_px": cntall,
    })
    panel["x_min"] = t.c + panel["grid_col"] * cell_px * res
    panel["y_max"] = t.f - panel["grid_row"] * cell_px * res
    panel["x_max"] = panel["x_min"] + cell_px * res
    panel["y_min"] = panel["y_max"] - cell_px * res
    panel = panel[panel["valid_px"] > 0.5 * cell_px * cell_px]
    panel["built_ratio_2019"] = panel["built_px_2019"] / panel["valid_px"]
    panel["built_ratio_2024"] = panel["built_px_2024"] / panel["valid_px"]
    panel["new_built_ratio"] = panel["new_built_px"] / panel["valid_px"]
    panel["space_id"] = panel["grid_row"].astype(str) + "_" + panel["grid_col"].astype(str)

    out_csv = INTEGRATED / "空间面板_佛山_5km网格.csv"
    panel.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"\n网格面板已保存: {out_csv}，{len(panel)} 个有效网格")
    print(f"2019 建设用地比例均值 {panel['built_ratio_2019'].mean():.2%}，"
          f"2024 均值 {panel['built_ratio_2024'].mean():.2%}")
    print(f"新增建设网格数 {(panel['new_built_px'] > 0).sum()} / {len(panel)}")


if __name__ == "__main__":
    main()
