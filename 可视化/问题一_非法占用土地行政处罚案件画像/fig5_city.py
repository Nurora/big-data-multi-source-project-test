# -*- coding: utf-8 -*-
"""绘图 · 图5：非法占用土地处罚的地市分布与确认司法关联比例。

数据来源：09_图5_地市分布.csv
输出：output/figures/图5_非法占用土地处罚的地市分布与确认司法关联比例.png
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from plot_style_report import GRAY, GRAY_L, INK, ORANGE, TEAL, header, save

from paths import TABLES as T
d = pd.read_csv(T / "09_图5_地市分布.csv").sort_values("处罚数", ascending=True).reset_index(drop=True)

fig = plt.figure(figsize=(6.000, 3.932))
ax1 = fig.add_axes([.105, .255, .40, .585])
ax2 = fig.add_axes([.605, .255, .27, .585])

y = np.arange(len(d))
ax1.barh(y, d["确认关联"], height=.66, color=TEAL, label="确认司法关联")
ax1.barh(y, d["未确认"], left=d["确认关联"], height=.66, color=GRAY_L, label="未确认司法关联")
for i, r in d.iterrows():
    ax1.text(r["处罚数"] + 60, i, f"{int(r['处罚数']):,}", va="center", fontsize=5.6, color="#5c6b76")
ax1.set(yticks=y, yticklabels=d["违法地市"], ylim=(-.6, len(d) - .4), xlim=(0, d["处罚数"].max() * 1.18))
ax1.tick_params(axis="y", length=0, labelsize=6.2)
ax1.tick_params(axis="x", labelsize=5.8)
ax1.grid(axis="x", color="#e7edf1", lw=.5)
ax1.set_axisbelow(True)
ax1.set_xlabel("非法占用土地处罚数（项）", fontsize=6.2, labelpad=1)
ax1.set_title("A  处罚数量（深色为确认关联）", fontsize=7.0, weight="bold", loc="left", pad=5, color=INK)


ax2.hlines(y, d["CI下限"], d["CI上限"], color="#b9a08c", lw=.9, alpha=.85)
colors = [ORANGE if n >= 200 else "#c9a58a" for n in d["处罚数"]]
ax2.scatter(d["确认关联比例"], y, s=15, color=colors, zorder=3, edgecolor="white", linewidth=.4)
median_n = 200
ax2.axvline(d["确认关联"].sum() / d["处罚数"].sum(), color="#7d8b95", lw=.7, ls=(0, (3, 2)))
ax2.text(d["确认关联"].sum() / d["处罚数"].sum() + .015, -.52, "全省 16.1%",
         fontsize=5.4, color="#6b7a85", va="bottom")
ax2.set(yticks=y, yticklabels=[], ylim=(-.75, len(d) - .4), xlim=(0, 1.02))
ax2.xaxis.set_major_formatter(lambda v, p: f"{v*100:.0f}%")
ax2.tick_params(axis="y", length=0)
ax2.tick_params(axis="x", labelsize=5.8)
ax2.grid(axis="x", color="#e7edf1", lw=.5)
ax2.set_axisbelow(True)
ax2.set_xlabel("确认司法关联比例（95%CI）", fontsize=6.2, labelpad=1)
ax2.set_title("B  确认关联比例", fontsize=7.0, weight="bold", loc="left", pad=5, color=INK)
for i, r in d.iterrows():
    if r["违法地市"] in ("惠州市", "佛山市", "梅州市", "韶关市"):
        ax2.text(min(r["CI上限"] + .018, .95), i, f"{r['确认关联比例']*100:.1f}%", va="center",
                 fontsize=5.2, color="#8a4b16")

header(fig, "非法占用土地处罚的地市分布：数量集中于珠三角，确认关联比例受文书覆盖影响",
       f"共 {int(d['处罚数'].sum()):,} 项处罚、21 个地市；确认关联 {int(d['确认关联'].sum()):,} 项",
       ["比例分母为该市全部非法占用土地处罚；误差线为 Wilson 95% 置信区间。",
        "浅色点为处罚量不足 200 项的地市，比例波动大。确认关联比例取决于裁判文书公开与采集覆盖，不能解释为真实司法申请率或执法效率。"])
save(fig, "图5_非法占用土地处罚的地市分布与确认司法关联比例")
print(d[["违法地市", "处罚数", "确认关联", "确认关联比例", "CI下限", "CI上限"]].to_string(index=False))
