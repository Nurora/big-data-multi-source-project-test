# -*- coding: utf-8 -*-
"""绘图 · 图8：主要处罚义务及常见共现组合。

数据来源（由 processing/2_build_transactions.py 与 analysis/3_obligation_stats.py 生成）：
  output/tables/义务频数.csv          七类义务的频数与占比（分母 2,967 项可识别义务处罚）
  output/tables/处罚义务组合排名.csv  两两与三项组合的频数与排名
输出：output/figures/图8_主要处罚义务及常见共现组合.png
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from plot_style import BLUE, GRAY, INK, ORANGE, TEAL, PercentFormatter, plt  # noqa: E402
from paths import FIGURES as FIGDIR, TABLES  # noqa: E402
SHORT = {"拆除建筑物或设施": "拆除", "恢复土地原状": "恢复原状"}
ORDER = ["拆除建筑物或设施", "恢复土地原状", "退还土地", "罚款"]


def data(name):
    return pd.read_csv(TABLES / (name + ".csv"))


def short(label):
    return "＋".join(SHORT.get(item, item) for item in label.split("＋"))


def main():
    freq = data("义务频数").sort_values("频数", ascending=False)
    combinations = data("处罚义务组合排名")
    pair = combinations.loc[combinations["组合类型"].eq("2项")].head(3)
    triple = combinations.loc[combinations["组合类型"].eq("3项")].head(2)
    fig, ax = plt.subplots(figsize=(10.4, 4.75))
    fig.subplots_adjust(left=.39, right=.965, top=.92, bottom=.14)
    ax.set(xlim=(0, 1), ylim=(12.6, -.8), yticks=[], xticks=np.arange(0, 1.01, .25),
           xlabel="占可识别义务处罚的比例")
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.spines["left"].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#dbe5eb")
    rows = [("单项义务", freq, "义务", list(range(7)), TEAL, False),
            ("常见共现与组合", pd.concat([pair, triple]), "组合", list(range(8, 13)), BLUE, True)]
    for title, frame, label, ticks, color, is_combo in rows:
        ax.text(-.66, min(ticks) - .62, title, transform=ax.get_yaxis_transform(),
                weight="bold", color=INK, fontsize=12, clip_on=False)
        for y, (_, row) in zip(ticks, frame.iterrows()):
            fill = ORANGE if is_combo and y == 11 else color
            ax.barh(y, row["占比"], color=fill, height=.59)
            text = short(row[label]) if is_combo else row[label]
            ax.text(-.66, y, text, transform=ax.get_yaxis_transform(),
                    va="center", fontsize=11, clip_on=False)
            ax.text(row["占比"] + .017, y, f"{row['占比']:.1%} · {row['频数']:,}",
                    va="center", fontsize=10.4)
    FIGDIR.mkdir(parents=True, exist_ok=True)
    out = FIGDIR / "图8_主要处罚义务及常见共现组合.png"
    fig.savefig(out, dpi=260, facecolor="white")
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
