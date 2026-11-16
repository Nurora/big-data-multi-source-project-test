# -*- coding: utf-8 -*-
"""分析 5 · 非法占地基础画像：识别非法占用土地，输出图1—图5 的统计表。

输入（由 processing/1_build_sample.py 生成）：
  01_处罚主表_20899.csv      20,899 项处罚分析单位（含处罚事由、处罚结果原文）
  02_确认关联处罚_3175.csv   3,175 项确认司法关联处罚
输出（output/tables）：
  01_全部处罚判定明细.csv        逐条判定、行为方式、命中规则、证据片段
  02_非法占地处罚底表.csv        19,702 项非法占地处罚 + 原地类 / 违法后用途
  03_样本流.csv                 20,899 → 19,702 → 3,167 的样本流
  04_图1 … 09_图5                五张图的底层统计表
判定规则见 classify.py（非法占地识别）与 landuse.py（地类与用途抽取）。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
import paths  # noqa: E402
from occupation_rules import identify  # noqa: E402

OUT = paths.TABLES
MAIN = paths.need(paths.MAIN)
CONF = paths.need(paths.CONF)
CONF_KEYS = set(pd.read_csv(CONF, keep_default_na=False, usecols=["处罚键"])["处罚键"])
SUBJECTS = ["自然人", "企业", "村委会/集体经济组织", "其他组织", "事业单位/政府机构"]
PERIODS = ["2015–2018", "2019–2021", "2022–2025"]


def period(year):
    if pd.isna(year):
        return np.nan
    if year <= 2014:
        return "2014年及以前"
    if year <= 2018:
        return "2015–2018"
    if year <= 2021:
        return "2019–2021"
    return "2022–2025"


def wilson(k, n, z=1.96):
    if not n:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z**2 / n
    mid = (p + z**2 / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / den
    return max(0, mid - half), min(1, mid + half)


def stratified_or(counts):
    """Mantel–Haenszel 共同 OR、Robins–Breslow–Greenland 区间与 CMH 检验。"""
    a, b, c, d = counts.astype(float).T
    n = a + b + c + d
    r, s = a * d / n, b * c / n
    rr, ss = r.sum(), s.sum()
    if not rr or not ss:
        return np.nan, np.nan, np.nan, np.nan
    p = (a + d) / n
    q = (b + c) / n
    var = (p * r).sum() / (2 * rr**2) + (p * s + q * r).sum() / (2 * rr * ss) + (q * s).sum() / (2 * ss**2)
    odds = rr / ss
    low, high = np.exp(np.log(odds) + np.array([-1, 1]) * 1.96 * np.sqrt(var))
    expected = (a + b) * (a + c) / n
    variance = ((a + b) * (c + d) * (a + c) * (b + d) / (n**2 * (n - 1))).sum()
    pval = chi2.sf((a - expected).sum() ** 2 / variance, 1) if variance > 0 else np.nan
    return odds, low, high, pval


def token_year(value):
    """从处罚文号中取四位年份（20xx），仅作为处罚年份缺失时的补充来源。"""
    m = pd.Series(value).astype(str).str.extract(r"(20[0-2]\d)")[0]
    y = pd.to_numeric(m, errors="coerce")
    return y.where(y.between(2010, 2025))


def build_base():
    d = pd.read_csv(MAIN, keep_default_na=False, low_memory=False)
    d["年份"] = pd.to_numeric(d["处罚年份"], errors="coerce")
    doc_year = token_year(d["行政处罚决定书文号"])
    d["年份来源"] = np.where(d["年份"].notna(), "处罚表", np.where(doc_year.notna(), "处罚文号", "缺失"))
    d["年份"] = d["年份"].fillna(doc_year)
    rows = [identify(a, b, None if pd.isna(y) else int(y))
            for a, b, y in zip(d["处罚事由"], d["处罚结果"], d["年份"])]
    d[["判定", "行为方式", "命中规则", "证据", "判定强度"]] = pd.DataFrame(rows, index=d.index)
    # 概括援引并入"未载明具体方式"，二者都不给出可区分的占用情节
    d["行为方式"] = d["行为方式"].replace({"概括援引法定情形（未区分）": "未载明具体方式",
                                           "仅载明非法占用（方式未细化）": "未载明具体方式"})
    d["司法关联"] = np.where(d["处罚键"].isin(CONF_KEYS), "确认关联", "未确认司法关联")
    d["时期"] = d["年份"].map(period)
    audit = ["处罚键", "行政处罚决定书文号", "主体", "处罚年份", "年份", "年份来源", "违法地市",
             "判定", "行为方式", "命中规则", "证据", "判定强度", "司法关联"]
    d[audit].to_csv(OUT / "01_全部处罚判定明细.csv", index=False, encoding="utf-8-sig")
    return d


def load_occ(d):
    """对判定为非法占地的记录抽取原地类与违法后用途（文本规则见 landuse.py）。"""
    from landuse_rules import clean, find_land, find_use
    y = d.loc[d["判定"].eq("是")].copy()
    land, use = [], []
    for a, b in zip(y["处罚事由"], y["处罚结果"]):
        rec = {"事由": clean(a), "结果": clean(b)}
        land.append(find_land(rec)[0])
        use.append(find_use(rec)[0])
    y["原地类"] = land
    y["违法后用途"] = use
    keep = ["处罚键", "行政处罚决定书文号", "主体", "处罚年份", "年份", "年份来源", "违法地市",
            "判定", "行为方式", "命中规则", "证据", "判定强度", "司法关联", "时期", "原地类", "违法后用途"]
    y[keep].to_csv(OUT / "02_非法占地处罚底表.csv", index=False, encoding="utf-8-sig")
    return y


def sample_flow(d):
    y = d["判定"].eq("是")
    rows = [
        {"阶段": "行政处罚分析单位（去重后）", "处罚数": len(d), "说明": "与第二、三节口径一致"},
        {"阶段": "其中：判定为非法占用土地", "处罚数": int(y.sum()), "说明": "文本与条文双通道识别"},
        {"阶段": "其中：非占用型土地违法", "处罚数": int(d["判定"].eq("否").sum()), "说明": "转让、破坏耕地、复垦、改变用途"},
        {"阶段": "其中：无法确定是否非法占用", "处罚数": int(d["判定"].eq("无法确定").sum()), "说明": "公开记录缺少占用表述，单列不归类"},
        {"阶段": "非法占地中：确认司法关联", "处罚数": int(d.loc[y, "司法关联"].eq("确认关联").sum()), "说明": "与裁判文书确认关联"},
        {"阶段": "非法占地中：未确认司法关联", "处罚数": int(d.loc[y, "司法关联"].eq("未确认司法关联").sum()), "说明": "不等于未进入司法程序"},
        {"阶段": "全部确认关联处罚", "处罚数": len(CONF_KEYS), "说明": "报告总体口径"},
        {"阶段": "确认关联中不属于非法占地", "处罚数": int(d.loc[d["司法关联"].eq("确认关联"), "判定"].ne("是").sum()),
         "说明": "非占用型或无法确定"},
    ]
    pd.DataFrame(rows).to_csv(OUT / "03_样本流.csv", index=False, encoding="utf-8-sig")
    return pd.DataFrame(rows)


def fig1(y):
    tab = pd.crosstab(y["主体"], y["司法关联"]).reindex(SUBJECTS).fillna(0)
    tab["合计"] = tab.sum(axis=1)
    total = tab["合计"].sum()
    conf_total = tab["确认关联"].sum()
    ref_total = tab["未确认司法关联"].sum()
    # 共同层：时期×地市，两组各≥5
    s = y.loc[y["时期"].isin(PERIODS)].copy()
    s["分层"] = s["时期"].astype(str) + " × " + s["违法地市"].astype(str)
    counts = pd.crosstab(s["分层"], s["司法关联"]).reindex(columns=["确认关联", "未确认司法关联"], fill_value=0)
    keep = counts.ge(5).all(axis=1)
    s = s.loc[s["分层"].isin(counts.index[keep])]
    weight = s["分层"].value_counts(normalize=True)
    std = pd.DataFrame(index=SUBJECTS)
    for g in ["确认关联", "未确认司法关联"]:
        ct = pd.crosstab(s.loc[s["司法关联"].eq(g), "分层"], s.loc[s["司法关联"].eq(g), "主体"])
        share = ct.div(ct.sum(axis=1), axis=0).reindex(columns=SUBJECTS, fill_value=0)
        std[g] = share.mul(weight, axis=0).sum()
    rows = []
    for sub in SUBJECTS:
        k, n = int(tab.loc[sub, "确认关联"]), int(tab.loc[sub, "合计"])
        low, high = wilson(k, n)
        rows.append({"主体": sub, "处罚数": n, "处罚构成": n / total,
                     "确认关联数": k, "确认样本构成": k / conf_total,
                     "未确认数": int(tab.loc[sub, "未确认司法关联"]),
                     "未确认样本构成": tab.loc[sub, "未确认司法关联"] / ref_total,
                     "确认关联比例": k / n if n else np.nan,
                     "CI下限": low, "CI上限": high,
                     "标准化确认构成": std.loc[sub, "确认关联"],
                     "标准化未确认构成": std.loc[sub, "未确认司法关联"]})
    res = pd.DataFrame(rows)
    # 各主体 vs 其余：时期×地市内 MH OR
    mh = []
    for sub in SUBJECTS:
        has = y["主体"].eq(sub)
        cells = pd.DataFrame({"a": has & y["司法关联"].eq("确认关联"),
                              "b": has & y["司法关联"].eq("未确认司法关联"),
                              "c": ~has & y["司法关联"].eq("确认关联"),
                              "d": ~has & y["司法关联"].eq("未确认司法关联"),
                              "分层": y["时期"].astype(str) + " × " + y["违法地市"].astype(str)})
        cells = cells.loc[y["时期"].isin(PERIODS)]
        c = cells.groupby("分层").sum()
        informative = c.loc[c[["a", "c"]].sum(axis=1).gt(0) & c[["b", "d"]].sum(axis=1).gt(0)]
        odds, low, high, p = stratified_or(informative.to_numpy())
        mh.append({"主体": sub, "MH_OR": odds, "CI下限": low, "CI上限": high, "CMH_p": p,
                   "信息层数": len(informative), "有效样本": int(informative.sum().sum())})
    mh = pd.DataFrame(mh)
    p = mh["CMH_p"].dropna().sort_values()
    mh["BH_FDR"] = (p * len(p) / np.arange(1, len(p) + 1)).iloc[::-1].cummin().iloc[::-1].clip(upper=1)
    res = res.merge(mh, on="主体", how="left")
    res["总体确认比例"] = conf_total / total
    res["层数"] = int(keep.sum())
    res["共同层样本"] = len(s)
    res.to_csv(OUT / "04_图1_主体结构与司法关联.csv", index=False, encoding="utf-8-sig")
    return res


def fig2(y):
    order = ["未经批准占用", "超出批准范围或面积占用", "临时用地违法占用", "未载明具体方式"]
    tab = y["行为方式"].value_counts().reindex(order).fillna(0).astype(int)
    rows = []
    for k in order:
        rows.append({"行为方式": k, "处罚数": int(tab[k]), "占非法占地比例": tab[k] / len(y),
                     "占情节可识别样本比例": tab[k] / int(tab[["未经批准占用", "超出批准范围或面积占用", "临时用地违法占用"]].sum())
                     if k != "未载明具体方式" else np.nan})
    res = pd.DataFrame(rows)
    res["骗取批准"] = 0
    res.to_csv(OUT / "05_图2_行为类型构成.csv", index=False, encoding="utf-8-sig")

    ct = pd.crosstab(y["主体"], y["行为方式"]).reindex(index=SUBJECTS, columns=order).fillna(0)
    ct["合计"] = ct.sum(axis=1)
    long = ct.reset_index().melt(id_vars=["主体", "合计"], var_name="行为方式", value_name="处罚数")
    long["主体内比例"] = long["处罚数"] / long["合计"]
    long["情节可识别"] = long["行为方式"].ne("未载明具体方式")
    long.to_csv(OUT / "06_图2_主体与行为类型.csv", index=False, encoding="utf-8-sig")

    ident = y[y["行为方式"].ne("未载明具体方式")]
    ct2 = pd.crosstab(ident["主体"], ident["行为方式"]).reindex(index=SUBJECTS, columns=order[:-1]).fillna(0)
    ct2["合计"] = ct2.sum(axis=1)
    ct2.reset_index().melt(id_vars=["主体", "合计"], var_name="行为方式", value_name="处罚数").assign(
        主体内比例=lambda x: x["处罚数"] / x["合计"]).to_csv(
        OUT / "06b_图2_情节可识别子样本_主体与行为.csv", index=False, encoding="utf-8-sig")
    return res, ct


def fig3(y):
    land_known = y["原地类"].ne("未知或未提及")
    use_known = y["违法后用途"].ne("未知或未提及")
    known = y.loc[land_known & use_known]
    order_l = ["耕地", "园地", "林地", "建设用地", "其他土地", "农用地(未细分)", "多类并列(未分面积)"]
    order_u = ["住宅/房屋建设", "工业厂房", "仓库/仓储设施", "商业经营设施", "道路及其他基础设施", "其他用途"]
    tab = pd.crosstab(known["原地类"], known["违法后用途"]).reindex(index=order_l, columns=order_u).fillna(0).astype(int)
    tab.to_csv(OUT / "07_图3_地类用途矩阵.csv", encoding="utf-8-sig")
    flows = tab.stack().reset_index()
    flows.columns = ["原地类", "违法后用途", "处罚数"]
    flows.to_csv(OUT / "07b_图3_流向明细.csv", index=False, encoding="utf-8-sig")
    land = tab.sum(axis=1).rename("处罚数").reset_index()
    land["构成"] = land["处罚数"] / len(known)
    land.to_csv(OUT / "07c_图3_原地类构成.csv", index=False, encoding="utf-8-sig")
    use = tab.sum(axis=0).rename("处罚数").reset_index()
    use["构成"] = use["处罚数"] / len(known)
    use.to_csv(OUT / "07d_图3_违法后用途构成.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([{"非法占地处罚": len(y), "原地类可识别": int(land_known.sum()),
                   "违法后用途可识别": int(use_known.sum()), "两端均可识别": len(known),
                   "两端可识别比例": len(known) / len(y)}]).to_csv(
        OUT / "07e_图3_样本量.csv", index=False, encoding="utf-8-sig")
    return tab, len(y)


def fig4(y):
    d = y.copy()
    d["年度"] = d["年份"].fillna(-1)
    g = d.groupby("年度").agg(处罚数=("处罚键", "size"),
                              确认关联=("司法关联", lambda s: int(s.eq("确认关联").sum())))
    g["未确认"] = g["处罚数"] - g["确认关联"]
    g["确认关联比例"] = g["确认关联"] / g["处罚数"]
    lo, hi = zip(*[wilson(k, n) for k, n in zip(g["确认关联"], g["处罚数"])])
    g["CI下限"], g["CI上限"] = lo, hi
    g = g.reset_index()
    g["年度"] = g["年度"].replace({-1: np.nan})
    g["年度标签"] = g["年度"].map(lambda v: "年份缺失" if pd.isna(v) else str(int(v)))
    g.to_csv(OUT / "08_图4_年度分布.csv", index=False, encoding="utf-8-sig")
    return g


def fig5(y):
    g = y.groupby("违法地市").agg(处罚数=("处罚键", "size"),
                                  确认关联=("司法关联", lambda s: int(s.eq("确认关联").sum())))
    g["未确认"] = g["处罚数"] - g["确认关联"]
    g["确认关联比例"] = g["确认关联"] / g["处罚数"]
    lo, hi = zip(*[wilson(k, n) for k, n in zip(g["确认关联"], g["处罚数"])])
    g["CI下限"], g["CI上限"] = lo, hi
    g["全省处罚占比"] = g["处罚数"] / g["处罚数"].sum()
    g = g.sort_values("处罚数", ascending=False).reset_index()
    g.to_csv(OUT / "09_图5_地市分布.csv", index=False, encoding="utf-8-sig")
    return g


def main():
    d = build_base()
    print(d["判定"].value_counts().to_string())
    y = load_occ(d)
    flow = sample_flow(d)
    r1 = fig1(y)
    r2, ct2 = fig2(y)
    tab3, n3 = fig3(y)
    r4 = fig4(y)
    r5 = fig5(y)
    print("\n图1\n", r1.to_string(index=False))
    print("\n图2\n", r2.to_string(index=False))
    print("\n图3 样本", n3, "两端", int(tab3.values.sum()))
    print(tab3.to_string())
    print("\n图4\n", r4.to_string(index=False))
    print("\n图5\n", r5.head(8).to_string(index=False))
    print("\n样本流\n", flow.to_string(index=False))


if __name__ == "__main__":
    main()
