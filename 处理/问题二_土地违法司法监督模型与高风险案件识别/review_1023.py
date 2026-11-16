"""2026-10-23增量文书：原文读取、去重和逐条审查资料。"""
import pathlib, json, re, csv, hashlib, zipfile, io, unicodedata
from collections import Counter,defaultdict
from screen_pkulaw import doc_text

ROOT=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
SOURCE=ROOT/'pkulaw_1023'
OUT=SOURCE/'整理结果'
FOLDER=OUT/'新增裁判文书'
OLD=ROOT/'pkulaw_20261021'/'最终目录数据.json'

def norm(t):return re.sub(r'[^\w\u4e00-\u9fff]','',unicodedata.normalize('NFKC',t))
def key(d):return norm(d.get('court',''))+'|'+norm(d.get('case','')) if d.get('court') and d.get('case') else None
def unpack(raw,source):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for e in z.infolist():
            if e.is_dir():continue
            b=z.read(e)
            if e.filename.lower().endswith('.zip'):yield from unpack(b,source+' / '+e.filename)
            elif e.filename.lower().endswith(('.doc','.docx')):yield source,e.filename,b

def read_doc(raw,name):
    if raw.startswith(b'PK'):
        from docx import Document
        doc=Document(io.BytesIO(raw));return '\n'.join(p.text for p in doc.paragraphs)
    return doc_text(raw)

def prep():
    OUT.mkdir(exist_ok=True);FOLDER.mkdir(exist_ok=True)
    old=json.loads(OLD.read_text('utf-8'));oldids={d['id']:d for d in old};oldkeys={key(d):d for d in old if key(d)}
    docs=[];seen={};duplicates=[];errors=[];total=0
    for z in sorted(SOURCE.glob('*.zip')):
        for source,name,raw in unpack(z.read_bytes(),z.name):
            total+=1
            m=re.search(r'FBMCLI\.C\.(\d+)',name);ident=m[1] if m else hashlib.sha256(raw).hexdigest()
            if ident in seen:duplicates.append(dict(id=ident,source=source,name=name));continue
            try:t=read_doc(raw,name)
            except Exception as exc:errors.append(dict(source=source,name=name,error=str(exc)));continue
            t=re.sub(r'\x13[^\x14]*\x14','',t).replace('\x15','')
            t=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','\n',t)
            def field(label):
                m=re.search(label+r'\s*[：:]\s*([^\n]+)',t);return m[1].strip() if m else ''
            title=re.sub(r'\(FBMCLI.*','',pathlib.PurePosixPath(name).name)
            body=t.split('//',1)[-1].split('©北大法宝')[0].strip()
            body=re.split(r'附法律依据|附：本裁定适用|附本裁定',body)[0]
            result=re.split(r'裁定如下[：:，,]?|判决如下[：:，,]?|裁判结果',body)[-1]
            result=re.split(r'落款|审\s*判\s*长|审\s*判\s*员',result)[0].strip()
            d=dict(id=ident,title=title,source=source,name=name,text=t,body=body,result=result,
                   case=field(r'案\s*号'),court=field('审理法院'),date=field('审结日期'),
                   sha256=hashlib.sha256(raw).hexdigest(),suffix=pathlib.Path(name).suffix)
            land=re.compile(r'土地管理法|土地行政处罚|非法.{0,8}(占用|转让|买卖).{0,15}土地|擅自.{0,8}(占用|改变).{0,15}(土地|林地)|退还.{0,25}土地|非法占用.{0,15}(耕地|园地|林地|农用地)|恢复土地原状')
            d['land_evidence']=[s.strip() for s in re.split('[。\n]',body) if land.search(s)]
            d['duplicate_old']=oldids.get(ident,oldkeys.get(key(d),{})).get('id')
            seen[ident]=d;docs.append(d)
            (FOLDER/(ident+d['suffix'])).write_bytes(raw)
    (OUT/'原文审查数据.json').write_text(json.dumps(docs,ensure_ascii=False,indent=2),'utf-8')
    (OUT/'重复下载记录.json').write_text(json.dumps(duplicates,ensure_ascii=False,indent=2),'utf-8')
    (OUT/'解析错误.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(dict(archives=len(list(SOURCE.glob('*.zip'))),total=total,unique_ids=len(docs),duplicate_downloads=len(duplicates),old_matches=sum(bool(d['duplicate_old']) for d in docs),errors=errors),ensure_ascii=False))
    print('Year fields',Counter(d['date'][:4] for d in docs))
    for d in docs:
        if not d['duplicate_old'] and (not d['land_evidence'] or not re.search(r'(不准予|不予|准予|准许|不准许).{0,10}(强制)?执行',re.sub(r'\s','',d['result'])) or not any(x in d['title'] for x in ['国土','自然资源','规划土地'])):
            print(d['id'],d['case'],d['title'],'|',d['result'][:150].replace('\n',' '),'land=',bool(d['land_evidence']))

def assess():
    ds=json.loads((OUT/'原文审查数据.json').read_text('utf-8'))
    for d in ds:
        t=re.sub(r'\s','',d['body']);r=re.sub(r'\s','',d['result'])
        evidence=[s for s in re.split('[。\n]',d['body']) if re.search(r'土地管理法|土地行政处罚|国土资源行政处罚|(?:非法|违法)占用.{0,500}(土地|农用地|基本农田)|退还.{0,500}土地|占用集体土地|土地违法|恢复土地原状|改变林地用途|破坏.{0,20}(耕地|林地)',s)]
        d['land_evidence']=evidence
        d['reason']='';d['decision']='待核对'
        if evidence and ('行政处罚' in t or '处罚决定' in t):
            d.update(decision='拟保留',reason='违法用地处罚执行审查，原文有土地违法事实/处罚和准予或不准予执行主文')
        if not evidence:
            if re.search(r'征收补偿决定|房屋征收补偿|补偿安置决定|实施搬迁',r):
                d.update(decision='拟删除',reason='房屋/土地征收补偿及搬迁执行，不是土地违法行政处罚')
            elif re.search(r'分配|分红|集体经济收益|土地补偿款|征地补偿款|征地款',r):
                d.update(decision='拟删除',reason='集体成员收益、分红或征地款分配执行，不是违法用地处罚')
            elif re.search(r'税务局|缴纳税款|税收',r):
                d.update(decision='拟删除',reason='税款、税收管理执行，不是土地违法处罚')
            elif re.search(r'排污|环罚|生态环境局|人居环境委员会',r):
                d.update(decision='拟删除',reason='环保行政处罚，不是土地违法处罚')
            elif re.search(r'分配|分红|集体经济收益|股东|股权|成员资格',t) and '行政处理决定书' in t:
                d.update(decision='拟删除',reason='集体成员权益、收益分配行政处理执行，不是违法用地处罚')
        if re.search(r'交出被征土地|交出土地决定书|房屋征收.{0,20}协议决定书|补缴土地差价',r):
            d.update(decision='拟删除',reason='征收交地、征收协议或补缴地价执行，不是土地违法行政处罚')
        if d['id'] in ['554346510','112222166','112130470']:
            d.update(decision='拟删除',reason='非法采矿处罚（停采、矿产罚款、偷采现场复绿），不属于违法用地处罚')
        if d['id']=='552710597':
            d.update(decision='拟删除',reason='仅依据城乡规划法作出的违章建筑规划处罚，不属于土地违法处罚')
        if d['id']=='122205525':
            d.update(decision='拟删除',reason='无食品经营许可证的食品安全处罚；土地仅为经营场所描述')
        d['evidence']='；'.join(evidence[:2])[:1200]
    (OUT/'初筛数据.json').write_text(json.dumps(ds,ensure_ascii=False,indent=2),'utf-8')
    print(Counter(d['decision'] for d in ds))
    print('\n\n'.join(d['id']+' '+d['case']+' '+d['title']+'\n'+d['body'] for d in ds if d['decision']=='待核对'))

def year_of(d):
    date=d.get('date','')
    if not date:
        m=re.search(r'审结日期\s*[：:]\s*([^\n]+)',d.get('text',''));date=m[1] if m else ''
    m=re.search(r'((?:19|20)\d{2})[.年/-]',date)
    if m:return m[1],'审结日期字段'
    end=d.get('body',d.get('text',''))[-1500:]
    # 只读落款，不取正文中处罚、申请或公告日期。
    if '落款' in end:end=end.rsplit('落款',1)[-1]
    c=re.search(r'([二一两三四五六七八九零〇○ＯO0]{4})年',end)
    if c:
        mapping=dict(zip('零一二三四五六七八九','0123456789'));mapping.update({'〇':'0','○':'0','Ｏ':'0','O':'0','0':'0'})
        try:y=''.join(mapping[x] for x in c[1])
        except KeyError:y=''
        if re.fullmatch(r'(19|20)\d{2}',y):return y,'正文中文落款年份'
    m=re.search(r'(20\d{2})年',end)
    if m:return m[1],'正文落款年份'
    m=re.search(r'[（(]((?:19|20)\d{2})[）)]',d.get('case',''))
    if m:return m[1],'案号年份辅助归年（裁判年份待核验）'
    return '未知','无可核验年份'

def finish():
    ds=json.loads((OUT/'初筛数据.json').read_text('utf-8'));old=json.loads(OLD.read_text('utf-8'))
    assert len(old)==1070
    knownids={d['id']:d for d in old};knownkeys={key(d):d for d in old if key(d)}
    knownbody={norm(d['body']):d for d in old}
    added=[]
    for d in ds:
        assert d['decision']!='待核对',d['id']
        d['decision']='不相关删除' if d['decision']=='拟删除' else '新增保留'
        if d['decision']=='新增保留':
            match=knownids.get(d['id']) or knownkeys.get(key(d)) or knownbody.get(norm(d['body']))
            if match:
                from difflib import SequenceMatcher
                ratio=SequenceMatcher(None,norm(d['body']),norm(match['body']),autojunk=False).ratio()
                if d['id']!=match['id'] and ratio<.97:raise ValueError('同案号内容不同需核对：'+d['id'])
                d.update(decision='重复删除',reason='同法院同案号/相同正文；保留CLI.C.'+match['id'],duplicate_of=match['id'],duplicate_similarity=ratio)
            else:
                added.append(d);knownids[d['id']]=d
                if key(d):knownkeys[key(d)]=d
                knownbody[norm(d['body'])]=d
        y,basis=year_of(d);d.update(year=y,year_basis=basis)
    folder=FOLDER.resolve();assert folder.is_relative_to(SOURCE.resolve())
    for d in ds:
        p=folder/(d['id']+d['suffix']);assert p.resolve().parent==folder
        if d['decision']!='新增保留':
            if p.exists():p.unlink()
        else:
            name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',d['title'][:65]+'__'+d['case']+'__'+d['id'])+d['suffix']
            dest=folder/name
            if p.exists():p.rename(dest)
            assert dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()==d['sha256']
            d['file']=str(dest)
    assert len(list(folder.glob('*.doc*')))==len(added)
    oldrows=[]
    for d in old:
        y,basis=year_of(d);oldrows.append(dict(id=d['id'],title=d['title'],case=d['case'],court=d['court'],year=y,year_basis=basis,batch='原有1070份'))
    newrows=[dict(id=d['id'],title=d['title'],case=d['case'],court=d['court'],year=d['year'],year_basis=d['year_basis'],batch='1023新增') for d in added]
    combined=oldrows+newrows
    assert len({key(d) for d in combined})==len(combined)
    for name,data in [('筛选与去重记录.json',ds),('新增保留目录.json',added),('合并去重目录.json',combined)]:
        (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    counts=Counter(d['decision'] for d in ds)
    oldyears=Counter(d['year'] for d in oldrows);newyears=Counter(d['year'] for d in newrows)
    years=sorted(oldyears.keys()|newyears.keys())
    with (OUT/'年份分布.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['年份','原有保留','本次新增去重后','合并去重后','其中按案号辅助归年'])
        w.writerows([y,oldyears[y],newyears[y],oldyears[y]+newyears[y],sum(d['year']==y and '案号' in d['year_basis'] for d in combined)] for y in years)
    with (OUT/'筛选与去重记录.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['法宝编号','标题','案号','处理','理由','正文证据','裁定主文','年份','年份依据','来源'])
        w.writerows([d['id'],d['title'],d['case'],d['decision'],d['reason'],d['evidence'],d['result'],d['year'],d['year_basis'],d['source']] for d in ds)
    with (OUT/'合并去重目录.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['法宝编号','标题','案号','法院','年份','年份依据','批次'])
        w.writerows([d['id'],d['title'],d['case'],d['court'],d['year'],d['year_basis'],d['batch']] for d in combined)
    summary=dict(原始压缩包=36,展开文书数=1898,重复下载=150,不同法宝编号=1748,处理=dict(counts),原有文书=len(old),新增保留=len(added),合并后=len(combined),
                 新增年份=dict(sorted(newyears.items())),合并年份=dict(sorted((oldyears+newyears).items())),
                 辅助归年=[d for d in combined if '案号' in d['year_basis']],原有数据重复数=sum(bool(d.get('duplicate_of') in {x['id'] for x in old}) for d in ds))
    (OUT/'处理统计.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('Deleted reasons',Counter(d['reason'] for d in ds if d['decision']=='不相关删除'))
if __name__=='__main__':
    import sys
    if 'assess' in sys.argv:assess()
    elif 'finish' in sys.argv:finish()
    else:prep()
