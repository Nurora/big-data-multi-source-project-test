# -*- coding: utf-8 -*-
"""图1—图5 的统一版式：标题、副标题、脚注与导出。"""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import PercentFormatter
import matplotlib.pyplot as plt

FONT = Path(os.environ.get("Q2_CJK_FONT", "C:/Windows/Fonts/msyh.ttc"))
if FONT.exists():
    font_manager.fontManager.addfont(FONT)
    FAMILY = font_manager.FontProperties(fname=FONT).get_name()
else:
    FAMILY = "Noto Sans CJK SC"

plt.rcParams.update({
    "font.family": FAMILY, "font.size": 7.4, "axes.unicode_minus": False,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
    "pdf.fonttype": 42, "text.color": "#1b2b38", "axes.labelcolor": "#1b2b38",
    "xtick.color": "#40525f", "ytick.color": "#40525f", "axes.edgecolor": "#b9c6cf",
    "axes.linewidth": .6, "xtick.major.width": .6, "ytick.major.width": .6,
})

INK = "#1b2b38"
TEAL = "#0d6b63"
TEAL_L = "#7fb3ac"
BLUE = "#3c6e9f"
BLUE_L = "#a8c2d8"
ORANGE = "#b5651d"
GRAY = "#8d9ba6"
GRAY_L = "#d8dfe4"
NAVY = "#213b52"
SAND = "#c9a227"

from paths import FIGURES as FIG  # noqa: E402


def canvas(w=7.4, h=3.35):
    fig, ax = plt.subplots(figsize=(w, h))
    return fig, ax


def header(fig, title, subtitle, notes, source="数据来源：广东省土地违法行政处罚数据、确认关联表及裁判原文。"):
    fig.text(.012, .975, title, fontsize=9.6, weight="bold", va="top", color=INK)
    fig.text(.012, .905, subtitle, fontsize=6.4, va="top", color="#54636e")
    fig.text(.012, .012, "\n".join([*notes, source]), fontsize=5.5, va="bottom", color="#6b7a85", linespacing=1.5)


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=400 if ext == "png" else 300, facecolor="white")
    plt.close(fig)


def pct(v, digits=1):
    return f"{v*100:.{digits}f}%"
