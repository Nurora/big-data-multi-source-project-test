"""Additional descriptive checks for dates, labels and all supplied geography sheets."""
from pathlib import Path
import io,zipfile,json,re,unicodedata
import pandas as pd,openpyxl
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二";OUT=ROOT/'reports/全面描述性分析_最新版_20261106';T=OUT/'统计表'
def norm(v):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(v or '')))
def load(f):
 w=openpyxl.load_workbook(f,read_only=True,data_only=True);it=w['最终保留'].values;h=next(it);d=pd.DataFrame([r for r in it if any(v is not None for v in r)],columns=h);d['源Excel行']=range(2,len(d)+2);w.close();return d
def save(n,d):d.to_csv(T/(n+'.csv'),index=False,encoding='utf-8-sig')
p=load(next(ROOT.glob('*1106*处罚保留*.xlsx')));c=load(next(ROOT.glob('*1106*裁判文书.xlsx')))
for tag,d,dc in [('处罚',p,'处罚决定日期'),('裁判',c,'标准裁判日期')]:
 d['日期']=pd.to_datetime(d[dc],errors='coerce');counts=d.groupby('日期').size().rename('记录数').reset_index().sort_values('记录数',ascending=False);save(f'{tag}_每日记录集中度',counts)
 year=d['日期'].dt.year
 if tag=='处罚':
  d['声明年份']=pd.to_numeric(d['处罚年份'],errors='coerce');d['日期年份']=year
  save('处罚_声明年份与日期年份核对',d[['源Excel行','处罚年份','处罚决定日期','声明年份','日期年份']])
 else:
  d['案号年份']=d['案号'].map(norm).str.extract(r'\((\d{4})\)',expand=False).astype('Int64');d['裁判年份']=year
  save('裁判_案号年份与裁判年份核对',d[['源Excel行','案号','标准裁判日期','案号年份','裁判年份']])
  d['法院层级']=d['法院'].map(lambda s:'高级' if '高级' in str(s) else '中级' if '中级' in str(s) else '基层或其他')
  save('裁判_法院层级频数',d.groupby('法院层级').size().rename('记录数').reset_index())
  save('裁判_法院层级与结果',pd.crosstab(d['法院层级'],d['结果类型']).reset_index())
# Anonymous-name rates are descriptive; repeated anonymous names are never identity keys.
for tag,d,col in [('处罚',p,'被处罚对象'),('裁判',c,'行政相对人')]:
 d['匿名标记']=d[col].map(norm).str.contains(r'某|\*{2,}|×{2,}');d['年份']=d['日期'].dt.year
 save(f'{tag}_年度匿名标记',d.groupby('年份').agg(记录数=('匿名标记','size'),匿名标记记录=('匿名标记','sum'),匿名标记比例=('匿名标记','mean')).reset_index())
with zipfile.ZipFile(ROOT/'广东建设用地数据.zip') as z:
 inventory=pd.DataFrame([{'压缩包成员':i.filename,'原始字节':i.file_size,'压缩字节':i.compress_size,'CRC32':f'{i.CRC:08x}'} for i in z.infolist() if not i.is_dir()]);save('地理_源压缩包完整清单',inventory)
 name=next(n for n in z.namelist() if n.endswith('广东省建设用地原始数据.xlsx'));w=openpyxl.load_workbook(io.BytesIO(z.read(name)),read_only=True,data_only=True)
 vals=list(w['全省年度'].values);hd=next(i for i,r in enumerate(vals) if r[0]=='年份');province=pd.DataFrame(vals[hd+1:],columns=vals[hd]);province=province[province['年份'].notna()];save('地理_随包原表_全省年度',province)
 province['不透水面差分']=province['不透水面'].diff();province['原新增减差分']=province['当年新增']-province['不透水面差分'];save('地理_全省原表新增字段核对',province)
 city=pd.DataFrame(list(w['地市年度'].values)[1:],columns=list(w['地市年度'].values)[0]);county=pd.DataFrame(list(w['区县年度'].values)[1:],columns=list(w['区县年度'].values)[0]);w.close()
 grouped=county.groupby(['地市','年份'])[['不透水面 km²','耕地 km²','林地 km²','陆域 km²']].sum().reset_index();check=city.merge(grouped,on=['地市','年份'],suffixes=('_地市表','_区县合计'))
 for k in ['不透水面 km²','耕地 km²','林地 km²','陆域 km²']:check[k+'差']=check[k+'_地市表']-check[k+'_区县合计']
 save('地理_区县汇总与地市表核对',check)
 ps=city.groupby('年份')[['不透水面 km²','耕地 km²','林地 km²','陆域 km²']].sum().reset_index();pc=province.merge(ps,on='年份')
 for x,y in [('不透水面','不透水面 km²'),('耕地类','耕地 km²'),('林地类','林地 km²'),('陆域面积','陆域 km²')]:pc[x+'差']=pc[x]-pc[y]
 save('地理_地市汇总与全省原表核对',pc)
 name=next(n for n in z.namelist() if n.endswith('广东省建设用地初步分析.xlsx'));w=openpyxl.load_workbook(io.BytesIO(z.read(name)),read_only=True,data_only=True);cells=[]
 for s in w:
  for row in s:
   for cell in row:
    if cell.value is not None:cells.append({'工作表':s.title,'单元格':cell.coordinate,'原值':str(cell.value),'口径':'随包既有说明或派生结果，不作为独立实证结论'})
 save('地理_随包说明分析页原单元格',pd.DataFrame(cells));w.close()
# All provincial fields, including the net-change field, get complete frequency tables.
profile=[]
for col in province.columns[:6]:
 g=province[col].dropna();profile.append({'数据表':'全省年度','字段':col,'记录数':len(province),'有效数':len(g),'缺失数':int(province[col].isna().sum()),'不同值数':int(g.nunique()),'最小':g.min(),'中位':g.median(),'最大':g.max()})
 g.value_counts().rename_axis('字段取值').reset_index(name='次数').to_csv(T/'全字段取值频数'/f'地理_全省年度_{col}.csv',index=False,encoding='utf-8-sig')
save('地理_全省原表全字段画像',pd.DataFrame(profile))
info={'全省与地市不透水面最大绝对差_km2':float(pc['不透水面差'].abs().max()),'地市与区县合计不透水面最大绝对差_km2':float(check['不透水面 km²差'].abs().max()),'全省原新增与不透水面差分最大绝对差_km2':float(province['原新增减差分'].abs().max()),'说明':'当年新增字段为存量差分，不能视为逐像元转入总面积。原说明页倍数换算及产品异常解释未在本轮验证，不采用为结论。'}
(OUT/'补充核验摘要.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(info,ensure_ascii=False))
