"""分析 4 · 对应与覆盖：义务 × 申请事项矩阵、处罚级与事件级覆盖率（图9 底层表）。"""
from math import sqrt
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "支撑文件" / "问题一" / "lib"))

from common import A, ID, LABELS, P, features, save  # noqa: E402


def wilson(x, n):
    if not n:
        return float("nan"), float("nan")
    z = 1.95996398454
    p = x / n
    scale = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / scale
    radius = z * sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / scale
    return max(0., center - radius), min(1., center + radius)


def coverage(frame, valid):
    rows = []
    for label, p, a in zip(LABELS, P, A):
        has_duty = frame[p].eq(1).fillna(False)
        eligible = has_duty & valid & frame[a].notna()
        numerator = int(frame.loc[eligible, a].eq(1).sum())
        denominator = int(eligible.sum())
        low, high = wilson(numerator, denominator)
        rows.append({"义务": label, "分子": numerator, "分母": denominator,
                     "覆盖率": numerator / denominator if denominator else float("nan"),
                     "95%CI下限": low, "95%CI上限": high, "包含义务总数": int(has_duty.sum()),
                     "范围门槛排除数": int((has_duty & ~eligible).sum()),
                     "排除记录中的明确申请数": int(frame.loc[has_duty & ~eligible, a].eq(1).sum())})
    return rows


def correspondence(row):
    if not row["P范围完整"]:
        return "信息不足"
    pairs = list(zip(row[P].tolist(), row[A].tolist()))
    if any(p == 0 and pd.notna(a) and a == 1 for p, a in pairs):
        return "申请新增事项"
    if any(pd.isna(a) for _, a in pairs):
        return "信息不足"
    has = [a for p, a in pairs if p == 1]
    if not has:
        return "信息不足"
    if all(has):
        return "完全对应"
    if any(has):
        return "部分对应"
    return "处罚义务未在明确申请中出现"


def main():
    pen = features("处罚级三状态事务")
    events = features("申请事件级三状态及证据").merge(pen[[ID, *P]], on=ID, validate="many_to_one")
    save("事件级覆盖率", coverage(events, events["申请范围"].eq("完整")))
    save("处罚级覆盖率", coverage(pen, pd.Series(True, index=pen.index)))
    status = pen.apply(correspondence, axis=1)
    order = ["完全对应", "部分对应", "申请新增事项", "处罚义务未在明确申请中出现", "信息不足"]
    counts = status.value_counts().reindex(order, fill_value=0)
    save("处罚级对应状态", counts.rename("处罚数").rename_axis("对应状态").reset_index()
         .assign(分母=len(pen), 占比=counts.to_numpy() / len(pen)))
    save("处罚级对应状态明细", pen[[ID, "P范围完整", "A范围完整"]].assign(对应状态=status))
    rows = []
    for p, p_col in zip(LABELS, P):
        sample = pen.loc[pen[p_col].eq(1).fillna(False)]
        for a, a_col in zip(LABELS, A):
            n1 = int(sample[a_col].eq(1).sum())
            n0 = int(sample[a_col].eq(0).sum())
            rows.append({"处罚义务": p, "司法申请事项": a, "明确申请数": n1, "明确未申请数": n0,
                         "事项NA数": len(sample) - n1 - n0, "有效分母": n1 + n0,
                         "明确申请比例": n1 / (n1 + n0) if n1 + n0 else float("nan")})
    save("处罚申请对应矩阵", rows)


if __name__ == "__main__":
    main()
