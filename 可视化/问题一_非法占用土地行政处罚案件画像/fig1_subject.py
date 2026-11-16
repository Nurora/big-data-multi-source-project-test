# -*- coding: utf-8 -*-
"""绘图 · 图1：非法占用土地处罚的违法主体结构与确认司法关联样本。

数据来源：output/tables/04_图1_主体结构与司法关联.csv（由 analysis/5_profile_tables.py 生成）
输出：output/figures/图1_非法占用土地处罚的违法主体结构与确认司法关联样本.png
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from plot_style_report import GRAY, GRAY_L, INK, ORANGE, TEAL, header, pct, save

from paths import TABLES as T
d = pd.read_csv(T / "04_图1_主体结构与司法关联.csv")
SUB = ["自然人", "企业", "村委会/集体经济组织", "其他组织", "事业单位/政府机构"]
d = d.set_index("主体").loc[SUB]

fig = plt.figure(figsize=(6.000, 3.203))
ax1 = fig.add_axes([.178, .255, .355, .545])
ax2 = fig.add_axes([.625, .255, .205, .545])

y = np.arange(len(SUB))
h = .34
ax1.barh(y - h/2, d["处罚构成"], height=h, color=GRAY_L, edgecolor="none", label="全部非法占地处罚")
ax1.barh(y + h/2, d["确认样本构成"], height=h, color=TEAL, edgecolor="none", label="确认司法关联样本")
for i, (a, b) in enumerate(zip(d["处罚构成"], d["确认样本构成"])):
    ax1.text(a + .012, i - h/2, pct(a), va="center", fontsize=6.0, color="#5c6b76")
    ax1.text(b + .012, i + h/2, pct(b), va="center", fontsize=6.0, color=TEAL, weight="bold")
ax1.set(yticks=y, yticklabels=SUB, ylim=(len(y)-.45, -.55), xlim=(0, 1.02))
ax1.xaxis.set_major_formatter(lambda v, p: f"{v*100:.0f}%")
ax1.grid(axis="x", color="#e7edf1", lw=.5)
ax1.set_axisbelow(True)
ax1.tick_params(axis="y", length=0, labelsize=6.6)
ax1.tick_params(axis="x", labelsize=6.1)
ax1.set_xlabel("占本组处罚项的比例", fontsize=6.3, labelpad=1)
ax1.set_title("A  主体构成：全部处罚（灰）与确认关联样本（绿）", fontsize=7.2, weight="bold", loc="left", pad=6, color=INK)

orv = d["MH_OR"].to_numpy()
lo = d["CI下限_y"].to_numpy()
hi = d["CI上限_y"].to_numpy()
colors = [TEAL if v > 1 else ORANGE for v in orv]
ax2.hlines(y, lo, hi, color=colors, lw=1.0, alpha=.7)
ax2.scatter(orv, y, s=18, color=colors, zorder=3, edgecolor="white", linewidth=.5)
ax2.axvline(1, color="#7d8b95", lw=.7, ls=(0, (3, 2)))
ax2.set_xscale("log")
ax2.set(yticks=y, yticklabels=[], ylim=(len(y)-.45, -.55))
ax2.set_xlim(.15, 5.0)
ax2.set_xticks([.25, .5, 1, 2, 4])
ax2.set_xticklabels(["0.25", "0.5", "1", "2", "4"], fontsize=6.0)
ax2.xaxis.set_minor_formatter(plt.NullFormatter())
ax2.grid(axis="x", color="#e7edf1", lw=.5)
ax2.set_axisbelow(True)
ax2.tick_params(axis="y", length=0)
ax2.tick_params(axis="x", which="minor", length=0)
ax2.set_xlabel("同一时期、地市内的 MH 共同 OR", fontsize=6.2, labelpad=1)
ax2.set_title("B  控制时期与地市后的主体关联", fontsize=7.2, weight="bold", loc="left", pad=6, color=INK)
for i, (o, l, h2) in enumerate(zip(orv, lo, hi)):
    ax2.text(1.04, i, f"{o:.2f} [{l:.2f}, {h2:.2f}]", transform=ax2.get_yaxis_transform(),
             ha="left", va="center", fontsize=5.6, color=INK if o > 1 else "#8a5a2b", clip_on=False)

n = int(d["处罚数"].sum())
k = int(d["确认关联数"].sum())
header(fig, "非法占用土地处罚的违法主体结构与确认司法关联样本",
       f"仅保留非法占用土地处罚（n={n:,}）；其中确认司法关联 {k:,} 项，占 {k/n:.1%}",
       ["主体按处罚决定记载的相对人类型划分；确认关联比例的分母为该主体全部非法占地处罚。",
        f"标准化与 OR 使用时期×地市共同层（两组各≥5 项），共 {int(d['层数'].iloc[0])} 层、{int(d['共同层样本'].iloc[0]):,} 项；BH 校正后各主体 CMH p<0.001。",
        "未确认司法关联不等于未进入司法程序，受裁判文书公开与采集范围影响。"])
save(fig, "图1_非法占用土地处罚的违法主体结构与确认司法关联样本")
