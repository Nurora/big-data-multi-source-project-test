"""字段规范化与源表读取：文号/机关/相对人规范化、日期解析、关联表读取。"""
import re
import struct
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zipfile import ZipFile

from openpyxl import load_workbook

from paths import CODE as PROJECT
from paths import DATA as EVIDENCE
from paths import FIGURES as IMAGES
from paths import INTEGRATED as OUT
from paths import RAW as SOURCE
CN = "零一二三四五六七八九"
DIGITS = "0-9零〇○Ｏ一二三四五六七八九十廿"
Y = r"(?:19\d{2}|20\d{2}|[一二][零〇○Ｏ一二三四五六七八九]{3})"
DATE = (rf"(?:{Y}年(?:[{DIGITS}]{{1,3}}月(?:[{DIGITS}]{{1,3}}[日号])?)?"
        rf"|{Y}[./-]\d{{1,2}}(?:[./-]\d{{1,2}})?|{Y})(?![{DIGITS}年月日号]|[./-]\d)")
DAY = rf"(?:{Y}年[{DIGITS}]{{1,3}}月[{DIGITS}]{{1,3}}[日号]|{Y}[./-]\d{{1,2}}[./-]\d{{1,2}}(?!\d))"


def number(value):
    if "十" in value:
        left, right = value.split("十")
        return 10 * (number(left) if left else 1) + (number(right) if right else 0)
    if value.startswith("廿"):
        return 20 + (number(value[1:]) if value[1:] else 0)
    return int(value.translate(str.maketrans(CN + "〇○Ｏ", "0123456789000")))


def parse_date(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:10], "日"
    value = unicodedata.normalize("NFKC", str(value or "")).replace("O", "〇")
    parts = [x for x in re.split(r"[年月日号./-]", value.strip()) if x]
    try:
        parts = [number(p) for p in parts]
        if len(parts) == 3:
            return date(*parts).isoformat(), "日"
        if len(parts) == 2 and 1 <= parts[1] <= 12:
            return f"{parts[0]:04d}-{parts[1]:02d}", "月"
        if len(parts) == 1 and 1900 <= parts[0] <= 2099:
            return str(parts[0]), "年"
    except ValueError:
        pass
    return "", "缺失或不可解析"


def norm(value):
    return unicodedata.normalize("NFKC", str(value or ""))


def key(value):
    value = re.sub(r"第(?=\d+号)", "", norm(value))
    return re.sub(r"[^a-zA-Z0-9\u3400-\u9fff]", "", value).upper()


def zip_name(item):
    if item.flag_bits & 0x800:
        return item.filename
    try:
        return item.filename.encode("cp437").decode("gb18030")
    except UnicodeError:
        return item.filename


def doc_text(data):
    """Decode the main Word 97+ story via CFB FAT and the Word piece table."""
    if data[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise ValueError("非 Word 二进制复合文档")

    def u32(blob, offset):
        return struct.unpack_from("<I", blob, offset)[0]

    def uints(blob):
        return struct.unpack(f"<{len(blob) // 4}I", blob)

    sector_size = 1 << struct.unpack_from("<H", data, 30)[0]
    mini_size = 1 << struct.unpack_from("<H", data, 32)[0]

    def sector(index):
        start = (index + 1) * sector_size
        return data[start:start + sector_size]

    difat = list(uints(data[76:512]))
    extension = u32(data, 68)
    for _ in range(u32(data, 72)):
        page = uints(sector(extension))
        difat.extend(page[:-1])
        extension = page[-1]
    fat = uints(b"".join(sector(i) for i in difat[:u32(data, 44)]))

    def chain(start, allocation, read):
        seen = set()
        chunks = []
        while start < len(allocation) and start not in seen:
            seen.add(start)
            chunks.append(read(start))
            start = allocation[start]
        return b"".join(chunks)

    directory = chain(u32(data, 48), fat, sector)
    streams = {}
    for offset in range(0, len(directory), 128):
        entry = directory[offset:offset + 128]
        length = struct.unpack_from("<H", entry, 64)[0]
        if length:
            name = entry[:length - 2].decode("utf-16le")
            streams[name] = (u32(entry, 116), u32(entry, 120))
    mini_fat = uints(chain(u32(data, 60), fat, sector))
    root_start, root_size = streams["Root Entry"]
    mini_data = chain(root_start, fat, sector)[:root_size]

    def stream(name):
        start, size = streams[name]
        if size >= u32(data, 56):
            return chain(start, fat, sector)[:size]
        return chain(start, mini_fat, lambda i: mini_data[i * mini_size:(i + 1) * mini_size])[:size]

    word = stream("WordDocument")
    if word[:2] != b"\xec\xa5":
        raise ValueError("Word FIB 无效")
    flags = struct.unpack_from("<H", word, 10)[0]
    table = stream("1Table" if flags & 0x200 else "0Table")
    clx_start, clx_size = struct.unpack_from("<II", word, 0x1A2)
    clx = table[clx_start:clx_start + clx_size]
    pos = 0
    while clx[pos] == 1:
        pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
    if clx[pos] != 2:
        raise ValueError("无 Word 正文片段表")
    size = u32(clx, pos + 1)
    plc = clx[pos + 5:pos + 5 + size]
    count = (size - 4) // 12
    limit = u32(word, 76)
    texts = []
    for i in range(count):
        start_cp = u32(plc, 4 * i)
        length = min(u32(plc, 4 * (i + 1)), limit) - start_cp
        if length <= 0:
            break
        fc = u32(plc, 4 * (count + 1) + 8 * i + 2)
        if fc & 0x40000000:
            start = (fc & 0x3fffffff) // 2
            texts.append(word[start:start + length].decode("gb18030", errors="replace"))
        else:
            texts.append(word[fc:fc + length * 2].decode("utf-16le", errors="replace"))
    return "".join(texts)


def clean(raw):
    raw = re.sub(r"\x13[^\x14\x15]*\x14", "", raw)
    raw = norm(raw.replace("\r", "\n").replace("\x0b", "\n").replace("\x07", "\t"))
    return re.sub(r"[\x00-\x08\x0c-\x1f\u200b\u3000]", "", raw)


def load_links():
    path = SOURCE / "广东省土地违法行政处罚与裁判文书关联表.xlsx"
    sheet = load_workbook(path, read_only=True, data_only=True)["关联结果"]
    rows = iter(sheet.values)
    headers = next(rows)
    links = []
    for rownum, row in enumerate(rows, 2):
        record = dict(zip(headers, row))
        record["关联表行"] = rownum
        record["案号键"] = key(record["裁判文书案号"])
        record["处罚键"] = "|".join(key(record[k]) for k in
                                 ["行政处罚决定书文号", "处罚机关", "处罚行政相对人"])
        links.append(record)
    return links


def original_judgments(links):
    wanted = {row["案号键"] for row in links}
    docs = defaultdict(list)
    path = SOURCE / "裁判文书 筛选后结果(2).zip"
    with ZipFile(path) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            member = zip_name(item)
            filename = member.rsplit("/", 1)[-1]
            parts = filename.rsplit("__", 2)
            case = key(parts[-2] if len(parts) >= 2 else Path(filename).stem)
            if case not in wanted:
                continue
            try:
                body = clean(doc_text(archive.read(item)))
                if len(body) < 80 or case not in key(body):
                    raise ValueError("正文未核对到案号")
                docs[case].append((member, body, ""))
            except (ValueError, KeyError, IndexError, struct.error) as exc:
                docs[case].append((member, "", str(exc)))
    return docs


def original_penalties(links, needed):
    """Find missing/contested dates only through a matching decision number and subject."""
    number_index = defaultdict(list)
    subject_index = defaultdict(list)
    for link in links:
        if link["处罚键"] not in needed:
            continue
        number, _, subject = link["处罚键"].split("|")
        if number and subject:
            item = (link["处罚键"], number, subject)
            if len(subject) >= 3:
                subject_index[subject[:3]].append(item)
            if len(number) >= 5:
                number_index[number[:5]].append(item)
    results = defaultdict(list)
    path = SOURCE / "行政处罚 最终19833份.zip"
    with ZipFile(path) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            member = zip_name(item)
            filename = key(member.rsplit("/", 1)[-1])
            candidates = set()
            for i in range(len(filename)):
                candidates.update(candidate for candidate in subject_index.get(filename[i:i + 3], ())
                                  if candidate[2] in filename)
                candidates.update(candidate for candidate in number_index.get(filename[i:i + 5], ())
                                  if candidate[1] in filename)
            if not candidates:
                continue
            try:
                body = clean(doc_text(archive.read(item)))
            except (ValueError, KeyError, IndexError, struct.error):
                continue
            number = re.search(r"行政处罚决定书文号[\t :]+([^\t\n]{3,130})", body)
            subject = re.search(r"(?:处罚对象|行政相对人)[\t :]+([^\t\n]{1,140})", body)
            written = re.search(rf"(?:行政)?处罚决定日期[\t :]+(?P<date>{DATE})", body)
            if not (number and subject and written):
                continue
            observed, precision = parse_date(written["date"])
            for penalty, target_number, target_subject in candidates:
                if key(number[1]) == target_number and key(subject[1]) == target_subject and observed:
                    results[penalty].append((observed, precision, member, written.group()))
    return results
