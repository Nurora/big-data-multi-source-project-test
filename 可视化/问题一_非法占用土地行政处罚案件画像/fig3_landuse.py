# -*- coding: utf-8 -*-
"""绘图 · 图3：非法占用土地的原地类至违法后用途流向。

数据来源：07_图3_地类用途矩阵.csv、07e_图3_样本量.csv
输出：output/figures/图3_非法占用土地的原地类至违法后用途流向.png
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from plot_style_report import INK, header, save

from paths import TABLES as T
tab = pd.read_csv(T / "07_图3_地类用途矩阵.csv", index_col=0)
meta = pd.read_csv(T / "07e_图3_样本量.csv").iloc[0]

LAND_COLORS = {
    "耕地": "#c9a227", "园地": "#8fae6b", "林地": "#4f7d4a", "建设用地": "#7f8b95",
    "其他土地": "#5b8fa8", "农用地(未细分)": "#b58a5a", "多类并列(未分面积)": "#9b7a8f",
}
RIGHT_COLOR = "#5f7585"

fig = plt.figure(figsize=(6.000, 3.811))
ax = fig.add_axes([.172, .155, .605, .665])
ax.set_xlim(-.02, 1.03)
ax.set_ylim(-.03, 1.07)
ax.axis("off")

gap = .024
total = int(tab.values.sum())
scale = (1 - gap * (max(tab.shape) - 1)) / total
left_tot = tab.sum(axis=1)
right_tot = tab.sum(axis=0)

pos_l, pos_r, mid_l, mid_r = {}, {}, {}, {}
top = 1.0
for name, v in left_tot.items():
    hgt = v * scale
    pos_l[name] = top
    mid_l[name] = top - hgt / 2
    ax.add_patch(Rectangle((-.012, top - hgt), .024, hgt, color=LAND_COLORS.get(name, "#999"), lw=0))
    ax.text(-.028, top - hgt / 2 + .012, name, ha="right", va="center", fontsize=6.5, color=INK)
    ax.text(-.028, top - hgt / 2 - .026, f"{int(v):,}", ha="right", va="center", fontsize=6.0, color="#5c6b76")
    top -= hgt + gap
top = 1.0
for name, v in right_tot.items():
    hgt = v * scale
    pos_r[name] = top
    mid_r[name] = top - hgt / 2
    ax.add_patch(Rectangle((.988, top - hgt), .024, hgt, color=RIGHT_COLOR, lw=0))
    top -= hgt + gap

# 右侧标签防重叠：按节点中心排序后强制最小间距，并画引线
min_gap = .044
placed, last = [], None
for name, y in sorted(mid_r.items(), key=lambda t: -t[1]):
    new_y = y if last is None else min(y, last - min_gap)
    placed.append((name, y, new_y))
    last = new_y
for name, y0, y1 in placed:
    ax.plot([1.012, 1.028], [y0, y1], color="#9aa8b2", lw=.5)
    ax.text(1.032, y1, f"{name}  {int(right_tot[name]):,}", ha="left", va="center", fontsize=5.9, color=INK)

flows = []
for land, row in tab.iterrows():
    for use, v in row.items():
        if v > 0:
            flows.append((land, use, int(v)))
labels = []
for land, use, v in sorted(flows, key=lambda x: -x[2]):
    hgt = v * scale
    y0, y1 = pos_l[land], pos_r[use]
    labels.append((v, (y0 + y1) / 2 - hgt / 2))
    verts = [(.012, y0), (.40, y0), (.60, y1), (.988, y1),
             (.988, y1 - hgt), (.60, y1 - hgt), (.40, y0 - hgt), (.012, y0 - hgt), (.012, y0)]
    codes = [MPath.MOVETO, *[MPath.CURVE4] * 3, MPath.LINETO, *[MPath.CURVE4] * 3, MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor=LAND_COLORS.get(land, "#999"), alpha=.34, lw=0))
    pos_l[land] -= hgt
    pos_r[use] -= hgt

for v, y in labels[:4]:
    ax.text(.5, y, f"{v:,}", ha="center", va="center", fontsize=6.0, color="#2c3e4c",
            bbox=dict(boxstyle="round,pad=.14", fc="white", ec="none", alpha=.86))

ax.text(.0, 1.045, "土地原地类", ha="center", va="bottom", fontsize=6.9, weight="bold", color=INK)
ax.text(1.0, 1.045, "违法后用途", ha="center", va="bottom", fontsize=6.9, weight="bold", color=INK)

header(fig, "非法占用土地的地类来源与违法后用途：基础设施与房屋建设是主要去向",
       f"原地类与违法后用途均可识别 {int(meta['两端均可识别']):,} 项，占非法占地处罚的 {meta['两端可识别比例']:.1%}；色带宽度为处罚数",
       [f"原地类可识别 {int(meta['原地类可识别']):,} 项、违法后用途可识别 {int(meta['违法后用途可识别']):,} 项；任一端未识别者不分配流向。",
        "地类只按原文记载归并；“农用地”等集合词不拆分推测，多类并列且无面积时单列。"])
save(fig, "图3_非法占用土地的原地类至违法后用途流向")
