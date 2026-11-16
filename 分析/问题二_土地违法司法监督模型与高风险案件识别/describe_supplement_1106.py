"""Identifier and cross-workbook consistency checks supporting the report."""
import sys,re,json,unicodedata
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
sys.path.insert(0,str(ROOT/'.local/feasibility_libs'))
import openpyxl,pandas as pd
OUT=ROOT/'reports/两类案件描述性分析_20261106';T=OUT/'统计表'
def norm(v):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(v or ''))).translate(str.maketrans('〔〕【】[]','()()()'))
def read(pattern,sheet):
    rows=list(openpyxl.load_workbook(next(ROOT.glob(pattern)),read_only=True,data_only=True)[sheet].values)
    d=pd.DataFrame(rows[1:],columns=rows[0]);d['源Excel行']=range(2,len(d)+2);return d
def save(n,d):pd.DataFrame(d).to_csv(T/(n+'.csv'),index=False,encoding='utf-8-sig')
p=read('*1106*保留清单*.xlsx','最终保留');a=read('*1106*摸底*.xlsx','清洗后数据');c=read('*1106*裁判文书*.xlsx','最终保留')
def pid(v):
    m=re.search(r'CLI\.ALE\.(\d+)',str(v));return m.group(1) if m else norm(v)
p['平台键']=p['标题'].map(pid);a['平台键']=a['标题'].map(pid)
rawgeo=pd.read_csv(T/'19_处罚_日期地域派生字段.csv').set_index('源Excel行')['地市'].to_dict()
cleangeo=pd.read_csv(T/'19_清洗处罚_日期地域派生字段.csv').set_index('源Excel行')['地市'].to_dict()
arows={r['平台键']:r for _,r in a.iterrows()};changes=[];geochanges=[]
for _,r in p.iterrows():
    if r['平台键'] not in arows:continue
    ar=arows[r['平台键']]
    for left,right in [('被处罚对象','标准行政相对人'),('执法地域','标准地级市'),('处罚决定日期','标准处罚日期')]:
        equal=(pd.to_datetime(r[left],errors='coerce')==pd.to_datetime(ar[right],errors='coerce')) if left=='处罚决定日期' else norm(r[left])==norm(ar[right])
        if not equal:changes.append({'平台键':r['平台键'],'保留表行':r['源Excel行'],'清洗表行':ar['源Excel行'],'原字段':left,'清洗字段':right,'原值':str(r[left]),'清洗值':str(ar[right])})
    if rawgeo[r['源Excel行']]!=cleangeo[ar['源Excel行']]:geochanges.append({'平台键':r['平台键'],'保留表行':r['源Excel行'],'清洗表行':ar['源Excel行'],'原始地域':r['执法地域'],'原表归并地市':rawgeo[r['源Excel行']],'清洗地市':cleangeo[ar['源Excel行']]})
save('20_跨表主体地域日期变化',changes);save('20_跨表归并地市不一致',geochanges)
ids=[]
for tag,df,col in [('处罚',p,'行政处罚决定书文号'),('裁判引用',c,'涉案行政处罚决定书文号_原始')]:
    for _,r in df.iterrows():
        s=norm(r[col]);years=re.findall(r'\(((?:19|20)\d{2})\)',s)
        nums=set(re.findall(r'[\u4e00-\u9fffA-Za-z()]*\((?:19|20)\d{2}\)(?:\([\u4e00-\u9fff]+\))?(?:第)?\d+号?',s))
        ids.append({'数据表':tag,'源Excel行':r['源Excel行'],'括号年份提及数':len(years),'不同处罚文号候选数':len(nums),'文号年份首值':years[0] if years else None,'含处罚结果语句':bool(re.search(r'准予|驳回|执行|不予受理',s)),'含其他字段词':bool(re.search(r'处罚对象|机构名称|处罚名称|统一社会信用|法定代表',s))})
save('20_处罚文号结构逐行',ids)
idframe=pd.DataFrame(ids)
save('20_处罚文号结构汇总',idframe.groupby('数据表').agg(行数=('源Excel行','size'),识别到文号记录数=('不同处罚文号候选数',lambda s:(s>0).sum()),多文号候选记录数=('不同处罚文号候选数',lambda s:(s>1).sum()),含结果语句=('含处罚结果语句','sum'),含其他字段词=('含其他字段词','sum')).reset_index())
cf=pd.read_csv(T/'08_裁判重复案号冲突.csv')
f=pd.read_csv(T/'11_处罚逐行分析特征.csv')
f['罚款疑似极值']=f['罚款候选最大值_元']>1e8
save('20_罚款超过一亿元候选复核',f[f['罚款疑似极值']])
contaminated=[]
for _,r in p.iterrows():
    if re.search(r'违法条款|法律依据|处罚依据|统一社会信用|处罚名称',str(r['被处罚对象'])):contaminated.append({'源Excel行':r['源Excel行'],'被处罚对象原值':r['被处罚对象']})
save('20_主体字段疑似串入事实依据',contaminated)
s={'主体字段串入其他信息候选数':len(contaminated),'跨表归并地市不一致行数':len(geochanges),'重复案号结果冲突组数':int((cf['结果取值数']>1).sum()),'重复案号日期冲突组数':int((cf['日期取值数']>1).sum()),'超过一亿元罚款候选记录数':int(f['罚款疑似极值'].sum())}
(OUT/'补充质量核验.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(s,ensure_ascii=False))
