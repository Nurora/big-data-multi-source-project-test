# -*- coding: utf-8 -*-
"""为清洗数据里的每个栅格生成可读预览图（存 清洗数据/预览图/）
tif 是数据文件直接看是黑的，本脚本把每个栅格渲染成带配色/图例/地名的 PNG"""
from pathlib import Path
import shutil

import numpy as np
import rasterio
from rasterio.mask import mask as rio_mask
from pyproj import Transformer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch

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
from matplotlib.colors import ListedColormap, LinearSegmentedColormap

BUILT_CMAP = LinearSegmentedColormap.from_list("built", ["#e0e0e0", "#e31a1c"])

PROJECT = Path(__file__).resolve().parent.parent
CLEANED = PROJECT / "清洗数据"
PREVIEW = CLEANED / "预览图"
PREVIEW.mkdir(exist_ok=True)
TRANS = Transformer.from_crs("EPSG:4326", "EPSG:32649", always_xy=True)
BLOCK = 8

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


def load_clipped(path):
    """读取栅格并裁剪到市界，返回 (数组, 变换)"""
    with rasterio.open(path) as src:
        city = get_city()
        clipped, t = rio_mask(src, [city], crop=True, filled=True, nodata=255)
    return clipped[0], t


def block_mean(arr, bs):
    h, w = arr.shape
    h2, w2 = h // bs, w // bs
    a = arr[:h2 * bs, :w2 * bs].reshape(h2, bs, w2, bs)
    return a.mean(axis=(1, 3))


def block_majority(arr, bs):
    h, w = arr.shape
    h2, w2 = h // bs, w // bs
    b = arr[:h2 * bs, :w2 * bs].reshape(h2, bs, w2, bs).transpose(0, 2, 1, 3).reshape(h2, w2, -1)
    cnts = np.stack([(b == c).sum(-1) for c in range(4)], -1)
    dom = cnts.argmax(-1).astype(np.uint8)
    inv = (b == 255).sum(-1)
    return np.where(inv > bs * bs // 2, 255, dom).astype(np.uint8)


def draw_base(ax, extent, towns=True, scale=True):
    x0, x1, y0, y1 = extent
    if towns:
        for lon, lat, name in TOWNS:
            x, y = TRANS.transform(lon, lat)
            ax.annotate(name, (x, y), fontsize=7.5, color="#333333", ha="center", va="center",
                        bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.7))
    ax.annotate("北", xy=(x0 + 0.03 * (x1 - x0), y0 + 0.20 * (y1 - y0)),
                xytext=(x0 + 0.03 * (x1 - x0), y0 + 0.07 * (y1 - y0)),
                fontsize=10, ha="center",
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.4))
    if scale:
        sx = x1 - 0.08 * (x1 - x0)
        sy = y0 + 0.05 * (y1 - y0)
        ax.plot([sx - 5000, sx], [sy, sy], color="black", lw=2)
        ax.plot([sx - 5000, sx - 5000], [sy - 500, sy + 500], color="black", lw=1.5)
        ax.plot([sx, sx], [sy - 500, sy + 500], color="black", lw=1.5)
        ax.text(sx - 2500, sy + 1500, "5 公里", fontsize=8.5, ha="center")
    ax.set_xticks([])
    ax.set_yticks([])


def render(path, out_name, title, kind, cmap=None, vmin=None, vmax=None,
           legend_labels=None, colorbar_label=None, source_note=None):
    arr, t = load_clipped(path)
    a = arr.astype(np.float32)
    a[a == 255] = np.nan
    t2 = rasterio.Affine(t.a * BLOCK, 0, t.c, 0, t.e * BLOCK, t.f)

    if kind == "change_rgb":
        # 变化图专用：每个块按新增占比染红、减少占比染蓝，颜色深浅=变化比例
        nf = block_mean((arr == 1).astype(np.float32), BLOCK)
        lf = block_mean((arr == 2).astype(np.float32), BLOCK)
        valid_frac = block_mean((arr != 255).astype(np.float32), BLOCK)
        base = np.float32(215)
        R = base - 12 * nf - 166 * lf
        G = base - 189 * nf - 85 * lf
        B = base - 187 * nf - 26 * lf
        rgb = np.stack([R, G, B], -1).clip(0, 255) / 255.0
        alpha = (valid_frac > 0.5).astype(np.float32)[..., None]
        rgba = np.concatenate([rgb, alpha], -1)
        h2, w2 = rgba.shape[:2]
        extent = [t2.c, t2.c + w2 * t2.a, t2.f + h2 * t2.e, t2.f]
        fig, ax = plt.subplots(figsize=(8, 8 * h2 / w2 + 1.5), dpi=160)
        ax.set_facecolor("white")
        ax.imshow(rgba, extent=extent, interpolation="nearest")
        inv = valid_frac <= 0.5
        if inv.sum():
            xs = np.linspace(extent[0], extent[1], w2 + 1)
            ys = np.linspace(extent[2], extent[3], h2 + 1)
            X, Y = np.meshgrid(xs, ys)
            ax.pcolormesh(X, Y, np.ma.masked_where(~inv, inv.astype(float)),
                          hatch="///", facecolor="none", edgecolor="none", alpha=0.6)
        handles = [Patch(color="#e31a1c", label="新增建设（红色越深越多）"),
                   Patch(color="#3182bd", label="减少建设（蓝色越深越多）"),
                   Patch(color="#d7d7d7", label="没有变化"),
                   Patch(facecolor="white", hatch="///", label="被云挡住，无法比较")]
        ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.95)
    elif kind == "categorical":
        disp = block_majority(arr, BLOCK)
        extent = [t2.c, t2.c + disp.shape[1] * t2.a, t2.f + disp.shape[0] * t2.e, t2.f]
        fig, ax = plt.subplots(figsize=(8, 8 * disp.shape[0] / disp.shape[1] + 1.5), dpi=160)
        ax.set_facecolor("white")
        m = np.ma.masked_equal(disp.astype(float), 255)
        im = ax.imshow(m, cmap=cmap, extent=extent, interpolation="nearest", vmin=0, vmax=vmax)
        handles = [Patch(color=cmap(i), label=legend_labels[i]) for i in range(len(legend_labels))]
        ax.legend(handles=handles, loc="lower left", fontsize=8, framealpha=0.95)
    else:
        disp = block_mean(a, BLOCK)
        extent = [t2.c, t2.c + disp.shape[1] * t2.a, t2.f + disp.shape[0] * t2.e, t2.f]
        fig, ax = plt.subplots(figsize=(8, 8 * disp.shape[0] / disp.shape[1] + 1.5), dpi=160)
        ax.set_facecolor("white")
        im = ax.imshow(disp, cmap=cmap, extent=extent, interpolation="nearest", vmin=vmin, vmax=vmax)
        cb = fig.colorbar(im, ax=ax, shrink=0.55, pad=0.02)
        cb.set_label(colorbar_label, fontsize=9)
        cb.ax.tick_params(labelsize=8)
    gpd.GeoSeries([get_city()]).boundary.plot(ax=ax, color="black", linewidth=1.0, zorder=3)
    draw_base(ax, extent)
    subtitle = source_note or "数据来源：见 数据源清单.md"
    ax.set_title(f"{title}\n{subtitle}", fontsize=11)
    fig.tight_layout()
    out = PREVIEW / out_name
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print("已保存:", out)


def main():
    built_cmap = ListedColormap(["#f2f2f2", "#e31a1c"])
    chg_cmap = ListedColormap(["#f2f2f2", "#e31a1c", "#3182bd", "#08519c"])
    chg_legend = {0: "一直没建筑", 1: "新增建设", 2: "减少建设", 3: "一直有建筑"}

    render(CLEANED / "建设用地_2019.tif", "01_建设用地_2019.png",
           "2019 年中山哪些地方是建设用地？", "fraction",
           cmap=BUILT_CMAP, vmin=0, vmax=1, colorbar_label="街区建设用地占比（灰=非建设，红=建设）",
           source_note="Sentinel-2 卫星 10m 影像")
    render(CLEANED / "建设用地_2024.tif", "02_建设用地_2024.png",
           "2024 年中山哪些地方是建设用地？", "fraction",
           cmap=BUILT_CMAP, vmin=0, vmax=1, colorbar_label="街区建设用地占比（灰=非建设，红=建设）",
           source_note="Sentinel-2 卫星 10m 影像")
    render(CLEANED / "建设用地变化_2019至2024.tif", "03_建设用地变化_2019至2024.png",
           "这五年（2019→2024）新盖的房子主要在哪里？", "categorical",
           cmap=chg_cmap, vmax=3, legend_labels=chg_legend,
           source_note="红色=新增建设，蓝色=减少建设（Sentinel-2）")
    render(CLEANED / "有效像元_2019.tif", "04_有效像元_2019.png",
           "2019 年影像哪些地方被云挡住不能用？", "fraction",
           cmap="RdYlGn_r", vmin=0, vmax=1, colorbar_label="有效像元占比（红=云多，绿=清晰）",
           source_note="约 7.5% 像元被云/云影遮挡（SCL 云掩膜）")
    render(CLEANED / "有效像元_2024.tif", "05_有效像元_2024.png",
           "2024 年影像哪些地方被云挡住不能用？", "fraction",
           cmap="RdYlGn_r", vmin=0, vmax=1, colorbar_label="有效像元占比（红=云多，绿=清晰）",
           source_note="这景几乎无云（SCL 云掩膜）")
    render(CLEANED / "植被指数_2019.tif", "06_植被指数_2019.png",
           "2019 年中山植被分布", "fraction",
           cmap="RdYlGn", vmin=-0.2, vmax=0.8, colorbar_label="NDVI 植被指数（绿=植被，红=水面/裸地）",
           source_note="NDVI = (近红外-红)/(近红外+红)，Sentinel-2")
    render(CLEANED / "植被指数_2024.tif", "07_植被指数_2024.png",
           "2024 年中山植被分布", "fraction",
           cmap="RdYlGn", vmin=-0.2, vmax=0.8, colorbar_label="NDVI 植被指数（绿=植被，红=水面/裸地）",
           source_note="NDVI，Sentinel-2")
    render(CLEANED / "Landsat建设用地_2019.tif", "08_Landsat建设用地_2019.png",
           "2019 年建设用地（Landsat 卫星独立验证）", "fraction",
           cmap=BUILT_CMAP, vmin=0, vmax=1, colorbar_label="街区建设用地占比（灰=非建设，红=建设）",
           source_note="Landsat 8 卫星 30m，与哨兵2号交叉验证 r=0.96")
    render(CLEANED / "Landsat建设用地_2024.tif", "09_Landsat建设用地_2024.png",
           "2024 年建设用地（Landsat 卫星独立验证）", "fraction",
           cmap=BUILT_CMAP, vmin=0, vmax=1, colorbar_label="街区建设用地占比（灰=非建设，红=建设）",
           source_note="Landsat 8 卫星 30m，与哨兵2号交叉验证 r=0.93")
    # 把两张主图也放进预览图文件夹
    shutil.copy(CLEANED / "中山建设用地变化图.png", PREVIEW / "10_中山建设用地变化图_主图.png")
    shutil.copy(CLEANED / "中山网格新增建设图.png", PREVIEW / "11_中山网格新增建设图_主图.png")
    print("已复制两张主图到预览图文件夹")


if __name__ == "__main__":
    main()
