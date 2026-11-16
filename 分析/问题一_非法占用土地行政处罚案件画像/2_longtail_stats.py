# -*- coding: utf-8 -*-
"""分析 2 · 申请时间长尾：按四区间重新划段，统计五类义务的时间分布（图7 底层表）。

与 01_time_stats.py（图6）保持同一事件口径，但**不拆分图6的统计结果**：
直接从证据台账的原始日期（处罚日、申请日）重新计算间隔，再按
180天内 / 181–365天 / 366–730天 / 731天及以上 四个区间重新汇总。

输入：data/integrated/01_申请事件与间隔.csv（3,393 个申请事件）
输出（output/tables）：
  04_图7_四区间分布.csv       图7 的底层统计表（五组 × 四个区间）
  05_图7_描述统计.csv         全体与分组的间隔描述统计（含中位数、P75、P90）
  06_图7_法院逾期认定对照.csv     裁定书明确认定“逾期申请”的事件按四区间对照
  07_图7_排除口径.csv             日期不可用事件的逐项排除数量
  08_图7_核验.json            关键断言与核验结果

口径（与图6一致）：
  事件 = 一个案号下的一次申请（3,393 个）；
  仅当处罚日与申请日都精确到日、间隔非负且不存在日期先后冲突时才进入分布；
  同一事件可同时计入多个义务组（处罚决定往往同时包含多项义务），故五组之和大于事件数；
  每个义务组单独计算有效分母 n。
"""
import json
import sys
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from paths import INTEGRATED, TABLES  # noqa: E402

EVIDENCE = INTEGRATED
OUT = TABLES
TIMING = EVIDENCE / "01_申请事件与间隔.csv"
FIG6_TABLE = TABLES / "01_图6_五组时间分布.csv"

GROUPS = [
    ("拆除", {"拆除", "限期拆除"}),
    ("恢复原状／复垦", {"恢复原状", "恢复原状/复垦"}),
    ("罚款", {"罚款"}),
    ("退还土地", {"退还土地", "责令退还土地"}),
    ("没收", {"没收", "没收建筑物/设施"}),
]
BANDS = ["180天内", "181–365天", "366–730天", "731天及以上"]


def band(days):
    if days <= 180:
        return "180天内"
    if days <= 365:
        return "181–365天"
    if days <= 730:
        return "366–730天"
    return "731天及以上"


def tags_of(value):
    return {t for t in str(value).replace("；", "、").replace(";", "、")
            .replace(",", "、").split("、") if t}


def round_half_up(value, decimals=1):
    """按“四舍五入”取整（避免 Python 内置 round 的银行家舍入）。"""
    quant = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))


def main():
    events = pd.read_csv(TIMING, keep_default_na=False, low_memory=False)
    assert len(events) == 3393, len(events)

    # ---- 1. 用原始日期重新计算间隔（不依赖台账中已算好的 处罚至申请天）----
    events["处罚日_解析"] = pd.to_datetime(events["处罚日"], format="%Y-%m-%d", errors="coerce")
    events["申请日_解析"] = pd.to_datetime(events["申请日"], format="%Y-%m-%d", errors="coerce")
    events["日期可计算"] = (events["处罚日"].str.len() == 10) & (events["申请日"].str.len() == 10) \
        & events["处罚日_解析"].notna() & events["申请日_解析"].notna()
    events["间隔天_重算"] = (events["申请日_解析"] - events["处罚日_解析"]).dt.days
    events["间隔为负"] = events["日期可计算"] & (events["间隔天_重算"] < 0)

    # 与原清洗规则一致：日期倒置及裁定书日期冲突的事件不进入分布
    valid = events["日期可计算"] & ~events["间隔为负"] \
        & events["处罚至申请状态"].ne("日期先后冲突")
    cal = events.loc[valid].copy()
    cal["间隔天"] = cal["间隔天_重算"].astype(int)
    cal["区间"] = cal["间隔天"].map(band)

    # 重算结果必须与台账已算好的间隔完全一致（事件级逐一核对）
    assert len(cal) == 1174, len(cal)
    recorded = events.loc[valid, "处罚至申请天"].astype(int)
    assert (recorded.values == cal["间隔天"].values).all()
    assert cal["间隔天"].min() >= 0
    assert cal["处罚日"].str.len().eq(10).all() and cal["申请日"].str.len().eq(10).all()

    # ---- 2. 排除口径（逐项记录，供报告与核验使用）----
    only_apply_missing = (~events["日期可计算"]) & (events["处罚日"].str.len() == 10)
    only_penalty_missing = (~events["日期可计算"]) & (events["申请日"].str.len() == 10)
    both_missing = (events["处罚日"].str.len() != 10) & (events["申请日"].str.len() != 10)
    exclusion = pd.DataFrame([
        {"排除项": "仅处罚决定日不可用（未载明或未定位）", "事件数": int(only_penalty_missing.sum())},
        {"排除项": "仅实际申请日不可用（未载明或未定位）", "事件数": int(only_apply_missing.sum())},
        {"排除项": "两个日期均不可用", "事件数": int(both_missing.sum())},
        {"排除项": "日期倒置（申请日早于处罚决定日）", "事件数": int(events["间隔为负"].sum())},
    ])
    dropped = int(exclusion["事件数"].sum())
    assert dropped + len(cal) == len(events), (dropped, len(cal), len(events))
    exclusion.loc[len(exclusion)] = {"排除项": "排除合计", "事件数": dropped}
    exclusion.loc[len(exclusion)] = {"排除项": "有效分析事件（进入图7）", "事件数": int(len(cal))}
    exclusion.loc[len(exclusion)] = {"排除项": "申请事件总数", "事件数": int(len(events))}
    OUT.mkdir(parents=True, exist_ok=True)
    exclusion.to_csv(OUT / "07_图7_排除口径.csv", index=False, encoding="utf-8-sig")

    # ---- 3. 五组 × 四区间（允许同一事件计入多个义务组）----
    counts = {label: Counter() for label, _ in GROUPS}
    for _, row in cal.iterrows():
        tags = tags_of(row["处罚措施标签"])
        for label, aliases in GROUPS:
            if tags & aliases:
                counts[label][row["区间"]] += 1

    rows, checks = [], {}
    for label, _ in GROUPS:
        c = counts[label]
        n = sum(c[b] for b in BANDS)
        exact = [Fraction(c[b], n) for b in BANDS]
        shown = [round_half_up(float(e) * 100) for e in exact]
        row = {"义务组": label}
        row.update({f"{b}件数": c[b] for b in BANDS})
        row["有效n"] = n
        row.update({f"{b}占比": round(float(e), 6) for b, e in zip(BANDS, exact)})
        row.update({f"{b}占比_展示%": s for b, s in zip(BANDS, shown)})
        row["占比合计_展示%"] = round(sum(shown), 1)
        row["占比合计_精确"] = round(sum(float(e) for e in exact), 12)
        row["超过365天件数"] = c["366–730天"] + c["731天及以上"]
        row["超过365天占比"] = round((c["366–730天"] + c["731天及以上"]) / n, 6)
        row["超过730天件数"] = c["731天及以上"]
        row["超过730天占比"] = round(c["731天及以上"] / n, 6)
        rows.append(row)
        checks[label] = {"有效n": n, "占比合计_展示": round(sum(shown), 1),
                         "比例精确和": round(sum(float(e) for e in exact), 12),
                         "件数合计等于n": c["180天内"] + c["181–365天"] + c["366–730天"]
                         + c["731天及以上"] == n}
        assert abs(sum(float(e) for e in exact) - 1) < 1e-12, (label, exact)
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "04_图7_四区间分布.csv", index=False, encoding="utf-8-sig")

    # ---- 4. 与图6的分母、180天内件数逐项对齐（证明同一口径、同一批事件）----
    fig1 = pd.read_csv(FIG6_TABLE, keep_default_na=False).set_index("义务组")
    for label, _ in GROUPS:
        assert int(fig1.loc[label, "有效n"]) == checks[label]["有效n"], label
        assert int(fig1.loc[label, "180天内件数"]) == counts[label]["180天内"], label
        # 图6 的“271天及以上”应等于本表的 366天以上 + 271–365天（≥0）
        assert int(fig1.loc[label, "271天及以上件数"]) >= counts[label]["366–730天"] \
            + counts[label]["731天及以上"], label

    # ---- 5. 描述统计（全体 + 五组）----
    def describe(values):
        v = pd.Series(values).astype(int)
        return {"有效n": int(len(v)), "最小": int(v.min()), "P25": float(v.quantile(.25)),
                "中位数": float(v.median()), "P75": float(v.quantile(.75)),
                "P90": float(v.quantile(.90)), "平均": round(float(v.mean()), 1),
                "最大": int(v.max()),
                "超过180天件数": int((v > 180).sum()), "超过365天件数": int((v > 365).sum()),
                "超过730天件数": int((v > 730).sum())}

    stats = [{"分组": "全部事件", **describe(cal["间隔天"])}]
    for label, aliases in GROUPS:
        mask = cal["处罚措施标签"].map(lambda s: bool(tags_of(s) & aliases))
        stats.append({"分组": label, **describe(cal.loc[mask, "间隔天"])})
    stats = pd.DataFrame(stats)
    stats["超过365天占比"] = (stats["超过365天件数"] / stats["有效n"]).round(6)
    stats.to_csv(OUT / "05_图7_描述统计.csv", index=False, encoding="utf-8-sig")

    # ---- 6. 法定期限相关字段的可得性（用于说明“不能判断个案是否超期”）----
    fields = [("送达日", "送达状态"), ("履行届满日", "履行届满状态"),
              ("救济届满日", "救济届满状态"), ("申请截止日", "申请截止状态")]
    availability = [{"字段": name, "可确定事件数": int(cal[flag].eq("明确记载").sum()),
                     "有效事件数": int(len(cal)),
                     "可确定占比": round(float(cal[flag].eq("明确记载").mean()), 6)}
                    for name, flag in fields]
    availability.append({"字段": "催告日", "可确定事件数": 0, "有效事件数": int(len(cal)),
                         "可确定占比": 0.0})
    availability = pd.DataFrame(availability)
    availability.to_csv(OUT / "09_图7_法定期限字段可得性.csv", index=False, encoding="utf-8-sig")

    # ---- 7. 裁定书明确认定“逾期申请”的事件按四区间对照（供司法实践分析引用）----
    cal["认定逾期"] = cal["法院明确认定超过申请期限"].astype(str).str.strip().ne("")
    cross = (cal.groupby("区间", as_index=False)
             .agg(事件数=("事件编号", "size"), 认定逾期件数=("认定逾期", "sum")))
    cross["区间"] = pd.Categorical(cross["区间"], BANDS, ordered=True)
    cross = cross.sort_values("区间").astype({"区间": str})
    cross["认定逾期占比"] = (cross["认定逾期件数"] / cross["事件数"]).round(6)
    cross.loc[len(cross)] = {"区间": "合计", "事件数": int(len(cal)),
                             "认定逾期件数": int(cal["认定逾期"].sum()),
                             "认定逾期占比": round(float(cal["认定逾期"].mean()), 6)}
    cross.to_csv(OUT / "06_图7_法院逾期认定对照.csv", index=False, encoding="utf-8-sig")

    summary = {
        "申请事件总数": int(len(events)),
        "有效分析事件": int(len(cal)),
        "排除合计": int(len(events) - len(cal)),
        "分区间件数": {b: int((cal["区间"] == b).sum()) for b in BANDS},
        "五组有效n": {r["义务组"]: int(r["有效n"]) for r in rows},
        "五组超过365天占比": {r["义务组"]: round(float(r["超过365天占比"]), 4) for r in rows},
        "占比合计_展示": {r["义务组"]: r["占比合计_展示%"] for r in rows},
        "占比精确合计": {r["义务组"]: r["占比合计_精确"] for r in rows},
        "与图6分母一致": True,
        "与图6_180天内件数一致": True,
        "认定逾期件数": int(cal["认定逾期"].sum()),
        "认定逾期占比": round(float(cal["认定逾期"].mean()), 4),
        "送达日可确定事件": int(availability.loc[0, "可确定事件数"]),
        "履行届满日可确定事件": int(availability.loc[1, "可确定事件数"]),
        "救济届满日可确定事件": int(availability.loc[2, "可确定事件数"]),
    }
    (Path(OUT).parent / "08_图7_核验.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(table[["义务组"] + [f"{b}件数" for b in BANDS] + ["有效n", "超过365天占比"]].to_string(index=False))
    print("\n" + exclusion.to_string(index=False))
    print("\n" + cross.to_string(index=False))


if __name__ == "__main__":
    main()
