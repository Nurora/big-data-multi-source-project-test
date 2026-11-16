import pathlib, sys, ast, struct, re, json, hashlib, zipfile, io, unicodedata, collections, csv
R=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
O=R/'reports'/'1029审查';O.mkdir(exist_ok=True)
ns={'struct':struct}
tree=ast.parse((R/'scripts/screen_pkulaw.py').read_text('utf8'))
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('ole_streams','doc_text')],type_ignores=[]),'decoder','exec'),ns)
def norm(t):return re.sub(r'[^\w\u4e00-\u9fff]','',unicodedata.normalize('NFKC',t))
def walk(raw,src):
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  for e in z.infolist():
   if e.is_dir():continue
   b=z.read(e)
   if e.filename.lower().endswith('.zip'):yield from walk(b,src+'/'+e.filename)
   elif e.filename.lower().endswith(('.doc','.docx')):yield src,e.filename,b
def parse(raw,name,src):
 t=ns['doc_text'](raw)
 t=re.sub(r'\x13[^\x14]*\x14','',t).replace('\x15','');t=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','\n',t)
 def field(l):
  m=re.search(l+r'\s*[：:]\s*([^\n]+)',t);return m[1].strip() if m else ''
 m=re.search(r'FBMCLI\.C\.(\d+)|CLI\.C\.(\d+)',name+'\n'+t)
 b=t.split('//',1)[-1].split('©北大法宝')[0].strip()
 core=re.split(r'附法律依据|附[：:]本裁定|附本裁定|本案法律依据|同案由重要案例|本法院同类案例',b)[0]
 case=field(r'案\s*号')
 cases=re.findall(r'[（(]\d{4}[）)][\u4e00-\u9fff\d]{1,18}号(?:之[一二三四五六七八九十]+)?',core)
 if cases:case=cases[0]
 result=re.split(r'裁判结果|裁定如下[：:，,]?',core)[-1]
 result=re.split(r'落款|审\s*判\s*长|审\s*判\s*员',result)[0].strip()
 return dict(id=next(x for x in m.groups() if x) if m else hashlib.sha256(raw).hexdigest(),name=name,source=src,title=re.sub(r'\(FBMCLI.*','',pathlib.PurePosixPath(name).name),case=case,court=field('审理法院'),date=field('审结日期'),body=b,core=core,result=result,sha256=hashlib.sha256(raw).hexdigest())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),'utf8')
def prep():
 old=[parse(p.read_bytes(),p.name,str(p)) for p in (R/'裁判文书').glob('*.doc*')];save('现有目录.json',old)
 ids={d['id']:d for d in old};bodies={norm(d['core']):d for d in old};keys={(norm(d['court']),norm(d['case'])):d for d in old if d['case'] and not re.search('[X某×]',d['case'])}
 ds=[];seen={};occ=[];errors=[]
 for src,name,raw in walk(next(R.glob('*17284531*.zip')).read_bytes(),'2026102917284531 (2).zip'):
  try:d=parse(raw,name,src)
  except Exception as e:errors.append(dict(source=src,name=name,error=str(e)));continue
  occ.append(dict(id=d['id'],source=src,name=name))
  if d['id'] in seen:continue
  seen[d['id']]=d
  match=ids.get(d['id']) or bodies.get(norm(d['core']))
  d['duplicate']=match['id'] if match else None
  k=(norm(d['court']),norm(d['case']));d['case_match']=keys[k]['id'] if k in keys else None
  d['evidence']=[s.strip() for s in re.split('[。\n]',d['core']) if re.search(r'土地管理法|土地行政处罚|非法.{0,10}(占用|转让|买卖).{0,40}土地|擅自.{0,20}(改变|占用).{0,20}林地|改变林地用途|退还.{0,25}土地|违法占用',s)]
  ds.append(d)
 save('候选原文.json',ds);save('下载出现记录.json',occ);save('解析错误.json',errors)
 print(dict(old=len(old),occurrences=len(occ),unique=len(ds),duplicates=sum(bool(d['duplicate']) for d in ds),case_matches=sum(bool(d['case_match']) and not d['duplicate'] for d in ds),errors=errors))
 print('Full extracted text and evidence saved in 候选原文.json')
def assess():
 ds=json.loads((O/'候选原文.json').read_text('utf8'))
 for d in ds:
  c=d['core'];r=d['result'];case=d['case']
  if d['duplicate']:decision='重复剔除';reason='与已有目录法宝编号或规范化正文相同'
  elif not re.search(r'行审|行非|非审',case):decision='不相关删除';reason='本件为民事、诉讼或执行实施/异议/复议程序，不属于土地处罚非诉执行审查裁定'
  elif not '粤' in case:decision='不相关删除';reason='正文案号不属于广东法院'
  elif d['evidence'] and re.search('处罚',c) and re.search(r'(准予|准许|不予|不准予|不准许).{0,12}(强制)?执行|撤回.{0,80}(强制)?执行申请',r):decision='拟保留';reason='广东土地违法行政处罚非诉执行审查，正文有土地违法事实及执行审查结论'
  else:decision='待复核';reason='需审查正文事实、申请事项和裁定主文'
  d.update(decision=decision,reason=reason)
 save('审查决定.json',ds)
 print(collections.Counter(d['decision'] for d in ds))
 for d in ds:
  if d['decision']=='待复核':print(d['id'],d['case'],d['title'],'\n',d['core'],'\n')
def decide():
 ds=json.loads((O/'审查决定.json').read_text('utf8'))
 for d in ds:
  if d['decision'] in ('拟保留','待复核'):
   substantive=d['core'].split('当事人',1)[-1]
   d['evidence']=[s.strip() for s in re.split('[。\n]',substantive) if re.search(r'土地管理法|土地行政处罚|(?:非法|违法)占用|擅自改变林地用途|退还.{0,300}土地|恢复土地原状|改变.{0,30}林地用途',s)]
   if d['id']=='575712782':d.update(decision='不相关删除',reason='正文为追回茶叶产业园财政补助资金5250868.03元；用地问题仅属项目背景，不是土地违法行政处罚')
   elif d['id']=='560863946':d.update(decision='不相关删除',reason='标题与正文不符：实际执行公共租赁住房腾退及租金，不是土地违法处罚')
   elif d['id']=='561056170':d.update(decision='证据不足排除',reason='撤回执行裁定正文仅载处罚编号，未披露违法事实及处罚内容；标题不足以确认土地违法处罚，按既有严格口径排除')
   else:
    assert d['evidence'],d['id']
    d.update(decision='新增保留',reason='广东法院土地违法行政处罚非诉执行审查；正文披露土地违法事实/处罚事项')
    if '撤回' in d['result']:d['reason']+='；准许撤回申请，单独标识，不视为准予实体执行'
    elif '驳回' in d['result']:d['reason']+='；驳回强制执行申请，保留负向审查结果'
    elif re.search('不予|不准予',d['result']):d['reason']+='；不予/不准予执行'
  if d['decision']=='不相关删除' and '程序' in d['reason']:
   if re.search('民',d['case']):d['reason']='民事纠纷裁定（包括租赁、借款、物权、合同等），不属于土地行政处罚非诉执行审查'
   elif re.search('执',d['case']):d['reason']='执行实施、执行异议或执行复议裁定，不属于本项目非诉执行合法性审查文书'
   elif re.search('行初|行终|行申|行再',d['case']):d['reason']='行政诉讼或再审程序裁定，不属于本项目行政处罚非诉执行审查'
 save('审查决定.json',ds)
 print(collections.Counter(d['decision'] for d in ds))
def finalize():
 ds=json.loads((O/'审查决定.json').read_text('utf8'));old=json.loads((O/'现有目录.json').read_text('utf8'))
 folder=R/'裁判文书';stage=O/'临时解压';assert not stage.exists();assert len(list(folder.glob('*.doc*')))==len(old)==3382
 for d in old:assert hashlib.sha256(pathlib.Path(d['source']).read_bytes()).hexdigest()==d['sha256']
 assert not any(d['decision'] in ('拟保留','待复核') for d in ds)
 keep=[d for d in ds if d['decision']=='新增保留'];assert len(keep)==198
 combined=old+keep
 for getter in (lambda d:d['id'],lambda d:norm(d['core']),lambda d:(norm(d['court']),norm(d['case'])) if d['case'] and not re.search('[X某×]',d['case']) else d['id']):
  values=[getter(d) for d in combined];assert len(values)==len(set(values)),'duplicate keys'
 stage.mkdir();lookup={d['id']:d for d in ds};processed=set();occ=[];added=[]
 for src,name,raw in walk(next(R.glob('*17284531*.zip')).read_bytes(),'2026102917284531 (2).zip'):
  m=re.search(r'FBMCLI\.C\.(\d+)',name);ident=m[1] if m else parse(raw,name,src)['id'];d=lookup[ident]
  p=stage/(str(len(occ))+'.doc');p.write_bytes(raw)
  assert p.resolve().is_relative_to(stage.resolve()) and stage.resolve().is_relative_to(R.resolve())
  decision=d['decision'] if ident not in processed else '批内重复下载剔除'
  row=dict(id=ident,source=src,name=name,decision=decision,reason=d['reason'],sha256=hashlib.sha256(raw).hexdigest());occ.append(row)
  if decision=='新增保留':
   assert row['sha256']==d['sha256']
   safe=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',d['title'][:60]+'__'+d['case']+'__'+ident)+'.doc'
   target=folder/safe;assert not target.exists();p.replace(target);d['file']=str(target);added.append(d)
   assert hashlib.sha256(target.read_bytes()).hexdigest()==d['sha256']
  else:p.unlink()
  processed.add(ident)
 assert len(occ)==2000 and len(processed)==1900 and len(added)==198
 assert not list(stage.iterdir());stage.rmdir()
 assert len(list(folder.glob('*.doc*')))==3580
 catalog=[dict(id=d['id'],title=d['title'],case=d['case'],court=d['court'],date=d['date'],file=d.get('file',d['source']),sha256=d['sha256']) for d in combined]
 for d in catalog:assert pathlib.Path(d['file']).exists()
 save('合并后文书目录.json',catalog);save('审查决定.json',ds);save('解压文件处理记录.json',occ)
 counts=collections.Counter(d['decision'] for d in ds);year=collections.Counter(d['date'][:4] or '未知' for d in added)
 summary=dict(downloads=2000,unique_ids=1900,within_batch_duplicates=100,existing_duplicates=counts['重复剔除'],unrelated=counts['不相关删除'],insufficient=counts['证据不足排除'],added=len(added),before=3382,after=3580,added_years=dict(year),added_bytes=sum(pathlib.Path(d['file']).stat().st_size for d in added),total_bytes=sum(p.stat().st_size for p in folder.glob('*.doc*')),parse_errors=0,original_archive_preserved=True)
 save('处理统计.json',summary)
 with (O/'逐份审查清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['法宝编号','标题','正文案号','法院','日期','处理','理由','正文证据','裁定主文','匹配已有编号','保存位置'])
  for d in ds:w.writerow([d['id'],d['title'],d['case'],d['court'],d['date'],d['decision'],d['reason'],'；'.join(d['evidence'])[:1800],d['result'],d['duplicate'],d.get('file','')])
 lines=['# 2026102917284531 (2) 批次审查结果','','沿用既有口径：广东法院土地违法行政处罚非诉执行审查，含改变林地用途；不限年份。准予、不准予、驳回和有明确土地处罚事实的撤回申请裁定均保留，并区分结果。排除民事、刑事、行政诉讼、执行实施/异议/复议及其他行政管理事项。标题、机关名称和土地关键词不单独作为纳入依据。','','采用逐件正文规则审查，重点人工复核标题正文冲突、证据稀少、撤回和驳回等边界记录；不声称进行了两名人工标注员独立复核。','','## 处理数量','','|项目|数量|','|---|---:|','|下载文书|2000|','|批内重复下载|100|','|与已有文书重复|195|','|不相关删除|1506|','|证据不足排除|1|','|新增保留|198|','|处理前|3382|','|处理后|3580|','','2000 = 100 + 195 + 1506 + 1 + 198。所有解压出的重复、不相关及证据不足DOC已删除；原始下载ZIP保留作来源备份。既有3382份均校验SHA256，未改动。合并目录按法宝编号、规范化正文、法院及完整案号校验无重复。案号不同的同名/匿名当事人、不同地块、不同处罚事项不直接判为重复。','','## 关键边界判断','','- 560863946：标题写退还非法占用土地，正文却为公租房退出与租金执行，删除。','- 575712782：茶叶产业园财政补助资金追回，用地审批仅属背景，删除。','- 561056170：正文未披露土地违法事实和处罚内容，仅标题相关、正文为撤回，证据不足排除；不据此断定实体上绝无土地违法。','- 569550117、561842861、561192485、556540724：分别涉及处罚已撤销、行政机关自行执行权限、催告期限、没收标的不明确等驳回理由，均属土地处罚审查，保留。','','## 新增年份','','|审结年份|新增|','|---|---:|']
 for y,n in sorted(year.items()):lines.append(f'|{y}|{n}|')
 lines+=['','## 新增及边界文书明细','','|法宝编号|正文案号|处理|依据|','|---|---|---|---|']
 for d in ds:
  if d['decision'] in ('新增保留','证据不足排除') or d['id'] in ('560863946','575712782'):lines.append('|'+ '|'.join([d['id'],d['case'],d['decision'],d['reason']])+'|')
 (O/'审查结果.md').write_text('\n'.join(lines),'utf8')
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='assess':assess()
 elif len(sys.argv)>1 and sys.argv[1]=='decide':decide()
 elif len(sys.argv)>1 and sys.argv[1]=='finalize':finalize()
 else:prep()
