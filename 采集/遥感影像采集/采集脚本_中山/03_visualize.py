# -*- coding: utf-8 -*-
"""中山试跑结果可视化（可读版）：
图1 建设用地变化图：裁市界 + 去噪 + 块聚合 + 镇街地名 + 主干道 + 北箭头 + 比例尺 + 全省位置图
图2 网格新增建设图：5km 网格 choropleth，同样带地理要素"""
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

for fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
           r"C:\Windows\Fonts\simsun.ttc"]:
    try:
        font_manager.fontManager.addfont(fp)
        plt.rcParams["font.sans-serif"] = [font_manager.FontProperties(fname=fp).get_name(), "DejaVu Sans"]
        break
    except FileNotFoundError:
        continue
plt.rcParams["axes.unicode_minus"] = False

import geopandas as gpd
import pandas as pd
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from scipy.ndimage import label as ndlabel
from shapely.geometry import box

PROJECT = Path(__file__).resolve().parent.parent
CLEANED = PROJECT / "清洗数据"
INTEGRATED = PROJECT / "融合数据"

MIN_PATCH = 30
BLOCK = 8
CMAP = ListedColormap(["#d9d9d9", "#e31a1c", "#3182bd", "#08519c"])
LEGEND = {0: "一直没建筑", 1: "新增建设（这五年新盖的）", 2: "减少建设（拆掉/复绿）", 3: "一直有建筑"}


def hatch_invalid(ax, invalid, extent):
    """给无效（云遮挡）区块画斜纹"""
    if invalid.sum() == 0:
        return
    h2, w2 = invalid.shape
    x0, x1, y0, y1 = extent
    xs = np.linspace(x0, x1, w2 + 1)
    ys = np.linspace(y0, y1, h2 + 1)
    X, Y = np.meshgrid(xs, ys)
    ax.pcolormesh(X, Y, np.ma.masked_where(~invalid, invalid.astype(float)),
                  hatch="///", facecolor="none", edgecolor="none", alpha=0.6)


def figure_for(aspect, extra=1.5):
    return plt.subplots(figsize=(8, 8 * aspect + extra), dpi=160)
TRANS = Transformer.from_crs("EPSG:4326", "EPSG:32649", always_xy=True)

# 中山主要镇街（经度, 纬度, 名称）
TOWNS = [
    (113.378, 22.521, "中山市区"), (113.250, 22.670, "小榄镇"), (113.188, 22.615, "古镇镇"),
    (113.290, 22.720, "南头镇"), (113.340, 22.710, "黄圃镇"), (113.420, 22.670, "三角镇"),
    (113.495, 22.620, "民众街道"), (113.395, 22.585, "港口镇"), (113.470, 22.560, "火炬开发区"),
    (113.530, 22.445, "南朗街道"), (113.440, 22.350, "三乡镇"), (113.470, 22.255, "坦洲镇"),
    (113.320, 22.400, "板芙镇"), (113.290, 22.470, "大涌镇"),
]


def get_city():
    gdf = gpd.read_file(PROJECT / "原始数据" / "行政区划" / "guangdong_440000_full.json")
    return gdf[gdf["adcode"] == 442000].to_crs("EPSG:32649").geometry.iloc[0]


def get_province():
    return gpd.read_file(PROJECT / "原始数据" / "行政区划" / "guangdong_440000_full.json")


def remove_small_patches(arr, classes=(1, 2), min_px=MIN_PATCH):
    out = arr.copy()
    for c in classes:
        m = arr == c
        if m.sum() == 0:
            continue
        lbl, n = ndlabel(m)
        sizes = np.bincount(lbl.ravel(), minlength=n + 1)
        small = np.where(sizes < min_px)[0]
        out[np.isin(lbl, small) & m] = 255
    return out


def block_majority(arr, bs):
    h, w = arr.shape
    h2, w2 = h // bs, w // bs
    b = arr[:h2 * bs, :w2 * bs].reshape(h2, bs, w2, bs).transpose(0, 2, 1, 3).reshape(h2, w2, -1)
    cnts = np.stack([(b == c).sum(-1) for c in range(4)], -1)
    dom = cnts.argmax(-1).astype(np.uint8)
    inv = (b == 255).sum(-1)
    return np.where(inv > bs * bs // 2, 255, dom)


def add_context(ax, extent, inset_axes):
    """加镇街地名、主干道、北箭头、比例尺、全省位置小图"""
    x0, x1, y0, y1 = extent
    # 主干道路
    try:
        roads = gpd.read_file(CLEANED / "道路要素_广东.gpkg", rows=20000)
        if "highway" in roads.columns:
            main = roads[roads["highway"].isin(["motorway", "trunk", "primary"])]
            main = gpd.clip(main, gpd.GeoSeries([get_city()], crs=main.crs))
            main.plot(ax=ax, color="#b8b8b8", linewidth=0.9, zorder=2)
    except Exception as e:
        print("  主干道加载失败:", e)
    # 镇街地名
    for lon, lat, name in TOWNS:
        x, y = TRANS.transform(lon, lat)
        ax.annotate(name, (x, y), fontsize=8, color="#333333",
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75))
    # 北箭头
    ax.annotate("北", xy=(x0 + 0.03 * (x1 - x0), y0 + 0.20 * (y1 - y0)),
                xytext=(x0 + 0.03 * (x1 - x0), y0 + 0.07 * (y1 - y0)),
                fontsize=11, ha="center",
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.5))
    # 比例尺（5 公里）
    sx = x1 - 0.08 * (x1 - x0)
    sy = y0 + 0.04 * (y1 - y0)
    ax.plot([sx - 5000, sx], [sy, sy], color="black", lw=2)
    ax.plot([sx - 5000, sx - 5000], [sy - 500, sy + 500], color="black", lw=1.5)
    ax.plot([sx, sx], [sy - 500, sy + 500], color="black", lw=1.5)
    ax.text(sx - 2500, sy + 1500, "5 公里", fontsize=9, ha="center")
    # 全省位置小图
    prov = get_province()
    prov.plot(ax=inset_axes, color="#e8e8e8", edgecolor="#888888", linewidth=0.4)
    prov[prov["adcode"] == 442000].plot(ax=inset_axes, color="#e31a1c")
    inset_axes.set_title("在广东的位置", fontsize=7)
    inset_axes.set_xticks([])
    inset_axes.set_yticks([])


def plot_change():
    with rasterio.open(CLEANED / "建设用地变化_2019至2024.tif") as src:
        city = get_city()
        clipped, out_transform = rio_mask(src, [city], crop=True, filled=True, nodata=255)
        chg = clipped[0]
    chg = remove_small_patches(chg)
    agg = block_majority(chg, BLOCK)
    t2 = rasterio.Affine(out_transform.a * BLOCK, 0, out_transform.c,
                         0, out_transform.e * BLOCK, out_transform.f)
    extent = [t2.c, t2.c + agg.shape[1] * t2.a, t2.f + agg.shape[0] * t2.e, t2.f]

    fig, ax = figure_for(agg.shape[0] / agg.shape[1])
    inset = fig.add_axes([0.76, 0.83, 0.18, 0.14])
    ax.imshow(np.ma.masked_equal(agg.astype(float), 255), cmap=CMAP,
              extent=extent, interpolation="nearest", vmin=0, vmax=3, zorder=1)
    hatch_invalid(ax, agg == 255, extent)
    gpd.GeoSeries([city]).boundary.plot(ax=ax, color="black", linewidth=1.0, zorder=3)
    add_context(ax, extent, inset)
    handles = [Patch(color=CMAP(i), label=LEGEND[i]) for i in range(4)]
    handles.append(Patch(facecolor="white", hatch="///", label="被云挡住，无法比较"))
    ax.legend(handles=handles, loc="lower left", fontsize=8.5, framealpha=0.95)
    ax.set_title("中山市这五年（2019→2024）新盖的房子主要在哪里？\n"
                 "红色 = 新增建设用地（Sentinel-2 卫星 10m 影像提取）", fontsize=12)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    out = CLEANED / "中山建设用地变化图.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print("已保存:", out)

    v = chg != 255
    for c in [1, 2, 3]:
        print(f"  {LEGEND[c]}: {(chg == c).sum() / max(v.sum(), 1):.2%}")


def plot_grid():
    panel = pd.read_csv(INTEGRATED / "空间面板_中山_含OSM密度.csv")
    city = get_city()
    cells = gpd.GeoDataFrame(
        {"new_ratio": panel["new_built_ratio"] * 100,
         "geometry": [box(x1, y1, x2, y2) for x1, y1, x2, y2 in
                      zip(panel.x_min, panel.y_min, panel.x_max, panel.y_max)]},
        crs="EPSG:32649")
    cells = gpd.clip(cells, gpd.GeoSeries([city], crs=cells.crs))
    x0, y0, x1, y1 = cells.total_bounds
    extent = [x0, x1, y0, y1]

    aspect = (y1 - y0) / (x1 - x0)
    fig, ax = figure_for(aspect)
    inset = fig.add_axes([0.76, 0.83, 0.18, 0.14])
    cells.plot(column="new_ratio", ax=ax, cmap="Reds", edgecolor="white",
               linewidth=0.4, legend=True,
               legend_kwds={"label": "网格内新增建设占比 (%)", "shrink": 0.55, "pad": 0.02},
               vmin=0, vmax=max(cells.new_ratio.max(), 5), zorder=1)
    gpd.GeoSeries([city]).boundary.plot(ax=ax, color="black", linewidth=1.0, zorder=3)
    add_context(ax, extent, inset)
    ax.set_title("中山哪些地方建设扩张最快？\n"
                 "5km×5km 网格内新增建设面积占比（2019→2024，颜色越深扩张越快）", fontsize=12)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    out = CLEANED / "中山网格新增建设图.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print("已保存:", out)
    print(f"网格新增建设占比: 均值 {panel['new_built_ratio'].mean():.2%}，"
          f"最大 {panel['new_built_ratio'].max():.2%}")


if __name__ == "__main__":
    plot_change()
    plot_grid()
