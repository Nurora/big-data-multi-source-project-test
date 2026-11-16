"""Evidence-based extraction of duties and the requested scope of enforcement."""
import re
from collections import defaultdict

from ledger import body_text, key, norm

UNKNOWN = "信息不足"
LABELS = {
    "罚款": r"(?<!加处)(?<!免予)(?<!不予)(?<!免除)(?<!不再)罚款",
    "退还土地": r"(?:退还|退回|交还|返还|归还)[^。;\n]{0,26}?(?:土地|地块|用地)|(?:土地|地块|用地)[^。;\n]{0,12}?(?:退还|退回|交还|返还|归还)",
    "拆除建筑物或设施": r"(?:责令|限期|自行|立即|强制|予以|负责|组织实施|进行)(?:[^。;,\n]{0,13}?)拆除|拆除[^。;\n]{0,85}?(?:建筑物|构筑物|设施|房屋|厂房|建筑|围墙|棚)|(?:地上建筑物|设施|建筑物|建\(构\)筑物)[^。;,\n]{0,16}?(?:自行|强制)?拆除",
    "恢复土地原状": r"(?:恢复|回复|还原)[^。;,\n]{0,18}?(?:原状|原貌|种植条件|耕种条件|耕作条件|地貌|种植功能|耕地质量|土地原状)",
    "复垦": r"(?:土地复垦|复垦|复耕)(?![费金基金])",
    "没收建筑物或设施": r"没收(?![^。;,\n]{0,10}违法所得)[^。;\n]{0,85}?(?:建筑物|构筑物|建\(构\)筑物|设施|房屋|建筑|厂房|硬化地面|附着物)",
    "其他明确义务": r"没收[^。;,\n]{0,12}违法所得|(?:责令|限期|必须)(?:立即)?(?:停止[^。;,\n]{0,12}(?:违法行为|施工|建设|用地)|改正|治理|清除|复绿|迁出|补办)|缴纳[^。;,\n]{0,10}(?:复垦费|开垦费)|加处(?:滞纳金|罚款)",
}
PATTERNS = {name: re.compile(pattern) for name, pattern in LABELS.items()}
RIGHTS = re.compile(r"(?:如|若)不服|不服本(?:处罚|决定)|逾期不(?:缴纳|履行|拆除)|"
                    r"(?:依法)?申请行政复议|可(?:以)?向[^。;\n]{0,22}提起行政诉讼|"
                    r"市国土局已依法将前述|本院(?:认为|查明)|按照《中华人民共和国行政处罚法》第")
ITEM = re.compile(r"(?:^|(?<=[。;:,\n])|(?<=\s))\s*(?:"
                  r"(?P<num>[1-9]\d?)[.、:](?!\d)|(?P<cn>[一二三四五六七八九十]{1,3})[、.]|"
                  r"\((?P<br>[1-9]\d?|[一二三四五六七八九十]{1,3})\))")
NUMBER_TEXT = r"[一二三四五六七八九十0-9]{1,3}"
REF = re.compile(rf"(?:第\s*{NUMBER_TEXT}(?:\s*[、,及和与]\s*(?:第\s*)?{NUMBER_TEXT})*项)"
                 rf"(?:\s*[、,及和与]?\s*第\s*{NUMBER_TEXT}项)*")
REQUEST = re.compile(
    r"(?:申请(?:执行)?人(?:向本院)?(?:提出的)?(?:申请)?(?:强制)?执行(?:的)?(?:事项|内容)(?:如下|为|是)?\s*[:：]?)"
    r"|(?:(?:其|现|又|再次|遂|该局)?\s*向(?:本院|我院|本法院)(?:正式|依法|重新|再次)?"
    r"(?:申请(?:依法)?(?:强制)?执行|提出(?:强制)?执行申请|递交(?:强制)?执行申请(?:书)?))"
    r"|(?:申请执行人(?:请求|申请)(?:本院|依法)?(?:强制)?执行)"
    r"|(?:(?:现|特)申请(?:依法)?(?:强制)?执行(?:以下|下列|该|上述|[:：]))"
)
JUDGE_STOP = re.compile(r"(?:\s*(?:经审查(?:查明)?|本院认为|本院查明|裁判结果|裁定如下|判决如下|"
                        r"本院(?:于[^。;\n]{0,30})?(?:依法)?(?:立案|受理)|现已审查|证据如下|"
                        r"(?:被申请执行人|被执行人)(?:辩称|陈述|称|未提出)|另查明))")
JUDGE_SECTION = re.compile(r"(?:裁判结果\s|[。;\n]\s*(?:裁定|判决)如下\s*[:：]|"
                           r"(?:一|二)、\s*(?:准予|不准予|驳回|不予)(?:强制)?执行)")
APPLICANT_LIMIT = re.compile(r"(?:,|\n|。|;)\s*(?:申请执行人|申请人|申请机关|该局)"
                             r"(?:(?!向本院).){0,45}?(?:已将|送达|催告|提交的证据|作出了|查明|经查|于\d{4}年.{1,16}作出)")
NONREQUEST = re.compile(r"^(?:[, :]*)(?:的|前|后)(?:申请|书|材料|日|应|须|,|。|$)|"
                        r"^(?:[, :]*)(?:即|是指)?(?:由|按|应当|应于)(?:人民法院|当事人|申请执行人)")
SCOPE_PART = re.compile(r"(?:之中|其中|第.{0,12}项中)[^。;\n]{0,35}?(?:部分|除|关于)|"
                        r"(?:部分|剩余|未履行|未缴纳|尚未履行)(?:的)?(?:处罚|事项|义务|内容)")
NO_EXHAUSTIVE = re.compile(r"等(?:处罚|事项|义务|内容)|(?:部分|有关|相关)(?:处罚|义务|事项)|"
                           r"(?:另|尚)有[^。;\n]{0,12}事项|并(?:提交|提供)证据")
SCOPE_FULL = re.compile(r"(?:全部|所有|各项)(?:的)?(?:行政处罚(?:决定)?|处罚内容|处罚事项|义务)|"
                        r"(?:处罚决定(?:书)?|处罚事项)(?:中|的)?(?:全部|所有)(?:内容|事项|义务)?")
EXCLUDED_FINE = re.compile(r"(?:除|不含|撤回|放弃|不再申请|不申请)[^。;]{0,20}?罚款|罚款[^。;]{0,8}?(?:之外|以外)")


def integer(value):
    if value.isdigit():
        return int(value)
    symbols = "零一二三四五六七八九"
    if "百" in value:
        a, b = value.split("百", 1)
        return integer(a) * 100 + (integer(b.lstrip("零")) if b.lstrip("零") else 0)
    if "十" in value:
        a, b = value.split("十", 1)
        return (integer(a) if a else 1) * 10 + (integer(b) if b else 0)
    return symbols.index(value) if value in symbols and value else 0


def combo(values):
    return "＋".join(label for label in LABELS if label in values)


def matches(text):
    """Recognize positive operative wording inside a bounded penalty or request."""
    hit = {}
    for label, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            left = text[max(0, m.start() - 22):m.start()]
            right = text[m.end():m.end() + 14]
            if re.search(r"(?:未|免予|不予|已(?:经)?履行|无需|不再|不包含|不包括|不申请(?:执行)?)$", left):
                continue
            if label == "罚款" and (EXCLUDED_FINE.search(text) or re.match(r"(?:已缴|已交|已履行|缴清|以外)", right)):
                continue
            if label == "复垦" and re.search(r"缴纳[^。;]{0,5}$", left):
                continue
            hit[label] = text[max(0, m.start() - 12):m.end() + 19].strip()
            break
    return hit


def numbered(text):
    hits = list(ITEM.finditer(text))
    ids = [integer(next(x for x in m.groups() if x)) for m in hits]
    if not ids or ids != list(range(1, len(hits) + 1)):
        return {}
    return {i: text[m.end():hits[j + 1].start() if j + 1 < len(hits) else len(text)].strip()
            for j, (i, m) in enumerate(zip(ids, hits))}


def penalty_text(text, source, explicit_field=False):
    text = norm(text).strip()
    bounded = RIGHTS.split(text, maxsplit=1)[0].strip()
    items = numbered(bounded)
    detected = matches(bounded)
    item_hits = {i: matches(part) for i, part in items.items()}
    if items and any(not hits for hits in item_hits.values()):
        complete = False
    else:
        complete = bool(detected and explicit_field and not NO_EXHAUSTIVE.search(bounded)
                        and not re.search(r"(?:无具体信息|未载明|详见|\.{2,}|…|同上|前述|上述|按规定)$", bounded.rstrip("。; ")))
    quality = "可识别的处罚结果" if detected else "无法识别" if text and text not in {"无具体信息", "未载明"} else "未载明"
    return {"text": text, "source": source, "labels": detected, "complete": complete, "status": quality,
            "items": items, "item_hits": item_hits}


def same_case_decision(text, decision_numbers):
    """Find a numbered decision quoted in the findings, if its number is identifiable."""
    if not text or not decision_numbers:
        return None
    before_order = JUDGE_SECTION.split(text, maxsplit=1)[0]
    finder = re.compile(r"(?:作出|决定作出|决定对[^。;\n]{1,65}?作出)"
                        r"(?:以下|如下)(?:的)?(?:行政)?处罚(?:决定)?\s*:")
    for m in finder.finditer(before_order):
        left = key(before_order[max(0, m.start() - 600):m.start()])
        if not any(d in left for d in decision_numbers):
            continue
        after = before_order[m.end():m.end() + 1350]
        limited = re.split(r"(?:本院认为|本院查明|申请执行人(?:已|于|依法|在|向)|申请人(?:已|于|依法|在|向)|"
                           r"被(?:申请)?执行人在法定期限|经催告|如不服|另查明|本院经审查)", after, maxsplit=1)[0]
        parsed = penalty_text(limited, "S2正文引述的处罚分项", True)
        if len(parsed["items"]) >= 2 and all(parsed["item_hits"].values()):
            return parsed
    return None


def references(text):
    return {integer(n) for m in REF.finditer(text) for n in re.findall(NUMBER_TEXT, m.group())}


def scope_from_requests(text, penalty, judicial_penalty=None, excerpt=False):
    text = norm(text)
    text = text if excerpt else body_text(text)
    before_order = JUDGE_SECTION.split(text, maxsplit=1)[0]
    out = []
    present = False
    full_scope = False
    proven_refs = set()
    for m in REQUEST.finditer(before_order):
        left = before_order[max(0, m.start() - 40):m.start()]
        if re.search(r"(?:应当|可以|可|依法应|有权|必须|须|未|拟|将|应|重新|今后|日内|日前)$", left):
            continue
        if re.search(r"(?:诉讼法|强制法|规定|期限届满)[^。;\n]{0,26}(?:应当|可以|应|有权)[^。;\n]{0,18}$", left):
            continue
        tail = before_order[m.end():m.end() + 850]
        if NONREQUEST.match(tail):
            continue
        # Keep numbered lists after the anchor, but stop when the narrative
        # switches to findings, service, legal evaluation or a new event.
        tail = JUDGE_STOP.split(tail, maxsplit=1)[0]
        tail = APPLICANT_LIMIT.split(tail, maxsplit=1)[0]
        tail = re.split(r"(?:[。\n]\s*(?:又查|查明|根据|依据|审理查明|为此|现已|原告|"
                        r"事实和理由|申请强制执行的理由|行政机关认为|经核查)|"
                        r"[,。;\n]\s*(?:现该|现涉案|在上述|鉴于|因此|属于逾期申请|符合法律规定|"
                        r"已超过(?:上述|法定)|不符合(?:法定|法律)|应予驳回))",
                        tail, maxsplit=1)[0].strip()
        plain = re.split(r"(?:[。\n]\s*(?:申请执行人于|其于|该局于|申请执行人向|申请执行人[^。;\n]{0,6}认定|"
                         r"被(?:申请)?执行人于|申请执行人作出)|申请执行人申请强制执行的(?:事项|内容))",
                         tail, maxsplit=1)
        # "要求由其组织实施强制执行……" at the beginning still belongs to this request.
        tail = plain[0] if plain[0] else tail
        if not tail:
            present = True
            continue
        # A period normally ends the request. Preserve consecutive enumerated
        # request items and a request clause immediately after a generic lead-in.
        chunks = re.split(r"(?<=。)|\n+", tail)
        clause = chunks[0]
        for chunk in chunks[1:]:
            if not chunk.strip():
                continue
            if re.match(r"\s*(?:[1-9一二三四五六七八九十][.、](?!\d)|\([1-9一二三四五六七八九十]\)|"
                        r"(?:要求|请求|具体为|申请事项))", chunk):
                clause += chunk
            else:
                break
        clause = clause.strip()
        present = True
        if re.match(r"^[, :]*(?:后|前|时)(?:[,。; ]|$)", clause):
            continue
        # Decision citation may repeat the party and date. Its non-operative
        # title is removed while the quoted request items after it remain.
        hits = matches(clause)
        refs = references(clause)
        is_partial = bool(SCOPE_PART.search(clause) and (hits or EXCLUDED_FINE.search(clause)))
        proof = {}
        scoped = False
        if refs and not is_partial:
            cited = judicial_penalty or penalty
            if (cited["complete"] or judicial_penalty) and refs.issubset(cited["item_hits"]):
                item_labels = {k: f"第{i}项 {v}" for i in sorted(refs) for k, v in cited["item_hits"][i].items()}
                if item_labels and all(cited["item_hits"][i] for i in refs):
                    proof.update(item_labels)
                    scoped = True
                    proven_refs.update(i for i in refs if i in penalty["item_hits"]
                                       and set(cited["item_hits"][i]) == set(penalty["item_hits"][i]))
        if SCOPE_FULL.search(clause) and penalty["complete"] and not is_partial:
            proof.update(penalty["labels"])
            scoped = True
            full_scope = True
        if hits:
            proof.update(hits)
            explicit_list = (not refs or bool(re.search(r"事项(?:如下|为)|内容(?:如下|为)|[:：]", m.group() + clause))
                             or bool(re.search(r"第[^。;]{1,15}项(?:关于|[“\"]|[, :]+即)", clause)))
            scoped = scoped or (explicit_list and not NO_EXHAUSTIVE.search(clause)
                                and not re.search(r"撤回(?:全部|部分)?申请|申请撤回", clause)
                                and len(clause) < 825)
        if proof:
            out.append((proof, scoped, before_order[m.start():m.end()] + clause,
                        "正文直接列明" if hits else "明确申请项号／全部范围后映射"))
        elif refs:
            out.append(({}, False, before_order[m.start():m.end()] + clause, "申请项号无法可靠映射"))
    positives = {}
    for hits, _, _, _ in out:
        positives.update(hits)
    complete_sets = [set(hits) for hits, complete, _, _ in out if complete]
    closed = bool(positives and any(s == set(positives) for s in complete_sets))
    if excerpt:
        # Excerpts may document a positive request but cannot establish that
        # the other requests in that judgment have been fully enumerated.
        closed = False
    status = "范围可判定" if closed else "仅有明确正例" if positives else "提及申请但范围不明" if present else "未找到申请事项陈述"
    return {"labels": positives, "closed": closed, "status": status,
            "item_refs": proven_refs, "full_scope": full_scope,
            "evidence": "｜".join(dict.fromkeys(p for _, _, p, _ in out))[:2300],
            "rule": "｜".join(dict.fromkeys(rule for _, _, _, rule in out))}


VIOLATION = [
    ("拒不复垦", r"拒不(?:履行)?[^。;\n]{0,10}复垦"),
    ("非法转让", r"非法转让|违法转让|买卖土地|买卖或者以其他形式非法转让"),
    ("超批准占地", r"超(?:出|过|越)(?:批准|审批|核准|用地红线|用地范围)[^。;\n]{0,20}|多占[^。;\n]{0,12}土地"),
    ("临时用地违法", r"临时用地[^。;\n]{0,20}(?:未|超|逾期|永久|改变)|未经批准[^。;\n]{0,12}临时用地"),
    ("破坏耕地或农用地", r"(?:破坏|毁坏)[^。;\n]{0,16}(?:耕地|农用地|种植条件|耕作层)|造成[^。;\n]{0,10}种植条件破坏"),
    ("擅自改变用途", r"(?:擅自|违法|未经批准)[^。;\n]{0,12}改变[^。;\n]{0,12}用途"),
    ("未经批准占地", r"非法占(?:用|地)|违法占(?:用|地)|擅自(?:占用|占地|使用[^。;\n]{0,22}土地)|未(?:经|办理)[^。;\n]{0,25}(?:批准|用地手续|用地审批)[^。;\n]{0,25}(?:占用|使用|动工|建设)"),
]


def violation(value):
    text = norm(value)
    for label, pattern in VIOLATION:
        m = re.search(pattern, text)
        if m:
            return label, text[max(0, m.start() - 13):m.end() + 18]
    return "", ""


def land_group(value):
    text = norm(value)
    if not text or text in {"无具体信息", "未明确", "无"}:
        return ""
    mapping = [
        ("耕地", r"耕地|水田|旱地|水浇地|基本农田"),
        ("园地", r"园地|果园|茶园"),
        ("林地", r"林地|有林地"),
        ("建设用地", r"建设用地|城镇住宅|农村宅基地|工矿用地"),
        ("其他农用地", r"农用地|鱼塘|养殖|草地|坑塘"),
        ("未利用地", r"未利用地|裸地|荒地"),
    ]
    tokens = re.split(r"[、,;/及和]", text)
    groups = {name for token in tokens for name in
              [next((name for name, pat in mapping if re.search(pat, token)), "其他地类")]}
    return "多地类" if len(groups) > 1 else next(iter(groups))


def use_group(value):
    text = norm(value)
    if not text or text in {"无具体信息", "未明确", "无"}:
        return ""
    mapping = [
        ("住宅或房屋", r"住宅|自建房|房屋|构筑物"),
        ("工业或仓储", r"工业|厂房|仓|堆场"),
        ("道路或公共设施", r"道路|公共设施|交通|学校|停车|市政"),
        ("平整或硬化", r"平整|硬化|堆填"),
        ("商业经营", r"商业|经营|商铺|餐饮"),
        ("农业或养殖", r"农业|种植|养殖"),
    ]
    return next((label for label, pattern in mapping if re.search(pattern, text)), "其他用途")


def numeric(value, *, zero=False):
    try:
        amount = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if amount < 0 or (amount == 0 and not zero) or not amount < float("inf"):
        return None
    return amount
