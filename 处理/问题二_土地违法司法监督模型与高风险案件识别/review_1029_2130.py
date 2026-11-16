import pathlib,json,re,hashlib,collections,csv,sys,difflib
from review_1029 import parse,norm,walk
R=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二";O=R/'reports'/'1029_21302051审查';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),'utf8')
def prep():
 p=R/'reports'/'1029最新批次审查'
 old=json.loads((p/'现有目录.json').read_text('utf-8-sig'))+[d for d in json.loads((p/'审查决定.json').read_text('utf-8-sig')) if d['decision']=='新增保留']
 assert len(old)==len(list((R/'裁判文书').glob('*.doc*')))==3610
 ids={d['id']:d for d in old};bodies={norm(d['core']):d for d in old};keys={(norm(d['court']),norm(d['case'])):d for d in old if d['case'] and not re.search('[X某×]',d['case'])}
 ds=[];occ=[];seen=set();errors=[];z=next(R.glob('*21302051*.zip'));rawzip=z.read_bytes();save('来源.json',dict(name=z.name,sha256=hashlib.sha256(rawzip).hexdigest()))
 for src,name,raw in walk(rawzip,z.name):
  try:d=parse(raw,name,src)
  except Exception as e:errors.append(dict(source=src,name=name,error=str(e)));continue
  occ.append(dict(id=d['id'],source=src,name=name,sha256=d['sha256']))
  if d['id'] in seen:continue
  seen.add(d['id']);m=ids.get(d['id']) or bodies.get(norm(d['core']));d['duplicate']=m['id'] if m else None
  k=(norm(d['court']),norm(d['case']));d['case_match']=keys[k]['id'] if k in keys else None
  sub=d['core'].split('当事人',1)[-1]
  d['evidence']=[s.strip() for s in re.split('[。\n]',sub) if re.search(r'土地管理法|土地行政处罚|(?:非法|违法)占用|擅自改变林地用途|退还.{0,300}土地|恢复土地原状|改变.{0,30}林地用途',s)]
  if m:d.update(decision='重复剔除',reason='与现有文书法宝编号或规范化正文一致')
  elif re.search('行审|行非|非审|非诉',d['case']+d['title']):d.update(decision='待复核',reason='核对本次程序、土地处罚及主文')
  else:d.update(decision='不相关删除',reason='民事、行政诉讼或执行实施等程序，不属于土地行政处罚非诉执行审查')
  ds.append(d)
 save('现有目录.json',old);save('审查决定.json',ds);save('下载出现记录.json',occ);save('解析错误.json',errors)
 print(dict(downloads=len(occ),unique=len(ds),counts=dict(collections.Counter(d['decision'] for d in ds)),errors=errors))
 for d in ds:
  if not d['duplicate']:print(d['id'],d['case'],d['title'],d['decision'])
def decide():
 ds=json.loads((O/'审查决定.json').read_text('utf8'));old=json.loads((O/'现有目录.json').read_text('utf8'));idx={d['id']:d for d in old};seen={};matches=[]
 for d in ds:
  if d['decision']!='待复核':continue
  if d['id']=='44815534':d.update(decision='不相关删除',reason='平台字段错误，正文为湖南省汉寿县人民法院案件，非广东')
  elif '审复' in d['case']:d.update(decision='不相关删除',reason='非诉执行审查复议程序，沿用既有排除复议程序的范围')
  else:
   assert '广东' in d['court'] and d['evidence'] and re.search('处罚',d['core'])
   assert re.search('准予|准许|不予|不准予|驳回',d['result'])
   d.update(decision='新增保留',reason='广东土地违法行政处罚非诉执行审查；正文有违法用地事实、处罚及本次审查结论')
   if '驳回' in d['result']:d['reason']+='；含驳回申请结论，保留负向或部分准予结果'
   elif '不予' in d['result'] or '不准予' in d['result']:d['reason']+='；不予执行，保留负向结果'
   elif '撤回' in d['result']:d['reason']+='；准予撤回申请，单独标识'
   k=(norm(d['court']),norm(d['case']));match=idx.get(d['case_match']) or seen.get(k)
   if match:
    ratio=difflib.SequenceMatcher(None,norm(d['core']),norm(match['core']),autojunk=False).ratio();assert ratio>.97,(d['id'],match['id'],ratio)
    d.update(decision='重复剔除',duplicate=match['id'],reason=f"同法院同案号，事实及主文一致，全文相似度{ratio:.6f}；保留{match['id']}");matches.append(dict(id=d['id'],matched=match['id'],ratio=ratio))
   else:seen[k]=d
 save('审查决定.json',ds);save('同案不同编号核对.json',matches)
 print(collections.Counter(d['decision'] for d in ds));print(matches)
def finalize():
 ds=json.loads((O/'审查决定.json').read_text('utf8'));old=json.loads((O/'现有目录.json').read_text('utf8'));source=json.loads((O/'来源.json').read_text('utf8'));folder=R/'裁判文书';keep=[d for d in ds if d['decision']=='新增保留']
 assert len(old)==len(list(folder.glob('*.doc*')))==3610
 for getter in (lambda d:d['id'],lambda d:norm(d['core']),lambda d:(norm(d['court']),norm(d['case'])) if d['case'] and not re.search('[X某×]',d['case']) else d['id']):
  values=[getter(d) for d in old+keep];assert len(values)==len(set(values))
 for d in old:assert hashlib.sha256(pathlib.Path(d['file']).read_bytes()).hexdigest()==d['sha256']
 z=R/source['name'];rawzip=z.read_bytes();assert hashlib.sha256(rawzip).hexdigest()==source['sha256']
 stage=O/'临时解压';assert not stage.exists();stage.mkdir();assert stage.resolve().is_relative_to(R.resolve())
 idx={d['id']:d for d in ds};seen=set();occ=[]
 for src,name,raw in walk(rawzip,z.name):
  m=re.search(r'FBMCLI\.C\.(\d+)',name);ident=m[1] if m else parse(raw,name,src)['id'];d=idx[ident];decision=d['decision'] if ident not in seen else '批内重复下载剔除'
  p=stage/(str(len(occ))+'.doc');assert p.resolve().parent==stage.resolve();p.write_bytes(raw)
  if decision=='新增保留':
   assert hashlib.sha256(raw).hexdigest()==d['sha256'];safe=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',d['title'][:60]+'__'+d['case']+'__'+ident)+'.doc';target=folder/safe;assert not target.exists();p.replace(target);d['file']=str(target);assert hashlib.sha256(target.read_bytes()).hexdigest()==d['sha256']
  else:p.unlink()
  seen.add(ident);occ.append(dict(id=ident,source=src,name=name,decision=decision,reason=d['reason'],sha256=hashlib.sha256(raw).hexdigest()))
 assert not list(stage.iterdir());stage.rmdir();assert len(seen)==len(ds) and len(occ)==700
 assert len(list(folder.glob('*.doc*')))==len(old)+len(keep)
 counts=collections.Counter(d['decision'] for d in occ);summary=dict(downloads=len(occ),unique_ids=len(ds),decisions=dict(counts),before=len(old),added=len(keep),after=len(old)+len(keep),total_bytes=sum(p.stat().st_size for p in folder.glob('*.doc*')),parse_errors=0,original_archive_preserved=True)
 save('审查决定.json',ds);save('解压文件处理记录.json',occ);save('处理统计.json',summary)
 save('合并后文书目录.json',[dict(id=d['id'],title=d['title'],case=d['case'],court=d['court'],date=d['date'],file=d['file'],sha256=d['sha256']) for d in old+keep])
 with (O/'逐份审查清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['编号','标题','案号','法院','日期','处理','理由','正文证据','主文','匹配编号','保存位置'])
  for d in ds:w.writerow([d['id'],d['title'],d['case'],d['court'],d['date'],d['decision'],d['reason'],'；'.join(d['evidence'])[:1800],d['result'],d['duplicate'],d.get('file','')])
 lines=['# 2026102921302051 (2) 批次审查','','范围：广东土地违法行政处罚非诉执行审查，不限年份，含林地用途违法；保留准予、不予、驳回、部分准予和相关撤回裁定。行政诉讼、执行实施及复议按既有范围排除。逐份正文规则筛查，并复核平台字段冲突、程序误标及同案副本，不声称进行了独立双人标注。','','700份下载，200个不同法宝编号；处理数量见下表。所有不符合及重复解压DOC已删除，原ZIP保留；旧3610份校验SHA256未变，合并后按编号、正文及法院案号校验无重复。','','|处理|份数|','|---|---:|']
 for k,v in counts.items():lines.append(f'|{k}|{v}|')
 lines+=['',f"处理前{len(old)}份，新增{len(keep)}份，处理后{len(old)+len(keep)}份。",'','关键复核：44815534虽平台标中山法院，实际正文是湖南汉寿法院，排除；中山部分标题标再审复查，但正文为土地处罚非诉审查，按正文保留；揭西县土地处罚申请被驳回仍属于研究对象；同法院同案号、不同法宝编号的副本经全文相似度及事实主文比对去重。','','|编号|案号|处理|理由|','|---|---|---|---|']
 for d in ds:lines.append('|'+ '|'.join([d['id'],d['case'],d['decision'],d['reason']])+'|')
 (O/'审查结果.md').write_text('\n'.join(lines),'utf8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='decide':decide()
 elif len(sys.argv)>1 and sys.argv[1]=='finalize':finalize()
 else:prep()
