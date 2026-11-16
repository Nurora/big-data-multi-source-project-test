"""分析 3 · 义务组合结构：单项频率、两两共现与 1—3 项组合排名（图8 底层表）。"""
from itertools import combinations
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))

from common import ID, LABELS, P, features, save  # noqa: E402


def main():
    pen = features("处罚级三状态事务")
    present = pen[P].eq(1).fillna(False)
    sample = present.loc[present.any(axis=1)].astype(int)
    assert pen[ID].is_unique and len(sample)
    n = len(sample)
    counts = sample.sum()
    save("义务频数", [{"义务": label, "频数": counts[col], "分母": n, "占比": counts[col] / n}
                    for label, col in zip(LABELS, P)])
    matrix = sample.T @ sample
    matrix.index = matrix.columns = LABELS
    save("义务共现计数", matrix.rename_axis("行义务").reset_index())
    save("义务共现行比例", matrix.div(matrix.values.diagonal(), axis=0).rename_axis("行义务").reset_index())
    rows = []
    for k in (1, 2, 3):
        for cols in combinations(P, k):
            count = int(sample[list(cols)].all(axis=1).sum())
            if count:
                rows.append({"组合": "＋".join(col[2:] for col in cols), "组合类型": f"{k}项",
                             "频数": count, "分母": n, "占比": count / n})
    rank = pd.DataFrame(rows).sort_values(["频数", "组合类型", "组合"], ascending=[False, True, True])
    rank.insert(0, "总体排名", range(1, len(rank) + 1))
    rank["组内排名"] = rank.groupby("组合类型").cumcount() + 1
    save("处罚义务组合排名", rank)
    save("处罚义务组合种数", rank.groupby("组合类型").size().reset_index(name="观察到的组合数"))
    size = sample.sum(axis=1)
    closed = pen.loc[sample.index, "P范围完整"]
    groups = [
        ("仅罚款（处罚范围完整）", sample[P[0]].eq(1) & size.eq(1) & closed),
        ("仅观察到罚款（处罚范围不完整）", sample[P[0]].eq(1) & size.eq(1) & ~closed),
        ("观察到多义务", size.ge(2)),
        ("仅观察到一项非罚款义务", sample[P[0]].eq(0) & size.eq(1)),
    ]
    save("处罚义务结构分类", [{"结构": label, "处罚数": int(mask.sum()), "分母": n, "占比": mask.mean()}
                              for label, mask in groups])


if __name__ == "__main__":
    main()
