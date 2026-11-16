# -*- coding: utf-8 -*-
"""处理 1 · 样本构建：从原始处罚表与已核验关联表生成四层分析样本。

产出（output/tables）：
  01_处罚主表_20899.csv     处罚级全样本，一行一项处罚（复合键=文号|机关|相对人）
  02_确认关联处罚_3175.csv  处罚级确认关联样本
  03_独立案号_3392.csv      案号级样本
  04_申请事件_3393.csv      事件级样本
  05_样本流.csv             20,970 → 20,899 → 3,175 / 3,392 / 3,393 的口径流
  06_口径核验.json          关键断言

口径说明见仓库根目录 README.md 第六节。外部输入：
  data/raw/广东省土地违法行政处罚数据.xlsx（合并数据）
  data/raw/广东省土地违法行政处罚与裁判文书关联表.xlsx（关联结果）
  data/integrated/01_申请事件与间隔.csv（事件级证据台账，含唯一一条“前次申请”补记）
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))
from normalize import clean, key, load_links, norm, parse_date, SOURCE  # noqa: E402
from paths import INTEGRATED, TABLES  # noqa: E402

OUT = TABLES
EVIDENCE = INTEGRATED

PENALTY = SOURCE / "广东省土地违法行政处罚数据.xlsx"
LINK = SOURCE / "广东省土地违法行政处罚与裁判文书关联表.xlsx"
TIMING = EVIDENCE / "01_申请事件与间隔.csv"

SUBJECT = {
    "自然人": "自然人",
    "企业": "企业",
    "村委会/集体经济组织": "村委会/集体经济组织",
    "事业单位/政府机构": "事业单位/政府机构",
    "其他组织": "其他组织",
    "法人或其他组织": "其他组织",
}
VIOLATION_RULES = [
    ("非法转让/出租土地", r"非法转让|买卖土地|擅自转让|转让土地|出租土地|以租代征"),
    ("临时用地逾期不归还", r"临时用地|临时使用土地"),
    ("非法采矿/破坏矿产资源", r"采矿|矿产资源|非法开采|砂石场"),
    ("土地登记/权属违法", r"土地登记|权属|发证|确权"),
    ("擅自改变土地用途", r"擅自改变.{0,6}用途|改变土地用途|违反用途管制"),
    ("破坏耕地（种植条件）", r"破坏种植条件|毁坏耕地|耕地破坏|破坏耕地|挖砂取土|取土|堆放废弃物"),
    ("非法占用土地（未批先建/未办用地手续）",
     r"未经批准|未批先建|未办理|未取得|擅自占用|非法占用|违法占地|未经依法批准|"
     r"未依法办理|未完善用地手续|未经国土|擅自将|非法占地|未供即用"),
]


def violation(text):
    """违法类型：按 s0_common.VIOLATION_RULES 的优先级匹配处罚事由与处罚结果。"""
    value = clean(text)
    for name, pat in VIOLATION_RULES:
        if __import__("re").search(pat, value):
            return name
    return "未载明"


def main():
    raw = pd.read_excel(PENALTY, "合并数据", keep_default_na=False)
    raw["源表行"] = raw.index + 2
    raw["处罚键"] = ["|".join([key(r["行政处罚决定书文号"]), key(r["处罚机关"]),
                              key(r["标准行政相对人"])]) for _, r in raw.iterrows()]
    raw["文本长度"] = raw["处罚事由"].str.len() + raw["处罚结果"].str.len()
    # 同一复合键的多条源记录：保留信息量最大的一条，其余登记在“同键源表行”
    raw = raw.sort_values(["处罚键", "文本长度"], ascending=[True, False])
    primary = raw.drop_duplicates("处罚键", keep="first").copy()
    spans = raw.groupby("处罚键")["源表行"].agg(lambda s: "、".join(str(x) for x in s))

    primary["同键源表行"] = primary["处罚键"].map(spans)
    primary["主体"] = primary["相对人类型"].map(lambda x: SUBJECT.get(str(x).strip(), "未识别"))
    primary["违法行为"] = [violation(f"{a} {b}") for a, b in zip(primary["处罚事由"], primary["处罚结果"])]
    primary["处罚年份"] = pd.to_numeric(primary["标准处罚年份"].astype(str).str[:4], errors="coerce").astype("Int64")
    primary["违法地市"] = primary["标准地级市"].astype(str).str.strip().replace({"": "未识别"})
    primary["处罚日期"] = [parse_date(v)[0] for v in primary["标准处罚日期"]]

    links = load_links()
    link = pd.DataFrame(links)
    link["案号键"] = link["裁判文书案号"].map(key)
    link["处罚键"] = ["|".join([key(r["行政处罚决定书文号"]), key(r["处罚机关"]),
                              key(r["处罚行政相对人"])]) for _, r in link.iterrows()]
    unknown = set(link["处罚键"]) - set(primary["处罚键"])
    assert not unknown, f"关联结果中有处罚键不在处罚主表：{len(unknown)}"

    confirmed = primary.loc[primary["处罚键"].isin(set(link["处罚键"]))].copy()
    confirmed["关联案号数"] = confirmed["处罚键"].map(link.groupby("处罚键")["案号键"].nunique())
    confirmed["关联表行"] = confirmed["处罚键"].map(
        link.groupby("处罚键")["关联表行"].agg(lambda s: "、".join(str(x) for x in s)))

    cases = (link.groupby("案号键", as_index=False)
             .agg(裁判日期=("裁判日期", "first"), 裁判地级市=("裁判地级市", "first"),
                  处罚键=("处罚键", lambda s: "、".join(sorted(set(s)))),
                  关联表行=("关联表行", "first"), 案号=("裁判文书案号", "first")))
    cases["关联处罚数"] = cases["处罚键"].str.count("、") + 1

    timing = pd.read_csv(TIMING, keep_default_na=False, low_memory=False,
                         usecols=["事件编号", "案号", "处罚键", "关联表行", "事件来源", "申请日", "裁判日"])
    events = timing.copy()
    events["案号键"] = events["案号"].map(key)

    # ---- 口径断言 ----
    checks = {
        "处罚源表记录": int(len(raw)),
        "处罚分析单位_复合键去重": int(len(primary)),
        "确认关联处罚": int(len(confirmed)),
        "独立案号": int(len(cases)),
        "申请事件": int(len(events)),
        "关联对数": int(len(link)),
        "确认关联处罚占比": round(len(confirmed) / len(primary), 6),
        "同一处罚关联多个案号的处罚数": int((confirmed["关联案号数"] > 1).sum()),
        "关联结果中未匹配到处罚的键": int(len(unknown)),
    }
    assert checks["处罚分析单位_复合键去重"] == 20899, checks
    assert checks["确认关联处罚"] == 3175, checks
    assert checks["独立案号"] == 3392, checks
    assert checks["申请事件"] == 3393, checks
    assert len(events["事件编号"]) == len(set(events["事件编号"]))
    assert set(events["处罚键"]) == set(confirmed["处罚键"])
    assert set(events["案号键"]) <= set(cases["案号键"])
    # 3,393 = 3,392 个案号 + 1 条“后次裁定追述前次申请”的补记事件
    extra = events.loc[events["事件来源"] != "同案号非诉执行审查", ["事件编号", "案号", "事件来源"]]
    checks["案号之外的补记事件"] = int(len(extra))
    checks["补记事件明细"] = extra.to_dict("records")
    assert len(extra) == 1, extra

    OUT.mkdir(parents=True, exist_ok=True)
    keep = ["处罚键", "行政处罚决定书文号", "处罚机关", "标准行政相对人", "主体", "相对人类型",
            "处罚日期", "处罚年份", "违法地市", "违法行为", "处罚措施标签", "处罚事由", "处罚结果",
            "占用土地类型", "占用土地用途", "占用土地面积（平方米）", "罚款金额（元）",
            "源表行", "同键源表行"]
    primary[keep].to_csv(OUT / "01_处罚主表_20899.csv", index=False, encoding="utf-8-sig")
    confirmed[keep + ["关联案号数", "关联表行"]].to_csv(
        OUT / "02_确认关联处罚_3175.csv", index=False, encoding="utf-8-sig")
    cases.to_csv(OUT / "03_独立案号_3392.csv", index=False, encoding="utf-8-sig")
    events.to_csv(OUT / "04_申请事件_3393.csv", index=False, encoding="utf-8-sig")

    flow = pd.DataFrame([
        {"阶段": "行政处罚源表记录", "数量": len(raw), "说明": "数据源「合并数据」明细行"},
        {"阶段": "处罚分析单位（复合键去重）", "数量": len(primary), "说明": "文号+处罚机关+行政相对人"},
        {"阶段": "确认关联处罚", "数量": len(confirmed), "说明": "关联结果按处罚键去重"},
        {"阶段": "独立案号", "数量": len(cases), "说明": "规范化案号去重"},
        {"阶段": "申请事件", "数量": len(events), "说明": "案号事件 + 1 条前次申请补记"},
    ])
    flow.to_csv(OUT / "05_样本流.csv", index=False, encoding="utf-8-sig")
    (Path(OUT).parent / "06_口径核验.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in checks.items() if k != "补记事件明细"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
