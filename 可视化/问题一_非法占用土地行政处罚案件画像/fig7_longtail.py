# -*- coding: utf-8 -*-
"""绘图 · 图7：不同处罚义务对应申请时间的长尾结构。

数据来源：output/tables/04_图7_四区间分布.csv（由 analysis/2_longtail_stats.py 生成）
输出：output/figures/图7_不同处罚义务对应申请时间的长尾结构.png

版式沿用图6（同为 2512 宽、微软雅黑、同一组深青—浅青—藏青配色），
仅把三个时间段细分为四个区间，并在条形上方补充 366 天以上区间的标注，
以免 0.1%–0.3% 的窄段无法在条形内部显示数字。
"""
import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from paths import FIGURES as FIGDIR, TABLES  # noqa: E402

TABLE = TABLES / "04_图7_四区间分布.csv"

BANDS = [("180天内", "#126868", "#ffffff"),
         ("181–365天", "#5c9299", "#ffffff"),
         ("366–730天", "#b9d4da", "#192d3a"),
         ("731天及以上", "#244b70", "#ffffff")]
# 条形上方窄段标注的文字色（取同色系加深，便于与色块对应）
NOTE_COLOR = {"366–730天": "#4d7f86", "731天及以上": "#244b70"}
FONT = "C:/Windows/Fonts/msyh.ttc"

W, H = 2512, 1160
LEFT, RIGHT = 604, 2408          # 条形的 0% 与 100%
PITCH, ROW0, HALF = 176, 268, 44  # 行距、首行中心、条半高
INK, SUB = "#192d3a", "#425c6b"


def main():
    with TABLE.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    groups = [(r["义务组"].replace("／", " / "),
               {b: int(r[f"{b}件数"]) for b, _, _ in BANDS}, int(r["有效n"])) for r in rows]
    assert len(groups) == 5 and all(n > 0 for _, _, n in groups)

    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)
    f_label = ImageFont.truetype(FONT, 50)
    f_tick = ImageFont.truetype(FONT, 50)
    f_note = ImageFont.truetype(FONT, 42)

    # ---- 图例（四色块 + 文字，整体居中）----
    widths = [50 + 12 + draw.textlength(b, font=f_label) for b, _, _ in BANDS]
    gap = 78
    x = (W - (sum(widths) + gap * (len(BANDS) - 1))) / 2
    for (band, color, _), width in zip(BANDS, widths):
        draw.rectangle((x, 46, x + 50, 84), fill=color)
        draw.text((x + 62, 65), band, font=f_label, fill=INK, anchor="lm")
        x += width + gap

    # ---- 条形 ----
    for idx, (name, hits, n) in enumerate(groups):
        y = ROW0 + idx * PITCH
        draw.text((LEFT - 28, y), name, font=f_label, fill=INK, anchor="rm")
        x = LEFT
        inside = []
        for j, (band, fill, foreground) in enumerate(BANDS):
            width = (RIGHT - LEFT) * hits[band] / n
            if hits[band]:
                draw.rectangle((x, y - HALF, x + max(width - 1, 1), y + HALF - 1), fill=fill)
            if j and hits[band]:
                draw.rectangle((x, y - HALF, x + 2, y + HALF - 1), fill="white")
            label = f"{hits[band] / n:.1%}"
            fits = width >= draw.textlength(label, font=f_label) + 26
            if j == 0:
                label += f"（{hits[band]}/{n}）"
                fits = width >= draw.textlength(label, font=f_label) + 26
            if fits:
                draw.text((x + width / 2, y), label, font=f_label, fill=foreground, anchor="mm")
            else:
                inside.append((band, label, x, width))
            x += width
        assert abs(x - RIGHT) < 1e-6

        # 条形上方标注：条形内部放不下的窄段，按右端对齐、从右向左排列
        # （与条形自左向右的排列一致，最右的“731天及以上”贴着 100% 端）
        if inside:
            pieces, total = [], 0
            for band, label, _, _ in inside:
                text = f"{band} {label}"
                width = draw.textlength(text, font=f_note)
                pieces.append((text, NOTE_COLOR.get(band, SUB), width))
                total += width
            total += 34 * (len(pieces) - 1)
            x = RIGHT - total
            for text, color, width in pieces:
                draw.text((x, y - HALF - 30), text, font=f_note, fill=color, anchor="ls")
                x += width + 34

    # ---- 横轴刻度 ----
    for p in range(0, 101, 25):
        draw.text((LEFT + (RIGHT - LEFT) * p / 100, 1064), f"{p}%", font=f_tick,
                  fill=SUB, anchor="mm")

    FIGDIR.mkdir(parents=True, exist_ok=True)
    out = FIGDIR / "图7_不同处罚义务对应申请时间的长尾结构.png"
    canvas.save(out, dpi=(430, 430), optimize=True)
    print(out)


if __name__ == "__main__":
    main()
