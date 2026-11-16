"""通过可见网页检索、翻页和单篇下载；不调用私有接口或处理验证码。"""
import csv
import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from wenshu import ROOT, RAW, allowed, digest, extract, save_json, stamp

STATE = ROOT / 'data/wenshu_auto_state.json'
DOWNLOADS = RAW / 'downloads'


class NeedsAttention(RuntimeError):
    pass


def canonical_url(url):
    p = urlsplit(url)
    doc = [(k.lower(), v) for k, v in parse_qsl(p.query) if k.lower() == 'docid']
    return urlunsplit((p.scheme, p.netloc.lower(), p.path, urlencode(doc) if doc else p.query, ''))


def case_key(court, number):
    if not court or not number:
        return None
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', court + '|' + number))


def existing_keys():
    """已有北大法宝目录只读取去重键，不改写原件。"""
    keys = set()
    candidates = [ROOT / 'pkulaw_20261021/最终目录数据.json',
                  ROOT / 'outputs/pkulaw_20261021/最终目录数据.json']
    for path in candidates:
        if path.exists():
            for d in json.loads(path.read_text('utf-8')):
                key = case_key(d.get('court'), d.get('case'))
                if key:
                    keys.add(key)
    return keys


def visible(locator):
    return [locator.nth(i) for i in range(locator.count()) if locator.nth(i).is_visible()]


def only(locator, label):
    matches = visible(locator)
    if len(matches) != 1:
        raise NeedsAttention(f'{label}应有1个可见元素，实际{len(matches)}个。请用 inspect 检查页面。')
    return matches[0]


def guard(page, cfg):
    """只检查可见验证/限制文字，隐藏的验证码 iframe 不算拦截。"""
    for phrase in cfg['attention_texts']:
        if visible(page.get_by_text(phrase, exact=False)):
            raise NeedsAttention(f'页面出现“{phrase}”，请在浏览器中人工处理后重新运行。')
    if re.search(r'open=login|/login(?:[/?]|$)', page.url, re.I):
        raise NeedsAttention('页面跳转登录，请人工登录。')


def fingerprint(page, cfg):
    links = page.locator(cfg['result_links']).evaluate_all(
        '(es)=>es.filter(e=>e.getClientRects().length).map(e=>[e.href,e.innerText])')
    return digest(json.dumps(links, ensure_ascii=False))


def conditions(page, cfg):
    if cfg.get('conditions_selector'):
        return only(page.locator(cfg['conditions_selector']), '已选条件').inner_text()
    # 基于页面实际标签寻找小范围容器，不假定站点私有class名称。
    label = only(page.get_by_text('已选条件：', exact=True), '已选条件标签')
    value = label.evaluate('''e => {
        let p=e;
        for(let i=0;i<4 && p;i++,p=p.parentElement){
            const t=p.innerText||'';
            if(t.length<3000 && t.includes('清空搜索条件') &&
               t.replace(/已选条件[：:]|清空搜索条件|保存搜索条件|\\s/g,'').length>0)return t;
        }
        return '';
    }''')
    if not value:
        raise NeedsAttention('无法辨认已选条件区域，请运行 inspect 后校正 conditions_selector。')
    return value


def wait_change(page, cfg, before=None):
    deadline = time.monotonic() + cfg['timeout_seconds']
    while time.monotonic() < deadline:
        guard(page, cfg)
        if visible(page.get_by_text(cfg['empty_text'], exact=False)):
            return 'empty'
        if visible(page.locator(cfg['result_links'])):
            fp = fingerprint(page, cfg)
            if before is None or fp != before:
                if visible(page.locator(cfg['result_links'])):
                    return 'results'
        page.wait_for_timeout(500)
    raise NeedsAttention('结果未加载或翻页后内容未改变；未将本页/本组标记为完成。')


def pace(cfg):
    time.sleep(max(10, cfg['delay_seconds']))


def choose(page, trigger, menu, text):
    only(page.locator(trigger), text + '下拉框').click()
    only(page.locator(menu).get_by_text(text, exact=True), text + '选项').click()


def run_search(page, cfg, query):
    page.goto(cfg['search_url'], wait_until='domcontentloaded', timeout=60000)
    guard(page, cfg)
    # 不以URL参数或隐藏表单值认定检索已生效。
    field = page.locator('#qbValue')
    if not visible(field):
        only(page.get_by_text('高级检索', exact=True), '高级检索入口').click()
    only(field, '全文检索输入框').fill(query)
    choose(page, '#s8', '#gjjs_ajlx', '行政案件')
    choose(page, '#s6', '#gjjs_wslx', '裁定书')
    only(page.locator('#searchBtn'), '检索按钮').click()
    page.wait_for_timeout(1000)
    status = wait_change(page, cfg)
    # 先核对关键词/类型实际在已选条件中，再添加地域。
    condition = conditions(page, cfg)
    for needle in [query, '行政案件', '裁定书']:
        if re.sub(r'\s+', '', needle) not in re.sub(r'\s+', '', condition):
            raise NeedsAttention(f'已选条件中缺少“{needle}”，拒绝下载未筛选的结果。')
    if status == 'empty':
        return status
    region = only(page.get_by_role('link', name=re.compile(r'^广东省\s*\(')), '广东省地域筛选')
    before = fingerprint(page, cfg)
    pace(cfg)
    region.click()
    status = wait_change(page, cfg, before)
    condition = conditions(page, cfg)
    if '广东' not in condition:
        raise NeedsAttention('已选条件未显示广东，未开始下载。')
    return status


def discover(page, cfg, state, query):
    links = page.locator(cfg['result_links']).evaluate_all(
        '(els) => els.map(a => ({url:a.href,title:a.innerText.trim()}))')
    urls = []
    for link in links:
        if not allowed(link['url']) or not re.search(cfg['detail_url_pattern'], link['url']):
            continue
        key = canonical_url(link['url'])
        if key in urls:
            continue
        urls.append(key)
        item = state['documents'].setdefault(key, dict(url=link['url'], title=link['title'],
                                                     status='pending', queries=[]))
        if query not in item['queries']:
            item['queries'].append(query)
    if not urls:
        raise NeedsAttention('页面没有发现可用的文书详情链接；不能据此认定本组为零结果。')
    return urls


def file_type(path):
    data = path.read_bytes()
    if data.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'):
        return '.doc'
    if data.startswith(b'PK\x03\x04'):
        import zipfile
        try:
            with zipfile.ZipFile(path) as z:
                if 'word/document.xml' in z.namelist():
                    return '.docx'
        except zipfile.BadZipFile:
            pass
    # 有些站点导出的是Word兼容HTML/RTF，不接收登录页或验证页。
    if data.startswith(b'{\\rtf'):
        return '.rtf'
    head = data[:4000].decode('utf-8', errors='ignore')
    if re.search(r'Word.Document|application/msword|xmlns:w=', head, re.I):
        return '.doc'
    raise NeedsAttention('下载文件不是已识别的Word文书，未标记成功。')


def capture_problem(page, item):
    folder = ROOT / 'reports/wenshu_auto'
    folder.mkdir(parents=True, exist_ok=True)
    key = digest(item['url'])[:16]
    try:
        page.screenshot(path=str(folder / (key + '-detail.png')), timeout=10000)
        (folder / (key + '-detail.html')).write_text(page.content(), encoding='utf-8')
        controls = page.locator('a,button,[role="button"],[title]').evaluate_all('''es=>es
            .filter(e=>e.getClientRects().length)
            .map(e=>({tag:e.tagName,id:e.id,text:e.innerText,title:e.getAttribute('title'),
                       href:e.getAttribute('href')}))''')
        save_json(folder / (key + '-controls.json'), controls)
    except Exception:
        pass


def get_download(page, cfg):
    """优先已知可见文字/提示；不猜接口，不点击多个候选。"""
    if cfg.get('download_selector'):
        return only(page.locator(cfg['download_selector']), '下载控件')
    for label in [cfg['download_text'], '全文下载', '下载全文', '下载文书']:
        matches = visible(page.get_by_text(label, exact=True))
        if len(matches) == 1:
            return matches[0]
    controls = page.locator('a,button,[role="button"]')
    matches = []
    for i in range(controls.count()):
        e = controls.nth(i)
        if not e.is_visible():
            continue
        name = ((e.inner_text() or '') + ' ' + (e.get_attribute('title') or '')
                + ' ' + (e.get_attribute('aria-label') or '')).strip()
        if re.search(r'下载', name) and len(name) < 60:
            matches.append(e)
    if len(matches) == 1:
        return matches[0]
    raise NeedsAttention(f'无法唯一识别下载控件（{len(matches)}个候选）')


def receive_download(page, cfg, item):
    if cfg.get('manual_download'):
        manual = True
    else:
        manual = False
        try:
            button = get_download(page, cfg)
            with page.expect_download(timeout=cfg['download_timeout_seconds'] * 1000) as event:
                button.click()
            return event.value
        except Exception as exc:
            capture_problem(page, item)
            print(f'自动下载未产生文件：{exc}')
            manual = True
    if manual:
        guard(page, cfg)
        page.bring_to_front()
        print('正文已加载。请在此详情页手动点击网站下载按钮，并选择Word（如有格式选项）。')
        print('程序将监听下载事件；下载成功后会自动保存并继续，无需回终端按回车。')
        # 确保监听在告知用户后立即启动；不会替用户解决验证码。
        with page.expect_download(timeout=cfg.get('manual_download_timeout_seconds', 120) * 1000) as event:
            pass
        return event.value


def download_one(context, item, cfg, base_cfg, state, known):
    page = context.new_page()
    try:
        response = page.goto(item['url'], wait_until='domcontentloaded', timeout=60000)
        if response and response.status >= 400:
            raise NeedsAttention(f'详情HTTP {response.status}')
        guard(page, cfg)
        body = page.locator(cfg['body_selector'])
        body.wait_for(state='visible', timeout=cfg['timeout_seconds'] * 1000)
        text = only(body, '文书正文').inner_text().strip()
        if len(text) < 300 or not re.search(r'人民法院', text) or not re.search(r'裁定|判决', text):
            raise NeedsAttention('正文过短或并非裁判文书。')
        fields = extract(text, base_cfg)
        key = case_key(fields['court'], fields['case_number'])
        content_hash = digest(re.sub(r'\s+', '', text))
        item.update(case_number=fields['case_number'], court=fields['court'], content_hash=content_hash)
        if (key and key in known) or content_hash in state['content_hashes']:
            item.update(status='duplicate', updated_at=stamp())
            return False
        # 不猜测下载接口，不在超时后重复点击下载。
        download = receive_download(page, cfg, item)
        if download.failure():
            raise NeedsAttention('浏览器报告下载失败：' + str(download.failure()))
        DOWNLOADS.mkdir(parents=True, exist_ok=True)
        temp = DOWNLOADS / (content_hash + '.part')
        download.save_as(str(temp))
        suffix = file_type(temp)
        final = DOWNLOADS / (content_hash + suffix)
        temp.replace(final)
        record = dict(source='中国裁判文书网', url=item['url'], retrieved_at=stamp(),
                      title=item['title'], text=text, queries=item['queries'],
                      text_sha256=digest(text), download_file=str(final.relative_to(ROOT)),
                      download_sha256=hashlib.sha256(final.read_bytes()).hexdigest(),
                      capture_method='visible_page_and_browser_download')
        save_json(RAW / 'auto' / (content_hash + '.json'), record)
        item.update(status='done', file=str(final.relative_to(ROOT)), updated_at=stamp())
        if key:
            known.add(key)
        state['content_hashes'].append(content_hash)
        return True
    except Exception:
        # 保留问题页，用户可看到验证码、登录、权限提示或下载弹窗。
        item['attention_page'] = page.url
        capture_problem(page, item)
        raise
    finally:
        if item.get('status') in ('done', 'duplicate'):
            page.close()


def write_manifest(state):
    out = ROOT / 'reports/wenshu_downloads.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['标题', '案号', '法院', '状态', '文件', '命中检索词', '来源网址'])
        for item in state['documents'].values():
            writer.writerow([item.get(k, '') for k in ['title', 'case_number', 'court', 'status', 'file']]
                            + ['；'.join(item['queries']), item['url']])


def search_total(page):
    m = re.search(r'共检索到\s*([\d,，]+)\s*篇', page.locator('body').inner_text())
    return int(re.sub(r'[,，]', '', m[1])) if m else None


def auto(args, base_cfg):
    from playwright.sync_api import sync_playwright
    cfg = json.loads((ROOT / 'config/wenshu_auto.json').read_text('utf-8'))
    if args.manual_download:
        cfg['manual_download'] = True
    queries = cfg['queries']
    if args.query:
        queries = [args.query]
    if args.limit is not None and args.limit < 1:
        raise SystemExit('--limit 必须大于0。')
    limit = args.limit or cfg['max_documents_per_run']
    state = json.loads(STATE.read_text('utf-8')) if STATE.exists() else dict(
        version=1, groups={}, documents={}, content_hashes=[])
    known = existing_keys()
    for item in state['documents'].values():
        if item['status'] == 'done':
            p = ROOT / item.get('file', '')
            if not p.is_file():
                item['status'] = 'pending'
                state['content_hashes'] = [h for h in state['content_hashes'] if h != item.get('content_hash')]
            else:
                key = case_key(item.get('court'), item.get('case_number'))
                if key:
                    known.add(key)
    report_dir = ROOT / 'reports/wenshu_auto'
    report_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(ROOT / '.local/wenshu-edge'), channel='msedge', headless=False,
            accept_downloads=True)
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(cfg['timeout_seconds'] * 1000)
        completed = 0
        try:
            try:
                page.goto('https://wenshu.court.gov.cn/', wait_until='domcontentloaded', timeout=60000)
            except Exception as exc:
                print(f'首次加载未完成：{exc}。浏览器保留，请手动刷新/打开官网后继续。')
            print('已打开独立Edge采集窗口。请先正常登录。不会读取你日常Edge的登录文件。')
            input('登录完成后按回车。若退出请按Ctrl+C > ')
            if args.command == 'inspect':
                print('请在此窗口完成任一组检索并打开高级检索，或打开需要检查的正文。')
                input('页面显示正常后按回车 > ')
                save_json(report_dir / 'inspect.json', dict(url=page.url,
                    inputs=page.locator('input,select').evaluate_all(
                        '(es)=>es.map(e=>({tag:e.tagName,id:e.id,name:e.name,type:e.type}))'),
                    links=page.locator('a[href]').evaluate_all(
                        '(es)=>es.map(e=>({title:e.innerText,href:e.href})).filter(e=>e.title.trim())')))
                (report_dir / 'inspect.html').write_text(page.content(), encoding='utf-8')
                page.screenshot(path=str(report_dir / 'inspect.png'), full_page=True)
                print('已保存 reports/wenshu_auto/inspect.json 和 inspect.png。')
                return
            for query in queries:
                group = state['groups'].setdefault(query, dict(status='pending', pages=[]))
                # 文件缺失时即便该组曾完成也需重跑，避免静默缺档。
                has_pending = any(query in d['queries'] and d['status'] not in ('done', 'duplicate')
                                  for d in state['documents'].values())
                if group['status'] == 'done' and not has_pending:
                    print('跳过已完成检索组：', query)
                    continue
                group.update(status='running', started_at=stamp())
                print('检索：', query)
                pace(cfg)
                try:
                    if args.manual_search:
                        raise NeedsAttention('已选择人工设置每组检索条件。')
                    status = run_search(page, cfg, query)
                except Exception as exc:
                    print(f'自动设置检索未通过：{exc}')
                    print(f'请在列表页人工设置全文【{query}】、广东省、行政案件、裁定书、时间不限。')
                    answer = input('条件和结果显示正常后回车，输入 stop 停止 > ').strip().lower()
                    if answer == 'stop':
                        raise NeedsAttention('用户停止本组检索')
                    guard(page, cfg)
                    status = wait_change(page, cfg)
                    actual = re.sub(r'\s+', '', conditions(page, cfg))
                    for needle in [query, '广东', '行政案件', '裁定书']:
                        if re.sub(r'\s+', '', needle) not in actual:
                            raise NeedsAttention('人工检索条件仍未核对通过：' + needle)
                if status == 'empty':
                    group.update(status='done', empty=True)
                    save_json(STATE, state)
                    continue
                seen_pages = set()
                group_urls = set()
                total = search_total(page)
                group['reported_total'] = total
                for number in range(1, cfg['max_pages_per_query'] + 1):
                    fp = fingerprint(page, cfg)
                    if fp in seen_pages:
                        raise NeedsAttention('翻页出现重复页面，未将本组标记完成。')
                    seen_pages.add(fp)
                    urls = discover(page, cfg, state, query)
                    group_urls.update(urls)
                    save_json(STATE, state)
                    for url in urls:
                        item = state['documents'][url]
                        if item['status'] in ('done', 'duplicate'):
                            continue
                        if completed >= limit:
                            group['status'] = 'partial'
                            print(f'本次已成功下载{completed}份，达到上限；重新运行会跳过已完成文件继续。')
                            return
                        pace(cfg)
                        try:
                            completed += int(download_one(context, item, cfg, base_cfg, state, known))
                        except Exception as exc:
                            item.update(status='attention', error=str(exc), updated_at=stamp())
                            raise
                        finally:
                            save_json(STATE, state)
                            write_manifest(state)
                    group['pages'].append(dict(page=number, fingerprint=fp, count=len(urls), at=stamp()))
                    next_links = visible(page.get_by_role('link', name='下一页', exact=True))
                    if not next_links or next_links[0].get_attribute('aria-disabled') == 'true' or re.search(
                            r'(^|\s)disabled(\s|$)', next_links[0].get_attribute('class') or ''):
                        if total is None or total > len(group_urls):
                            group.update(status='partial', discovered=len(group_urls),
                                         note='列表已到末页，但总数未知或大于可见链接数；可能受600条展示上限影响，需细分检索。')
                            print(group['note'])
                        else:
                            group.update(status='done', finished_at=stamp())
                        break
                    pace(cfg)
                    next_links[0].click()
                    wait_change(page, cfg, fp)
                else:
                    group['status'] = 'partial'
                    print('达到本组页数上限，未标记为完成。请按年份或法院细分后继续。')
                save_json(STATE, state)
        except (Exception, KeyboardInterrupt) as exc:
            state['last_error'] = dict(message=str(exc), time=stamp(), url=page.url)
            save_json(STATE, state)
            write_manifest(state)
            try:
                page.screenshot(path=str(report_dir / 'attention.png'), timeout=10000)
            except Exception:
                pass
            print(f'已暂停：{exc}\n本次成功下载{completed}份。记录已保存，不会自动绕过验证或反复重试。')
            input('可先在浏览器查看问题；按回车关闭本次采集窗口 > ')
        finally:
            save_json(STATE, state)
            write_manifest(state)
            context.close()
