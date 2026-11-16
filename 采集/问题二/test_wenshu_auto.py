"""离线回归与本地模拟站点测试。不会连接裁判文书网。"""
import base64
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import wenshu_auto as a

TEST_TMP = (a.ROOT / '.local/test-wenshu').resolve()
TEST_TMP.mkdir(parents=True, exist_ok=True)


class DataTests(unittest.TestCase):
    def test_docid_dedup(self):
        self.assertEqual(a.canonical_url('https://wenshu.court.gov.cn/content.html?pageId=1&DocID=abc#x'),
                         a.canonical_url('https://wenshu.court.gov.cn/content.html?docId=abc&pageId=2'))
        self.assertEqual(a.case_key('广东省某法院', '（2021）粤01行审1号'),
                         a.case_key('广东省某法院', '(2021)粤01行审1号'))
        self.assertIsNone(a.case_key('', '(2021)粤01行审1号'))

    def test_download_validation(self):
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp:
            p = Path(tmp) / 'download'
            p.write_bytes(b'<html>please login</html>')
            with self.assertRaises(a.NeedsAttention):
                a.file_type(p)
            with zipfile.ZipFile(p, 'w') as z:
                z.writestr('word/document.xml', '<document/>')
            self.assertEqual(a.file_type(p), '.docx')


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel='msedge', headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(accept_downloads=True)
        self.page = self.context.new_page()
        self.cfg = json.loads((a.ROOT / 'config/wenshu_auto.json').read_text('utf-8'))
        self.cfg.update(timeout_seconds=2, download_timeout_seconds=2)

    def tearDown(self):
        self.context.close()

    def test_discovery_guard_and_page_change(self):
        self.page.set_content('''<section><span>已选条件：</span><a>清空搜索条件</a>
            <b>行政非诉审查 广东省 行政案件 裁定书</b></section>
            <h4><a href="https://wenshu.court.gov.cn/content.html?docId=1">甲案</a></h4>
            <h4><a href="https://wenshu.court.gov.cn/content.html?docId=1&amp;pageId=2">甲案</a></h4>
            <h4><a href="https://evil.example/content.html?docId=2">外站</a></h4>
            <span hidden>请输入验证码</span>''')
        a.guard(self.page, self.cfg)
        self.assertIn('广东', a.conditions(self.page, self.cfg))
        state = {'documents': {}}
        self.assertEqual(len(a.discover(self.page, self.cfg, state, '甲组')), 1)
        a.discover(self.page, self.cfg, state, '乙组')
        self.assertEqual(next(iter(state['documents'].values()))['queries'], ['甲组', '乙组'])
        fp = a.fingerprint(self.page, self.cfg)
        with self.assertRaises(a.NeedsAttention):
            a.wait_change(self.page, self.cfg, fp)
        self.page.set_content('<p>请输入验证码</p>')
        with self.assertRaises(a.NeedsAttention):
            a.guard(self.page, self.cfg)

    def test_native_download_and_duplicate_skip(self):
        content = io.BytesIO()
        with zipfile.ZipFile(content, 'w') as z:
            z.writestr('word/document.xml', '<document/>')
        text = ('广东省广州市中级人民法院\n行政裁定书\n(2021)粤01行审12号\n'
                + '非法占用土地行政处罚。' * 40 + '裁定如下：准予强制执行。')
        html = '<div class="PDF_pox">' + text.replace('\n', '<br>') + '</div><a href="/download">下载</a>'

        def serve(route):
            if route.request.url.endswith('/download'):
                route.fulfill(body=content.getvalue(), headers={
                    'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'Content-Disposition': 'attachment; filename="test.docx"'})
            else:
                route.fulfill(body=html, content_type='text/html; charset=utf-8')
        self.context.route('**/*', serve)
        item = dict(url='https://wenshu.court.gov.cn/content.html?docId=1', title='测试案', queries=['甲组'])
        state = {'content_hashes': []}
        base_cfg = json.loads((a.ROOT / 'config/wenshu.json').read_text('utf-8'))
        with tempfile.TemporaryDirectory(dir=TEST_TMP) as tmp, patch.object(a, 'ROOT', Path(tmp)), \
                patch.object(a, 'RAW', Path(tmp) / 'raw'), patch.object(a, 'DOWNLOADS', Path(tmp) / 'downloads'):
            self.assertTrue(a.download_one(self.context, item, self.cfg, base_cfg, state, set()))
            self.assertEqual(item['status'], 'done')
            self.assertTrue((Path(tmp) / item['file']).is_file())
            other = dict(url=item['url'], title='重复', queries=['乙组'])
            self.assertFalse(a.download_one(self.context, other, self.cfg, base_cfg, state, set()))
            self.assertEqual(other['status'], 'duplicate')
            self.assertEqual(len(list((Path(tmp) / 'downloads').iterdir())), 1)


if __name__ == '__main__':
    unittest.main()
