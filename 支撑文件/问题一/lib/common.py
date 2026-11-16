# -*- coding: utf-8 -*-
"""义务与申请事项分析共用的列名常量与表格读写（4.3、4.4 节）。"""
import sys
from pathlib import Path

import pandas as pd

LIB = Path(__file__).resolve().parent
ROOT = LIB.parent
from paths import FIGURES, INTEGRATED, RAW, TABLES  # noqa: E402

EVIDENCE = INTEGRATED
SOURCE = RAW
DOCS = TABLES.parent
UPSTREAM = TABLES

LABELS = ("罚款", "退还土地", "拆除建筑物或设施", "恢复土地原状",
          "没收建筑物或设施", "复垦", "其他明确义务")
SHORT = ("罚款", "退还土地", "拆除", "恢复原状", "没收建筑设施", "复垦", "其他")
P = ["P_" + item for item in LABELS]
A = ["A_" + item for item in LABELS]
ID = "处罚ID"
EVENT = "申请事件ID"
SEP = "＋"


def read(path):
    return pd.read_csv(path, keep_default_na=False, low_memory=False)


def save(name, frame):
    path = TABLES / (name + ".csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(frame).to_csv(path, index=False, encoding="utf-8-sig", na_rep="NA")


def features(name):
    path = TABLES / (name + ".csv")
    if not path.exists():
        path = UPSTREAM / (name + ".csv")
    frame = read(path)
    for field in P + A:
        if field in frame:
            frame[field] = pd.to_numeric(frame[field].replace("NA", pd.NA)).astype("Int8")
    return frame


def labels(value):
    found = set(str(value).split(SEP)) - {""}
    assert found <= set(LABELS), found
    return found


def pick(values):
    return SEP.join(item for item in LABELS if item in values)


def unique(values):
    return list(dict.fromkeys(value for value in values if value))


def year_span(values):
    import re
    years = [str(value)[:4] for value in values if re.match(r"\d{4}", str(value))]
    return f"{min(years)}—{max(years)}年" if years else "日期未载"
