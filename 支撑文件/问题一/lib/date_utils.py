"""Extract dates attached to explicit event wording, with reviewable evidence."""
import re
from collections import defaultdict

from normalize import DATE, DAY, key, parse_date

D = rf"(?P<date>{DATE})"
COURT = r"(?:本院|我院|人民法院)"
ACT = (r"(?:向(?:本院|我院|本法院|人民法院|[^,。;\n]{1,20}?人民法院)(?:再次|重新|才|正式)?"
       r"(?:提[出交](?:(?:强制)?执行)?申请|申请(?:强制)?执行|递交(?:强制)?执行申请(?:书)?|"
       r"提交(?:强制)?执行申请(?:书)?|申请(?!撤回|撤销|中止|终结|变更)[^,。;\n]{0,12}?强制执行))")
AGENCY = r"(?:申请执行人|申请人|申请机关|该局|该机关|[^\d,。;\n]{2,30}?(?:分局|资源局|人民政府|委员会|执法局))"
APPLY = [
    (rf"{D}(?:[前后以前之内日至]|起)?(?:,?(?:{AGENCY})?(?:才|即|遂|又|已|第一次|首次|再次|重新|正式){{0,3}}"
     rf"(?:通过邮寄方式|以邮寄方式|邮寄)?{ACT})",
     "日期在申请动作前"),
    (rf"{ACT}(?:的)?(?:时间|日期)(?:为|是|系|:){D}", "文书明示申请时间"),
    (rf"{AGENCY}(?:向{COURT})?(?:提出|提交|递交)(?:强制)?执行申请(?:书)?(?:的)?(?:日期|时间)(?:为|是|:){D}",
     "文书明示递交时间"),
    (rf"{AGENCY}(?:向{COURT})?于{D}(?:再次|重新|正式)?(?:提出|提交|递交)(?:强制)?执行申请(?:书)?",
     "明确提交申请"),
    (rf"{AGENCY}于{D}(?:正式|再次)?申请{COURT}(?:依法)?强制执行", "申请法院强制执行"),
    (rf"{AGENCY}(?:经催告后)?(?:于|在){D}(?:即|遂|才|再次)?申请强制执行(?=其|该|上述|案涉|[,。;\n])",
     "日期与申请强制执行直接相邻"),
]
RECEIVE = [
    (rf"(?:{COURT}(?:已)?(?:于|在)|^){D},?(?:{COURT})?(?:已)?(?:收到|接到|收悉|收取)"
     rf"(?:{AGENCY})?(?:提交|送交|递交|报送|的){{0,3}}(?:(?:强制)?执行申请(?:书)?|申请强制执行(?:书|的申请|的材料)?)",
     "法院收到执行申请"),
    (rf"{D},?{COURT}(?:收到|接到|收悉)[^。;\n]{{0,55}}?(?:强制执行申请|申请强制执行|执行申请书)",
     "日期在法院收件动作前"),
    (rf"{COURT}(?:于|在){D}(?:收到|接到|收悉)[^。;\n]{{0,55}}?(?:强制执行申请|申请强制执行|执行申请书)",
     "法院收到申请书或材料"),
]
ENTRY = {
    "受理": [
        (rf"{COURT}(?:已)?(?:于|在){D}(?:依法|正式|决定|予以)?(?:立案)?受理", "法院受理"),
        (rf"{D},?{COURT}(?:依法|正式|决定|予以)?(?:立案)?受理", "法院受理"),
    ],
    "立案": [
        (rf"{COURT}(?:已)?(?:于|在){D}(?:依法|正式|决定|予以)?(?:登记)?立案", "法院立案"),
        (rf"{D},?{COURT}(?:依法|正式|决定|予以)?(?:登记)?立案", "法院立案"),
    ],
}
SERVICE = [
    (rf"{D},?(?:{AGENCY})?(?:依法|已|将|已将|向|已向|通过|以|采用|采取)?[^。;\n]{{0,30}}?"
     rf"(?:送达(?:了)?(?:上述|前述|该|涉案)?[《\"]?[^,。;\n《》]{{0,24}}?(?:行政处罚决定(?:书)?|处罚决定书)|"
     rf"(?:行政处罚决定(?:书)?|处罚决定书)[》\"]?(?:直接|邮寄|留置|公告|依法)?送达)", "明确送达处罚决定"),
    (rf"(?:行政处罚决定(?:书)?|处罚决定书)[》\"]?(?:已)?于{D}(?:依法|直接|邮寄|留置|公告)?送达", "明确送达处罚决定"),
]
LEGAL = {
    "履行届满": [
        (rf"(?:履行期限|自行履行期限|自行拆除期限|缴纳罚款期限)(?:于|至|为|:){D}(?:届满|届至|止)", "明示履行期限届满日"),
        (rf"{D}(?:为|系)(?:其|该决定的)?(?:履行期限|自行拆除期限|缴纳罚款期限)(?:的)?(?:届满日|最后一日)", "明示履行期限届满日"),
    ],
    "救济届满": [
        (rf"(?:起诉期限|诉讼期限|复议期限|救济期限)(?:于|至|为|:|在){D}(?:届满|届至|止)", "明示救济期限届满日"),
        (rf"{D}(?:为|系)(?:其|该决定的)?(?:起诉期限|诉讼期限|救济期限)(?:的)?(?:届满日|最后一日)", "明示救济期限届满日"),
    ],
    "申请截止": [
        (rf"(?:应当|应|即|最迟|至迟|应至迟|应最迟)(?:当)?于{D}(?:日)?(?:之?前|以内|之?内){ACT}", "法院说明应申请的截止日期"),
        (rf"(?:申请强制执行(?:的)?(?:期限|截止时间|截止日期))(?:为|至|截至|截止于|届满于|:){D}", "明示申请截止日"),
    ],
}
REPEAT = re.compile(r"再[次度](?:向[^,。;\n]{0,14})?(?:申请|提交)|重新(?:向[^,。;\n]{0,14})?(?:提出|申请)|"
                    r"曾(?:经)?(?:向[^,。;\n]{0,12})?(?:申请|提出执行申请)|(?:先前|此前|前次|首次|上次)[^。;\n]{0,22}(?:申请|裁定)|"
                    r"(?:撤回|补正)[^。;\n]{0,15}(?:后|又)(?:申请|提起|重新|再次)")


def body_text(body):
    """Discard unrelated precedents and duplicated case metadata above the judgment."""
    body = re.split(r"\n\s*(?:本案法律依据|同案由重要案例|同案由其他案例)\s*\n", body, maxsplit=1)[0]
    if re.search(r"\n\s*//\s*\n", body):
        body = re.split(r"\n\s*//\s*\n", body, maxsplit=1)[-1]
    return body


def evidence(text, start, end, before=42, after=65):
    return text[max(0, start - before):end + after].replace("\n", " ").strip()


def extracted(text, patterns, kind):
    matches = {}
    for pattern, rule in patterns:
        for match in re.finditer(pattern, text, re.M):
            start, end = match.span("date")
            value, precision = parse_date(match["date"])
            if not value:
                continue
            left = text[max(0, start - 22):start]
            right = text[end:match.end()]
            if kind == "申请":
                if (re.search(r"^(?:前|后|以前|之内|内|起|届满)", right)
                        or re.search(r"(?:应当|应|最迟|至迟|不得迟于|不晚于|须|必须)于?$", left)
                        or re.search(r"(?:可|可以|应|须|应当)于$", left)):
                    continue
            if kind == "送达" and re.search(r"催告|听证|告知书|公告期满", match.group()):
                continue
            matches.setdefault((start, value), {
                "日期": value, "精度": precision, "位置": start, "规则": rule,
                "日期原文": match["date"], "证据": evidence(text, match.start(), match.end()),
            })
    return sorted(matches.values(), key=lambda item: item["位置"])


def explicit_relative_entry(text):
    """Resolve ‘同年’ only where the same sentence explicitly gives its year."""
    result = defaultdict(list)
    pat = (rf"(?P<anchor>{DAY})[^。;\n]{{0,130}}?,(?:{COURT})(?:已)?于"
           rf"(?P<relative>同年[{DIGIT_CN}]{{1,3}}月[{DIGIT_CN}]{{1,3}}日|同日)"
           r"(?:依法|决定|予以)?(?P<action>立案受理|受理|立案)")
    for m in re.finditer(pat, text):
        # A second explicit year between the anchor and reference makes the antecedent ambiguous.
        between = text[m.end("anchor"):m.start("relative")]
        if re.search(DATE, between):
            continue
        anchor, _ = parse_date(m["anchor"])
        rel = m["relative"]
        resolved = anchor if rel == "同日" else parse_date(anchor[:4] + rel[1:])[0]
        if not resolved:
            continue
        for kind in ["受理", "立案"]:
            if kind in m["action"]:
                result[kind].append({"日期": resolved, "精度": "日", "位置": m.start("relative"),
                                     "规则": "同句明确同年或同日", "日期原文": rel,
                                     "证据": evidence(text, m.start(), m.end())})
    return result


DIGIT_CN = "0-9零〇○Ｏ一二三四五六七八九十廿"


def signature(body):
    matches = list(re.finditer(rf"(?m)^[ \t]*(?P<date>{DAY})[ \t]*\n(?=[ \t]*(?:书\s*记\s*员|法官助理|本件与原本核对))", body))
    if not matches:
        return "", ""
    match = matches[-1]
    return parse_date(match["date"])[0], evidence(body, match.start(), match.end(), 25, 24)


def sanction_dates(body, numbers):
    """Use the decision number in the same clause to resolve the decision date."""
    hits = {}
    pattern = (rf"(?P<date>{DATE})(?:[, ]|依法|正式){{0,3}}"
               r"(?:(?:对|向)(?!本院|我院|本法院|法院)[^,\d。;\n]{1,45}?)?作出(?:了|的)?")
    for m in re.finditer(pattern, body):
        tail = re.split(r"[,。;\n]", body[m.end():m.end() + 125], maxsplit=1)[0]
        if any(n in key(tail) for n in numbers) and re.search(r"罚|决定", tail):
            value, precision = parse_date(m["date"])
            if value:
                hits[value] = (precision, evidence(body, m.start(), m.end() + min(len(tail), 80)))
    return hits


def all_dates(body, numbers):
    result = {kind: extracted(body, rules, kind) for kind, rules in
              {"申请": APPLY, "收件": RECEIVE, **ENTRY, "送达": SERVICE, **LEGAL}.items()}
    for kind, matches in explicit_relative_entry(body).items():
        result[kind + "相对表述"] = matches
    result["处罚"] = sanction_dates(body, numbers)
    return result
