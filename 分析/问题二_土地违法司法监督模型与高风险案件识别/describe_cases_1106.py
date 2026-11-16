"""Full-field descriptive analysis of the three 1106 source worksheets.

Run with bundled Python. Original spreadsheets are read-only. Derived text
labels and quantities remain candidates and retain source row references.
"""
import sys, re, json, csv, hashlib, unicodedata, html
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
sys.path.insert(0,str(ROOT/'.local/feasibility_libs'))
import numpy as np
import pandas as pd
import openpyxl
OUT=ROOT/'reports/两类案件描述性分析_20261106'
TABLES=OUT/'统计表'
TABLES.mkdir(parents=True,exist_ok=True)
NULLS={'','null','none','nan','nat','n/a','无','未知','不详','未公开','未载明','-','--'}
def text(v):
    if v is None: return ''
    return unicodedata.normalize('NFKC',str(v)).strip()
def norm(v): return re.sub(r'\s+','',text(v)).translate(str.maketrans('〔〕【】[]','()()()'))
def missing(v): return text(v).lower() in NULLS
def date(v):
    if missing(v): return pd.NaT
    s=text(v).replace('年','-').replace('月','-').replace('日','')
    return pd.to_datetime(s,errors='coerce')
def export(name,frame):
    if not isinstance(frame,pd.DataFrame): frame=pd.DataFrame(frame)
    frame.to_csv(TABLES/(name+'.csv'),index=False,encoding='utf-8-sig')
    return frame
def read(pattern,sheet):
    path=next(ROOT.glob(pattern))
    rows=list(openpyxl.load_workbook(path,read_only=True,data_only=True)[sheet].values)
    df=pd.DataFrame(rows[1:],columns=rows[0]);df.insert(0,'源Excel行',range(2,len(df)+2))
    return path,df
pf,p=read('*1106*保留清单*.xlsx','最终保留')
cf,c=read('*1106*裁判文书*.xlsx','最终保留')
af,a=read('*1106*摸底*.xlsx','清洗后数据')
sources={'处罚保留':(pf,p),'裁判保留':(cf,c),'处罚清洗':(af,a)}
profiles=[];frequencies=[];anomalies=[];summary={};tables={}
def anomaly(source,row,field,kind,value):
    anomalies.append({'数据表':source,'源Excel行':int(row),'字段':field,'问题':kind,'原值':str(value)})
for name,(path,df) in sources.items():
    summary[name]={'行数':len(df),'原始字段数':len(df.columns)-1,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'文件':str(path)}
    for col in df.columns[1:]:
        vals=df[col].map(text);valid=~df[col].map(missing);good=vals[valid];length=good.str.len()
        counts=good.value_counts()
        profiles.append({'数据表':name,'字段':col,'总行数':len(df),'有效行数':int(valid.sum()),'缺失或缺失标记数':int((~valid).sum()),'有效率':float(valid.mean()),'不同原始取值数':int(good.nunique()),'规范化不同值数':int(good.map(norm).nunique()),'最短长度':int(length.min()) if len(length) else 0,'中位长度':float(length.median()) if len(length) else 0,'P95长度':float(length.quantile(.95)) if len(length) else 0,'最长长度':int(length.max()) if len(length) else 0,'乱码行数':int(vals.str.contains('\ufffd',regex=False).sum()),'匿名化标记行数':int(vals.str.contains(r'某|\*{2,}|×{2,}').sum()),'高频值':str(counts.index[0])[:160] if len(counts) else '', '高频值次数':int(counts.iloc[0]) if len(counts) else 0})
        # Every field is represented, including high-cardinality titles and text.
        for value,count in counts.items():
            frequencies.append({'数据表':name,'字段':col,'字段取值':value,'次数':int(count),'占全部记录比例':count/len(df)})
        for i,r in df.loc[~valid | vals.str.contains('\ufffd',regex=False)].iterrows():
            anomaly(name,r['源Excel行'],col,'缺失标记' if missing(r[col]) else '乱码',r[col])
export('01_全字段画像',profiles)
export('02_全字段完整取值频数',frequencies)
# Generic frequency and cross-tab functions always include missing groups.
def dist(df,col,name,denominator=None):
    s=df[col].astype(object).fillna('缺失').astype(str).replace({'':'缺失','nan':'缺失'})
    v=s.value_counts(dropna=False).rename_axis(col).reset_index(name='记录数')
    v['占比']=v['记录数']/(len(df) if denominator is None else denominator);export(name,v);tables[name]=v;return v
def cross(df,left,right,name):
    v=pd.crosstab(df[left].astype(object).fillna('缺失').reset_index(drop=True),df[right].astype(object).fillna('缺失').reset_index(drop=True),dropna=False)
    export(name,v.reset_index());tables[name]=v;return v
# Geography mapping is taken from the supplied land-cover county dictionary.
county_path=ROOT/'reports/方案可行性实验_20261106/土地表_广东省建设用地原始数据_区县年度.json'
county=json.loads(county_path.read_text(encoding='utf-8'))
mapping={r[1]:r[2] for r in county[1:]}
mapping.update({'云安县':'云浮市','电白县':'茂名市','阳东县':'阳江市','高要市':'肇庆市'})
cities=sorted({r[2] for r in county[1:]})
def city(v):
    s=norm(v).removeprefix('广东省')
    if s in cities:return s
    return mapping.get(s,'未可靠映射')
for df,col in [(p,'处罚决定日期'),(c,'标准裁判日期'),(a,'标准处罚日期')]:
    df['分析日期']=df[col].map(date)
    df['年份']=df['分析日期'].dt.year.astype('Int64')
    df['月份']=df['分析日期'].dt.month.astype('Int64')
    df['季度']=df['分析日期'].dt.quarter.astype('Int64')
    df['日']=df['分析日期'].dt.day.astype('Int64')
    df['月末']=df['分析日期'].map(lambda v:'缺失' if pd.isna(v) else '月末日' if v.is_month_end else '其他日期')
    df['年月']=df['分析日期'].dt.strftime('%Y-%m').fillna('缺失')
    df['星期']=df['分析日期'].dt.dayofweek.map(dict(enumerate(['周一','周二','周三','周四','周五','周六','周日']))).fillna('缺失')
p['地市']=p['执法地域'].map(city);c['地市']=c['所属地区'].map(city);a['地市']=a['标准地级市'].map(city)
c['规范法院']=c['法院'].map(norm).str.removeprefix('广东省')
c['法院层级']=c['法院'].map(lambda v:'中级法院' if '中级' in text(v) else '高级法院' if '高级' in text(v) else '基层及专门法院')
c['案号键']=c['案号'].map(norm)
c['案号年份']=c['案号键'].str.extract(r'\(((?:19|20)\d{2})\)',expand=False).astype('Float64')
c['公开日期']=c['标准公开日期'].map(date)
c['公开滞后天数']=(c['公开日期']-c['分析日期']).dt.days
c['公开年份']=c['公开日期'].dt.year.astype('Int64')
for name,df in [('处罚',p),('裁判',c),('清洗处罚',a)]:
    for col in ['年份','月份','季度','星期','日','月末','地市']:
        dist(df,col,f'03_{name}_{col}分布')
    cross(df,'地市','年份',f'04_{name}_地市年份')
    cross(df,'年份','月份',f'04_{name}_年份月份')
dist(c,'规范法院','05_裁判_法院分布');dist(c,'法院层级','05_裁判_法院层级')
dist(c,'结果类型','05_裁判_结果分布');dist(c,'行政相对人类型','05_裁判_主体类型')
for col in ['年份','地市','规范法院','行政相对人类型','法院层级','公开年份']:
    cross(c,col,'结果类型',f'06_裁判_{col}与结果')
cross(c,'地市','行政相对人类型','06_裁判_地市主体');cross(c,'年份','行政相对人类型','06_裁判_年份主体')
cross(c,'年份','公开年份','06_裁判_裁判年份公开年份')
for col in ['地市','年份']:
    cross(a,col,'相对人类型',f'07_清洗处罚_{col}主体')
dist(a,'相对人类型','07_清洗处罚_主体分布')
cross(a,'相对人类型','处罚措施标签','07_清洗处罚_主体与措施标签')
cross(a,'相对人类型','处罚类别','07_清洗处罚_主体与原类别')
dist(p,'处罚机关','07_处罚_机关分布');cross(p,'地市','处罚机关','07_处罚_地市机关')
cross(p,'年份','处罚机关','07_处罚_年份机关')
# Deduplication audits preserve all originals and make alternative counts explicit.
duplicate_stats=[]
for tag,df,keys in [('裁判',c,['案号键']),('处罚',p,['行政处罚决定书文号','被处罚对象','处罚机关']),('清洗处罚',a,['行政处罚决定书文号','标准行政相对人','处罚机关'])]:
    temp=df[keys].map(norm)
    mask=temp.duplicated(keep=False)
    dup=df.loc[mask].copy();export('08_'+tag+'_重复键明细',dup)
    duplicate_stats.append({'数据表':tag,'键':'＋'.join(keys),'涉及行数':int(mask.sum()),'重复差额':int(temp.duplicated().sum()),'不同键数':len(temp.drop_duplicates())})
    original=[col for col in sources['裁判保留' if tag=='裁判' else '处罚保留' if tag=='处罚' else '处罚清洗'][1].columns if col not in ['源Excel行']][:10 if tag=='裁判' else 11 if tag=='处罚' else 13]
    summary[tag+'完全相同行差额']=int(df[original].astype(str).duplicated().sum())
export('08_重复键汇总',duplicate_stats)
conflicts=[]
for k,g in c.groupby('案号键'):
    if len(g)>1:
        conflicts.append({'案号':k,'行数':len(g),'结果取值数':g['结果类型'].nunique(),'法院取值数':g['规范法院'].nunique(),'日期取值数':g['分析日期'].nunique(),'结果集合':'；'.join(g['结果类型'].astype(str).unique()),'源行号':'；'.join(g['源Excel行'].astype(str))})
export('08_裁判重复案号冲突',conflicts)
# Compare the two punishment populations using platform IDs where possible.
def platform(v):
    m=re.search(r'CLI\.ALE\.(\d+)',text(v));return m.group(1) if m else norm(v)
p['平台键']=p['标题'].map(platform);a['平台键']=a['标题'].map(platform)
counts_a=a['平台键'].value_counts();counts_p=p['平台键'].value_counts()
export('09_处罚表差额逐键核对',[{'平台键':k,'保留表行数':int(counts_p.get(k,0)),'清洗表行数':int(counts_a.get(k,0))} for k in sorted(set(counts_a.index)|set(counts_p.index)) if counts_a.get(k,0)!=counts_p.get(k,0)])
export('09_保留表未进入清洗表',p.loc[~p['平台键'].isin(a['平台键'])])
summary['处罚表差额']={'保留行数':len(p),'清洗行数':len(a),'净差额':len(p)-len(a),'保留表未出现于清洗表行数':int((~p['平台键'].isin(a['平台键'])).sum()),'清洗表未出现于保留表行数':int((~a['平台键'].isin(p['平台键'])).sum()),'保留表平台ID重复差额':int(p['平台键'].duplicated().sum()),'清洗表平台ID重复差额':int(a['平台键'].duplicated().sum())}
changed=[]
am={k:g.iloc[0] for k,g in a.groupby('平台键') if len(g)==1}
for _,r in p.iterrows():
    if r['平台键'] not in am:continue
    ar=am[r['平台键']]
    for col in ['标题','行政处罚决定书文号','处罚类别','处罚事由','处罚结果','处罚机关']:
        if norm(r[col])!=norm(ar[col]):changed.append({'平台键':r['平台键'],'字段':col,'保留表行':r['源Excel行'],'清洗表行':ar['源Excel行'],'保留值':str(r[col]),'清洗值':str(ar[col])})
export('09_两表共同字段变化',changed)
# Date audits and disclosure delays.
for _,r in c.iterrows():
    if pd.notna(r['公开滞后天数']) and r['公开滞后天数']<0:anomaly('裁判保留',r['源Excel行'],'标准公开日期','公开早于裁判',r['公开滞后天数'])
    if pd.notna(r['年份']) and pd.notna(r['案号年份']) and r['年份']!=r['案号年份']:anomaly('裁判保留',r['源Excel行'],'案号','案号年份与裁判年份不同',r['案号'])
for _,r in p.iterrows():
    if pd.notna(r['年份']) and text(r['处罚年份'])!=str(r['年份']):anomaly('处罚保留',r['源Excel行'],'处罚年份','年份与日期不同',r['处罚年份'])
def describe(series):
    s=pd.to_numeric(series,errors='coerce').dropna()
    if not len(s):return {'有效数':0}
    return {'有效数':len(s),'最小值':float(s.min()),'P25':float(s.quantile(.25)),'中位数':float(s.median()),'均值':float(s.mean()),'P75':float(s.quantile(.75)),'P95':float(s.quantile(.95)),'最大值':float(s.max())}
summary['公开滞后_全部可计算']=describe(c['公开滞后天数'])
summary['公开滞后_非负']=describe(c.loc[c['公开滞后天数']>=0,'公开滞后天数'])
export('10_公开滞后逐行',c[['源Excel行','案号','年份','地市','规范法院','结果类型','分析日期','公开日期','公开滞后天数']])
export('10_公开滞后分组',c.groupby(['年份','结果类型'],dropna=False)['公开滞后天数'].agg(['count','median','mean','min','max']).reset_index())
dist(c.assign(滞后区间=pd.cut(c['公开滞后天数'],[-np.inf,-1,0,30,90,180,365,1095,np.inf],labels=['负值','当天','1至30天','31至90天','91至180天','181至365天','1至3年','3年以上']).astype(str)),'滞后区间','10_公开滞后分档')
# Raw text diagnostics, multi-label measures and grounded phrase candidates.
measure_rules={'罚款':r'罚款','退还土地':r'退还.{0,8}土地','拆除':r'拆除','没收':r'没收','恢复或复垦':r'恢复.{0,8}(原状|土地)|复垦','责令改正':r'责令.{0,6}改正','停止行为':r'停止.{0,8}(建设|施工|违法|占用|行为)'}
use_rules={'住宅':r'住宅|住房|建房|宅基地|自建房','厂房生产':r'厂房|车间|加工厂|生产厂|工厂','仓储':r'仓库|仓储','经营商业':r'商铺|商店|市场|酒店|宾馆|餐饮|经营','养殖设施':r'养殖|猪舍|鸡舍|牛棚|鱼塘|畜禽','种植设施':r'种植|大棚|温室|设施农业','道路停车':r'道路|公路|停车场','硬化堆放':r'硬底化|硬化|堆放|堆场|堆料'}
land_rules={'耕地':r'耕地|水田|旱地','基本农田':r'基本农田','林地':r'林地','园地':r'园地','建设用地':r'建设用地','未利用地':r'未利用地','农用地':r'农用地'}
feature_rows=[];quantities=[];legal_mentions=[]
amount_pat=re.compile(r'(\d[\d,]*(?:\.\d+)?)\s*(万元|元)')
area_pat=re.compile(r'(\d[\d,]*(?:\.\d+)?)\s*(平方米|平方公尺|公顷|亩|m²|m2)',re.I)
for _,r in p.iterrows():
    fact=text(r['处罚事由']);result=text(r['处罚结果']);category=text(r['处罚类别']);content=text(r['处罚内容'])
    # Measures are counted once per record even when repeated across fields.
    measures=[k for k,pat in measure_rules.items() if re.search(pat,category+' '+result+' '+content)]
    uses=[k for k,pat in use_rules.items() if re.search(pat,fact)]
    lands=[k for k,pat in land_rules.items() if re.search(pat,fact)]
    legal_only=bool(re.match(r'^处罚依据',fact)) and not bool(re.search(r'未经|擅自|占用|建成|建设|查明|违法事实',fact))
    placeholder=bool(re.search(r'原始公开记录仅载明|未载明|未公开|未提取',result))
    fine_values=[];area_values=[]
    for field,txt in [('处罚结果',result),('处罚事由',fact)]:
        pattern=amount_pat if field=='处罚结果' else area_pat
        for match in pattern.finditer(txt):
            before=txt[max(0,match.start()-22):match.start()];after=txt[match.end():match.end()+12]
            value=float(match.group(1).replace(',',''));unit=match.group(2)
            if field=='处罚结果':
                # Explicit fine context, excluding obvious per-area unit rates.
                if '罚款' not in before or re.search(r'每[^。；;]{0,12}$',before) or re.match(r'[/／](平方米|亩)',after):continue
                standard=value*(10000 if unit=='万元' else 1);fine_values.append(standard);kind='罚款金额候选'
            else:
                standard=value*({'公顷':10000,'亩':2000/3}.get(unit,1));area_values.append(standard);kind='事实面积候选'
            quantities.append({'源Excel行':r['源Excel行'],'字段':field,'种类':kind,'原数值':value,'单位':unit,'标准数值':standard,'上下文':before+match.group()+after})
    row={'源Excel行':r['源Excel行'],'年份':r['年份'],'地市':r['地市'],'主体':r['被处罚对象'],'处罚机关':r['处罚机关'],'处罚措施组合':'；'.join(measures) or '未识别','用途提及组合':'；'.join(uses) or '未识别','地类提及组合':'；'.join(lands) or '未识别','事由仅依据候选':legal_only,'结果占位说明':placeholder,'内容与结果一致':norm(content)==norm(result),'文号字段污染':bool(re.search(r'处罚对象|处罚名称|统一社会信用|机构名称|法定代表',text(r['行政处罚决定书文号']))),'主体匿名化':bool(re.search(r'某|\*|×',text(r['被处罚对象']))),'罚款候选最大值_元':max(fine_values) if fine_values else None,'事实面积候选最大值_m2':max(area_values) if area_values else None,'罚款候选数':len(fine_values),'面积候选数':len(area_values)}
    feature_rows.append(row)
    for law in set(re.findall(r'《([^》]{2,65})》',fact+' '+result)):
        legal_mentions.append({'源Excel行':r['源Excel行'],'年份':r['年份'],'法规名称原文':law})
features=pd.DataFrame(feature_rows)
export('11_处罚逐行分析特征',features);export('11_金额面积候选含证据',quantities)
export('11_处罚法规提及明细',legal_mentions)
if legal_mentions:dist(pd.DataFrame(legal_mentions),'法规名称原文','11_处罚法规提及频数')
for col in ['处罚措施组合','用途提及组合','地类提及组合']:
    dist(features,col,'12_'+col+'分布')
    long=features[['源Excel行','年份','地市',col]].assign(标签=features[col].str.split('；')).explode('标签')
    dist(long,'标签','12_'+col+'逐标签频数',denominator=len(features))
    cross(long,'年份','标签','12_'+col+'年份')
    cross(long,'地市','标签','12_'+col+'地市')
    pairs=Counter(pair for labels in features[col].str.split('；') for pair in combinations(sorted(set(labels)),2))
    export('12_'+col+'共现',[{'标签一':k[0],'标签二':k[1],'同现记录数':n,'占处罚记录比例':n/len(p)} for k,n in pairs.most_common()])
summary['文本质量']={col:int(features[col].sum()) for col in ['事由仅依据候选','结果占位说明','内容与结果一致','文号字段污染','主体匿名化']}
summary['数量候选']={col:describe(features[col]) for col in ['罚款候选最大值_元','事实面积候选最大值_m2']}
for col in ['罚款候选最大值_元','事实面积候选最大值_m2']:
    export('13_'+col+'最大记录',features.nlargest(30,col)[['源Excel行','年份','地市','主体',col,'罚款候选数','面积候选数']])
    export('13_'+col+'年度描述',features.groupby('年份',dropna=False)[col].agg(['count','median','mean','min','max']).reset_index())
# Repeated subjects are record repetition candidates, not established recidivism.
for name,df,subject in [('处罚',p,'被处罚对象'),('裁判',c,'行政相对人')]:
    df['主体键']=df[subject].map(norm)
    d=df.loc[~df[subject].map(missing)].groupby('主体键').agg(记录数=(subject,'size'),涉及年份数=('年份','nunique'),涉及地市数=('地市','nunique'))
    export('14_'+name+'_同名主体多记录',d[d['记录数']>1].sort_values('记录数',ascending=False).reset_index())
    summary[name+'主体重复']={'不同文本主体数':len(d),'多记录主体数':int((d['记录数']>1).sum()),'多记录涉及行数':int(d.loc[d['记录数']>1,'记录数'].sum()),'匿名化主体说明':'某、星号、简称可能合并不同人，同名不证明重复违法'}
# Missingness and publication coverage by year; denominator remains all rows.
coverage=c.groupby('年份',dropna=False).agg(记录数=('案号','size'),有效公开日期=('公开日期','count'),有效处罚文号=('涉案行政处罚决定书文号_原始',lambda s:sum(not missing(v) for v in s)))
coverage['公开日期有效率']=coverage['有效公开日期']/coverage['记录数']
coverage['处罚文号有效率']=coverage['有效处罚文号']/coverage['记录数']
export('15_裁判年度信息覆盖',coverage.reset_index())
for df,tag in [(p,'处罚'),(c,'裁判')]:
    d=df.groupby('地市').size().sort_values(ascending=False)
    summary[tag+'地区集中度']={'地市数_含未知':len(d),'前一地区占比':float(d.iloc[:1].sum()/len(df)),'前三地区占比':float(d.iloc[:3].sum()/len(df)),'HHI':float(((d/len(df))**2).sum())}
# Source rows and outcome shares after one-row-per-case sensitivity.
dedup=c.drop_duplicates('案号键')
dist(dedup,'结果类型','16_裁判_按案号首行去重敏感性')
summary['裁判去重敏感性说明']='仅用于检查行重复影响，遇冲突优先回查原文，首行不代表金标准。'
summary['裁判案号数']=int(c['案号键'].nunique())
# Current matching output is reused solely as a candidate linkage sensitivity.
linkpath=ROOT/'reports/方案可行性实验_20261106/案件关联明细.csv'
if linkpath.exists():
    links=pd.read_csv(linkpath)
    links['年份']=pd.to_datetime(links['裁判日期'],errors='coerce').dt.year.astype('Int64')
    for col in ['方法','裁判结果','年份','地区']:
        export('17_关联候选_'+col,links.groupby(col,dropna=False).agg(匹配对数=('案号','size'),司法案号数=('案号','nunique'),处罚行数=('处罚Excel行','nunique')).reset_index())
    strong=links[links['方法']!='同主体同市候选']
    matched=set(strong['裁判Excel行']);c['文号候选关联']=c['源Excel行'].isin(matched).map({True:'文号规则候选命中',False:'未命中'})
    cross(c,'文号候选关联','结果类型','17_候选关联与裁判结果')
    summary['关联候选']={'文号规则不同案号':strong['案号'].map(norm).nunique(),'匹配对数':len(strong),'说明':'规则候选，未经本轮全文人工核验'}
export('18_字段异常逐行清单',anomalies)
# Save reusable time series and generated features without rewriting sources.
for name,df in [('处罚',p),('裁判',c),('清洗处罚',a)]:
    export('19_'+name+'_月度数量',df.groupby('年月',dropna=False).size().rename('记录数').reset_index())
    original_count=11 if name=='处罚' else 10 if name=='裁判' else 13
    export('19_'+name+'_日期地域派生字段',df[['源Excel行','分析日期','年份','月份','季度','年月','地市']])
(OUT/'统计摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str))
