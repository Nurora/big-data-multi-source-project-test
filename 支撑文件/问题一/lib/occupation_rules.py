# -*- coding: utf-8 -*-
"""非法占用土地识别规则（4.1 节的样本口径）。

判定单位：一项行政处罚决定（20,899 项去重后的处罚分析单位）。
判定结果：是 / 否 / 无法确定，并保留命中规则与原文证据片段，供逐条复核。

法条版本口径：
  1998/2004 年《土地管理法》  第76条=非法占用土地；第77条=农村村民非法占地建住宅
  2019 年修正（2020-01-01 施行）第77条=非法占用土地；第78条=农村村民非法占地建住宅
  条文编号在两版之间整体后移一位，因此按处罚年份选择释义。
"""
import re
import unicodedata

CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
            "十": 10, "零": 0, "〇": 0}
ARTICLE = re.compile(r"第\s*([一二三四五六七八九十百零〇\d]{1,6})\s*条")
SPLIT = re.compile(r"[。；;\n\r]")

# —— 排除类：非占用型土地违法 ——
TRANSFER = re.compile(r"非法转让|违法转让|买卖(?:或者|或)?以其他形式|买卖土地|擅自(?:将)?[^，,。；;]{0,12}(?:出让|转让|出租)")
DESTROY = re.compile(r"破坏[^，,。；;]{0,12}(?:耕地|基本农田|种植条件|耕作层)|(?:取土|挖砂|采石|采矿|建窑|建坟)[^，,。；;]{0,10}(?:耕地|基本农田)?|造成[^，,。；;]{0,8}种植条件[^，,。；;]{0,6}破坏")
RECLAIM = re.compile(r"拒不(?:履行)?[^，,。；;]{0,10}复垦|未履行[^，,。；;]{0,8}复垦义务")
CHANGE_USE = re.compile(r"(?:擅自|违法|未经批准)[^，,。；;]{0,10}改变[^，,。；;]{0,8}用途")

# —— 纳入类 ——
OCCUPY = re.compile(r"占(?:用|地)|违法用地|非法用地|违法建设|非法建设|未批先(?:占|建)|擅自[^，,。；;]{0,30}(?:使用|利用|占用|将)[^，,。；;]{0,30}土地|使用[^，,。；;]{0,10}土地")
APPROVAL_FAIL = re.compile(r"未经[^，,。；;]{0,20}批准|未经[^，,。；;]{0,10}审批|未(?:经)?办理[^，,。；;]{0,20}(?:手续|批准|审批)|未取得[^，,。；;]{0,10}合法用地手续|未获得[^，,。；;]{0,10}用地手续|没有[^，,。；;]{0,12}批准")
BUILD = re.compile(r"建设|建房|建(?:造|成|起|了)?[^，,。；;]{0,6}(?:房|楼|棚|厂|场|住宅)|动工|施工|硬底化|推填土|填土|搭建|推平|堆填|用作")
REMEDY = re.compile(r"(?:退还|交还|返还)[^，,。；;]{0,45}(?:非法|违法)占用|拆除[^，,。；;]{0,30}(?:非法|违法)占用|没收[^，,。；;]{0,30}(?:非法|违法)占用")
EXCESS = re.compile(r"超(?:出|过|越)(?:原)?(?:批准|审批|用地红线|红线|用地范围|批复|用地批复)[^，,。；;]{0,14}|"
                    r"超(?:出|过|越)[^，,。；;]{0,10}(?:用地范围|红线范围)|少批多(?:占|建)|超(?:面积|建)[^，,。；;]{0,8}(?:占用|建设|建房)")
NOISE = re.compile(r"追究刑事责任|以非法占用土地论处|依法给予处分|依照《|第[一二三四五六七八九十百零〇\d]{1,6}条")
TEMP = re.compile(r"临时用地")
TEMP_BAD = re.compile(r"到期|逾期|期满|届满|超期|未(?:经)?办理|未经批准|改变[^，,。；;]{0,4}用途|永久|续期|未恢复|未交还|未归还")
DECEIT = re.compile(r"(?<!或者)(?<!或)(?:以|采取|通过|用)(?:欺骗|隐瞒|虚假)[^，,。；;]{0,12}(?:手段)?[^，,。；;]{0,8}(?:骗取|获得|取得)[^，,。；;]{0,8}批准|"
                    r"提供虚假[^，,。；;]{0,10}(?:材料|证明)[^，,。；;]{0,10}(?:骗取|获得)[^，,。；;]{0,6}批准")
BOILER = re.compile(r"未经批准或者(?:采取欺骗手段)?骗取批准|未经批准或(?:采取欺骗手段)?骗取批准")

ORDER = ["未经批准占用", "超出批准范围或面积占用", "临时用地违法占用", "骗取批准后占用",
         "仅载明非法占用（方式未细化）", "概括援引法定情形（未区分）"]


def text(value):
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"[\s\u3000]+", "", s)


def _num(s):
    if s.isdigit():
        return int(s)
    if "百" in s:
        a, b = s.split("百", 1)
        return CN_DIGIT.get(a, 1) * 100 + (_num(b) if b else 0)
    if "十" in s:
        a, b = s.split("十", 1)
        return (CN_DIGIT.get(a, 1) if a else 1) * 10 + (CN_DIGIT.get(b, 0) if b else 0)
    return CN_DIGIT.get(s, 0)


def articles(s):
    return {_num(x) for x in ARTICLE.findall(s) if _num(x)}


def evidence(s, pattern, width=24):
    m = pattern.search(s)
    return "" if not m else s[max(0, m.start() - width):m.end() + width]


def article_verdict(arts, year):
    """按处罚年份对应的法条版本判断是否属于非法占用土地。"""
    if not arts or year is None:
        return None
    if year <= 2019:
        if 76 in arts or 77 in arts:
            return "是"
        if 78 in arts:
            return None
        if 73 in arts or 81 in arts:
            return "否"
        return None
    if 77 in arts or 78 in arts:
        return "是"
    if 81 in arts:
        return "否"
    return None


def _clauses(s):
    return [c for c in SPLIT.split(s) if len(c) >= 3]


def identify(reason, result, year):
    """返回 (判定, 行为方式, 命中规则, 证据片段, 判定强度)。"""
    r = text(reason)
    out = text(result)
    s = (r + "。" + out).strip("。")
    if len(s) < 3:
        return "无法确定", "未载明", "无有效文本", "", "无法判定"

    arts = articles(s)
    av = article_verdict(arts, year)

    # 逐子句识别占用事实：审批失败语与占用/建设语在同一子句内共现
    occ_clause = ""
    for c in _clauses(r):
        if OCCUPY.search(c) or (APPROVAL_FAIL.search(c) and BUILD.search(c)):
            occ_clause = c
            break
    if not occ_clause and OCCUPY.search(out):
        occ_clause = out
    remedy = REMEDY.search(out) or REMEDY.search(r)
    temp_bad = TEMP.search(s) and TEMP_BAD.search(s)
    occupied = bool(occ_clause or remedy or temp_bad)

    # 1) 非占用型排除（仅在无任何占用表述时生效）
    if not occupied:
        for pattern, label, rule in ((TRANSFER, "非占用（转让/出租）", "转让出租排除"),
                                     (DESTROY, "非占用（破坏耕地）", "破坏耕地排除"),
                                     (RECLAIM, "非占用（复垦义务）", "复垦义务排除"),
                                     (CHANGE_USE, "非占用（改变用途）", "改变用途排除")):
            if pattern.search(s):
                return "否", label, rule, evidence(s, pattern), "文本明示"
        if av == "否":
            return "否", "非占用（依据条文）", "依据条文指向非占用条款", evidence(s, ARTICLE), "条文推定"

    # 2) 占用事实成立后的行为方式细分
    if occupied:
        if DECEIT.search(s):
            return "是", "骗取批准后占用", "骗取批准事实", evidence(s, DECEIT), "文本明示"
        excess = EXCESS.search(r)
        if excess and not NOISE.search(r[max(0, excess.start() - 30):excess.end() + 30]):
            return "是", "超出批准范围或面积占用", "超批准表述", evidence(r, EXCESS), "文本明示"
        if temp_bad:
            return "是", "临时用地违法占用", "临时用地到期或未批", evidence(s, TEMP), "文本明示"
        if occ_clause:
            if APPROVAL_FAIL.search(occ_clause) and not BOILER.search(occ_clause):
                return "是", "未经批准占用", "未经批准占用事实", occ_clause[:90], "文本明示"
            if BOILER.search(occ_clause):
                return "是", "概括援引法定情形（未区分）", "法定情形概括表述", BOILER.search(occ_clause).group(0), "文本明示"
            if remedy:
                return "是", "仅载明非法占用（方式未细化）", "处罚结果载明退还/拆除非法占用土地", remedy.group(0), "结果推定"
            return "是", "仅载明非法占用（方式未细化）", "占用事实但未载明方式", occ_clause[:90], "文本明示"
        if remedy:
            return "是", "仅载明非法占用（方式未细化）", "处罚结果载明退还/拆除非法占用土地", remedy.group(0), "结果推定"

    # 3) 无占用表述时，用处罚依据条文补判
    if av == "是":
        decisive = min(arts & {76, 77, 78})
        return "是", "仅载明非法占用（方式未细化）", f"依据条文{decisive}", evidence(s, ARTICLE), "条文推定"
    if av == "否":
        return "否", "非占用（依据条文）", "依据条文指向非占用条款", evidence(s, ARTICLE), "条文推定"
    return "无法确定", "未载明", "无可判定线索", "", "无法判定"
