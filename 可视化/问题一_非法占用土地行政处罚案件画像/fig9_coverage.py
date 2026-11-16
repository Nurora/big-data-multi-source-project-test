# -*- coding: utf-8 -*-
"""绘图 · 图9：处罚义务与申请强制执行事项的对应矩阵及覆盖率。

数据来源（由 analysis/4_coverage_stats.py 生成）：
  output/tables/处罚申请对应矩阵.csv   A 面板：处罚义务 × 申请事项的明确申请比例与分母
  output/tables/事件级覆盖率.csv       B 面板：完整事件级同名覆盖
  output/tables/处罚级覆盖率.csv       B 面板：处罚级同名覆盖
输出：output/figures/图9_处罚义务与申请事项对应矩阵及覆盖率.png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from plot_style import BLUE, GRAY, INK, TEAL, plt  # noqa: E402
from paths import FIGURES as FIGDIR, TABLES  # noqa: E402
SHORT = {"拆除建筑物或设施": "拆除", "恢复土地原状": "恢复原状"}
ORDER = ["拆除建筑物或设施", "恢复土地原状", "退还土地", "罚款"]


def data(name):
    return pd.read_csv(TABLES / (name + ".csv"))


def short(label):
    return SHORT.get(label, label)


def main():
    matrix = data("处罚申请对应矩阵").set_index(["处罚义务", "司法申请事项"])
    counts = [data(k + "级覆盖率").set_index("义务") for k in ["事件", "处罚"]]
    fig, (ax, side) = plt.subplots(1, 2, figsize=(10.4, 4.25),
                                   gridspec_kw={"width_ratios": [1.16, 1]})
    fig.subplots_adjust(left=.145, right=.98, bottom=.10, top=.74, wspace=.18)
    shares = np.array([[matrix.loc[(p, a), "明确申请比例"] for a in ORDER] for p in ORDER])
    heat = LinearSegmentedColormap.from_list("q2", ["#f1f7f8", "#0a6663"])
    ax.imshow(shares, cmap=heat, vmin=0, vmax=1, aspect="auto")
    for i, p in enumerate(ORDER):
        for j, a in enumerate(ORDER):
            r = matrix.loc[(p, a)]
            hue = "white" if shares[i, j] > .6 else INK
            ax.add_patch(Rectangle((j - .5, i - .5), 1, 1, fill=False,
                                   ec=BLUE if i == j else "white", lw=1.3 if i == j else 1))
            ax.text(j, i, f"{r['明确申请比例']:.1%}\n{int(r['明确申请数'])}/{int(r['有效分母'])}",
                    ha="center", va="center", fontsize=10.5, color=hue)
    ax.set(xticks=range(4), yticks=range(4), xticklabels=[short(x) for x in ORDER],
           yticklabels=[short(x) for x in ORDER], ylabel="处罚义务")
    ax.xaxis.tick_top()
    ax.tick_params(length=0, pad=5, labelsize=9)
    fig.text(.057, .94, "A  处罚义务与申请事项", fontsize=13, weight="bold", color=INK)
    fig.text(.55, .94, "B  同名事项申请覆盖率", fontsize=13, weight="bold", color=INK)
    ax.text(.5, 1.17, "申请事项", transform=ax.transAxes, ha="center", color=GRAY, fontsize=10)
    side.set(xlim=(0, 1), ylim=(-.5, 3.5))
    side.invert_yaxis()
    side.axis("off")
    for i, p in enumerate(ORDER):
        side.add_patch(Rectangle((0, i - .43), 1, .86,
                                 color="#e8f2f3" if i % 2 == 0 else "#f2f5f7", lw=0))
        side.text(.035, i, short(p), va="center", fontsize=10)
        for table, x, col in zip(counts, (.54, .83), (TEAL, BLUE)):
            r = table.loc[p]
            side.text(x, i - .10, f"{r['覆盖率']:.1%}", ha="center", va="center",
                      color=col, weight="bold", fontsize=12)
            side.text(x, i + .19, f"{int(r['分子'])}/{int(r['分母'])}", ha="center",
                      va="center", color=GRAY, fontsize=9)
    for x, label, col in zip((.54, .83), ("完整事件级", "处罚级"), (TEAL, BLUE)):
        side.text(x, -.70, label, ha="center", color=col, fontsize=10)
    FIGDIR.mkdir(parents=True, exist_ok=True)
    out = FIGDIR / "图9_处罚义务与申请事项对应矩阵及覆盖率.png"
    fig.savefig(out, dpi=260, facecolor="white")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
