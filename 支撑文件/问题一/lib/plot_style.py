# -*- coding: utf-8 -*-
"""图8、图9 的绘图样式：中文字体、配色与导出设置。"""
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402,F401

font_path = Path(os.environ.get("Q2_CJK_FONT", "C:/Windows/Fonts/msyh.ttc"))
if font_path.exists():
    font_manager.fontManager.addfont(font_path)
    font = font_manager.FontProperties(fname=font_path).get_name()
else:
    font = "Noto Sans CJK SC"
plt.rcParams.update({"font.family": font, "font.size": 11, "axes.unicode_minus": False,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": "white", "axes.facecolor": "white",
                     "pdf.fonttype": 42, "text.color": "#142d43",
                     "axes.labelcolor": "#142d43", "xtick.color": "#364e60",
                     "ytick.color": "#364e60", "axes.edgecolor": "#a2b3bf"})

INK = "#142d43"
TEAL = "#067c76"
BLUE = "#4067a1"
ORANGE = "#a95028"
GRAY = "#546b7b"
