"""人工检索 + 正常浏览器会话采集；不调用未公开接口。"""
import argparse
import csv
import hashlib
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
RAW = ROOT / 'data/raw/wenshu'
CONFIG = ROOT / 'config/wenshu.json'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def allowed(url):
    p = urlparse(url)
    return p.scheme == 'https' and p.hostname == 'wenshu.court.gov.cn'


def extract(text, cfg):
    text = unicodedata.normalize('NFKC', text)
    case = re.search(r'[（(]\d{4}[）)][^\s，。:：]{2,35}?号', text)
    court = re.search(r'[^\s，。:：]{2,35}人民法院', text)
    # 年月日以文尾签署日期优先；网站发布日期不能当裁判日期。
    dates = re.findall(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', text)
    date = None
    if dates:
        try:
            date = datetime(*map(int, dates[-1])).date().isoformat()
        except ValueError:
            pass
    penalties = re.findall(r'[^\s，。；:：、《》]{1,24}(?:罚|处罚)[^\s，。；:：、《》]{0,10}[〔（(\[]\d{4}[〕）)\]][^\s，。；]{1,16}?号', text)
    nonlit = bool(re.search(r'非诉|准予强制执行|不准予强制执行|申请强制执行', text))
    administrative = bool(re.search(r'行政判决书|行政裁定书|行初|行终|行审', text))
    procedure = '行政非诉执行审查候选' if administrative and nonlit else ('行政诉讼候选' if administrative else '待人工复核')
    reason = text.split('本院认为', 1)[1].split('依照', 1)[0] if '本院认为' in text else ''
    laws = sorted(set(re.findall(r'《[^》]{2,80}》(?:第[一二三四五六七八九十百零\d]+条)?', text)))
    results = [x for x in ['不准予强制执行', '准予强制执行', '驳回', '撤销', '确认违法', '维持'] if x in text]
    if '不准予强制执行' in results:
        results.remove('准予强制执行')
    local = bool(re.search(r'广东', (court.group() if court else '') + text[:500]))
    year = int(date[:4]) if date else None
    return dict(case_number=case.group() if case else None,
                court=court.group() if court else None, decision_date=date,
                city_candidates=[c for c in cfg['cities'] if c in text],
                procedure_candidate=procedure, penalty_numbers=sorted(set(penalties)),
                law_references=laws, result_candidates=results, reasoning=reason,
                guangdong_candidate=local,
                land_candidate=any(k in text for k in cfg['keywords']),
                year_in_range=cfg['start_year'] <= year <= cfg['end_year'] if year else None,
                review_status='pending')


def collect(args, cfg):
    from playwright.sync_api import sync_playwright
    queue_path = ROOT / 'data/wenshu_queue.json'
    queue = json.loads(queue_path.read_text('utf-8')) if queue_path.exists() else {}
    robot = RobotFileParser('https://wenshu.court.gov.cn/robots.txt')
    try:
        robot.read()
    except Exception as exc:
        raise SystemExit(f'无法核验 robots.txt，未开始采集：{exc}')
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(ROOT / '.local/wenshu-browser'), headless=False, accept_downloads=False)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://wenshu.court.gov.cn/', wait_until='domcontentloaded', timeout=60000)
        print('请正常登录并人工检索：广东省、2019—2025、行政案件、土地违法相关关键词。')
        print('每到一页结果，输入 add 收集当前页链接；翻页由你操作。输入 run 采集队列，quit 退出。')
        while True:
            command = input('add / run / quit > ').strip().lower()
            if command == 'quit':
                break
            if command == 'add':
                links = page.locator('a[href]').evaluate_all('(els) => els.map(a => ({url:a.href,title:a.innerText}))')
                added = 0
                for link in links:
                    url = link['url']
                    if allowed(url) and re.search(cfg['detail_url_pattern'], url) and url not in queue:
                        queue[url] = {'status': 'pending', 'title': link['title'], 'discovered_at': stamp()}
                        added += 1
                save_json(queue_path, queue)
                print(f'新增 {added}；队列 {len(queue)}。若为 0，请检查页面链接结构，不代表没有案件。')
            elif command == 'run':
                done = 0
                for url, item in queue.items():
                    if item['status'] == 'done':
                        continue
                    if done >= cfg['max_documents']:
                        break
                    if not robot.can_fetch('*', url):
                        print('robots 禁止访问，停止：', url)
                        break
                    time.sleep(max(10, cfg['delay_seconds']))
                    detail = context.new_page()
                    try:
                        response = detail.goto(url, wait_until='domcontentloaded', timeout=60000)
                        status = response.status if response else None
                        if status is None or status >= 400:
                            raise RuntimeError(f'HTTP {status}；停止本批次，稍后人工检查')
                        print('请确认详情已加载；遇登录或验证码请人工完成。无权访问时输入 skip。')
                        if input('正文可见后回车 / skip > ').strip().lower() == 'skip':
                            raise RuntimeError('人工跳过；需重新检查访问权限或页面状态')
                        body = detail.locator(cfg['body_selector'])
                        if body.count() != 1:
                            raise RuntimeError('正文选择器不唯一或不存在；请检查配置')
                        text = body.inner_text().strip()
                        if len(text) < 300 or not re.search(r'人民法院|判决如下|裁定如下', text):
                            raise RuntimeError('非完整文书，拒绝作为成功数据保存')
                        html = detail.content()
                        key = digest(text)
                        folder = RAW / datetime.now().strftime('%Y/%m')
                        folder.mkdir(parents=True, exist_ok=True)
                        html_path = folder / f'{key}.html'
                        if not html_path.exists():
                            html_path.write_bytes(html.encode('utf-8'))
                        record = dict(source='中国裁判文书网', url=url, retrieved_at=stamp(),
                                      http_status=status, title=detail.title(), text=text,
                                      text_sha256=key, html_sha256=hashlib.sha256(html_path.read_bytes()).hexdigest(),
                                      html_file=str(html_path.relative_to(ROOT)), capture_method='rendered_dom')
                        if not (folder / f'{key}.json').exists():
                            save_json(folder / f'{key}.json', record)
                        item.update(status='done', content_hash=key, last_attempt=stamp())
                        done += 1
                    except Exception as exc:
                        item.update(status='failed', error=str(exc), last_attempt=stamp())
                        print(str(exc))
                        save_json(queue_path, queue)
                        break
                    finally:
                        detail.close()
                    save_json(queue_path, queue)
                print(f'本批完成 {done} 条；失败保留在队列，下一次 run 可重试。')
        context.close()


def clean(cfg):
    records, seen, manifest = [], set(), []
    for path in sorted(RAW.rglob('*')):
        if not path.is_file():
            continue
        manifest.append({'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        if path.suffix != '.json':
            continue
        raw = json.loads(path.read_text('utf-8'))
        key = digest(raw['text'])
        if key in seen:
            continue
        seen.add(key)
        fields = extract(raw['text'], cfg)
        # 清洗层不复制包含自然人姓名的原文；全文仅保留在受控 Raw。
        fields.pop('reasoning')
        records.append(dict(court_case_id=key, source_url=raw['url'], **fields))
    out = ROOT / 'data/cleaned/wenshu'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'court_case.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), 'utf-8')
    with (out / 'court_case.csv').open('w', encoding='utf-8-sig', newline='') as f:
        if records:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v for k, v in r.items()} for r in records)
    save_json(ROOT / 'reports/wenshu_manifest.json', manifest)
    quality = dict(generated_at=stamp(), unique_documents=len(records),
                   raw_bytes=sum(x['bytes'] for x in manifest),
                   documents_with_penalty_number=sum(bool(r['penalty_numbers']) for r in records),
                   missing_decision_date=sum(not r['decision_date'] for r in records),
                   scope_candidates=sum(r['guangdong_candidate'] and r['land_candidate'] and r['year_in_range'] is True for r in records),
                   all_extractions_require_review=True)
    save_json(ROOT / 'reports/wenshu_quality.json', quality)
    print(json.dumps(quality, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', nargs='?', default='auto', choices=['auto', 'inspect', 'collect', 'clean', 'selftest'])
    parser.add_argument('--query', help='只运行指定的全文检索词；空格按站点AND关系处理')
    parser.add_argument('--limit', type=int, help='本次成功下载上限；默认10份')
    parser.add_argument('--manual-search', action='store_true', help='每组先人工设好检索条件，随后自动翻页和下载')
    parser.add_argument('--manual-download', action='store_true', help='逐篇打开正文，人工点击网站下载，程序自动保存并续采')
    args = parser.parse_args()
    cfg = json.loads(CONFIG.read_text('utf-8'))
    if args.command in ('auto', 'inspect'):
        from wenshu_auto import auto
        auto(args, cfg)
    elif args.command == 'collect':
        collect(args, cfg)
    elif args.command == 'clean':
        clean(cfg)
    else:
        sample = '广东省广州市中级人民法院\n行政裁定书\n(2021)粤01行审12号\n非法占用土地。粤自然资案处(罚)〔2020〕5号。本院认为申请强制执行不符合要求，裁定不准予强制执行。二〇二一年五月六日'
        value = extract(sample, cfg)
        assert value['procedure_candidate'] == '行政非诉执行审查候选'
        assert value['result_candidates'] == ['不准予强制执行']
        assert value['penalty_numbers'] and value['decision_date'] is None
        assert allowed('https://wenshu.court.gov.cn/a')
        assert not allowed('https://wenshu.court.gov.cn.example.com/a')
        print('离线自检通过；合成文本未写入正式数据。')


if __name__ == '__main__':
    main()
