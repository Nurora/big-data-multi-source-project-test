import sys,json,re,csv,hashlib,zipfile,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_1029 import walk
R=Path.cwd().resolve();O=R/'reports'/'深圳审查';source=R/'深圳.zip';rawzip=source.read_bytes();ds=json.loads((O/'决定.json').read_text('utf8'))
for d in ds:
 if d['index']==587:d.update(decision='删除',reason='本次按土地管理法七十四条处罚破坏耕地种植条件，非非法占地处罚条款')
 if d['index']==888:d.update(decision='保留',reason='虽事实为超期用地，本件明确按土地管理法七十七条非法占地处罚，保留并标注')
 if d['index'] in [633,732]:d['reason']='正文明确非法占地及责令退地；原文引用七十八条，按实际事实与处罚结果保留，法条字段异常'
 if d['index'] in [715,841,843,844,1278,1348]:d['reason']+='；处罚金额或结果字段不完整，保留原文，不补造'
folder=R/'深圳_非法占用土地行政处罚';assert not folder.exists();folder.mkdir()
records=[]; expected={}
for i,(src,name,raw) in enumerate(walk(rawzip,'深圳.zip')):
 d=ds[i];assert d['name']==name and d['source']==src
 sha=hashlib.sha256(raw).hexdigest()
 rec=dict(序号=i+1,法宝编号=d['id'],标题=d['title'],处理=d['decision'],理由=d['reason'],SHA256=sha,保存位置='')
 if d['decision']=='保留':
  safe=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',d['title'])[:95]+'__'+d['id']+'.doc'
  p=folder/safe;assert p.resolve().parent==folder and not p.exists();p.write_bytes(raw);expected[safe]=sha;rec['保存位置']=str(p)
 records.append(rec)
assert len(records)==1433
assert len(expected)==114
for p in folder.iterdir():assert hashlib.sha256(p.read_bytes()).hexdigest()==expected[p.name]
# Rebuild the requested ZIP so rejected documents no longer remain nested inside it.
stage=R/'深圳.筛选中.zip';assert not stage.exists()
with zipfile.ZipFile(stage,'w',zipfile.ZIP_DEFLATED) as z:
 for p in folder.iterdir():z.write(p,folder.name+'/'+p.name)
with zipfile.ZipFile(stage) as z:
 assert z.testzip() is None and len(z.namelist())==114
 for n in z.namelist():assert hashlib.sha256(z.read(n)).hexdigest()==expected[Path(n).name]
assert hashlib.sha256(source.read_bytes()).hexdigest()==hashlib.sha256(rawzip).hexdigest()
stage.replace(source)
with (O/'逐份审查清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
summary=dict(原文书数=len(ds),保留=114,删除=1319,解析失败=0,源压缩包原SHA256=hashlib.sha256(rawzip).hexdigest(),处理后压缩包SHA256=hashlib.sha256(source.read_bytes()).hexdigest(),文件夹=str(folder),压缩包='深圳.zip已重建，仅含保留文书',说明='依据正文事实及本次处罚事项筛选；不予处罚、规划施工、闲置土地、单纯改变用途、到期拒还等排除。超期用地但本件明确按七十七条处罚的888号保留。不同编号的同案公开版本均保留，114份并非114个独立案件。')
(O/'处理统计.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf8')
# Remove review intermediates containing rejected full texts; retain only the audit manifest.
for name in ['原文.json','决定.json']:
 p=O/name;assert p.resolve().parent==O.resolve() and p.is_file();p.unlink()
print(json.dumps(summary,ensure_ascii=False,indent=2))
