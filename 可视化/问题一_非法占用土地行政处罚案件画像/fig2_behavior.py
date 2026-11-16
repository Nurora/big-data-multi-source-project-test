# -*- coding: utf-8 -*-
"""绘图 · 图2：非法占用土地的行为方式构成。

数据来源：05_图2_行为类型构成.csv、06_图2_主体与行为类型.csv
输出：output/figures/图2_非法占用土地的行为方式构成.png
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from plot_style_report import GRAY, GRAY_L, INK, ORANGE, SAND, TEAL, TEAL_L, header, pct, save

from paths import TABLES as T
r = pd.read_csv(T / "05_图2_行为类型构成.csv")
ct = pd.read_csv(T / "06_图2_主体与行为类型.csv")

ORDER = ["未经批准占用", "超出批准范围或面积占用", "临时用地违法占用", "未载明具体方式"]
COLORS = {"未经批准占用": TEAL, "超出批准范围或面积占用": ORANGE,
          "临时用地违法占用": SAND, "未载明具体方式": GRAY_L}
r = r.set_index("行为方式").loc[ORDER]
total = int(r["处罚数"].sum())

fig = plt.figure(figsize=(6.000, 2.878))
ax1 = fig.add_axes([.235, .305, .265, .49])
ax2 = fig.add_axes([.715, .305, .255, .49])

# A 行为类型：对数刻度点线图，避免小类别被大类别压没
y = np.arange(len(ORDER))
vals = r["处罚数"].to_numpy()
shares = r["占非法占地比例"].to_numpy()
ax1.hlines(y, 20, vals, color=[COLORS[k] for k in ORDER], lw=1.0, alpha=.55)
ax1.scatter(vals, y, s=34, color=[COLORS[k] for k in ORDER], zorder=3, edgecolor="white", linewidth=.6)
for i, (v, s) in enumerate(zip(vals, shares)):
    ax1.text(v * 1.22, i, f"{v:,}（{s*100:.1f}%）", va="center", fontsize=6.3,
             color=INK if v > 100 else "#5b6a75")
ax1.set_xscale("log")
ax1.set(yticks=y, yticklabels=ORDER, ylim=(len(y)-.45, -.55), xlim=(20, 60000))
ax1.set_xticks([100, 1000, 10000])
ax1.set_xticklabels(["100", "1,000", "10,000"], fontsize=6.0)
ax1.xaxis.set_minor_formatter(plt.NullFormatter())
ax1.tick_params(axis="x", which="minor", length=0)
ax1.tick_params(axis="y", length=0, labelsize=6.6)
ax1.grid(axis="x", color="#e7edf1", lw=.5)
ax1.set_axisbelow(True)
ax1.set_xlabel("处罚数（对数刻度）", fontsize=6.3, labelpad=1)
ax1.set_title("A  全部非法占地处罚的行为方式", fontsize=6.9, weight="bold", loc="left", pad=6, color=INK)

# B 分主体构成（含未载明，用于比较记录详略）
sub_order = ["自然人", "企业", "村委会/集体经济组织", "其他组织", "事业单位/政府机构"]
piv = ct.pivot(index="主体", columns="行为方式", values="主体内比例").reindex(index=sub_order, columns=ORDER).fillna(0)
yb = np.arange(len(sub_order))
left = np.zeros(len(sub_order))
for k in ORDER:
    ax2.barh(yb, piv[k], left=left, height=.58, color=COLORS[k], edgecolor="white", linewidth=.5, label=k)
    left += piv[k].to_numpy()
for i, sub in enumerate(sub_order):
    a = piv.loc[sub, "未经批准占用"]
    b = piv.loc[sub, "未载明具体方式"]
    ax2.text(a / 2, i, f"{a*100:.0f}%", ha="center", va="center", fontsize=5.9, color="white", weight="bold")
    ax2.text(1 - b / 2, i, f"{b*100:.0f}%", ha="center", va="center", fontsize=5.9, color="#48565f")
ax2.set(yticks=yb, yticklabels=sub_order, ylim=(len(yb)-.45, -.55), xlim=(0, 1))
ax2.xaxis.set_major_formatter(lambda v, p: f"{v*100:.0f}%")
ax2.tick_params(axis="y", length=0, labelsize=6.0)
ax2.tick_params(axis="x", labelsize=6.0)
ax2.grid(axis="x", color="#e7edf1", lw=.5)
ax2.set_axisbelow(True)
ax2.set_xlabel("主体内构成", fontsize=6.3, labelpad=1)
ax2.set_title("B  分主体的行为方式构成", fontsize=6.9, weight="bold", loc="left", pad=6, color=INK)

header(fig, "非法占用土地的行为方式构成：以未经批准占用为绝对主体",
       f"非法占地处罚 {total:,} 项；情节可识别 {total-int(r.loc['未载明具体方式','处罚数']):,} 项"
       f"（{(1-r.loc['未载明具体方式','占非法占地比例'])*100:.1f}%），未载明具体方式 {int(r.loc['未载明具体方式','处罚数']):,} 项",
       ["行为方式仅描述占地的批准状态，不含主体类型与违法后用途，避免维度混用。",
        "骗取批准：全部记录均无以欺骗手段骗取批准的明确事实记载；“未经批准或者采取欺骗手段骗取批准”属法条选择性表述，不计为行为类型。",
        "未载明具体方式指公开记录仅记“非法占地/非法占用土地”及处罚依据，未记批准状态与占地情节。"])
save(fig, "图2_非法占用土地的行为方式构成")
print(piv.round(3).to_string())
