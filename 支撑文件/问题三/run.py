"""问题三运行入口：依次执行数据提取、处理、分析与可视化。"""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
CODE_ROOT = ROOT.parents[1]
Q3 = "问题三_法院裁定后案件执行效果检验"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--source-dir", default=str(CODE_ROOT))
    args = ap.parse_args()

    if args.extract:
        subprocess.run(
            [sys.executable, str(CODE_ROOT / "采集" / Q3 / "extract_archives.py"),
             "--source-dir", args.source_dir],
            check=True, cwd=ROOT
        )

    steps = [
        CODE_ROOT / "处理" / Q3 / "prepare.py",
        CODE_ROOT / "分析" / Q3 / "analyze.py",
        CODE_ROOT / "可视化" / Q3 / "plot_results.py",
    ]
    for script in steps:
        subprocess.run([sys.executable, str(script)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
