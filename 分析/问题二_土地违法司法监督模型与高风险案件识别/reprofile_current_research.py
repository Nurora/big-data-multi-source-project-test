"""Read only the current source workbooks; no prior audit results are inputs."""
from pathlib import Path
from collections import Counter, defaultdict
import datetime as dt
import hashlib, io, json, re, unicodedata, zipfile
import openpyxl

ROOT = Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
OUT = ROOT / 'reports' / '当前数据重新画像_20261106'
OUT.mkdir(exist_ok=True)
def norm(v):
    if v is None: return ''
    s=unicodedata.normalize('NFKC',str(v)).strip()
    return '' if s.lower() in {'null','none','nan','未知','不详','-'} else re.sub(r'\s+','',s)
def date(v):
    if isinstance(v,(dt.datetime,dt.date)): return v.date() if isinstance(v,dt.datetime) else v
    if isinstance(v,(int,float)):
        try: return (dt.datetime(1899,12,30)+dt.timedelta(days=v)).date()
        except (OverflowError,ValueError):return None
    m=re.search(r'(20\d\d)[年/-](\d{1,2})[月/-](\d{1,2})',str(v))
    if m:
        try:return dt.date(*map(int,m.groups()))
        except ValueError:pass
    return None
def load(f):
    w=openpyxl.load_workbook(f,read_only=True,data_only=True)
    s=w['最终保留'];it=s.iter_rows(values_only=True);h=next(it)
    rows=[dict(zip(h,r),_row=i+2) for i,r in enumerate(it) if any(norm(v) for v in r)]
    w.close();return rows,list(h)
pf=next(ROOT.glob('*1106*处罚保留*.xlsx'));cf=next(ROOT.glob('*1106*裁判文书.xlsx'))
p,ph=load(pf);c,ch=load(cf)
with zipfile.ZipFile(ROOT/'广东建设用地数据.zip') as z:
    name=next(n for n in z.namelist() if n.endswith('广东省建设用地原始数据.xlsx'))
    w=openpyxl.load_workbook(io.BytesIO(z.read(name)),read_only=True,data_only=True)
    land={s.title:list(s.values) for s in w};w.close()
    inventory=[{'file':i.filename,'bytes':i.file_size} for i in z.infolist() if not i.is_dir()]
county={str(r[1]):str(r[2]) for r in land['区县年度'][1:]}
cities={str(r[1]) for r in land['地市年度'][1:]}
county.update({'云安县':'云浮市','电白县':'茂名市','阳东县':'阳江市','高要市':'肇庆市'})
def city(v):
    s=norm(v).removeprefix('广东省')
    return s if s in cities else county.get(s,'未映射')
out={'inputs':{'处罚':{'file':pf.name,'sha256':hashlib.sha256(pf.read_bytes()).hexdigest()},'裁判':{'file':cf.name,'sha256':hashlib.sha256(cf.read_bytes()).hexdigest()}}}
for tag,rows,headers,dc,gc in [('处罚',p,ph,'处罚决定日期','所属地级市'),('裁判',c,ch,'标准裁判日期','所属地区')]:
    years=Counter();cs=Counter();panel=Counter()
    for r in rows:
        d=date(r[dc]);y=str(d.year) if d else '无有效日期';ci=city(r[gc]);years[y]+=1;cs[ci]+=1;panel[(ci,y)]+=1
    out[tag]={'非空记录':len(rows),'完全重复差额':len(rows)-len({tuple(norm(r[h]) for h in headers) for r in rows}),'字段':{h:{'有效数':sum(bool(norm(r[h])) for r in rows),'不同值数':len({norm(r[h]) for r in rows if norm(r[h])}),'文本中位长度':sorted(len(norm(r[h])) for r in rows)[len(rows)//2]} for h in headers},'年份':dict(sorted(years.items())),'地区':dict(cs.most_common()),'有效地区年度数':sum(ci!='未映射' and y!='无有效日期' for ci,y in panel),'地区年度': [{'地市':ci,'年':y,'记录数':n} for (ci,y),n in sorted(panel.items())]}
out['裁判']['结果']=dict(Counter(norm(r['结果类型']) for r in c))
out['裁判']['主体类型']=dict(Counter(norm(r['行政相对人类型']) for r in c))
out['裁判']['去重案号']=len({norm(r['案号']) for r in c if norm(r['案号'])})
out['裁判']['案件名称程序关键词']={k:sum(k in norm(r['案件名称']) for r in c) for k in ['非诉','行政处罚','行政强制','再审','执行']}
rules={'住宅':'住宅|住房|建房|宅基地|自建房','厂房仓储':'厂房|仓库|车间|工厂','硬化堆放':'硬化|硬底化|堆放|堆场','农业养殖':'养殖|猪舍|鸡舍|大棚|设施农业','耕地':'耕地|农田','拆除':'拆除','没收':'没收','罚款':'罚款','退还土地':'退还.*土地'}
out['处罚']['仅关键词覆盖_不是分类结果']={k:sum(bool(re.search(rx,str(r['处罚事由'] if k in ['住宅','厂房仓储','硬化堆放','农业养殖','耕地'] else r['处罚内容'] or ''))) for r in p) for k,rx in rules.items()}
out['处罚']['内容结果完全一致']=sum(norm(r['处罚内容'])==norm(r['处罚结果']) for r in p)
out['处罚']['同机关文号主体重复差额']=len(p)-len({(norm(r['处罚机关']),norm(r['行政处罚决定书文号']),norm(r['被处罚对象'])) for r in p})
def docno(v):
    s=norm(v).split('处罚对象')[0].translate(str.maketrans('〔〕【】[]','()()()'))
    return s.replace('第','').removesuffix('号')
idx=defaultdict(list)
for r in p:
    if docno(r['行政处罚决定书文号']):idx[docno(r['行政处罚决定书文号'])].append(r)
links=[]
for r in c:
    for pr in idx.get(docno(r['涉案行政处罚决定书文号_原始']),[]):
        pd,cd=date(pr['处罚决定日期']),date(r['标准裁判日期'])
        links.append({'处罚行':pr['_row'],'裁判行':r['_row'],'主体一致':norm(pr['被处罚对象'])==norm(r['行政相对人']),'同市':city(pr['所属地级市'])==city(r['所属地区']),'时序合理':bool(pd and cd and pd<=cd),'间隔天':(cd-pd).days if pd and cd else None,'结果':norm(r['结果类型'])})
out['新做严格整字段文号规则_非人工确认']={'对数':len(links),'处罚记录':len({r['处罚行'] for r in links}),'裁判记录':len({r['裁判行'] for r in links}),'主体字面一致':sum(r['主体一致'] for r in links),'同市':sum(r['同市'] for r in links),'时序合理':sum(r['时序合理'] for r in links),'结果':dict(Counter(r['结果'] for r in links))}
def candidates(v):
    s=norm(v).translate(str.maketrans('〔〕【】[]﹝﹞','()()()()'))
    rx=r'[\u4e00-\u9fffA-Za-z()]{0,35}\(20\d{2}\)(?:\([^()]{1,10}\))?(?:第)?[A-Za-z\u4e00-\u9fff]{0,5}\d+[A-Za-z\d-]*号?'
    return {m.group(0).replace('第','').removesuffix('号') for m in re.finditer(rx,s)}
def first_candidates(v):
    # The first field often contains annotations; cut at explicit labels first.
    return candidates(re.split(r'处罚对象|执法依据|行政处罚信息',str(v))[0])
ix=defaultdict(list)
for pr in p:
    for key in first_candidates(pr['行政处罚决定书文号']):ix[key].append(pr)
ex=[]
for cr in c:
    seen=set()
    for key in candidates(cr['涉案行政处罚决定书文号_原始']):
        for pr in ix.get(key,[]):
            if pr['_row'] in seen:continue
            seen.add(pr['_row']);pd,cd=date(pr['处罚决定日期']),date(cr['标准裁判日期'])
            ex.append({'处罚行':pr['_row'],'裁判行':cr['_row'],'案号':norm(cr['案号']),'主体一致':norm(pr['被处罚对象'])==norm(cr['行政相对人']),'同市':city(pr['所属地级市'])==city(cr['所属地区']),'时序合理':bool(pd and cd and pd<=cd),'结果':norm(cr['结果类型'])})
out['新做嵌入文号抽取规则_非人工确认']={'对数':len(ex),'处罚记录':len({r['处罚行'] for r in ex}),'裁判案号':len({r['案号'] for r in ex}),'同市':sum(r['同市'] for r in ex),'主体一致':sum(r['主体一致'] for r in ex),'时序合理':sum(r['时序合理'] for r in ex),'结果':dict(Counter(r['结果'] for r in ex))}
pp={(r['地市'],r['年']):r['记录数'] for r in out['处罚']['地区年度']}
cp={(r['地市'],r['年']):r['记录数'] for r in out['裁判']['地区年度']}
out['共同地区年度']={str(t):sum(k[0]!='未映射' and pp[k]>=t and cp.get(k,0)>=t for k in pp) for t in [1,10,20,30]}
out['土地']={'表结构':{k:{'行数':len(v),'首行':list(v[0])} for k,v in land.items()},'地市数':len(cities),'区县数':len({r[0] for r in land['区县年度'][1:]}),'年份':sorted({r[2] for r in land['地市年度'][1:]}),'2015至2025栅格字节':sum(i['bytes'] for i in inventory if re.search(r'_(201[5-9]|202[0-5])\.tif$',i['file']))}
out['新增字段提取前提']={'裁判表无正文和审查理由':True,'处罚表无独立结构化金额面积用途主体类型':True}
(OUT/'直接读取当前文件统计.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
(OUT/'新文号规则候选.json').write_text(json.dumps(links,ensure_ascii=False,indent=2),encoding='utf-8')
for tag in ['处罚','裁判']:
    t=out[tag];print(tag,json.dumps({k:v for k,v in t.items() if k not in ['字段','地区年度']},ensure_ascii=False))
print('字段',json.dumps({k:out[k]['字段'] for k in ['处罚','裁判']},ensure_ascii=False))
print('关联',json.dumps(out['新做严格整字段文号规则_非人工确认'],ensure_ascii=False))
print('土地',json.dumps(out['土地'],ensure_ascii=False))
