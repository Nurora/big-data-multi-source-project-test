"""处理 2 · 事务构建：把处罚义务与申请事项按处罚—事件对齐，生成三状态事务表。"""
import re
import sys
import unicodedata
import pandas as pd

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))

from common import (A, DOCS, EVIDENCE, EVENT, ID, LABELS, LIB, P, SOURCE, TABLES,  # noqa: E402
                    labels, pick, read, save, unique, year_span)
from court_fields import agency_level, court_level  # noqa: E402
from obligation_rules import matches, penalty_text, numbered  # noqa: E402
from normalize import key  # noqa: E402

S1 = SOURCE / "广东省土地违法行政处罚数据.xlsx"
LINK = SOURCE / "广东省土地违法行政处罚与裁判文书关联表.xlsx"
TIMING = EVIDENCE / "01_申请事件与间隔.csv"
CITIES = [c + "市" for c in "广州 深圳 珠海 汕头 佛山 韶关 河源 梅州 惠州 汕尾 东莞 中山 江门 阳江 湛江 茂名 肇庆 清远 潮州 揭阳 云浮".split()]
FS_DISTRICTS = re.compile(r"禅城区|南海区|顺德区|高明区|三水区")
CITY_RE = re.compile("|".join(CITIES))
S2_END = re.compile(r"(?:。|;|,|\n)\s*(?:该《|上述《|该(?:行政)?处罚决定(?:书)?送达|"
                    r"申请(?:执行)?人(?:书面|已|向|于|在)|被(?:申请)?执行人(?:在法定|未在|逾期)|"
                    r"经催告|现(?:申请人|申请执行人|佛山市)|该决定书(?:已|送达))")
GAP = re.compile(r"…|\.{3,}|(?:其余|其他)(?:处罚)?(?:事项|义务)(?:略|详见)|"
                 r"(?:详见|另见)[^。;\n]{0,20}(?:决定书|附件|附表)|无具体信息|内容不详")
ZERO_FINE = re.compile(r"(?:^|\n)\s*罚款\s*:\s*0(?:\.0+)?\s*\((?:万)?元\)\s*(?=\n|$)")
EMPTY_CONFISCATION = re.compile(r"没收违法所得[、,]没收非法财物\s*:\s*"
                                r"可确定金额0(?:\.0+)?\(万元\),\s*不确定金额:0(?:\.0+)?(?=\s|$)")
OPEN_REQUEST = re.compile(r"等(?:处罚|事项|义务|内容)|(?:其余|剩余|未履行)(?:的)?"
                          r"(?:处罚事项|处罚内容|义务)|(?:详见|参见)(?:申请书|附件)")


def extract_penalty(row):
    source = row["处罚结果来源"]
    text = unicodedata.normalize("NFKC", row["处罚结果原文"]).strip()
    if source == "S2正文引述的处罚分项":
        text = S2_END.split(text, maxsplit=1)[0].strip()
    text = EMPTY_CONFISCATION.sub("", ZERO_FINE.sub("", text)).strip()
    parsed = penalty_text(text, source, bool(row["处罚义务范围可判定"]))
    result = set(parsed["labels"])
    if re.search(r"(?:责令)?(?:退还|交还|返还)[^。;\n]{0,110}(?:土地|地块|用地)", text):
        result.add("退还土地")
    complete = parsed["complete"] and not GAP.search(parsed["text"])
    if source == "S2正文引述的处罚分项":
        complete = complete and len(numbered(parsed["text"])) >= 2
    if not text or text in {"无具体信息", "未载明"}:
        reason = "处罚结果缺失"
    elif not result:
        reason = "处罚义务未识别"
    elif not row["处罚义务范围可判定"]:
        reason = "无经核验的完整处罚结果"
    elif not complete:
        reason = "处罚原文有省略或分项无法完整解析"
    else:
        reason = "处罚范围完整"
    return result, bool(complete), reason, text


def region(group, fallback):
    locations = unique(group["处罚具体位置或地块"])
    direct = {city for loc in locations for city in CITY_RE.findall(loc)}
    if any(FS_DISTRICTS.search(loc) for loc in locations):
        direct.add("佛山市")
    cities = unique(city for city in [*group["处罚地级市"], fallback] if city in CITIES)
    if len(direct) == 1:
        return next(iter(direct)), "违法地块位置"
    if len(direct) > 1 or len(cities) > 1:
        return "", "地市冲突"
    return (cities[0], "处罚记录地市") if cities else ("", "地市缺失")


def states(columns, positive, closed):
    return {field: 1 if item in positive else 0 if closed else pd.NA
            for field, item in zip(columns, LABELS)}


def scope(row, penalty):
    result = labels(row["明确申请事项"])
    evidence = row["原文申请陈述"]
    method = row["提取依据"]
    reasons = []
    if row["文书来源"] != "S2裁判原文":
        reasons.append("仅裁判摘录或后次追述")
    if "申请项号无法可靠映射" in method:
        reasons.append("有未解析申请项号")
        for clause in evidence.split("｜"):
            if re.search(r"向本院(?:申请|提出)|申请执行人(?:申请|请求)", clause) and re.search(
                    r"项(?:关于|责令)|事项(?:为|如下)|内容(?:为|如下)|决定书[》\"”]中", clause):
                result.update(matches(clause))
    if OPEN_REQUEST.search(evidence):
        reasons.append("开放式申请表述")
    if str(row["明确申请全部范围"]) == "1" and not penalty["P范围完整"]:
        reasons.append("全部范围引用的处罚未闭合")
    if "范围后映射" in method and penalty["处罚证据文本"] != penalty["既有处罚证据文本"].strip():
        result &= labels(penalty["处罚义务"]) | set(matches(evidence))
    if row["申请事项可判定"] and not reasons and result:
        return result, "完整", "原文列明或明确引用可映射的申请项号"
    if result:
        return result, "部分", "；".join(reasons) or "原文只有正向事项证据"
    if row["申请事项状态"] == "未找到申请事项陈述":
        return result, "无陈述", "未定位申请范围陈述"
    return result, "无法判断", "；".join(reasons) or "概括申请或事项无法映射"


def load_inputs():
    raw = pd.read_excel(S1, "合并数据", keep_default_na=False)
    links = pd.read_excel(LINK, "关联结果", keep_default_na=False)
    links["关联表行"] = links.index + 2
    links[ID] = links.apply(lambda r: "|".join(key(r[k]) for k in
                            ["行政处罚决定书文号", "处罚机关", "处罚行政相对人"]), axis=1)
    all_p = read(EVIDENCE / "01_S1处罚记录与义务组合.csv").rename(columns={"处罚键": ID})
    linked = read(EVIDENCE / "07_确认关联处罚对应分类.csv").rename(columns={
        "处罚键": ID, "处罚结果范围可判定": "处罚义务范围可判定", "处罚原文文件": "原文文件"})
    ev = read(EVIDENCE / "06_S2司法申请事件证据.csv").rename(columns={"处罚键": ID, "事件编号": EVENT})
    timing = read(TIMING)
    if "处罚键" in timing.columns:
        timing = timing.drop(columns=ID, errors="ignore")
    timing = timing.rename(columns={"处罚键": ID, "事件编号": EVENT})
    for name, frame in [("合并数据", raw), ("关联结果", links), ("处罚证据", all_p),
                        ("关联处罚证据", linked), ("事件证据", ev), ("日期证据", timing)]:
        print(name, " | ".join(frame.columns))
    assert all_p[ID].is_unique and linked[ID].is_unique and ev[EVENT].is_unique and timing[EVENT].is_unique
    assert set(linked[ID]) == set(links[ID]) == set(ev[ID])
    assert set(zip(ev[ID], ev[EVENT])) == set(zip(timing[ID], timing[EVENT]))
    assert sum(len(str(x).split("｜")) for x in all_p["同键S1行"]) == len(raw)
    return raw, links, all_p, linked, ev, timing


def build():
    raw, links, all_p, linked, ev, timing = load_inputs()
    by_link = dict(tuple(links.groupby(ID, sort=False)))
    by_master = all_p.set_index(ID).to_dict("index")
    penalties = {}
    for _, row in linked.iterrows():
        code = row[ID]
        group = by_link[code]
        base = group.iloc[0]
        master = by_master.get(code)
        raw_base = raw.iloc[int(master["S1表行"]) - 2] if master else None
        result, complete, reason, text = extract_penalty(row)
        city, city_source = region(group, raw_base["标准地级市"] if master else "")
        penalties[code] = {
            ID: code, "处罚文号": row["处罚文号"], "处罚机关": base["处罚机关"],
            "行政相对人": base["处罚行政相对人"],
            "处罚日期": master["处罚日期"] if master and master["处罚日期"] else str(base["行政处罚日期"])[:10],
            "违法地市": city, "违法地市依据": city_source, "处罚地级市源值": "｜".join(unique(group["处罚地级市"])),
            "违法位置": "｜".join(unique(group["处罚具体位置或地块"])),
            "主体类型": base["处罚相对人类型"], "土地原地类": base["占用土地类型"],
            "违法后用途": base["占用土地用途"], "占地面积平方米": base["占用土地面积（平方米）"],
            "罚款金额元": base["罚款金额（元）"], "处罚源标签": base["处罚措施标签"],
            "处罚义务": pick(result), "P范围完整": complete, "处罚判定": reason,
            "处罚证据来源": row["处罚结果来源"], "处罚原文文件": row["原文文件"],
            "处罚证据文本": text, "既有处罚证据文本": row["处罚结果原文"],
            "既有处罚义务": row["义务组合"], **states(P, result, complete),
        }

    dates = timing.set_index(EVENT).to_dict("index")
    by_link_row = links.set_index("关联表行").to_dict("index")
    events = []
    for _, row in ev.iterrows():
        code, event = row[ID], row[EVENT]
        date = dates[event]
        p = penalties[code]
        source_rows = [by_link_row[int(i)] for i in str(date["关联表行"]).split("、")]
        assert all(r[ID] == code for r in source_rows)
        court_city = "｜".join(unique(r["裁判地级市"] for r in source_rows))
        court = row["法院"] or source_rows[0]["法院"]
        agency = row["申请机关源值"] or source_rows[0]["裁判侧识别的申请执行机关"]
        positives, status, why = scope(row, p)
        sortable = (date["申请精度"] == "日" and date["申请日"]
                    and "日期先后冲突" not in (date["处罚至申请状态"], date["申请至裁判状态"]))
        events.append({
            ID: code, EVENT: event, "案号": row["案号"], "关联表行": date["关联表行"],
            "事件来源": date["事件来源"], "法院": court, "法院地市": court_city,
            "法院层级": court_level(court), "申请机关": agency, "申请机关层级": agency_level(agency, p["违法地市"]),
            "申请日": date["申请日"], "可排序申请日": date["申请日"] if sortable else "",
            "裁判日": row["裁判日"], "申请范围": status, "范围判定依据": why,
            "申请事项": pick(positives), "原文申请陈述": row["原文申请陈述"],
            "事项原文证据": row["事项原文证据"], "申请日期证据": date["申请证据"],
            "司法证据来源": row["文书来源"], "司法原文文件": row["原文文件"],
            "既有范围完整标记": row["申请事项可判定"], "既有申请事项": row["明确申请事项"],
            "既有提取依据": row["提取依据"], **states(A, positives, status == "完整"),
        })

    event_frame = pd.DataFrame(events)
    groups = dict(tuple(event_frame.groupby(ID, sort=False)))
    for code, p in penalties.items():
        rel = groups.get(code, event_frame.iloc[:0])
        positive = set().union(*(labels(value) for value in rel["申请事项"]))
        closed = bool(len(rel) and rel["申请范围"].eq("完整").all())
        p.update(states(A, positive, closed))
        p["事件数"] = len(rel)
        p["完整事件数"] = int(rel["申请范围"].eq("完整").sum())
        p["已明确申请事项"] = pick(positive)
        p["A范围完整"] = all(pd.notna(p[col]) for col in A)
        p["任一A可判断"] = any(pd.notna(p[col]) for col in A)
        p["主样本"] = p["P范围完整"] and p["A范围完整"]
    penalty_frame = pd.DataFrame(penalties.values())
    assert penalty_frame[ID].is_unique and event_frame[EVENT].is_unique
    assert penalty_frame["事件数"].sum() == len(event_frame)
    assert penalty_frame.loc[penalty_frame["主样本"], P + A].notna().all().all()
    assert penalty_frame.loc[~penalty_frame["主样本"], P + A].isna().any(axis=1).all()
    assert not event_frame.loc[event_frame["申请范围"].ne("完整"), A].eq(0).any().any()
    save("处罚级三状态事务", penalty_frame)
    save("申请事件级三状态及证据", event_frame)
    save("处罚与申请事件映射", event_frame[[ID, EVENT, "案号", "关联表行", "事件来源"]])
    save("申请范围判定样例", event_frame.groupby("申请范围", sort=False).head(5))
    save("事项标准化映射", [{"处罚义务": p, "申请事项": "申请" + p, "P特征": pc, "A特征": ac}
                         for p, pc, ac in zip(LABELS, P, A)])
    write_flow(raw, links, all_p, penalty_frame, event_frame)


def write_flow(raw, links, all_p, pen, ev):
    positive = pen["处罚义务"].ne("")
    judged = positive & pen["任一A可判断"]
    complete_p = judged & pen["P范围完整"]
    main = pen["主样本"]
    assert (main <= complete_p).all()
    records = [
        ("处罚源表记录", len(raw), "源表行", "合并数据全表"),
        ("全部处罚", len(all_p), "处罚", "同文号、机关、相对人合并；缺稳定键的行保留"),
        ("确认关联处罚（按处罚键直接匹配）", pen[ID].isin(all_p[ID]).sum(), "处罚",
         "1 项因证据台账键写法与源表不同，未能直接匹配"),
        ("确认关联处罚", len(pen), "处罚", "按处罚文号核对后确认归属，与 01 模块确认表一致"),
        ("可识别义务", positive.sum(), "处罚", "排除无明确义务正向证据的处罚"),
        ("有可判断申请", judged.sum(), "处罚", "A全集至少一项为1或0，排除A全NA"),
        ("有可判断申请且处罚义务范围完整", complete_p.sum(), "处罚", "P全集均为0或1"),
        ("处罚级主分析", main.sum(), "处罚", "A全集均为0或1"),
        ("确认关联表源行", len(links), "关联行", "确认关联表"),
        ("独立关联案号", ev["案号"].nunique(), "案号", "规范案号与日期证据核对"),
        ("所有已知申请事件", len(ev), "事件", "独立案号事件加明确追述前次事件"),
        *[(f"申请范围{label}", int(ev["申请范围"].eq(label).sum()), "事件", "按事件原文和核验台账判定")
          for label in ["完整", "部分", "无法判断", "无陈述"]],
    ]
    flow = pd.DataFrame(records, columns=["阶段", "数量", "单位", "纳入或排除说明"])
    # 只有前 8 行构成"处罚级"逐级收敛链，才计算相对上一阶段的变动；其余为并列口径
    diffs = [""] * len(flow)
    for i in range(1, 8):
        diffs[i] = int(flow["数量"].iloc[i] - flow["数量"].iloc[i - 1])
    flow["相对上阶段变动"] = diffs
    save("样本流", flow)
    save("样本流分支", pen.assign(可识别处罚义务=positive, 司法侧可判断=pen["任一A可判断"])
         .groupby(["可识别处罚义务", "P范围完整", "司法侧可判断", "A范围完整", "处罚判定"],
                  dropna=False).size().reset_index(name="处罚数"))
    save("地市证据核对", pen.groupby(["违法地市", "违法地市依据", "主样本"]).size().reset_index(name="处罚数"))
    lines = ["# 第二问样本流", "",
             f"处罚决定日期 {year_span(pen['处罚日期'])}，关联裁判日期 {year_span(ev['裁判日'])}，日期范围按已知日期。",
             "", "| 阶段 | 数量 | 单位 | 说明 |", "|---|---:|---|---|"]
    lines += [f"| {stage} | {int(n):,} | {unit} | {reason} |" for stage, n, unit, reason in records]
    lines += ["", f"可识别义务处罚中，{int((positive & ~pen['任一A可判断']).sum())} 项的 A 全部为 NA。"
              f"有可判断申请的处罚中，{int((judged & ~pen['P范围完整']).sum())} 项的 P 仍有 NA。"
              f"通过 P 完整门槛后，{int((complete_p & ~main).sum())} 项的 A 仍有至少一个 NA。",
              f"有 {int(pen['事件数'].gt(1).sum())} 项处罚对应多个已知申请事件，"
              f"超出每处罚首个事件的记录共 {len(ev)-len(pen)} 条。",
              "", "分支计数、地市证据、处罚与事件明细见 outputs/tables。"]
    DOCS.mkdir(exist_ok=True)
    (DOCS / "02_sample_flow.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(flow.to_string(index=False))


if __name__ == "__main__":
    build()
