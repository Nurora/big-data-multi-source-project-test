# -*- coding: utf-8 -*-
"""全仓库统一的路径约定。

数据目录默认为「仓库根/data/」，可用环境变量 REPORT_DATA 指向外部数据集目录：

    REPORT_DATA=D:/数据集/广东土地  python run_all.py

目录结构：
    <仓库根>/data/raw/          两张原始表（行政处罚明细、已核验的处罚—裁判关联表）+ 代表性原文样本
    <仓库根>/data/integrated/   证据台账（逐条义务、申请事项、日期原文依据）
    output/tables/     全部中间统计表（运行时生成）
    output/figures/    全部正式图表（运行时生成）
"""
import os
from pathlib import Path

CODE = Path(__file__).resolve().parents[1]          # 支撑文件/问题一/
REPO = CODE.parent                                  # 支撑文件/
ROOT = REPO.parent                                  # 仓库根（README 所在目录）

DATA = Path(os.environ.get("REPORT_DATA", ROOT / "data")).resolve()
RAW = DATA / "raw"
INTEGRATED = DATA / "integrated"

OUTPUT = CODE / "output"
TABLES = OUTPUT / "tables"
FIGURES = OUTPUT / "figures"

# 处理阶段（processing/1_build_sample.py）产出的两张表，供 4.1 基础画像直接使用
MAIN = TABLES / "01_处罚主表_20899.csv"
CONF = TABLES / "02_确认关联处罚_3175.csv"

for _folder in (TABLES, FIGURES):
    _folder.mkdir(parents=True, exist_ok=True)


def need(path):
    """确认输入存在，缺失时给出可操作的提示。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"缺少输入：{path}\n"
            f"请把数据放到 {DATA}（raw/ 与 integrated/），或设置环境变量 REPORT_DATA 指向数据集目录。")
    return path
