"""Full-field descriptive analysis of current source files; no research modelling."""
from pathlib import Path
from collections import Counter,defaultdict
import sys,re,json,hashlib,unicodedata,datetime as dt,itertools
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
sys.path.append(str(ROOT/'.local/feasibility_libs'))
import pandas as pd,numpy as np,openpyxl
OUT=ROOT/'reports/全面描述性分析_最新版_20261106';OUT.mkdir(exist_ok=True)
T=OUT/'统计表';T.mkdir(exist_ok=True)
F=T/'全字段取值频数';F.mkdir(exist_ok=True)
NULL={'','null','none','nan','nat','n/a','未知','不详','未公开','未载明','-','--'}
def txt(v):return '' if v is None or isinstance(v,float) and np.isnan(v) else unicodedata.normalize('NFKC',str(v)).strip()
def norm(v):return re.sub(r'\s+','',txt(v))
def missing(v):return txt(v).lower() in NULL
def date(v):
    if missing(v):return pd.NaT
    if isinstance(v,(int,float)):
        if 20000<float(v)<70000:return pd.Timestamp('1899-12-30')+pd.to_timedelta(v,unit='D')
        return pd.NaT
    return pd.to_datetime(txt(v).replace('年','-').replace('月','-').replace('日',''),errors='coerce')
def save(name,d):
    if not isinstance(d,pd.DataFrame):d=pd.DataFrame(d)
    d.to_csv(T/f'{name}.csv',index=False,encoding='utf-8-sig');return d
def freq(d,col,name):
    s=d[col].astype(object).fillna('缺失').astype(str).replace({'':'缺失','<NA>':'缺失','NaT':'缺失'})
    a=s.value_counts(dropna=False).rename_axis(col).reset_index(name='记录数');a['占比']=a['记录数']/len(d)
    return save(name,a)
def cross(d,left,right,name):return save(name,pd.crosstab(d[left].astype(object).fillna('缺失'),d[right].astype(object).fillna('缺失')).reset_index())
def load(f):
    w=openpyxl.load_workbook(f,read_only=True,data_only=True);s=w['最终保留'];it=s.values;h=next(it)
    rows=[dict(zip(h,r),源Excel行=i+2) for i,r in enumerate(it) if any(not missing(v) for v in r)];w.close()
    return pd.DataFrame(rows),list(h)
pf=next(ROOT.glob('*1106*处罚保留*.xlsx'));cf=next(ROOT.glob('*1106*裁判文书.xlsx'))
p,ph=load(pf);c,ch=load(cf)
# Geography dictionary comes directly from supplied archive, not from an old audit.
import zipfile,io
with zipfile.ZipFile(ROOT/'广东建设用地数据.zip') as z:
    m=next(n for n in z.namelist() if n.endswith('广东省建设用地原始数据.xlsx'))
    w=openpyxl.load_workbook(io.BytesIO(z.read(m)),read_only=True,data_only=True)
    lv=list(w['区县年度'].values);cv=list(w['地市年度'].values);w.close()
county={norm(r[1]):norm(r[2]) for r in lv[1:]};cities={norm(r[1]) for r in cv[1:]}
county.update({'云安县':'云浮市','电白县':'茂名市','阳东县':'阳江市','高要市':'肇庆市'})
def city(v):
    s=norm(v).removeprefix('广东省');return s if s in cities else county.get(s,'未可靠映射')
profiles=[];anomalies=[];summary={};field_desc=[]
for tag,f,d,headers,dc,gc in [('处罚',pf,p,ph,'处罚决定日期','所属地级市'),('裁判',cf,c,ch,'标准裁判日期','所属地区')]:
    summary[tag]={'文件':f.name,'sha256':hashlib.file_digest(f.open('rb'),'sha256').hexdigest(),'记录数':len(d),'字段数':len(headers),'全字段规范化重复差额':int(pd.DataFrame({h:d[h].map(norm) for h in headers}).duplicated().sum())}
    for h in headers:
        s=d[h].map(txt);valid=~d[h].map(missing);g=s[valid];length=g.str.len();counts=g.value_counts()
        base={'数据':tag,'字段':h,'总记录':len(d),'有效数':int(valid.sum()),'缺失数':int((~valid).sum()),'有效率':float(valid.mean()),'真空白数':int((s=='').sum()),'NULL等标记数':int(((~valid)&(s!='')).sum()),'不同原值数':int(g.nunique()),'规范化不同值数':int(g.map(norm).nunique()),'长度最小':int(length.min()) if len(g) else None,'长度中位':float(length.median()) if len(g) else None,'长度P95':float(length.quantile(.95)) if len(g) else None,'长度最大':int(length.max()) if len(g) else None,'含乱码数':int(s.str.contains('\ufffd').sum()),'含匿名标记数':int(s.str.contains(r'某|\*{2,}|×{2,}').sum()),'最高频值次数':int(counts.iloc[0]) if len(counts) else 0}
        profiles.append(base)
        vals=counts.rename_axis('字段取值').reset_index(name='次数');vals['占全部比例']=vals['次数']/len(d)
        vals.to_csv(F/f'{tag}_{h}.csv',index=False,encoding='utf-8-sig')
        for i in d.index[~valid|s.str.contains('\ufffd')]:anomalies.append({'数据':tag,'源Excel行':int(d.loc[i,'源Excel行']),'字段':h,'问题':'缺失' if not valid.loc[i] else '乱码','原值':s.loc[i]})
    d['分析日期']=d[dc].map(date);d['地市']=d[gc].map(city)
    d['年份']=d['分析日期'].dt.year.astype('Int64');d['月份']=d['分析日期'].dt.month.astype('Int64');d['季度']=d['分析日期'].dt.quarter.astype('Int64')
    d['星期']=d['分析日期'].dt.dayofweek.astype('Int64');d['年月']=d['分析日期'].dt.strftime('%Y-%m');d['日']=d['分析日期'].dt.day.astype('Int64')
    d['月末日']=d['分析日期'].dt.is_month_end
    for h in ['年份','月份','季度','星期','年月','日','地市','月末日']:freq(d,h,f'{tag}_{h}分布')
    cross(d,'地市','年份',f'{tag}_地市年度');cross(d,'年份','月份',f'{tag}_年月交叉')
    save(f'{tag}_日期地域派生字段',d[['源Excel行',dc,gc,'分析日期','地市','年份','月份','季度','星期','年月','日','月末日']])
    missing_date=d[d['分析日期'].isna()]
    save(f'{tag}_无效日期记录',missing_date[headers+['源Excel行']])
    save(f'{tag}_未映射地区',d[d['地市']=='未可靠映射'][['源Excel行',gc]])
    summary[tag].update({'有效日期':int(d['分析日期'].notna().sum()),'日期最早':str(d['分析日期'].min()),'日期最晚':str(d['分析日期'].max()),'2015至2025之外日期数':int(((d['年份']<2015)|(d['年份']>2025)).sum()),'地市数':len(set(d['地市'])-{'未可靠映射'}),'地域未映射数':int((d['地市']=='未可靠映射').sum()),'有效市年单元':int(d[d['地市']!='未可靠映射'].dropna(subset=['年份']).groupby(['地市','年份']).ngroups),'匿名主体记录':int(d['被处罚对象' if tag=='处罚' else '行政相对人'].map(txt).str.contains(r'某|\*{2,}|×{2,}').sum())})
save('全字段画像',profiles)
# Exact and key duplicates, without deleting originals.
c['规范案号']=c['案号'].map(norm);p['规范主体']=p['被处罚对象'].map(norm)
p['处罚联合键']=p.apply(lambda r:'|'.join(norm(r[k]) for k in ['处罚机关','行政处罚决定书文号','被处罚对象']),axis=1)
for tag,d,key,headers in [('裁判',c,'规范案号',ch),('处罚',p,'处罚联合键',ph)]:
    dup=d[d.duplicated(key,keep=False)].copy();save(f'{tag}_重复键逐行',dup[headers+['源Excel行',key]])
    groups=[]
    for k,g in dup.groupby(key):
        row={'键':k,'记录数':len(g),'源行':','.join(map(str,g['源Excel行']))}
        for h in headers:row[h+'不同值数']=g[h].map(norm).nunique()
        groups.append(row)
    save(f'{tag}_重复键冲突汇总',groups);summary[tag]['唯一分析键数']=int(d[key].nunique());summary[tag]['重复键涉及行']=len(dup);summary[tag]['重复键差额']=len(d)-int(d[key].nunique())
# Court results, types, courts and publication delay.
for h in ['结果类型','行政相对人类型','法院']:freq(c,h,f'裁判_{h}分布')
for left,right in [('年份','结果类型'),('地市','结果类型'),('行政相对人类型','结果类型'),('法院','结果类型'),('年份','行政相对人类型'),('地市','行政相对人类型')]:cross(c,left,right,f'裁判_{left}_{right}')
c['公开日期']=c['标准公开日期'].map(date);c['公开滞后天']=(c['公开日期']-c['分析日期']).dt.days
save('裁判_公开滞后逐行',c[['源Excel行','案号','分析日期','公开日期','公开滞后天','年份','地市']])
save('裁判_负公开滞后',c[c['公开滞后天']<0][ch+['源Excel行','公开滞后天']])
save('裁判_公开滞后年度统计',c.groupby('年份')['公开滞后天'].describe(percentiles=[.25,.5,.75,.95]).reset_index())
summary['裁判']['结果分布']=dict(Counter(c['结果类型'].map(txt)));summary['裁判']['公开日期有效']=int(c['公开日期'].notna().sum());summary['裁判']['负公开滞后']=int((c['公开滞后天']<0).sum())
# Measures: existing category field only, plus separately labelled text mentions.
for h in ['处罚类别','处罚机关']:freq(p,h,f'处罚_{h}分布')
cross(p,'年份','处罚类别','处罚_年份_原始类别');cross(p,'地市','处罚类别','处罚_地市_原始类别')
measures=['罚款','没收','退还土地','拆除','恢复土地原状或复垦']
def tokens(v):return sorted({x.strip() for x in re.split(r'[;；、,，]',txt(v)) if x.strip() and x.strip().lower() not in NULL})
p['类别拆分']=p['处罚类别'].map(tokens)
mt=[]
for _,r in p.iterrows():
    for a in r['类别拆分']:mt.append({'源Excel行':r['源Excel行'],'年份':r['年份'],'地市':r['地市'],'措施':a})
md=pd.DataFrame(mt);save('处罚_类别拆分逐行',md);freq(md,'措施','处罚_拆分措施频数')
ms=md.groupby('措施').size().rename('涉及记录数').reset_index();ms['占处罚全部记录']=ms['涉及记录数']/len(p);save('处罚_拆分措施占比',ms)
cross(md,'年份','措施','处罚_年度措施');cross(md,'地市','措施','处罚_地市措施')
co=Counter()
for v in p['类别拆分']:
    for a,b in itertools.combinations(v,2):co[(a,b)]+=1
save('处罚_措施共现', [{'措施1':a,'措施2':b,'共现记录数':n} for (a,b),n in co.most_common()])
facts={'耕地':'耕地','基本农田':'基本农田','林地':'林地','建设用地':'建设用地','住宅建房':'住宅|住房|建房|宅基地','厂房仓储':'厂房|仓库|车间','硬化堆放':'硬化|硬底化|堆放|堆场','养殖设施':'养殖|猪舍|鸡舍|大棚','规划':'规划','手续审批':'批准|审批|手续'}
mentions=[]
for k,rx in facts.items():
    flag=p['处罚事由'].map(txt).str.contains(rx)
    mentions.append({'提及词组':k,'命中记录数':int(flag.sum()),'占比':float(flag.mean()),'口径':'处罚事由词语提及，不代表用途或地类真值'})
save('处罚_事实关键词提及_非分类',mentions)
summary['处罚']['内容结果一致记录']=int((p['处罚内容'].map(norm)==p['处罚结果'].map(norm)).sum())
# Quantity candidates; preserve all occurrences and contexts; only unique nonnegative candidates summarized.
quant=[]
rx=re.compile(r'(?<![\d*×.])([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(万平方米|平方米|平米|㎡|公顷|亩|万元|元)')
for _,r in p.iterrows():
    for field in ['处罚事由','处罚内容']:
        s=txt(r[field])
        for m in rx.finditer(s):
            val=float(m[1].replace(',',''));unit=m[2];typ='面积' if unit not in ['万元','元'] else '金额'
            if typ=='金额' and not re.search('罚款|罚金',s[max(0,m.start()-25):m.start()]):continue
            factor={'万平方米':10000,'平方米':1,'平米':1,'㎡':1,'公顷':10000,'亩':2000/3,'万元':10000,'元':1}[unit]
            quant.append({'源Excel行':int(r['源Excel行']),'年份':r['年份'],'地市':r['地市'],'字段':field,'类型':typ,'原值':m[0],'统一数值':val*factor,'统一单位':'平方米' if typ=='面积' else '元','上下文':s[max(0,m.start()-35):m.end()+35]})
q=save('处罚_金额面积全部候选含上下文',quant)
uniq=[]
if len(q):
    for (row,typ),g in q.groupby(['源Excel行','类型']):
        values=sorted(set(round(x,6) for x in g['统一数值']));uniq.append({'源Excel行':row,'类型':typ,'不同候选数':len(values),'唯一候选值':values[0] if len(values)==1 else None,'最小候选':min(values),'最大候选':max(values),'年份':g.iloc[0]['年份'],'地市':g.iloc[0]['地市']})
uq=save('处罚_金额面积候选歧义',uniq)
if len(uq):
    save('处罚_唯一金额面积候选描述',uq.groupby('类型')['唯一候选值'].describe(percentiles=[.05,.25,.5,.75,.95,.99]).reset_index())
    save('处罚_唯一金额面积候选年度描述',uq.groupby(['类型','年份'])['唯一候选值'].describe(percentiles=[.25,.5,.75,.95]).reset_index())
    save('处罚_金额面积极值待核',uq.sort_values('最大候选',ascending=False).groupby('类型').head(30))
summary['金额面积口径']='仅数值候选；多候选不选最大值当真值；唯一候选仍需核对语义，不计算单位面积罚款。脱敏数字不补值。'
# Number-field contamination and extraction-based matching candidates.
def docnums(v):
    s=norm(v).translate(str.maketrans('〔〕【】[]﹝﹞','()()()()'))
    rx=r'[\u4e00-\u9fffA-Za-z()]{0,35}\(20\d{2}\)(?:\([^()]{1,10}\))?(?:第)?[A-Za-z\u4e00-\u9fff]{0,5}\d+[A-Za-z\d-]*号?'
    return {m.group(0).replace('第','').removesuffix('号') for m in re.finditer(rx,s)}
number_rows=[];idx=defaultdict(list)
for _,r in p.iterrows():
    v=re.split(r'处罚对象|执法依据|行政处罚信息',txt(r['行政处罚决定书文号']))[0]
    for n in docnums(v):idx[n].append(r)
for tag,d,col in [('处罚',p,'行政处罚决定书文号'),('裁判',c,'涉案行政处罚决定书文号_原始')]:
    for _,r in d.iterrows():number_rows.append({'数据':tag,'源Excel行':r['源Excel行'],'不同文号候选数':len(docnums(r[col])),'含其他字段标签':bool(re.search('处罚对象|执法依据|行政处罚信息|裁判结果',txt(r[col]))),'字段长度':len(txt(r[col]))})
save('文号字段结构逐行',number_rows)
links=[]
for _,cr in c.iterrows():
    seen=set()
    for n in docnums(cr['涉案行政处罚决定书文号_原始']):
        for pr in idx.get(n,[]):
            if pr['源Excel行'] in seen:continue
            seen.add(pr['源Excel行']);delay=(cr['分析日期']-pr['分析日期']).days if pd.notna(cr['分析日期']) and pd.notna(pr['分析日期']) else None
            links.append({'处罚源行':pr['源Excel行'],'裁判源行':cr['源Excel行'],'规范文号候选':n,'案号':cr['案号'],'主体字面一致':norm(pr['被处罚对象'])==norm(cr['行政相对人']),'同市':pr['地市']==cr['地市'],'处罚年':pr['年份'],'裁判年':cr['年份'],'处罚至裁判间隔天':delay,'原始结果标签':cr['结果类型'],'地市':pr['地市']})
lk=save('跨源_文号规则候选逐对_非人工确认',links)
if len(lk):
    for h in ['地市','原始结果标签','处罚年','裁判年']:freq(lk,h,f'跨源_规则候选_{h}')
    save('跨源_规则候选时间间隔描述',lk['处罚至裁判间隔天'].describe(percentiles=[.05,.25,.5,.75,.95]).reset_index())
    save('跨源_候选负间隔',lk[lk['处罚至裁判间隔天']<0])
    summary['跨源规则候选']={'候选对数':len(lk),'不同处罚记录':int(lk['处罚源行'].nunique()),'不同案号':int(lk['案号'].map(norm).nunique()),'同市':int(lk['同市'].sum()),'主体字面一致':int(lk['主体字面一致'].sum()),'负间隔':int((lk['处罚至裁判间隔天']<0).sum()),'说明':'嵌入文号规则命中，未经逐对人工确认；不是司法进入率或匹配准确率。'}
# Coverage and land join. Missing cells remain missing, never zero-filled as no enforcement.
pp=p.dropna(subset=['年份']).groupby(['地市','年份']).size().rename('处罚记录数').reset_index()
cc=c.dropna(subset=['年份']).groupby(['地市','年份']).size().rename('裁判记录数').reset_index()
panel=pp.merge(cc,on=['地市','年份'],how='outer')
land=pd.DataFrame(cv[1:],columns=cv[0]);land['年份']=land['年份'].astype(int)
land=land.sort_values(['地市','年份']);land['不透水面净变化_km2']=land.groupby('地市')['不透水面 km²'].diff();land['耕地净变化_km2']=land.groupby('地市')['耕地 km²'].diff()
panel=panel.merge(land,on=['地市','年份'],how='left');panel['处罚有记录']=panel['处罚记录数'].notna();panel['裁判有记录']=panel['裁判记录数'].notna()
save('跨源_市年覆盖与土地背景',panel)
complete=pd.MultiIndex.from_product([sorted(cities),range(2015,2026)],names=['地市','年份']).to_frame(index=False).merge(panel,on=['地市','年份'],how='left')
save('跨源_全省231市年覆盖_缺记录不等于零',complete)
cor=[]
for x,y in [('处罚记录数','不透水面净变化_km2'),('裁判记录数','不透水面净变化_km2'),('处罚记录数','裁判记录数')]:
    d=panel[[x,y]].dropna();cor.append({'变量1':x,'变量2':y,'共同记录市年数':len(d),'Pearson':d[x].corr(d[y]),'Spearman':d[x].rank().corr(d[y].rank()),'说明':'有公开记录样本的描述性相关，未控制公开覆盖、时间、地区，不作因果或显著性推断'})
save('跨源_描述性相关_非因果',cor)
save('全字段异常清单',anomalies)
summary['分析口径']={'输入':'仅当前根目录两份1106更新版Excel和土地ZIP；旧报告不作为数据输入','有效记录':'最终保留页至少一个字段有效，保留原始行','缺失标记':sorted(NULL),'日期':'支持Excel日期、数字序列和字符串；按决定/裁判日期分年','原标签':'裁判结果未在本轮全量回原文重标','关键词':'只描述文字提及，不构造用途分类','隐私':'全量频数及逐行清单仅保存在本地；报告不展示自然人高频姓名','省界':'GADM4.1固定科研边界；非历史法定边界'}
(OUT/'案件统计摘要.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2,default=str),flush=True)
