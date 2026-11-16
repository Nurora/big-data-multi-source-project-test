"""行政机关层级与法院层级识别辅助函数。"""
import re

from ledger import norm

EMPTY = {"", "无具体信息", "未明确", "不详", "未知", "无"}


def observed(value):
    """将缺失或无效的文本值规范为空字符串。"""
    text = norm(value).strip()
    return text if text not in EMPTY else ""


def agency_level(name, city):
    """根据申请执行机关名称识别机关层级。"""
    name = observed(name)
    if not name or re.search(r"[;；、]|和.{0,8}(?:局|政府)", name):
        return ""
    if re.search(r"街道办事处|镇人民政府|乡人民政府", name):
        return "乡镇街道"
    if re.search(r"(?:分局|县.{0,18}(?:局|政府)|区.{0,18}(?:局|政府))", name):
        return "县区或分局"
    if "广东省" in name and not re.search(r"市", name):
        return "省级"
    return "地级市" if observed(city) and observed(city) in name else ""


def court_level(name):
    """根据法院名称识别法院层级。"""
    text = observed(name)
    if re.search(r"最高人民法院", text):
        return "最高法院"
    if re.search(r"高级人民法院", text):
        return "高级法院"
    if re.search(r"中级人民法院|铁路运输中级法院", text):
        return "中级法院"
    if "铁路运输" in text and "法院" in text:
        return "基层法院（铁路运输）"
    return "基层法院" if "法院" in text else ""
