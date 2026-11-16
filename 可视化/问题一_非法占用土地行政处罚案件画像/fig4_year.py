# -*- coding: utf-8 -*-
"""绘图 · 图4：非法占用土地处罚的年度分布与确认司法关联比例。

数据来源：08_图4_年度分布.csv、02_非法占地处罚底表.csv（年份来源）
输出：output/figures/图4_非法占用土地处罚的年度分布与确认司法关联比例.png
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from plot_style_report import GRAY, GRAY_L, INK, ORANGE, TEAL, header, save

from paths import TABLES as T
d = pd.read_csv(T / "08_图4_年度分布.csv")
base = pd.read_csv(T / "02_非法占地处罚底表.csv", usecols=["年份来源"], low_memory=False)
doc_year = int(base["年份来源"].eq("处罚文号").sum())
known = d.dropna(subset=["年度"]).copy()
known["年度"] = known["年度"].astype(int)
missing = int(d.loc[d["年度"].isna(), "处罚数"].sum())
known = known[known["年度"] >= 2013].sort_values("年度")

fig = plt.figure(figsize=(6.000, 2.635))
ax1 = fig.add_axes([.085, .335, .575, .45])
ax2 = fig.add_axes([.715, .335, .255, .45])

x = np.arange(len(known))
ax1.bar(x, known["确认关联"], width=.62, color=TEAL, label="确认司法关联")
ax1.bar(x, known["未确认"], bottom=known["确认关联"], width=.62, color=GRAY_L, label="未确认司法关联")
ax1.set_xticks(x)
ax1.set_xticklabels(known["年度"].astype(str), fontsize=5.6, rotation=45, ha="right")
ax1.set_ylim(0, known["处罚数"].max() * 1.10)
ax1.tick_params(axis="y", labelsize=6.0)
ax1.tick_params(axis="x", length=0)
ax1.grid(axis="y", color="#e7edf1", lw=.5)
ax1.set_axisbelow(True)
ax1.set_ylabel("处罚数（项）", fontsize=6.2, labelpad=2)
ax1.legend(loc="upper right", frameon=False, fontsize=5.8, handlelength=1.0, handletextpad=.35,
           borderaxespad=.2, labelspacing=.25)
ax1.set_title("A  处罚数量：确认关联与未确认部分", fontsize=7.0, weight="bold", loc="left", pad=5, color=INK)
peak = known.loc[known["处罚数"].idxmax()]
ax1.annotate(f"{int(peak['处罚数']):,}", xy=(int(np.where(known['年度'].eq(peak['年度']))[0][0]), peak["处罚数"]),
             xytext=(0, 3), textcoords="offset points", ha="center", fontsize=5.8, color="#5c6b76")

ax2.fill_between(x, known["CI下限"], known["CI上限"], color=ORANGE, alpha=.14, lw=0)
ax2.plot(x, known["确认关联比例"], color=ORANGE, lw=1.2, marker="o", ms=2.4)
ax2.set_xticks(x)
ax2.set_xticklabels(known["年度"].astype(str), fontsize=5.2, rotation=90)
ax2.set_ylim(0, .90)
ax2.yaxis.set_major_formatter(lambda v, p: f"{v*100:.0f}%")
ax2.tick_params(axis="y", labelsize=6.0)
ax2.tick_params(axis="x", length=0)
ax2.grid(axis="y", color="#e7edf1", lw=.5)
ax2.set_axisbelow(True)
ax2.set_ylabel("确认关联比例", fontsize=6.2, labelpad=2)
ax2.set_title("B  当年确认司法关联比例（95%CI）", fontsize=7.0, weight="bold", loc="left", pad=5, color=INK)
for xi, (_, r) in zip(x, known.iterrows()):
    off = {2014: (0, .04), 2016: (0, .04), 2018: (0, .04), 2019: (0, .05), 2020: (0, -.095)}.get(r["年度"])
    if off:
        ax2.text(xi + off[0], r["确认关联比例"] + off[1], f"{r['确认关联比例']*100:.1f}%", ha="center",
                 fontsize=5.4, color="#8a4b16")

header(fig, "非法占用土地处罚的年度分布：2019 年为记录高峰，2019 年后确认关联比例快速下降",
       f"2013–2025 年共 {int(known['处罚数'].sum()):,} 项；其中 {doc_year:,} 项年份取自处罚文号，缺失 {missing} 项",
       ["比例分母为当年非法占用土地处罚数；阴影为 Wilson 95% 置信区间；文号年份与已知处罚年份 99.5% 一致或相差一年。",
        "2019 年后确认关联比例快速下降，主要与裁判文书公开及采集截止时点有关，不能解释为违法发生或申请强制执行的下降。"])
save(fig, "图4_非法占用土地处罚的年度分布与确认司法关联比例")
print(known[["年度", "处罚数", "确认关联", "确认关联比例"]].to_string(index=False))
