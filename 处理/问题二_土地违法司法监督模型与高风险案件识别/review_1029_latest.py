import pathlib,json,re,hashlib,collections,csv,sys
from review_1029 import parse,norm,walk
R=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二";O=R/'reports'/'1029最新批次审查';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),'utf8')
def archives():return sorted(R.glob('北大法宝*20261029*.zip'))
def prep():
 previous=R/'reports'/'1029审查'
 old=json.loads((previous/'现有目录.json').read_text('utf8'))+[d for d in json.loads((previous/'审查决定.json').read_text('utf8')) if d['decision']=='新增保留']
 for d in old:d['file']=d.get('file',d['source'])
 assert len(old)==len(list((R/'裁判文书').glob('*.doc*')))==3580
 ids={d['id']:d for d in old};bodies={norm(d['core']):d for d in old};keys={(norm(d['court']),norm(d['case'])):d for d in old if d['case'] and not re.search('[X某×]',d['case'])}
 ds=[];seen={};occ=[];errors=[];zs=[]
 for z in archives():
  rawzip=z.read_bytes();zs.append(dict(name=z.name,sha256=hashlib.sha256(rawzip).hexdigest(),bytes=len(rawzip)))
  for src,name,raw in walk(rawzip,z.name):
   try:d=parse(raw,name,src)
   except Exception as e:errors.append(dict(source=src,name=name,error=str(e)));continue
   occ.append(dict(id=d['id'],source=src,name=name,sha256=d['sha256']))
   if d['id'] in seen:continue
   seen[d['id']]=d
   m=ids.get(d['id']) or bodies.get(norm(d['core']));d['duplicate']=m['id'] if m else None
   k=(norm(d['court']),norm(d['case']));d['case_match']=keys[k]['id'] if k in keys else None
   substantive=d['core'].split('当事人',1)[-1]
   d['evidence']=[s.strip() for s in re.split('[。\n]',substantive) if re.search(r'土地管理法|土地行政处罚|(?:非法|违法)占用|擅自改变林地用途|退还.{0,300}土地|恢复土地原状|改变.{0,30}林地用途',s)]
   if m:d.update(decision='重复剔除',reason='与已有目录法宝编号或规范化正文匹配')
   elif not re.search('行审|行非|非审',d['case']):d.update(decision='不相关删除',reason='民事、诉讼或执行实施/异议/复议等程序，不是土地处罚非诉执行审查')
   elif '粤' not in d['case']:d.update(decision='不相关删除',reason='正文案号不是广东法院案件')
   else:d.update(decision='待复核',reason='需核对土地处罚事实及申请审查事项')
   ds.append(d)
 save('现有目录.json',old);save('审查决定.json',ds);save('下载出现记录.json',occ);save('压缩包清单.json',zs);save('解析错误.json',errors)
 print(dict(archives=len(zs),occurrences=len(occ),unique=len(ds),counts=dict(collections.Counter(d['decision'] for d in ds)),errors=errors))
 for d in ds:
  if not d['duplicate']:print(d['id'],d['case'],d['title'],d['decision'])
def decide():
 ds=json.loads((O/'审查决定.json').read_text('utf8'))
 for d in ds:
  if d['duplicate']:continue
  if d['id'] in ('19337553','111258857'):
   d.update(decision='重复剔除',duplicate=d['case_match'],reason='与已有文书同法院同案号；全文相似度分别为0.99927、0.99755，事实、处罚和主文一致，保留已有版本')
   continue
  if re.search('行非|行审|非审',d['case']):
   if re.search('审复',d['case']):d.update(decision='不相关删除',reason='非诉审查复议程序，沿用既有排除执行复议的程序口径；不认定其实体事项必然无关')
   elif d['id']=='19338257':d.update(decision='不相关删除',reason='平台案号与正文不符：正文为(2014)江新法执字第1579—2号终结本次执行裁定，不是非诉合法性审查')
   elif d['evidence'] and '广东省' in d['court']:
    assert re.search('不予受理|准予.{0,8}执行|准许.*撤回|准予强制执行',d['result'],re.S),d['id']
    d.update(decision='新增保留',reason='广东法院土地违法行政处罚非诉执行审查；正文明确违法用地处罚及本次审查事项')
    if '不予受理' in d['result']:d['reason']+='；不予受理，属于审查结果，保留'
    elif '撤回' in d['result']:d['reason']+='；已清理退地后撤回申请，单独标识'
   else:raise ValueError('Need review '+d['id'])
 save('审查决定.json',ds)
 print(collections.Counter(d['decision'] for d in ds))
 print('case_matches',[(d['id'],d['case_match']) for d in ds if d['decision']=='新增保留' and d['case_match']])
def finalize():
 ds=json.loads((O/'审查决定.json').read_text('utf8'));old=json.loads((O/'现有目录.json').read_text('utf8'));zs=json.loads((O/'压缩包清单.json').read_text('utf8'))
 folder=R/'裁判文书';assert len(list(folder.glob('*.doc*')))==len(old)
 keep=[d for d in ds if d['decision']=='新增保留'];assert len(keep)==30
 for getter in (lambda d:d['id'],lambda d:norm(d['core']),lambda d:(norm(d['court']),norm(d['case'])) if d['case'] and not re.search('[X某×]',d['case']) else d['id']):
  values=[getter(d) for d in old+keep];assert len(values)==len(set(values)),'Duplicate found'
 # Verify the existing source directory against the saved, previously audited hashes.
 for d in old:assert hashlib.sha256(pathlib.Path(d['file']).read_bytes()).hexdigest()==d['sha256']
 stage=O/'临时解压';assert not stage.exists();stage.mkdir();assert stage.resolve().is_relative_to(R.resolve())
 lookup={d['id']:d for d in ds};processed=set();occ=[];by=collections.defaultdict(collections.Counter)
 for z in zs:
  pz=R/z['name'];rawzip=pz.read_bytes();assert hashlib.sha256(rawzip).hexdigest()==z['sha256']
  for src,name,raw in walk(rawzip,pz.name):
   m=re.search(r'FBMCLI\.C\.(\d+)',name);ident=m[1] if m else parse(raw,name,src)['id'];d=lookup[ident]
   p=stage/(str(len(occ))+'.doc');p.write_bytes(raw);assert p.resolve().parent==stage.resolve()
   decision=d['decision'] if ident not in processed else '批内重复下载剔除'
   if decision=='新增保留':
    assert hashlib.sha256(raw).hexdigest()==d['sha256']
    safe=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',d['title'][:60]+'__'+d['case']+'__'+ident)+'.doc';target=folder/safe;assert not target.exists()
    p.replace(target);d['file']=str(target);assert hashlib.sha256(target.read_bytes()).hexdigest()==d['sha256']
   else:p.unlink()
   processed.add(ident);by[pz.name][decision]+=1;occ.append(dict(source=src,name=name,id=ident,decision=decision,reason=d['reason'],sha256=hashlib.sha256(raw).hexdigest()))
 assert not list(stage.iterdir());stage.rmdir();assert len(processed)==len(ds)
 assert len(list(folder.glob('*.doc*')))==len(old)+len(keep)
 counts=collections.Counter(d['decision'] for d in occ);summary=dict(archives=len(zs),downloads=len(occ),unique_ids=len(ds),decisions=dict(counts),before=len(old),added=len(keep),after=len(old)+len(keep),total_bytes=sum(p.stat().st_size for p in folder.glob('*.doc*')),by_archive={k:dict(v) for k,v in by.items()},original_archives_preserved=True,missing_seventh_archive=True)
 save('审查决定.json',ds);save('解压文件处理记录.json',occ);save('处理统计.json',summary)
 catalog=[dict(id=d['id'],title=d['title'],case=d['case'],court=d['court'],date=d['date'],file=d['file'],sha256=d['sha256']) for d in old+keep];save('合并后文书目录.json',catalog)
 with (O/'逐份审查清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['编号','标题','案号','法院','处理','理由','正文证据','裁定主文','匹配编号','保存位置'])
  for d in ds:w.writerow([d['id'],d['title'],d['case'],d['court'],d['decision'],d['reason'],'；'.join(d['evidence'])[:1800],d['result'],d['duplicate'],d.get('file','')])
 lines=['# 最新批次审查结果','','本次工作目录仅发现6个新北大法宝ZIP（17472154、17480126、17484417、17493226、17501845、17510412）；未发现用户所指第7批，已请求提供位置。没有将之前已完成的批次算作本次新处理。','','沿用广东法院土地违法行政处罚非诉执行审查口径，不限年份，含改变林地用途。旧案使用“行非诉审”“立行非执”等案号，依正文判断程序；不因旧案号无“粤”字而排除。土地处罚非诉申请不予受理及撤回裁定保留；行政诉讼、执行实施和复议裁定按既有程序范围排除。','','6包300份下载，150个不同法宝编号。150份批次间重复下载、33份与现有目录重复、87份不符合程序/事项范围，新增30份。原3580份增加至3610份。全部解压DOC按审查结论清理，原始ZIP保留。法宝编号、法院案号及规范化正文校验无重复；原有文件SHA256均未改变。','','主要边界：19338257平台写非诉审查案号，正文实际为执行终本裁定，删除；梅县等“立行非执”文书实为土地处罚非诉申请不予受理，保留；27434682为土地已清理退还后撤回申请，保留；审复程序按既有范围排除并明确其可能具有实体研究参考价值。','','采用逐份正文规则筛查与边界原文复核，不称为独立双人标注。','','|压缩包|新增|已有重复|批间重复|不相关|','|---|---:|---:|---:|---:|']
 for k,v in by.items():lines.append(f"|{k}|{v['新增保留']}|{v['重复剔除']}|{v['批内重复下载剔除']}|{v['不相关删除']}|")
 lines+=['','|编号|案号|处理|理由|','|---|---|---|---|']
 for d in ds:lines.append('|'+ '|'.join([d['id'],d['case'],d['decision'],d['reason']])+'|')
 (O/'审查结果.md').write_text('\n'.join(lines),'utf8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='decide':decide()
 elif len(sys.argv)>1 and sys.argv[1]=='finalize':finalize()
 else:prep()

