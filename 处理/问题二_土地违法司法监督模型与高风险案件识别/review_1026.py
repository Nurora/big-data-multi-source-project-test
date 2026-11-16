import pathlib,sys,json,re,hashlib,collections
from review_1023 import unpack,read_doc,norm,year_of
R=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
O=R/'reports'/'1026审查';O.mkdir(exist_ok=True)
def parse(raw,name,source):
 t=read_doc(raw,name);t=re.sub(r'\x13[^\x14]*\x14','',t).replace('\x15','');t=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','\n',t)
 def field(label):
  m=re.search(label+r'\s*[：:]\s*([^\n]+)',t);return m[1].strip() if m else ''
 m=re.search(r'FBMCLI\.C\.(\d+)|【法宝引证码】CLI.C.(\d+)',name+'\n'+t)
 body=t.split('//',1)[-1].split('©北大法宝')[0].strip()
 d=dict(id=next(x for x in m.groups() if x) if m else hashlib.sha256(raw).hexdigest(),name=name,source=source,title=re.sub(r'\(FBMCLI.*','',pathlib.Path(name).name),case=field(r'案\s*号'),court=field('审理法院'),date=field('审结日期'),text=t,body=body,sha256=hashlib.sha256(raw).hexdigest())
 d['year'],d['year_basis']=year_of(d)
 d['result']=re.split(r'(?m)^\s*落款\s*$',re.split(r'裁判结果|裁定如下[：:]?',body)[-1])[0].strip()
 return d
def prep():
 old=[parse(p.read_bytes(),p.name,str(p)) for p in (R/'裁判文书').glob('*.doc*')]
 (O/'现有目录.json').write_text(json.dumps(old,ensure_ascii=False),'utf-8')
 ids={d['id']:d for d in old};keys={(norm(d['court']),norm(d['case'])):d for d in old if d['case']};bodies={norm(d['body']):d for d in old};ds=[];occ=[];errors=[];seen={}
 for z in sorted((R/'1026').glob('*.zip')):
  for source,name,raw in unpack(z.read_bytes(),z.name):
   try:d=parse(raw,name,source)
   except Exception as e:errors.append(dict(source=source,name=name,error=str(e)));continue
   occ.append(dict(id=d['id'],source=source,name=name))
   if d['id'] in seen:continue
   seen[d['id']]=d
   match=ids.get(d['id']) or bodies.get(norm(d['body']))
   d['duplicate']=match['id'] if match else None
   k=(norm(d['court']),norm(d['case']));d['case_match']=keys[k]['id'] if k in keys else None
   sentences=[s.strip() for s in re.split('[。\n]',d['body']) if s.strip()]
   d['evidence']=[s for s in sentences if re.search(r'土地管理法|土地行政处罚|非法.{0,10}(占用|转让|买卖).{0,30}土地|擅自.{0,20}(改变|开垦).{0,20}林地|改变用途林地|退还非法占用|违法占用',s) and s!=d['title']]
   d['decision']='重复' if match else '待审'
   ds.append(d)
 (O/'候选原文.json').write_text(json.dumps(ds,ensure_ascii=False,indent=2),'utf-8')
 (O/'下载出现记录.json').write_text(json.dumps(occ,ensure_ascii=False),'utf-8')
 (O/'解析错误.json').write_text(json.dumps(errors,ensure_ascii=False),'utf-8')
 print(json.dumps(dict(old=len(old),archives=len(list((R/'1026').glob('*.zip'))),occurrences=len(occ),unique=len(ds),duplicate=sum(bool(d['duplicate']) for d in ds),errors=errors),ensure_ascii=False))
 print('NEW',collections.Counter(d['year'] for d in ds if not d['duplicate']))
if __name__=='__main__':prep()
