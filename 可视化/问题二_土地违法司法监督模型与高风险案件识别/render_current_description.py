"""Build a self-contained Chinese HTML/Markdown report and chart artifacts."""
from pathlib import Path
import sys,json,html,base64,zipfile,re,hashlib,os
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二";sys.path.append(str(ROOT/'.local/feasibility_libs'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.local/matplotlib_cache'))
import pandas as pd,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.colors import ListedColormap
OUT=ROOT/'reports/全面描述性分析_最新版_20261106';T=OUT/'统计表';FIG=OUT/'图表';FIG.mkdir(exist_ok=True)
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc');plt.rcParams['font.family']=font.get_name();plt.rcParams['axes.unicode_minus']=False;plt.rcParams['figure.dpi']=110
S=json.loads((OUT/'案件统计摘要.json').read_text(encoding='utf-8'));G=json.loads((OUT/'地理处理摘要.json').read_text(encoding='utf-8'))
def read(n):return pd.read_csv(T/(n+'.csv'))
def table(d,maxrows=50):
    d=d.head(maxrows).copy()
    for c in d.select_dtypes('number'):
        d[c]=d[c].map(lambda v:'—' if pd.isna(v) else f'{v:,.0f}' if float(v).is_integer() else f'{v:,.4f}')
    return d.fillna('—').to_html(index=False,escape=True,border=0)
charts=[]
def savefig(name,title,fig):
    fig.tight_layout();fig.savefig(FIG/(name+'.png'),dpi=150,bbox_inches='tight');plt.close(fig);charts.append((name,title))
def bars(n,col,title,top=None):
    d=read(n)
    if top:d=d.head(top)
    fig,ax=plt.subplots(figsize=(10,5));ax.barh(d[col].astype(str)[::-1],d['记录数'][::-1],color='#31728e');ax.set_xlabel('记录数');ax.set_title(title);savefig(n,title,fig)
# 1. Time distributions (no arbitrary smoothing).
py=read('处罚_年份分布');cy=read('裁判_年份分布')
fig,ax=plt.subplots(figsize=(11,4.7))
for d,label in [(py,'处罚记录'),(cy,'裁判记录')]:
    d['年']=pd.to_numeric(d['年份'],errors='coerce');d=d.dropna(subset=['年']).sort_values('年');ax.plot(d['年'],d['记录数'],marker='o',label=label)
ax.set_xticks(range(2015,2026));ax.set_ylabel('记录数');ax.set_title('2015—2025年两类公开记录如何分布？');ax.legend();savefig('01_年度分布','2015—2025年两类公开记录如何分布？',fig)
for tag in ['处罚','裁判']:
    d=read(f'{tag}_地市年度').set_index('地市');d=d.reindex(columns=[str(y) for y in range(2015,2026)]).apply(pd.to_numeric,errors='coerce');d=d.replace(0,np.nan)
    fig,ax=plt.subplots(figsize=(11,8));im=ax.imshow(np.ma.masked_invalid(d.values),aspect='auto',cmap='YlGnBu');ax.set_yticks(range(len(d)),d.index);ax.set_xticks(range(11),range(2015,2026));fig.colorbar(im,ax=ax,label='记录数；白色=无记录，不能认定为零事件');ax.set_title(f'{tag}记录在各市、各年覆盖是否均衡？');savefig(f'02_{tag}覆盖',f'{tag}记录在各市、各年覆盖是否均衡？',fig)
bars('裁判_结果类型分布','结果类型','裁判原始结果标签如何分布？')
bars('裁判_行政相对人类型分布','行政相对人类型','裁判相对人类型如何分布？')
bars('裁判_法院分布','法院','哪些法院贡献较多裁判记录？（前15）',15)
bars('处罚_地市分布','地市','哪些地市的公开处罚记录较多？')
bars('处罚_处罚机关分布','处罚机关','处罚机关记录量如何分布？（前15）',15)
md=read('处罚_拆分措施占比').sort_values('涉及记录数').tail(12)
fig,ax=plt.subplots(figsize=(11,5));ax.barh(md['措施'],md['涉及记录数'],color='#2a8676');ax.set_xlabel('涉及记录数，一条记录可含多措施');ax.set_title('现有处罚类别中包含哪些措施？');savefig('03_处罚措施','现有处罚类别中包含哪些措施？',fig)
pr=read('全字段画像');fig,ax=plt.subplots(figsize=(12,8));labels=pr['数据']+'·'+pr['字段'];ax.barh(labels[::-1],(pr['有效率']*100)[::-1],color='#5b8299');ax.set_xlim(0,105);ax.set_xlabel('有效率（%），已排除NULL等标记');ax.set_title('全部原始字段的有效率是多少？');savefig('04_字段有效率','全部原始字段的有效率是多少？',fig)
delay=read('裁判_公开滞后逐行')['公开滞后天'].dropna();fig,ax=plt.subplots(figsize=(10,4.5));bins=[-100000,-1,0,7,30,90,365,100000];labels=['负值','当天','1—7天','8—30天','31—90天','91—365天','超过365天'];counts=pd.cut(delay,bins=bins,labels=labels,include_lowest=True).value_counts(sort=False);ax.bar(labels,counts,color='#8869a0');ax.set_ylabel('记录数');ax.set_title('裁判日期与公开日期相隔多久？');savefig('05_公开滞后','裁判日期与公开日期相隔多久？',fig)
q=read('处罚_金额面积候选歧义');fig,axs=plt.subplots(1,2,figsize=(12,4.6))
for ax,typ in zip(axs,['金额','面积']):
    vals=q.loc[(q['类型']==typ)&(q['不同候选数']==1),'唯一候选值'].dropna();positive=vals[vals>0]
    ax.hist(np.log10(positive),bins=35,color='#6c91a1',edgecolor='white');ax.set_xlabel('log10(元)' if typ=='金额' else 'log10(平方米)');ax.set_ylabel('可解析记录数');ax.set_title(f'{typ}唯一候选的偏态分布（正值n={len(positive):,}）')
savefig('05b_金额面积候选','金额面积唯一候选如何分布？仅候选，不代表核验后的处罚总额或违法总面积',fig)
rr=read('裁判_年份_结果类型');rr['年']=pd.to_numeric(rr['年份'],errors='coerce');rr=rr.dropna(subset=['年']).set_index('年').drop(columns='年份');rr=rr.apply(pd.to_numeric,errors='coerce').fillna(0);totals=rr.sum(axis=1)
fig,ax=plt.subplots(figsize=(12,5.3));(rr.div(totals,axis=0)*100).plot.bar(stacked=True,ax=ax,colormap='tab20');ax.set_xticklabels([str(int(y)) for y in rr.index],rotation=0);ax.set_ylabel('当年有效日期裁判记录占比（%）');ax.set_xlabel('裁判年份');ax.set_title('不同年份的裁判原标签结构是否相同？小样本年份需谨慎');ax.legend(loc='upper left',bbox_to_anchor=(1,1),fontsize=9)
savefig('05c_年度结果结构','不同年份的裁判原标签结构是否相同？',fig)
la=read('地理_省界内年度地类面积');lc=read('地理_变化与转移摘要');fig,axs=plt.subplots(1,2,figsize=(13,4.8))
for label in ['不透水面','耕地','林地']:
    a=la[la['地类']==label];axs[0].plot(a['年份'],a['面积_km2'],label=label)
axs[0].legend();axs[0].set_ylabel('km²');axs[0].set_title('固定省界内主要地类面积如何变化？')
a=lc[lc['结束年'].between(2015,2025)];axs[1].plot(a['结束年'],a['新增不透水面_km2'],marker='o',label='转入不透水面');axs[1].plot(a['结束年'],a['不透水面转出_km2'],marker='s',label='不透水面转出');axs[1].legend();axs[1].set_ylabel('km²');axs[1].set_title('2015—2025年不透水面转入、转出各有多少？');savefig('06_土地变化','主要地类及不透水面转入转出如何变化？',fig)
tr=read('地理_相邻期转移矩阵');tr=tr[tr['结束年'].between(2015,2025)].groupby(['原地类','新地类'])['面积_km2'].sum().unstack().fillna(0);trv=tr.to_numpy(copy=True);np.fill_diagonal(trv,0)
fig,ax=plt.subplots(figsize=(9,7));im=ax.imshow(np.log1p(trv),cmap='YlOrRd');ax.set_xticks(range(len(tr.columns)),tr.columns,rotation=45,ha='right');ax.set_yticks(range(len(tr.index)),tr.index);ax.set_xlabel('转入地类');ax.set_ylabel('原地类');fig.colorbar(im,ax=ax,label='log(1+累计转移面积km²)，对角线置零');ax.set_title('2015—2025年主要发生哪些地类转移？');savefig('07_地类转移','2015—2025年主要发生哪些地类转移？',fig)
city=read('地理_随包原表_地市年度');a=city[city['年份'].isin([2015,2025])].pivot(index='地市',columns='年份',values='不透水面 km²');a['变化']=a[2025]-a[2015];a=a.sort_values('变化');fig,ax=plt.subplots(figsize=(10,7));ax.barh(a.index,a['变化'],color='#c28942');ax.set_xlabel('2025年减2015年，不透水面存量净变化km²');ax.set_title('随包原统计中，各市2015—2025年净变化多少？');savefig('08_地市净变化','随包原统计中，各市2015—2025年净变化多少？',fig)
# Preview of the delivered actual raster, retaining categorical colors.
import rasterio
from rasterio.enums import Resampling
with rasterio.open(G['output']) as ds:
    y0=ds.descriptions.index('2015')+1;y1=ds.descriptions.index('2025')+1
    fig,axs=plt.subplots(1,2,figsize=(12,7));colors=['#ffffff','#e7c579','#286b3a','#7f9d4e','#b5cc80','#458ec4','#f6ffff','#bcaa91','#d54f44','#83c9c2'];cmap=ListedColormap(colors)
    for ax,b,y in [(axs[0],y0,2015),(axs[1],y1,2025)]:
        image=ds.read(b,out_shape=(700,int(ds.width/ds.height*700)),resampling=Resampling.nearest);ax.imshow(image,cmap=cmap,vmin=-.5,vmax=9.5);ax.set_title(f'{y}年，省界外=NoData');ax.axis('off')
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=colors[k],label=label) for k,label in [(1,'耕地'),(2,'林地'),(5,'水体'),(8,'不透水面'),(9,'湿地')]],loc='lower center',ncol=5)
    savefig('09_省界裁剪实图','交付GeoTIFF中的2015与2025年地类预览',fig)
# Full-field profiles and frequencies for the supplied geography tables too.
geo_prof=[]
for name in ['地市年度','区县年度']:
    d=read(f'地理_随包原表_{name}')
    for col in d:
        v=d[col];good=v.dropna();geo_prof.append({'数据表':name,'字段':col,'记录数':len(d),'有效数':len(good),'缺失数':int(v.isna().sum()),'不同值数':int(good.nunique()),'最小':good.min() if pd.api.types.is_numeric_dtype(v) else None,'中位':good.median() if pd.api.types.is_numeric_dtype(v) else None,'最大':good.max() if pd.api.types.is_numeric_dtype(v) else None})
        fr=good.astype(str).value_counts().rename_axis('字段取值').reset_index(name='次数');fr.to_csv(T/'全字段取值频数'/f'地理_{name}_{col}.csv',index=False,encoding='utf-8-sig')
if (T/'地理_全省原表全字段画像.csv').exists():geo_prof=read('地理_全省原表全字段画像').to_dict('records')+geo_prof
pd.DataFrame(geo_prof).to_csv(T/'地理_原统计表全字段画像.csv',index=False,encoding='utf-8-sig')
# Cross-check supplied provincial sum against independently clipped totals: different boundaries, not automatic errors.
landyr=la.pivot(index='年份',columns='地类',values='面积_km2')
sup=city.groupby('年份')[['不透水面 km²','耕地 km²','林地 km²']].sum();cmp=sup.join(landyr[['不透水面','耕地','林地']])
for x in ['不透水面','耕地','林地']:cmp[x+'差值_原表减新裁剪']=cmp[x+' km²']-cmp[x]
cmp.reset_index().to_csv(T/'地理_随包原统计与独立省界统计差异.csv',index=False,encoding='utf-8-sig')
citystats=[]
for name in ['地市年度','区县年度']:
    d=read(f'地理_随包原表_{name}');unit='地市' if name=='地市年度' else '区县';idcol='地市代码' if name=='地市年度' else '区县代码'
    d['不透水面占陆域']=d['不透水面 km²']/d['陆域 km²'];d['耕地占陆域']=d['耕地 km²']/d['陆域 km²'];d['林地占陆域']=d['林地 km²']/d['陆域 km²']
    du=d.sort_values([idcol,'年份']);du['不透水面净变化_km2']=du.groupby(idcol)['不透水面 km²'].diff();du.to_csv(T/f'地理_{name}_结构与净变化.csv',index=False,encoding='utf-8-sig')
    a=du[du['年份'].isin([2015,2025])].pivot(index=idcol,columns='年份',values='不透水面 km²');a['2015至2025净变化_km2']=a[2025]-a[2015];a=a.join(du.drop_duplicates(idcol).set_index(idcol)[[unit]+(['地市'] if unit=='区县' else [])]);a.sort_values('2015至2025净变化_km2',ascending=False).reset_index().to_csv(T/f'地理_{unit}_2015至2025净变化排序.csv',index=False,encoding='utf-8-sig')
# Build report sections (all detailed high-cardinality field values remain local CSV).
sections=[]
def section(title,body):sections.append((title,body))
section('范围、输入与统计口径',f'<p>本报告重新读取根目录两份最新版Excel及广东建设用地压缩包。原件保持只读。处罚{S["处罚"]["记录数"]:,}条、裁判{S["裁判"]["记录数"]:,}条；裁判规范化案号{S["裁判"]["唯一分析键数"]:,}个。地理保留全部36年，重点分析2015—2025年。</p><p>记录数不同于独立违法事件数。NULL等标记按缺失处理；匿名名称不作主体身份识别。下文裁判结果为原表标签，尚未全量回文书重标。金额面积均为候选。逐行清单及全字段完整频数仅保存在本地。</p>')
section('全部案件字段画像',table(pr[['数据','字段','总记录','有效数','缺失数','有效率','不同原值数','长度中位','长度P95','含乱码数','含匿名标记数']])+ '<p>每一个原始字段均有独立完整频数CSV：统计表/全字段取值频数。高基数字段不只保留前十；报告不展示自然人姓名排行榜。</p>')
section('年度、地域与公开覆盖', '<p>两类数据在年份与地区上明显不均衡；无记录单元不补作真实零值。司法日期与处罚日期分别归年，不以裁判公开日期替代裁判日期。</p>'+table(read('处罚_年份分布'))+table(read('裁判_年份分布'))+table(read('处罚_地市分布'))+table(read('裁判_地市分布')))
section('处罚类别、措施、机关与文本',table(read('处罚_处罚类别分布'),20)+table(read('处罚_拆分措施占比'))+f'<p>处罚内容与处罚结果规范化后一致{S["处罚"]["内容结果一致记录"]:,}条，不能把结果字段认定为实际履行。类别拆分允许一条多措施，措施数量合计可超过记录数。措施共现只是频数描述。</p>'+table(read('处罚_事实关键词提及_非分类'))+'<p>完整原类别、机关、文本字段频数及各年各市交叉表见统计表。文字提及不等于事实地类或实际用途，含引用法条的文字也可能命中。</p>')
section('金额与面积的描述边界', '<p>保留所有候选及上下文，统一元与平方米；多候选单列，不以最大数字当成罚款或总面积。脱敏数字不补齐。唯一候选仍不保证语义正确，仅反映可解析文本样本。</p>'+table(read('处罚_唯一金额面积候选描述'))+table(read('处罚_金额面积候选歧义').groupby(['类型','不同候选数']).size().rename('记录数').reset_index(),30))
section('裁判结果、相对人、法院和公开滞后',table(read('裁判_结果类型分布'))+table(read('裁判_行政相对人类型分布'))+table(read('裁判_公开滞后年度统计'))+f'<p>公开日期有效{S["裁判"]["公开日期有效"]:,}条，负公开滞后{S["裁判"]["负公开滞后"]}条单列待核。公开滞后不等于审理时长。驳回、不予受理与实体不准予不是同一法律含义；一份文书可能部分准予、部分不准予。</p>')
quality=pd.DataFrame([{'数据':k,**{key:S[k][key] for key in ['记录数','有效日期','地域未映射数','唯一分析键数','重复键涉及行','重复键差额']}} for k in ['处罚','裁判']])
section('重复、缺失与异常',table(quality)+'<p>无全字段完全重复不等于无业务重复。处罚联合键为机关、原始文号、主体；裁判按规范化案号检查。原文号串入其他标签、匿名化、同案号不同结果和日期等记录均保留源Excel行，未自动删除。完整问题清单见CSV。</p>')
if (T/'裁判_按案号首条去重敏感性_非最终清洗.csv').exists():
    section('重复案号对裁判结果分布的影响',table(read('裁判_按案号首条去重敏感性_非最终清洗'))+'<p>取首条只用于检查分布对重复记录的敏感性，不是确定真实裁判结果的清洗规则。冲突案号必须回原文辨别版本或分项处理。</p>')
if (OUT/'原文统计摘要.json').exists():
    R=json.loads((OUT/'原文统计摘要.json').read_text(encoding='utf-8'))
    section('本地裁判原文的覆盖与文本结构',table(pd.DataFrame([{'项目':k,'值':v} for k,v in R.items()]))+table(read('裁判原文_文本长度描述'))+table(read('裁判原文_理由词语提及_非原因分类'))+'<p>原文覆盖与当前Excel记录不是一一相等；仅对文件名案号可靠对应的原件进行理由词语和书名号标题统计。推荐案例和平台尾部内容被截除。关键词仅为提及，不等于法院否定理由；混合主文候选仍需人工阅读，不能直接改写原表标签。</p>')
link=S.get('跨源规则候选',{})
section('处罚与裁判的关联描述',f'<p>本次嵌入文号规则得到{link.get("候选对数",0)}个候选对、涉及{link.get("不同处罚记录",0)}条处罚、{link.get("不同案号",0)}个案号；同市{link.get("同市",0)}对、主体文字一致{link.get("主体字面一致",0)}对、负间隔{link.get("负间隔",0)}对。均未逐对人工确认，不能当作司法进入率、准确率或关联召回率。</p>'+table(read('跨源_规则候选时间间隔描述'))+table(read('跨源_描述性相关_非因果'))+'<p>地区年度关联使用同一地区的聚合，不意味着同一宗地或同一事件。相关系数未控制来源覆盖、地区或年度依赖，不作显著性和因果解释。</p>')
section('广东省地理数据：单文件交付与裁剪',f'<p>交付文件：{html.escape(Path(G["output"]).name)}。共36个波段，依次为1990—2025年；30米，uint8，0为NoData，省界外全部清零；保持原有分类编码和网格。尺寸{G["grid"]["width"]:,}×{G["grid"]["height"]:,}；文件{G["bytes"]/1e6:,.2f}MB。省界内原始NoData仍保留，不推断或补填地类。</p><p>裁剪采用GADM4.1 WGS84广东研究边界，转换至原栅格Albers投影，按像元中心判定；不是逐年法定边界或地籍测绘结果。边界来源与许可见独立说明JSON。香港澳门及其他省份不作为广东保留。36波段均已重新读遍验证：省界外非零像元为0，全部地类计数与处理统计一致。</p>'+table(pd.DataFrame(G['verification'])))
section('地理数据全字段、时空结构与转移',table(pd.DataFrame(geo_prof))+ '<p>随包统计表涵盖全省、21市、124区县、1990—2025年，各字段完整频数及数值分布均已输出。原表按其原口径保留，与本次GADM省界独立统计分开展示；差值不直接认定为原表错误。另输出全省—地市—区县汇总核对。全省原表“当年新增”是存量差分，不是逐像元转入总面积。随包说明页的1.66倍换算及对产品异常的原因判断未验证，不采用为结论。</p>'+table(la[la['年份'].isin([1990,2015,2025])])+table(lc[lc['结束年'].between(2015,2025)])+'<p>不透水面是地表覆盖指标，不等于法定建设用地，也不能凭像元判断违法。逐年转移面积累计可能重复经过同一像元，不能当作全期唯一变化地块面积。</p>')
section('关键结论与使用限制','<p>可直接使用的基础是公开记录的时空分布、字段质量、措施结构、原始司法标签及土地覆盖变化。不能由公开记录下降推断违法减少；不能由未匹配推断没有司法程序；不能由裁判准予推断实际执行。金额面积、文号候选及关键词必须保持候选身份。地理原表与独立裁剪的边界和分辨率口径分别留痕。</p>')
section('复现、来源与文件索引','<p>处理脚本：scripts/describe_current_full.py、describe_geography_current.py、render_current_description.py。源文件哈希见案件统计摘要.json；输出GeoTIFF哈希及省界元数据见地理处理摘要.json。详细CSV清单见统计明细.zip；含匿名主体和逐行数据的文件只供本地分析。</p><p>边界来源：<a href="https://gadm.org/download.html">GADM 4.1</a>；许可：<a href="https://gadm.org/license.html">学术非商业使用许可</a>；土地覆盖来源按包内说明为<a href="https://zenodo.org/records/18180184">CLCD v1.0.5</a>。</p>')
chart_html=''.join(f'<figure><img src="data:image/png;base64,{base64.b64encode((FIG/(n+".png")).read_bytes()).decode()}"><figcaption>{html.escape(title)}</figcaption></figure>' for n,title in charts)
body=''.join(f'<section><h2>{html.escape(title)}</h2>{b}</section>' for title,b in sections)
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>最新版三类数据全面描述性分析</title><style>body{font-family:"Microsoft YaHei",sans-serif;max-width:1350px;margin:35px auto;padding:0 26px;color:#243343;line-height:1.75;background:#f6f8fa}h1,h2{color:#16465c}section,figure{background:white;padding:22px;border-radius:10px;margin:24px 0;overflow:auto}table{border-collapse:collapse;font-size:13px;width:100%;white-space:nowrap}td,th{border-bottom:1px solid #e0e7ec;padding:7px 10px;text-align:left}th{background:#eaf1f5}img{max-width:100%;height:auto}figcaption{color:#486174}p{max-width:1180px}</style><body><h1>最新版裁判、处罚与广东地理数据：全面描述性分析</h1><p>2026年11月6日 · 重新读取当前原始文件 · 全字段、质量、时空与跨源描述</p>'+body+'<h2>可视化结果</h2>'+chart_html+'</body></html>'
(OUT/'全面描述性分析报告.html').write_text(page,encoding='utf-8')
md='# 最新版三类数据全面描述性分析\n\n'+ '\n\n'.join('## '+title+'\n\n'+re.sub('<[^>]+>',' ',b.replace('</p>','\n\n').replace('</tr>','\n').replace('</td>',' | ').replace('</th>',' | ')) for title,b in sections)
(OUT/'全面描述性分析报告_文字摘要.md').write_text(html.unescape(md),encoding='utf-8')
manifest=[{'file':str(p.relative_to(OUT)),'bytes':p.stat().st_size} for p in T.rglob('*.csv')]
(OUT/'统计文件清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(OUT/'全字段统计与明细.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in T.rglob('*.csv'):z.write(p,p.relative_to(OUT))
    for p in OUT.glob('*.json'):z.write(p,p.name)
# Compact independent chart contact sheet for visual QA.
from PIL import Image,ImageOps,ImageDraw
thumbs=[]
for n,title in charts:
    im=Image.open(FIG/(n+'.png')).convert('RGB');im.thumbnail((650,450));cell=Image.new('RGB',(670,480),'white');cell.paste(im,((670-im.width)//2,10));thumbs.append(cell)
canvas=Image.new('RGB',(1340,480*((len(thumbs)+1)//2)), '#e7edf0')
for i,im in enumerate(thumbs):canvas.paste(im,((i%2)*670,(i//2)*480))
canvas.save(OUT/'图表检查拼图.jpg',quality=85)
print(json.dumps({'report':str(OUT/'全面描述性分析报告.html'),'charts':len(charts),'csv_files':len(manifest),'geo':G['output']},ensure_ascii=False),flush=True)
