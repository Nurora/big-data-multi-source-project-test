# -*- coding: utf-8 -*-
"""分析 1 · 申请时间间隔：按处罚义务比较“处罚决定日→实际申请日”（图6 底层表）。

输入：data/integrated/01_申请事件与间隔.csv（3,393 个申请事件，含日期证据与精度）
输出：
  output/tables/01_图6_五组时间分布.csv   图6 的底层统计表（五组 × 三个时间段）
  output/tables/02_图6_描述统计.csv 全体与分组的间隔描述统计
  output/tables/03_图6_日期可得性.csv         处罚日/申请日的精度构成
口径：
  事件 = 一个案号下的一次申请（3,393 个）；
  仅当“处罚至申请状态=可计算”（处罚日与申请日均精确到日）才进入分布；
  同一事件可同时计入多个义务组（处罚决定往往同时包含多项义务），因此五组人数之和大于事件数。
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from paths import INTEGRATED, TABLES  # noqa: E402

EVIDENCE = INTEGRATED
OUT = TABLES

TIMING = EVIDENCE / "01_申请事件与间隔.csv"

# 图6 的五组义务及措施标签别名（与报告图6一致）
GROUPS = [
    ("拆除", {"拆除", "限期拆除"}),
    ("恢复原状／复垦", {"恢复原状", "恢复原状/复垦"}),
    ("罚款", {"罚款"}),
    ("退还土地", {"退还土地", "责令退还土地"}),
    ("没收", {"没收", "没收建筑物/设施"}),
]
BANDS = ["180天内", "181–270天", "271天及以上"]


def band(days):
    return "180天内" if days <= 180 else "181–270天" if days <= 270 else "271天及以上"


def main():
    events = pd.read_csv(TIMING, keep_default_na=False, low_memory=False)
    assert len(events) == 3393, len(events)
    valid = events.loc[events["处罚至申请状态"].eq("可计算")].copy()
    valid["处罚至申请天"] = valid["处罚至申请天"].astype(int)
    assert len(valid) > 1000

    counts = {label: Counter() for label, _ in GROUPS}
    for _, row in valid.iterrows():
        tags = {t for t in str(row["处罚措施标签"]).replace("；", "、").replace(";", "、")
                .replace(",", "、").split("、") if t}
        for label, aliases in GROUPS:
            if tags & aliases:
                counts[label][band(row["处罚至申请天"])] += 1

    rows = []
    for label, _ in GROUPS:
        c = counts[label]
        n = sum(c[b] for b in BANDS)
        rows.append({"义务组": label, **{f"{b}件数": c[b] for b in BANDS},
                     "有效n": n, **{f"{b}占比": (c[b] / n if n else np.nan) for b in BANDS}})
    table = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT / "01_图6_五组时间分布.csv", index=False, encoding="utf-8-sig")

    def describe(values):
        v = pd.Series(values).dropna()
        return {"有效n": int(len(v)), "最小": int(v.min()), "P25": float(v.quantile(.25)),
                "中位数": float(v.median()), "平均": round(float(v.mean()), 2),
                "P75": float(v.quantile(.75)), "最大": int(v.max()),
                "180天内占比": float((v <= 180).mean()), "270天内占比": float((v <= 270).mean())}

    stats = [{"分组": "全体事件", **describe(valid["处罚至申请天"])}]
    for label, _ in GROUPS:
        tags = {t for t in valid["处罚措施标签"].astype(str)}
        mask = valid["处罚措施标签"].map(
            lambda s: bool({t for t in str(s).replace("；", "、").replace(";", "、")
                            .replace(",", "、").split("、") if t} & dict(GROUPS)[label]))
        stats.append({"分组": label, **describe(valid.loc[mask, "处罚至申请天"])})
    pd.DataFrame(stats).to_csv(OUT / "02_图6_描述统计.csv", index=False, encoding="utf-8-sig")

    date_quality = []
    for node in ("处罚", "申请", "裁判"):
        col = f"{node}精度"
        c = Counter(valid[col].astype(str)) if col in valid else Counter()
        date_quality.append({"节点": node, "事件数": len(valid), "精确到日": c.get("日", 0),
                             "仅到月": c.get("月", 0), "仅到年": c.get("年", 0),
                             "缺失或冲突": len(valid) - sum(c.get(k, 0) for k in ("日", "月", "年"))})
    pd.DataFrame(date_quality).to_csv(OUT / "03_图6_日期可得性.csv", index=False, encoding="utf-8-sig")

    summary = {"事件总数": int(len(events)), "可计算间隔事件": int(len(valid)),
               "五组有效n": {r["义务组"]: int(r["有效n"]) for r in rows},
               "180天内占比": {r["义务组"]: round(float(r["180天内占比"]), 4) for r in rows}}
    (Path(OUT).parent / "01_时间统计核验.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
