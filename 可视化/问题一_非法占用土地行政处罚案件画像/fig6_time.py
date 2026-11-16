# -*- coding: utf-8 -*-
"""绘图 · 图6：不同处罚义务对应的申请时间间隔。

数据来源：output/tables/01_图6_五组时间分布.csv（由 analysis/1_time_stats.py 生成）
输出：output/figures/图6_不同处罚义务对应的申请时间间隔.png
画布与配色沿用报告排版（2512×1016、微软雅黑、深青—浅青—藏青三色）。
"""
import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from paths import FIGURES as FIGDIR, TABLES  # noqa: E402

TABLE = TABLES / "01_图6_五组时间分布.csv"

BANDS = [("180天内", "#126868", "#ffffff"),
         ("181–270天", "#b9d4da", "#183041"),
         ("271天及以上", "#244b70", "#ffffff")]
FONT = "C:/Windows/Fonts/msyh.ttc"


def main():
    with TABLE.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    groups = [(r["义务组"], {b: int(r[f"{b}件数"]) for b, _, _ in BANDS},
               int(r["有效n"])) for r in rows]
    assert groups and all(n > 0 for _, _, n in groups)

    canvas = Image.new("RGB", (2512, 1016), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, size=50)
    ink, sub = "#192d3a", "#425c6b"

    def box(x1, y1, x2, y2, fill):
        draw.rectangle((round(2 * x1), round(2 * y1), round(2 * x2) - 1, round(2 * y2) - 1), fill=fill)

    def text(x, y, label, fill=ink, anchor="mm"):
        draw.text((round(2 * x), round(2 * y)), label, font=font, fill=fill, anchor=anchor)

    left, right = 302, 1204
    for x, (band, color, _) in zip((302, 511, 749), BANDS):
        box(x, 24, x + 50, 43, color)
        text(x + 69, 34, band, anchor="lm")
    for idx, (name, hits, n) in enumerate(groups):
        y = 104 + idx * 78
        text(left - 16, y, name, anchor="rm")
        x = left
        for j, (band, fill, foreground) in enumerate(BANDS):
            width = (right - left) * hits[band] / n
            box(x, y - 22, x + width, y + 22, fill)
            if j:
                box(x, y - 22, x + 1.3, y + 22, "white")
            label = f"{hits[band] / n:.1%}"
            if j == 0:
                label += f"（{hits[band]}/{n}）"
            text(x + width / 2, y, label, foreground)
            x += width
        assert abs(x - right) < 1e-7
    for p in range(0, 101, 25):
        text(left + (right - left) * p / 100, 460, f"{p}%", sub)

    FIGDIR.mkdir(parents=True, exist_ok=True)
    out = FIGDIR / "图6_不同处罚义务对应的申请时间间隔.png"
    canvas.save(out, dpi=(430, 430), optimize=True)
    print(out)


if __name__ == "__main__":
    main()
