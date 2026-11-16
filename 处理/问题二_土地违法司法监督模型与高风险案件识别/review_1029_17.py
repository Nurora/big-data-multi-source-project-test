import pathlib,json,re,hashlib,collections,csv,sys,difflib
from review_1029 import parse,norm,walk as walk_one
R=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二";O=R/'reports'/'1029_17批审查';O.mkdir(exist_ok=True)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),'utf8')

def walk(raw,src):
 zs=sorted(R.glob('北大法宝*20261029*.zip'))[-17:];assert len(zs)==17 and '23225139' in zs[0].name
 manifest=[dict(name=z.name,sha256=hashlib.sha256(z.read_bytes()).hexdigest()) for z in zs]
 mp=O/'来源清单.json'
 if mp.exists():assert json.loads(mp.read_text('utf8'))==manifest
 else:save('来源清单.json',manifest)
 for z in zs:yield from walk_one(z.read_bytes(),z.name)

def prep():
 p=R/'reports'/'1029_47批审查'
 old=json.loads((p/'现有目录.json').read_text('utf-8-sig'))+[d for d in json.loads((p/'审查决定.json').read_text('utf-8-sig')) if d['decision']=='新增保留']
 assert len(old)==len(list((R/'裁判文书').glob('*.doc*')))==5294
 ids={d['id']:d for d in old};bodies={norm(d['core']):d for d in old};keys={(norm(d['court']),norm(d['case'])):d for d in old if d['case'] and not re.search('[X某×]',d['case'])}
 ds=[];occ=[];seen=set();errors=[];z=sorted(R.glob('北大法宝*20261029*.zip'))[-17];rawzip=z.read_bytes();save('来源.json',dict(name=z.name,sha256=hashlib.sha256(rawzip).hexdigest()))
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
  if d['decision']=='待复核' and (not d['evidence'] or not re.search('处罚',d['core'])):print('WEAK',d['id'],d['case'],d['title'])
def decide():
 ds=json.loads((O/'审查决定.json').read_text('utf8'));old=json.loads((O/'现有目录.json').read_text('utf8'));idx={d['id']:d for d in old};seen={};matches=[]
 for d in ds:
  sub=d['core'].split('\n',1)[-1]
  d['evidence']=[s.strip() for s in re.split('[。\n]',sub) if re.search(r'土地管理法|土地行政处罚|(?:非法|违法)占用|擅自改变林地用途|擅自占用|退还.{0,300}土地|恢复土地原状|改变.{0,30}林地用途',s)]
  if d['id'] in ('75689196','73942157','72325457','74949986','73014990') and not d['duplicate']:
   d.update(case_raw=d['case'],case='',case_quality='平台仅列年份和序号；正文无完整法院案号，不推造',decision='待复核')
  if d['decision']!='待复核':continue
  if d['id']=='44815534':d.update(decision='不相关删除',reason='平台字段错误，正文为湖南省汉寿县人民法院案件，非广东')
  elif d['id']=='112217713':d.update(decision='不相关删除',reason='执行事项为行政决定责令交出已有房地产权证的宅基地及裁执分离组织实施，非土地违法行政处罚审查')
  elif d['id']=='42611991':d.update(decision='不相关删除',reason='本次执行征收后的交地通知书和清场交地，不是土地违法行政处罚')
  elif '审复' in d['case']:d.update(decision='不相关删除',reason='非诉执行审查复议程序，沿用既有排除复议程序的范围')
  else:
   assert '广东' in d['court'] and d['evidence'] and re.search('处罚',d['core'])
   assert re.search('准予|准许|不予|不准予|驳回',d['result']) or d['id'] in ('64990494','64806759')
   d.update(decision='新增保留',reason='广东土地违法行政处罚非诉执行审查；正文有违法用地事实、处罚及本次审查结论')
   if '驳回' in d['result']:d['reason']+='；含驳回申请结论，保留负向或部分准予结果'
   elif '不予' in d['result'] or '不准予' in d['result']:d['reason']+='；不予执行，保留负向结果'
   elif '撤回' in d['result']:d['reason']+='；准予撤回申请，单独标识'
   if d['id'] in ('64990494','64806759'):d['reason']+='；主文直接裁定由行政机关组织实施，正文已完成处罚执行合法性审查，保留'
   if d.get('case_quality'):d['reason']+='；完整案号缺失，以法宝编号及正文定位'
   k=(norm(d['court']),norm(d['case'])) if d['case'] else ('id',d['id']);match=idx.get(d['case_match']) or seen.get(k)
   if match:
    ratio=difflib.SequenceMatcher(None,norm(d['core']),norm(match['core']),autojunk=False).ratio()
    assert ratio>.97 or (d['id'],match['id'])==('76303778','56567440'),(d['id'],match['id'],ratio)
    d.update(decision='重复剔除',duplicate=match['id'],reason=f"同法院同案号，事实及主文一致，全文相似度{ratio:.6f}；保留{match['id']}");matches.append(dict(id=d['id'],matched=match['id'],ratio=ratio))
    if d['id']=='76303778':d['reason']+='；原文逐段核对同为梁国明、3-1号处罚、30平方米及600元，新增版本缺少部分法律引文，保留已有完整版本'
   else:seen[k]=d
 save('审查决定.json',ds);save('同案不同编号核对.json',matches)
 print(collections.Counter(d['decision'] for d in ds));print(matches)
def finalize():
 ds=json.loads((O/'审查决定.json').read_text('utf8'));old=json.loads((O/'现有目录.json').read_text('utf8'));source=json.loads((O/'来源.json').read_text('utf8'));folder=R/'裁判文书';keep=[d for d in ds if d['decision']=='新增保留']
 assert len(old)==len(list(folder.glob('*.doc*')))==5294
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
 assert not list(stage.iterdir());stage.rmdir();assert len(seen)==len(ds) and len(occ)==len(json.loads((O/'下载出现记录.json').read_text('utf8')))
 assert len(list(folder.glob('*.doc*')))==len(old)+len(keep)
 counts=collections.Counter(d['decision'] for d in occ);summary=dict(downloads=len(occ),unique_ids=len(ds),decisions=dict(counts),before=len(old),added=len(keep),after=len(old)+len(keep),total_bytes=sum(p.stat().st_size for p in folder.glob('*.doc*')),parse_errors=0,original_archive_preserved=True)
 summary['archives']=17
 summary['includes_previously_processed_archive']=False
 summary['by_archive']={name:dict(collections.Counter(d['decision'] for d in occ if d['source'].split('/')[0]==name)) for name in sorted({d['source'].split('/')[0] for d in occ})}
 save('审查决定.json',ds);save('解压文件处理记录.json',occ);save('处理统计.json',summary)
 save('合并后文书目录.json',[dict(id=d['id'],title=d['title'],case=d['case'],case_raw=d.get('case_raw',''),case_quality=d.get('case_quality',''),court=d['court'],date=d['date'],file=d['file'],sha256=d['sha256']) for d in old+keep])
 with (O/'逐份审查清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['编号','标题','案号','法院','日期','处理','理由','正文证据','主文','匹配编号','保存位置'])
  for d in ds:w.writerow([d['id'],d['title'],d['case'],d['court'],d['date'],d['decision'],d['reason'],'；'.join(d['evidence'])[:1800],d['result'],d['duplicate'],d.get('file','')])
 lines=['# 最新17个压缩包审查','','范围：广东土地违法行政处罚非诉执行审查，不限年份，含林地用途违法；保留准予、不予、驳回、部分准予和相关撤回裁定。行政诉讼、执行实施及复议按既有范围排除。逐份正文规则筛查，并复核平台字段冲突、程序误标及同案副本，不声称进行了独立双人标注。','','本次为按下载编号排序最新17个包（23225139至23333967）；目录中更早的23213167、23220940不在本次指定17包内。下载份数、唯一编号及逐包统计见处理统计.json。所有不符合及重复解压DOC已删除，原ZIP保留；旧5294份校验SHA256未变，合并后按编号、正文及法院案号校验无重复。','','|处理|份数|','|---|---:|']
 for k,v in counts.items():lines.append(f'|{k}|{v}|')
 lines+=['','依据正文核对程序和土地处罚事项；复议等超出既有程序范围的文书排除。案号或标题不单独决定相关性。', '', '|压缩包|新增|重复|不符合|','|---|---:|---:|---:|']
 lines.insert(-3,'112217713为交出宅基地的行政决定及组织执行，未披露土地违法行政处罚，排除。64990494、64806759虽主文未写“准予”，但正文为处罚合法性审查并裁定行政机关组织实施，保留。无“当事人”段落标记的文书保留完整事实段，不在法律引文中的普通“当事人”一词处截断。')
 for name,c in summary['by_archive'].items():lines.append(f"|{name}|{c.get('新增保留',0)}|{c.get('重复剔除',0)+c.get('批内重复下载剔除',0)}|{c.get('不相关删除',0)}|")
 lines+=['',f"处理前{len(old)}份，新增{len(keep)}份，处理后{len(old)+len(keep)}份。",'','关键复核：正文决定地域、程序与处罚性质，土地处罚驳回结果亦纳入。不同编号的同案副本按法院案号和正文比对。','','|编号|案号|处理|理由|','|---|---|---|---|']
 for d in ds:lines.append('|'+ '|'.join([d['id'],d['case'],d['decision'],d['reason']])+'|')
 (O/'审查结果.md').write_text('\n'.join(lines),'utf8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='decide':decide()
 elif len(sys.argv)>1 and sys.argv[1]=='finalize':finalize()
 else:prep()

