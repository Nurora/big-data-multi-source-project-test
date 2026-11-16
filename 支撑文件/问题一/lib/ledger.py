"""证据台账读取：确认关联表、处罚原文、申请事件与间隔。"""
import csv
import re
from collections import defaultdict
from struct import error as StructError
from zipfile import ZipFile

from openpyxl import load_workbook

from date_utils import body_text
from normalize import (PROJECT, SOURCE, clean, doc_text, key, load_links, norm,
                       original_judgments, zip_name)
from paths import INTEGRATED

OUT = INTEGRATED
TIMING_LEDGER = OUT / "01_申请事件与间隔.csv"


def workbook_rows(filename, sheet):
    with (SOURCE / filename).open("rb") as file:
        book = load_workbook(file, read_only=True, data_only=True)
        rows = iter(book[sheet].values)
        columns = next(rows)
        for index, row in enumerate(rows, 2):
            yield {"源表行": index, **dict(zip(columns, row))}
        book.close()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def export(path, records):
    if not records:
        return
    columns = list(dict.fromkeys(k for row in records for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, columns)
        writer.writeheader()
        writer.writerows(records)


def grouping(rows, field):
    groups = defaultdict(list)
    for row in rows:
        groups[row[field]].append(row)
    return groups


def penalty_id(row, person_field):
    parts = [key(row[k]) for k in ("行政处罚决定书文号", "处罚机关", person_field)]
    return "|".join(parts)


def final_penalties():
    rows = list(workbook_rows("广东省土地违法行政处罚数据.xlsx", "合并数据"))
    for row in rows:
        code = penalty_id(row, "标准行政相对人")
        row["处罚键"] = code if all(code.split("|")) else f"S1:{row['源表行']}"
    return rows


def field(body, labels, line=False):
    sep = r" *: *|[\t ]+" if line else r"\t+| *: *"
    end_chars = r"\n\t" if line else r"\t"
    matches = re.finditer(rf"(?:^|[\n\t])(?:{labels})(?:{sep})([^{end_chars}]+)", body)
    return next((m[1].strip() for m in matches if m[1].strip()), "")


def penalty_archive(wanted):
    """Locate public penalty records using the existing decision numbers and parties."""
    pairs = {(p[0], p[2]) for i in wanted if len((p := i.split("|"))) == 3}
    recovered = defaultdict(list)
    n_read = n_failed = 0
    with ZipFile(SOURCE / "行政处罚 最终19833份.zip") as z:
        for item in z.infolist():
            if item.is_dir():
                continue
            try:
                body = clean(doc_text(z.read(item)))
            except (ValueError, KeyError, IndexError, StructError):
                n_failed += 1
                continue
            n_read += 1
            code = field(body, "行政处罚决定书文号|决定文书号|决定文书文号|发文案号|案 *号", line=True)
            party = field(body, "行政相对人名称|被处罚对象|处罚对象|行政相对人", line=True)
            pair = (key(code), key(party))
            if pair not in pairs:
                continue
            result = field(body, "处罚结果|处罚内容|行政处罚内容")
            basis = field(body, "处罚依据|法律依据|违法依据")
            if not result and not basis:
                continue
            agency = field(body, "处罚机关|执法主体名称|执法机关", line=True)
            recovered[pair].append({
                "机关键": key(agency), "处罚内容": result, "处罚依据": basis, "原文文件": zip_name(item),
            })
    return recovered, {"处罚压缩包可读文件": n_read, "处罚压缩包解析失败文件": n_failed}


def linked_source(timing_ledger=TIMING_LEDGER):
    links = load_links()
    ledger = read_csv(timing_ledger)
    current = {r["事件编号"]: r for r in ledger if r["事件来源"] == "同案号非诉执行审查"}
    by_row = {r["关联表行"]: r for r in links}
    unique = {}
    for case, timing in current.items():
        refs = [int(i) for i in timing["关联表行"].split("、")]
        link = next((by_row[i] for i in refs if
                     str(by_row[i]["裁判日期"])[:10] == timing["裁判日"]), by_row[refs[0]])
        assert link["案号键"] == case and link["处罚键"] == timing["处罚键"]
        unique[case] = link
    assert len({r["处罚键"] for r in links}) == len({r["处罚键"] for r in unique.values()})
    return unique, current, ledger
