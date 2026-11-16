# -*- coding: utf-8 -*-
"""按报告顺序运行问题一的数据处理、统计分析与图表生成流程。"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

SUPPORT = Path(__file__).resolve().parent
CODE_ROOT = SUPPORT.parents[1]
Q1 = "问题一_非法占用土地行政处罚案件画像"

STEPS = [
    ("处理", "1_build_sample.py"),
    ("分析", "1_time_stats.py"),
    ("可视化", "fig6_time.py"),
    ("分析", "2_longtail_stats.py"),
    ("可视化", "fig7_longtail.py"),
    ("处理", "2_build_transactions.py"),
    ("分析", "3_obligation_stats.py"),
    ("可视化", "fig8_obligation.py"),
    ("分析", "4_coverage_stats.py"),
    ("可视化", "fig9_coverage.py"),
    ("分析", "5_profile_tables.py"),
    ("可视化", "fig1_subject.py"),
    ("可视化", "fig2_behavior.py"),
    ("可视化", "fig3_landuse.py"),
    ("可视化", "fig4_year.py"),
    ("可视化", "fig5_city.py"),
]
SKIP_WITH_PROFILE = {
    ("分析", "5_profile_tables.py"),
    ("可视化", "fig1_subject.py"),
    ("可视化", "fig2_behavior.py"),
    ("可视化", "fig3_landuse.py"),
    ("可视化", "fig4_year.py"),
    ("可视化", "fig5_city.py"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-profile", action="store_true", help="跳过4.1基础画像")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    started, failed = time.time(), []
    for category, script in STEPS:
        if args.skip_profile and (category, script) in SKIP_WITH_PROFILE:
            print(f"[skip] {category}/{script}")
            continue
        script_path = CODE_ROOT / category / Q1 / script
        print(f"\n=== {category}/{script} " + "=" * max(0, 46 - len(script)), flush=True)
        run = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(script_path)],
            cwd=SUPPORT, capture_output=True, encoding="utf-8", errors="replace"
        )
        if run.returncode:
            failed.append(f"{category}/{script}")
            print(run.stdout[-1500:])
            print(run.stderr[-3000:])
        else:
            tail = [line for line in run.stdout.strip().splitlines() if line][-1:]
            print("ok", tail[0] if tail else "")

    tables_dir = SUPPORT / "output" / "tables"
    figures_dir = SUPPORT / "output" / "figures"
    tables = sorted(p.name for p in tables_dir.glob("*.csv")) if tables_dir.exists() else []
    figures = sorted(p.name for p in figures_dir.glob("*.png")) if figures_dir.exists() else []
    print(f"\n统计表 {len(tables)} 张 → 支撑文件/问题一/output/tables/")
    print(f"图表 {len(figures)} 张 → 支撑文件/问题一/output/figures/")
    for name in figures:
        print("   ", name)
    print(f"耗时 {time.time() - started:.1f}s；失败步骤 {len(failed)} 个 {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
