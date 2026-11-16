# -*- coding: utf-8 -*-
"""
landuse.py —— 原地类与违法后用途文本抽取规则（源自 p2_text_extract.py）：土地原地类 / 违法后用途 / 是否违法建设 的自动文本抽取
====================================================================================
输入：01_行政处罚主表.csv 的「处罚事由_原文」「处罚结果_原文」（只读，不改写原文）
输出：
  work/text_extract.pkl                     每处罚项一行，供后续模块 join
  out/tables/02_文本抽取_逐条_带原文依据.csv  逐条结果 + 原文依据片段（可核对）
  out/tables/02_文本抽取_覆盖率.csv          字段覆盖率（分样本组）
  out/tables/02_地类词表映射.csv             原始地类词 → 主类 的映射表（可审计、可复算）
  out/tables/02_抽样核验清单.csv             分层随机抽样，供逐条人工/大模型复核

规则要点（不猜、不补、不推测）：
  1. 先按标点切子句；含"规划"的子句从该关键词处截断，避免把"规划用途/规划地类"误当成原地类或违法用途。
  2. 原地类证据分三档：
     R-a 直接地类表述（"土地利用现状地类为…""地类:…""原地类为…""现状为…""变更前是…"）
     R-b 面积—地类共现（"940平方米草地""水田153平方米"），常见于罚款分档计算，仍是现状地类信息
     R-c 处罚结果中的处置对象描述（"没收…沥青道路""拆除…篮球场"）
  3. "农用地/一般农用地/非耕农用地/其他农用地/设施农用地"等集合词只记为「农用地(未细分)」，
     不拆成耕地/园地/林地——拆分即为推测。
  4. 面积可解析时用面积加权取主类；多类并列且无面积时记「多类并列(未分面积)」；无线索记「未知或未提及」。
  5. 用途只在"事实描述"语境取（用于/用作/作…用途/进行…建设/建设…），法条引用与处罚依据一律不取。
"""
import os
import re
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# 0. 词表
# ---------------------------------------------------------------------------
# 原始地类词 → 主类。主类口径：耕地 / 林地 / 园地 / 建设用地 / 其他土地 / 农用地(未细分)
LAND_MAP = {
    # —— 耕地 ——
    "耕地": "耕地", "水田": "耕地", "水浇地": "耕地", "旱地": "耕地", "菜地": "耕地",
    "稻田": "耕地", "垌田": "耕地", "田坎": "耕地", "基本农田": "耕地", "永久基本农田": "耕地",
    "稻水田": "耕地", "灌溉水田": "耕地", "望天田": "耕地",
    # —— 园地 ——
    "园地": "园地", "果园": "园地", "茶园": "园地", "桑园": "园地", "橡胶园": "园地",
    "其它园地": "园地", "其他园地": "园地", "可调整果园": "园地", "柑桔园": "园地",
    "龙眼": "园地", "荔枝园": "园地", "苗圃": "园地", "花圃": "园地", "花卉": "园地",
    "果场": "园地", "梅林": "园地", "李园": "园地",
    # —— 林地 ——
    "林地": "林地", "有林地": "林地", "灌木林地": "林地", "其他林地": "林地",
    "乔木林地": "林地", "竹林地": "林地", "竹林地": "林地", "疏林地": "林地",
    "幼林地": "林地", "针叶林": "林地", "阔叶林": "林地", "生态公益林": "林地", "树林": "林地",
    # —— 建设用地 ——
    "建设用地": "建设用地", "城镇": "建设用地", "建制镇": "建设用地", "城市": "建设用地",
    "村庄": "建设用地", "农村居民点": "建设用地", "独立工矿": "建设用地", "采矿用地": "建设用地",
    "工矿仓储用地": "建设用地", "公路用地": "建设用地", "农村道路": "建设用地",
    "城镇村道路用地": "建设用地", "交通用地": "建设用地", "水工建筑用地": "建设用地",
    "科教文卫": "建设用地", "科教文卫用地": "建设用地", "特殊用地": "建设用地",
    "机场": "建设用地", "铁路用地": "建设用地", "港口码头用地": "建设用地",
    "宅基地": "建设用地", "集体建设用地": "建设用地", "商服用地": "建设用地",
    "工业用地": "建设用地", "仓储用地": "建设用地", "住宅用地": "建设用地",
    "公共设施用地": "建设用地", "公园绿地": "建设用地", "旅游用地": "建设用地",
    # —— 其他土地（含水域、草地、未利用地）——
    "未利用地": "其他土地", "裸地": "其他土地", "裸土地": "其他土地", "裸岩石砾地": "其他土地",
    "草地": "其他土地", "其他草地": "其他土地", "天然牧草地": "其他土地", "人工牧草地": "其他土地",
    "盐碱地": "其他土地", "沼泽地": "其他土地", "沙地": "其他土地", "Gobi": "其他土地",
    "河流水面": "其他土地", "湖泊水面": "其他土地", "水库水面": "其他土地",
    "坑塘水面": "其他土地", "坑塘": "其他土地", "养殖水面": "其他土地", "可调整养殖水面": "其他土地",
    "沟渠": "其他土地", "水坑": "其他土地", "滩涂": "其他土地", "河口": "其他土地",
    "鱼塘": "其他土地", "堤防": "其他土地", "农田水利用地": "其他土地",
    # —— 集合词：只到"农用地(未细分)"，不拆细 ——
    "农用地": "农用地(未细分)", "一般农用地": "农用地(未细分)", "非耕农用地": "农用地(未细分)",
    "其他农用地": "农用地(未细分)", "其它农用地": "农用地(未细分)", "设施农用地": "农用地(未细分)",
    "可调整农用地": "农用地(未细分)", "非耕地及非可调整的农用地": "农用地(未细分)",
    "非可调整的农用地": "农用地(未细分)",
}
# 主类输出顺序（桑基图左列）
LAND_MAIN_ORDER = ["耕地", "园地", "林地", "建设用地", "其他土地", "农用地(未细分)",
                   "多类并列(未分面积)", "未知或未提及"]
# 明确不作为原地类识别的规划分区词（出现在"规划"语境内，靠截断+黑名单双重防御）
PLAN_WORDS = ["规划", "国土空间总规", "用途管制", "控规", "基本农田保护区", "农地区",
              "建设用地区", "允许建设区", "有条件建设区", "限制建设区", "禁止建设区"]
TRIG_LAND = (r"(土地利用现状分类|土地利用现状地类|土地利用现状|现状地类|原地类|建设前地类|地类|"
             r"土地现状|现状|变更前|地类情况|地块地类|地类构成)")
# 违法后用途词表：主类 → [正则]
USE_PATTERNS = {
    "住宅/房屋建设": [
        r"住宅", r"住房", r"民居", r"民房", r"别墅", r"自建.{0,2}房", r"楼房", r"住宅楼", r"居民楼",
        r"出租房", r"出租屋", r"安居房?", r"保障性?安居", r"商品房", r"住宅小[区区]", r"农房",
        r"(?:建|盖|砌).{0,4}(?:房|屋|楼房)", r"建(?:设)?房(?:屋|子|棚)?", r"房屋", r"住宅用途", r"居住用途",
    ],
    "工业厂房": [
        r"厂房", r"车间", r"工厂", r"厂区", r"工业(?:园|区|厂房|用途|生产)", r"加工[厂场坊]", r"制造",
        r"生产厂房", r"制衣", r"五金厂", r"电子厂", r"水泥厂", r"砖厂",
        r"搅拌站", r"石场", r"石材厂", r"工业用途", r"生产工场",
    ],
    "仓库/仓储设施": [
        r"仓库", r"仓储", r"堆场", r"物流", r"货运", r"存货", r"囤积", r"储场", r"配送", r"冷库",
    ],
    "商业经营设施": [
        r"商铺", r"店面", r"门店", r"铺位", r"商场", r"超市", r"市场", r"商业", r"餐饮", r"酒楼",
        r"酒家", r"饭店", r"农庄", r"农[业家]乐", r"酒店", r"宾馆", r"民宿", r"加油站", r"充电站",
        r"洗车[场店房]", r"4S[店]?", r"娱乐", r"会所", r"写字楼", r"办公", r"综合楼?", r"经营", r"销售",
        r"交易", r"培训班?", r"游乐场?", r"烧烤", r"大排档", r"临时摊", r"摊贩", r"市集",
    ],
    "道路及其他基础设施": [
        r"道路", r"公路", r"村道", r"路面", r"人行道", r"硬(?:底|化)化?", r"水泥(?:地面|地|化)",
        r"桥(?:梁|墩)", r"立交桥", r"隧道", r"广场", r"公园", r"绿地", r"停车场", r"充电桩",
        r"变电站?", r"电力", r"供电", r"通讯", r"通信", r"基站", r"管网", r"供水", r"排水",
        r"排污", r"污水", r"泵站", r"排涝站", r"泵房", r"水利", r"灌渠", r"灌溉", r"堤围", r"护坡",
        r"垃圾", r"公厕", r"卫生站", r"学校", r"幼儿园", r"医院", r"文化室", r"文化广场",
        r"体育[馆场]", r"篮球场", r"运动场", r"足球场", r"羽[毛]球", r"健身", r"铁路", r"高速",
        r"地铁", r"公交", r"候车", r"消防", r"执勤", r"安防", r"气象", r"市政", r"管廊",
    ],
    "其他用途": [
        r"填土", r"堆填", r"平整", r"推平", r"晒谷", r"养殖", r"猪[场棚栏舍]", r"养鸡", r"鸭场",
        r"禽畜", r"畜牧", r"种植", r"栽培", r"挖[砂土石]", r"取土", r"采矿", r"开采", r"堆放",
        r"堆料", r"大棚", r"温室", r"看护房", r"临时用地", r"临时棚", r"临时设", r"围挡", r"围栏",
        r"围墙", r"公[墓园]", r"骨灰[楼堂]", r"坟墓", r"墓地", r"祠堂", r"庙宇", r"寺庙", r"教堂",
    ],
}
BUILD_PAT = (r"建设|建筑物|构筑物|新建|重建|改建|扩建|动工|施工|搭建|建[造设成]|盖房|建房|"
             r"硬底化|硬化|铺[设装]|道路|厂房|棚|房|楼|基础|设施|安装|浇筑")
NONBUILD_PAT = r"堆放|填土|推平|平整|取土|挖[砂土]|采矿|开荒|种植|耕种|闲置|围[挡栏墙]"

CLAUSE_SPLIT = re.compile(r"[。；;，,！!？?\n\r|]")
NUM = r"[\d][\d,\.]*|\*+\.\*+|\*+"
UNIT = r"(?:平方米|平米|公亩|㎡|m2|M2|m²|亩|公顷|ha)"
# 地类噪声：法条/裁量标准/罚款分档表述里出现的"耕地/农用地/未利用地"不是本案地块的地类
LAND_NOISE = re.compile(r"(?:自由裁量|裁量权|实施标准|实施基准|实施办法|罚款额|开垦费|倍以上|倍以下|"
                        r"不良后果|工作规程|查处工作|土地管理法|土地管理条例|实施条例|保护条例|"
                        r"第\s*[一二三四五六七八九十百零〇\d]{1,6}\s*条|规定|依据|序号\d)")
# "占用/使用 + 地类词"（无面积也可，如"擅自占用农用地建设农村住宅"）
OCCUPY_PAT = re.compile(r"(?:非法)?(?:占用|使用|侵占|占)\s*[^\s，,、。;；()（）]{0,8}?(?:%s)" %
                        "|".join(re.escape(t) for t in sorted(LAND_MAP, key=len, reverse=True)))
# 面积—地类相邻（正向"水田3496.03平方米" / 反向"141平方米集体园地"）
ADJ_FWD = re.compile(r"(?:%s)[^\d，,。;；]{0,6}(%s)" % ("|".join(re.escape(t) for t in sorted(LAND_MAP, key=len, reverse=True)), NUM))
ADJ_REV = re.compile(r"(%s)\s*(?:%s)[^\d，,。;；]{0,4}(?:%s)" % (NUM, UNIT,
                      "|".join(re.escape(t) for t in sorted(LAND_MAP, key=len, reverse=True))))


# ---------------------------------------------------------------------------
# 1. 文本预处理
# ---------------------------------------------------------------------------
def clean(s):
    if not isinstance(s, str):
        return ""
    s = re.sub(r'HYPERLINK\s+"[^"]*"', "", s)
    s = re.sub(r"https?://\S+", "", s)
    s = re.sub(r"\\l\s|\\s|\\o|\'", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def plan_cut(clause):
    """子句内含规划词时，从规划词处截断（保留其前的现状信息）。"""
    for w in PLAN_WORDS:
        i = clause.find(w)
        if i > 0:
            clause = clause[:i]
        elif i == 0:
            return ""
    return clause


def clauses(text):
    return [c.strip() for c in CLAUSE_SPLIT.split(text) if c and len(c.strip()) > 1]


# ---------------------------------------------------------------------------
# 2. 原地类
# ---------------------------------------------------------------------------
LAND_TOKENS = sorted(LAND_MAP.keys(), key=len, reverse=True)
LAND_RE = re.compile("|".join(re.escape(t) for t in LAND_TOKENS))
TRIG_LAND_RE = re.compile(TRIG_LAND)


def _area_after(c2, end):
    """token 之后 window 内的面积（平方米）；脱敏数字返回 (None, True)。"""
    tail = c2[end:end + 18]
    m = re.match(r"^\s*[(（]?[^\d]{0,6}(%s)\s*(%s)" % (NUM, UNIT), tail)
    if not m:
        return None, False
    v, u = m.group(1), m.group(2)
    if "*" in v:
        return None, True
    try:
        return round(float(v.replace(",", "")) * unit_factor(u), 2), False
    except Exception:
        return None, False


def _area_before(c2, start):
    head = c2[max(0, start - 22):start]
    m = re.search(r"(%s)\s*(%s)[^\d，,。;；]{0,4}$" % (NUM, UNIT), head)
    if not m:
        return None, False
    v, u = m.group(1), m.group(2)
    if "*" in v:
        return None, True
    try:
        return round(float(v.replace(",", "")) * unit_factor(u), 2), False
    except Exception:
        return None, False


def find_land(rec):
    """
    返回 (主类, 提及类集合, {类: 面积}, 依据片段, 判定规则, 是否含脱敏面积, 原文地类词)
    规则优先级：R1 直接地类表述 > R2 面积—地类共现 > R3 处罚结果处置对象 > R4 占用/使用宾语。
    """
    areas = {}      # cls -> set(面积)，跨子句去重（同一面积在事实与罚款分档里会重复出现）
    seen = {}       # cls -> 是否出现过无面积的同地类词
    words = {}      # 原文词 -> 主类
    ev, rules = [], []
    masked_any = False
    for src, rule_name in (("事由", None), ("结果", "R3处罚结果处置对象")):
        txt = rec.get(src, "")
        if not txt:
            continue
        for c in clauses(txt):
            c2 = plan_cut(c)
            if len(c2) < 3 or LAND_NOISE.search(c2):
                continue
            trig = bool(TRIG_LAND_RE.search(c2)) and re.search(r"(为|是|[:：]|含|属|分别|全部)", c2)
            adj = bool(ADJ_FWD.search(c2) or ADJ_REV.search(c2))
            occ = bool(OCCUPY_PAT.search(c2))
            if not (trig or adj or occ):
                continue
            if rule_name:
                rule = rule_name
            elif trig:
                rule = "R1直接地类表述"
            elif adj:
                rule = "R2面积-地类共现"
            else:
                rule = "R4占用/使用宾语"
            found = False
            for m in LAND_RE.finditer(c2):
                tok, cls = m.group(0), LAND_MAP[m.group(0)]
                a, mk = _area_after(c2, m.end())
                if a is None:
                    a2, mk2 = _area_before(c2, m.start())
                    a, mk = (a2, mk2) if a2 is not None else (None, mk or mk2)
                masked_any = masked_any or mk
                areas.setdefault(cls, set())
                if a is not None:
                    areas[cls].add(a)
                else:
                    seen[cls] = True
                words.setdefault(tok, cls)
                found = True
            if found:
                rules.append(rule)
                if len(ev) < 5:
                    ev.append(("[" + rule + "] ") + c2[:110])
    if not areas:
        return ("未知或未提及", "", {}, "", "无", False, "")
    # 集合词与细类并存时，只保留细类（把"农用地"拆成耕地/园地/林地就是推测，因此不拆；
    # 但若原文已给出细类，集合词不再单独计入主类）
    specific = [k for k in areas if k != "农用地(未细分)"]
    keys = specific if specific else list(areas)
    a_tot = {k: sum(areas[k]) for k in keys if areas[k]}
    if len(keys) == 1:
        main = keys[0]
    elif a_tot:
        mx = max(a_tot.values())
        top = sorted([k for k, v in a_tot.items() if abs(v - mx) < 1e-6])
        if len(top) == 1:
            main = top[0]
        else:  # 面积并列：耕地优先（法定保护等级最高），否则记为并列
            main = "耕地" if "耕地" in top else "多类并列(未分面积)"
    else:
        main = "多类并列(未分面积)"
    rule_out = "/".join(dict.fromkeys(rules)) if rules else "无"
    return (main, "/".join(sorted(keys)), a_tot, " ‖ ".join(dict.fromkeys(ev)), rule_out,
            masked_any, "/".join(sorted(words)))


def unit_factor(u):
    return {"平方米": 1.0, "平米": 1.0, "㎡": 1.0, "m2": 1.0, "M2": 1.0, "m²": 1.0,
            "公亩": 100.0, "亩": 666.6666667, "公顷": 10000.0, "ha": 10000.0}.get(u, 1.0)


# ---------------------------------------------------------------------------
# 3. 违法后用途
# ---------------------------------------------------------------------------
USE_RE = {k: re.compile("|".join(v)) for k, v in USE_PATTERNS.items()}
PRIO = {"工业厂房": 1, "仓库/仓储设施": 2, "住宅/房屋建设": 3, "商业经营设施": 4,
        "道路及其他基础设施": 5, "其他用途": 6}
# T1：显式用途表述。触发词 + 其后 0~24 字窗口里出现用途类别词，即认为该窗口描述了"违法后用途"
USE_TRIG = re.compile(r"用作|用于|作为|作|进行|实施|搞|建设|建成|建|搭建|修建|硬底化|硬化")
# 处罚结果中的处置对象（如"没收…沥青道路""拆除…篮球场"）作为补充证据
OBJ_IN_RESULT = re.compile(r"(?:没收|拆除)[^。，,;；]{0,40}?"
                           r"(厂房|仓库|仓储|住宅|住房|房屋|楼房|商铺|市场|道路|硬底化|篮球场|广场|公园|"
                           r"停车场|锌铁棚|铁皮棚|建筑物|板房|棚)")
# 明确不是用途的语境：法条引用、处罚依据、责令内容
NOISE = re.compile(r"(?:违反|依照|根据|规定|第\s*[一二三四五六七八九十百零〇\d]{1,6}\s*条|"
                   r"处罚依据|执法依据|法律依据|违法依据|拒不|送达|告知|听证|复议|诉讼)")


def _cat_of(window):
    """在窗口内找类别；同一窗口多类时取类别词出现位置最靠前、其次按具体度优先级。"""
    cand = []
    for k, rx in USE_RE.items():
        m = rx.search(window)
        if m:
            cand.append((m.start(), PRIO.get(k, 9), k, m.group(0)))
    if not cand:
        return None, None
    cand.sort()
    return cand[0][2], cand[0][3]


def find_use(rec):
    """
    返回 (主用途, 提及集合, 依据, 来源, 判定层级, 仅泛化非农建设)
      T1 = 显式"用作/用于/作…用途/进行+建设对象"表述
      T2 = 建设语境子句内的类别词共现（较弱，如"已建成钢结构铁棚"）
      T3 = 处罚结果里的处置对象（"没收/拆除 … 篮球场"），仅作补充
    """
    cands, mentioned, ev = [], set(), []
    txt = rec.get("事由", "")
    for ci, c in enumerate(clauses(txt)):
        c2 = plan_cut(c)
        if len(c2) < 4 or NOISE.search(c2):
            continue
        # ---- T1 ----
        for m in USE_TRIG.finditer(c2):
            win = c2[m.end():m.end() + 24]
            win = re.sub(r"^(?:农业|非农业|非农|合法|违法|建设|了|其|该)", "", win) if m.group(0) in ("进行", "实施", "搞") else win
            k, w = _cat_of(win)
            if k:
                cands.append((1, ci, m.start(), k, (m.group(0) + win)[:100]))
                mentioned.add(k)
                break  # 每子句只取第一个显式触发，避免"作X用途"被后续窗口重复命中
        # ---- T2 ----
        k, w = _cat_of(c2)
        if k:
            cands.append((2, ci, 0, k, w))
            mentioned.add(k)
    for c in clauses(rec.get("结果", "")):
        m = OBJ_IN_RESULT.search(c)
        if m:
            k, w = _cat_of(m.group(0))
            if k:
                cands.append((3, 99, 0, k, c[:100]))
                mentioned.add(k)
    generic = int(bool(re.search(r"非农(?:农业)?建设|非农业建设|进行建设|实施建设|违法建设|搞建设|动工建设", txt)))
    if not cands:
        return ("未知或未提及", "", "", "无", "无", generic)
    cands.sort(key=lambda x: (x[0], x[1], x[2], PRIO.get(x[3], 9)))
    main_t, main_ci, _, main_k, main_ev = cands[0]
    for x in cands:
        if len(ev) < 4 and x[4] not in ev:
            ev.append(x[4])
    tier = {1: "T1显式用途表述", 2: "T2建设语境类别词", 3: "T3处罚结果处置对象"}[main_t]
    src = "事由" if main_t in (1, 2) else "结果(处置对象)"
    return (main_k, "/".join(sorted(mentioned)), " ‖ ".join(ev), src, tier, generic)


# ---------------------------------------------------------------------------
# 4. 是否违法建设
# ---------------------------------------------------------------------------
def find_build(rec):
    txt = rec.get("事由", "") or rec.get("结果", "")
    if not txt:
        return "未知", ""
    for c in clauses(txt):
        c2 = plan_cut(c)
        if not c2 or NOISE.search(c2):
            continue
        m = re.search(BUILD_PAT, c2)
        if m:
            return "是", c2[:110]
    m = re.search(NONBUILD_PAT, txt)
    if m:
        return "否/非建设类(堆填取土等)", txt[max(0, m.start() - 20):m.start() + 90]
    return "未知或未提及", ""


# ---------------------------------------------------------------------------
# 5. 主流程
# ---------------------------------------------------------------------------
