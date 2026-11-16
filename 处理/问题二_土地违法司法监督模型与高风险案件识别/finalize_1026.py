import pathlib,json,re,hashlib,collections
from review_1023 import unpack,norm
R=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二";O=R/'reports'/'1026审查'
D=json.loads((O/'审查决定.json').read_text('utf-8'));old=json.loads((O/'现有目录.json').read_text('utf-8'))
folder=R/'裁判文书';stage=R/'1026'/'临时解压审查'
assert len(list(folder.glob('*.doc*')))==len(old)==2847
assert not stage.exists();stage.mkdir()
lookup={(d['source'],d['name']):d for d in D};written=set();deleted=collections.Counter();added=[]
for z in sorted((R/'1026').glob('*.zip')):
 for source,name,raw in unpack(z.read_bytes(),z.name):
  d=lookup.get((source,name))
  if d is None or d['id'] in written:continue
  written.add(d['id']);p=stage/(d['id']+pathlib.Path(name).suffix);p.write_bytes(raw)
  assert p.resolve().is_relative_to((R/'1026').resolve())
  assert hashlib.sha256(raw).hexdigest()==d['sha256']
  if d['decision']!='新增保留':p.unlink();deleted[d['decision']]+=1;continue
  safe=re.sub(r'[<>:"/\\|?*]','_',d['title'][:65]+'__'+d['case']+'__'+d['id'])+pathlib.Path(name).suffix
  target=folder/safe;assert not target.exists();p.replace(target)
  assert hashlib.sha256(target.read_bytes()).hexdigest()==d['sha256']
  d['file']=str(target);added.append(d)
assert len(written)==len(D) and not list(stage.iterdir());stage.rmdir()
assert len(added)==538
fields=['id','title','case','court','date','year','year_basis','file','sha256']
catalog=[]
for d in old+added:
 row={k:d.get(k,'') for k in fields}
 if d in old:row['file']=d['source']
 catalog.append(row)
assert len(catalog)==len(list(folder.glob('*.doc*')))==3385
assert len({d['id'] for d in catalog})==len(catalog)
keys=[(norm(d['court']),norm(d['case'])) for d in catalog if d['case'] and not re.search('[X×某]',d['case'])]
assert len(keys)==len(set(keys))
for d in catalog:assert pathlib.Path(d['file']).is_file()
years=collections.Counter(d['year'] for d in catalog);newyears=collections.Counter(d['year'] for d in added)
occ=json.loads((O/'下载出现记录.json').read_text('utf-8'))
summary=dict(archives=67,download_occurrences=len(occ),unique_ids=len(D),duplicate_downloads=len(occ)-len(D),duplicate_cases=deleted['重复剔除'],unrelated=deleted['不相关删除'],insufficient=deleted['证据不足排除'],added=len(added),before=len(old),after=len(catalog),years=dict(sorted(years.items())),added_years=dict(sorted(newyears.items())),provisional_years=[d['id'] for d in catalog if '辅助' in d['year_basis']],original_archives_preserved=True)
(O/'处理统计.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
(O/'合并后文书目录.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),'utf-8')
(O/'审查决定.json').write_text(json.dumps(D,ensure_ascii=False,indent=2),'utf-8')
lines=['# 1026批次筛选、去重及年份分布','','研究口径：广东法院对土地违法行政处罚的非诉执行审查裁定，含违法改变林地用途。排除纯采矿、滥伐林木、野生动物、规划、征收交地等。准予、不准予及部分准予均纳入。','','67个压缩包，共3243份下载文书、3193个法宝编号。50份重复下载、2548条重复裁判；新增538份，不相关70份，原文信息不足37份。解压件已按审查结论清理，原始压缩包保留。','','部分导出字段的案号显示XXX，目录优先采用正文完整案号；剔除了法院字段与正文不符的外省案例。信息不足单独列明，不能据此断言其实体上一定与课题无关。','','## 合并后年份分布','','|年份|本次新增|合并后总数|','|---|---:|---:|']
for y,n in sorted(years.items()):lines.append(f'|{y}|{newyears[y]}|{n}|')
lines+=['|合计|538|3385|','','2020年中有7份原文无法核实裁判年份，暂按案号归年，已在目录year_basis字段标注。其余优先按审结日期、正文落款归年。','','## 非重复文书审查明细','','|法宝编号|标题|正文案号|处理|理由|','|---|---|---|---|---|']
for d in D:
 if d['decision']!='重复剔除':lines.append('|'+ '|'.join([d['id'],d['title'],d['case'],d['decision'],d['reason']]).replace('\n',' ')+'|')
(O/'审查结果与年份分布.md').write_text('\n'.join(lines),'utf-8')
print(json.dumps(summary,ensure_ascii=False))
