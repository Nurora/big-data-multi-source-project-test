# -*- coding: utf-8 -*-
"""从 china-latest.osm.pbf 提取广东道路/建筑，计算 5km 网格密度"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import box

PROJECT = Path(__file__).resolve().parent.parent
RAW = PROJECT / "原始数据"
CLEANED = PROJECT / "清洗数据"
INTEGRATED = PROJECT / "融合数据"
cfg = json.load(open(PROJECT / "参数配置" / "thresholds.json", encoding="utf-8"))
EPSG = cfg["epsg"]

PBF = RAW / "OSM地图数据" / "china-latest.osm.pbf"
GD_BBOX = (109.6, 20.2, 117.4, 25.5)  # 广东省大致范围 lon/lat


def main():
    from pyrosm import OSM, get_data

    if not PBF.exists():
        sys.exit(f"缺少 {PBF}")
    print("解析 PBF（全中国文件较大，需几分钟）...")
    osm = OSM(str(PBF))

    print("提取建筑...")
    buildings = osm.get_buildings()
    b = buildings.cx[GD_BBOX[0]:GD_BBOX[2], GD_BBOX[1]:GD_BBOX[3]].to_crs(f"EPSG:{EPSG}")
    b["area"] = b.geometry.area
    b.to_file(CLEANED / "建筑要素_广东.gpkg", driver="GPKG")
    print(f"  广东建筑要素: {len(b)}")

    print("提取路网...")
    roads = osm.get_network()
    r = roads.cx[GD_BBOX[0]:GD_BBOX[2], GD_BBOX[1]:GD_BBOX[3]].to_crs(f"EPSG:{EPSG}")
    r["length"] = r.geometry.length
    r.to_file(CLEANED / "道路要素_广东.gpkg", driver="GPKG")
    print(f"  广东道路要素: {len(r)}")

    # ---- 5km 网格聚合（用 spatial_panel 的网格定义） ----
    panel = pd.read_csv(INTEGRATED / "空间面板_中山_5km网格.csv")
    cells = [box(x1, y1, x2, y2) for x1, y1, x2, y2 in
             zip(panel["x_min"], panel["y_min"], panel["x_max"], panel["y_max"])]
    grid = gpd.GeoDataFrame({"space_id": panel["space_id"], "geometry": cells}, crs=f"EPSG:{EPSG}")

    bj = gpd.sjoin(b, grid, predicate="intersects")
    area_per_cell = bj.groupby("space_id")["area"].sum()
    panel["building_area_m2"] = panel["space_id"].map(area_per_cell).fillna(0)

    rj = gpd.sjoin(r, grid, predicate="intersects")
    rj["seg_len"] = rj["length"].clip(lower=0)
    # 简单处理：长度按比例计入（不做切割）
    len_per_cell = rj.groupby("space_id")["seg_len"].sum()
    panel["road_length_m"] = panel["space_id"].map(len_per_cell).fillna(0)

    cell_area_km2 = (cfg["grid_km"] * 1000) ** 2 / 1e6
    panel["road_density_km_km2"] = panel["road_length_m"] / 1000 / cell_area_km2
    panel["building_density"] = panel["building_area_m2"] / (cfg["grid_km"] * 1000) ** 2

    out = INTEGRATED / "空间面板_中山_含OSM密度.csv"
    panel.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"已保存: {out}")
    print(f"道路密度均值 {panel['road_density_km_km2'].mean():.2f} km/km2，"
          f"建筑密度均值 {panel['building_density'].mean():.2%}")


if __name__ == "__main__":
    main()
