"""Audit and present the outcome-blind clustering experiment without refitting."""
from pathlib import Path
import sys,re,json,html,base64,zipfile,hashlib,unicodedata
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二";sys.path.append(str(ROOT/'.local/feasibility_libs'))
import pandas as pd,numpy as np
OUT=ROOT/'reports/处罚司法聚类画像_20261106';T=OUT/'数据与统计';F=OUT/'图表'
M=json.loads((OUT/'实验摘要.json').read_text(encoding='utf-8'))
def read(n):return pd.read_csv(T/(n+'.csv'))
def save(n,d):d.to_csv(T/(n+'.csv'),index=False,encoding='utf-8-sig')
def norm(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(s)))
dictionary=[]
for k in ['退还土地','拆除','没收','罚款','恢复原状']:
 dictionary.append({'字段组':'原处罚/措施','字段':k,'来源':'处罚表处罚类别','含义':'原类别拆分或词语指示，未全量核实与处罚内容一致','0含义':'原类别未识别到，不代表法律上不存在'})
 dictionary.append({'字段组':'申请措施','字段':k,'来源':'裁判原文审查意见之前的申请语句','含义':'申请语句中的措施词语指示','0含义':'规则未识别到，不代表申请绝对不含该事项'})
for k in ['住宅','厂房仓储','硬化堆放','农业养殖','耕地','林地','建设用地','符合规划','不符合规划']:
 dictionary.append({'字段组':'事实提及','字段':k,'来源':'处罚事由及裁判前叙述','含义':'文本提及，可能存在法条引用或部分地块不同情况','0含义':'未提及，不代表事实不存在'})
dictionary.append({'字段组':'主体线索','字段':'组织/自然人','来源':'裁判原主体类型；处罚主体名称后缀或姓名形式线索','含义':'处罚侧只是启发式线索，匿名机构与匿名个人可能无法区分','0含义':'不符合当前规则或未知，不能当作反向身份判断'})
save('特征口径字典',pd.DataFrame(dictionary))
def table(d):
 a=d.copy()
 for k in a.select_dtypes('number'):
  a[k]=a[k].map(lambda x:'—' if pd.isna(x) else f'{x:,.0f}' if float(x).is_integer() else f'{x:.3f}')
 return a.fillna('—').to_html(index=False,escape=True,border=0)
an={1:'建设用地提及的综合处罚型',2:'组织主体、退还土地并罚款型',3:'拆除并恢复原状型',4:'没收并罚款型',5:'罚款为主、其他特征较少型',6:'组织主体、罚款／没收型',7:'退还土地、拆除与恢复原状组合型'}
bn={1:'组织主体、多项原处罚—拆除恢复申请型',2:'自然人住宅提及—拆除恢复申请型',3:'自然人、多项原处罚—拆除恢复申请型',4:'自然人、多项申请含退还及罚款型',5:'原表退还等措施—拆除恢复申请型',6:'住宅与建设用地提及—拆除申请型',7:'没收、退还等原处罚—没收申请为主型'}
A=read('A处罚画像_关联比例与市年标准化');A.insert(1,'画像描述',A['簇'].map(an));A['严格主体一致关联比例']=A['严格主体一致关联数']/A['观察窗口处罚记录'];save('A处罚画像_命名与敏感性',A)
B=read('B1跨源融合申请画像_结果比例');B.insert(1,'画像描述',B['簇'].map(bn));cases=read('B1跨源融合申请画像_案件与特征')
# Source-label agreement sensitivity. No source label is overwritten.
orig=read('裁判_主文候选与申请事项抽取')[['规范案号','结果类型']];cases=cases.merge(orig,on='规范案号',how='left',validate='one_to_one')
mapping={'准予执行':'准予执行','不准予执行':'不准予执行','驳回执行申请':'驳回申请','不予受理':'不予受理','由行政机关组织实施':'准予执行'}
cases['原表主文一致']=cases['结果类型'].map(mapping)==cases['主文候选标签']
agreement=cases[cases['原表主文一致']].groupby('融合簇').agg(一致样本数=('规范案号','size'),准予候选=('主文候选标签',lambda s:s.eq('准予执行').sum())).reset_index();agreement['一致样本准予比例']=agreement['准予候选']/agreement['一致样本数'];save('B1跨源融合申请画像_原标签一致敏感性',agreement)
conflicts=cases[~cases['原表主文一致']][['规范案号','结果类型','主文候选标签','主文证据']];save('B1跨源融合申请画像_原标签不一致待复核',conflicts)
courts=[];overlap=[]
for cl,g in cases.groupby('融合簇'):
 v=g['法院'].map(lambda s:norm(s).removeprefix('广东省')).value_counts();courts.append({'簇':cl,'最大来源法院':v.index[0],'该院案件数':int(v.iloc[0]),'该院占比':float(v.iloc[0]/len(g))})
B=B.merge(pd.DataFrame(courts),on='簇');B=B.merge(read('B1跨源融合申请画像_同法院年标准化').rename(columns={'融合簇':'簇'})[['簇','观察期望比']],on='簇');save('B1跨源融合申请画像_命名与法院构成',B)
cases['法院年']=cases['法院'].map(lambda s:norm(s).removeprefix('广东省'))+'|'+cases['裁判日期'].str[:4]
st=cases.groupby('法院年').agg(n=('规范案号','size'),簇数=('融合簇','nunique'),结果数=('主文候选标签','nunique'))
informative=set(st[(st['n']>=10)&(st['簇数']>=2)&(st['结果数']>=2)].index)
cases['有同院年异结果对照']=cases['法院年'].isin(informative)
save('B1跨源融合申请画像_同院年对照覆盖',cases.groupby('融合簇').agg(案件数=('规范案号','size'),有异结果对照案件=('有同院年异结果对照','sum')).reset_index())
# Preserve precisely the cases that were actually read, updating current cluster assignment.
review_ids=['(2020)粤0982行审448号','(2020)粤0982行审483号','(2020)粤0704行审101号','(2019)粤0704行审735号','(2019)粤0704行审752号','(2019)粤0704行审759号','(2020)粤0606行审78号','(2020)粤0606行审256号','(2020)粤0704行审195号','(2020)粤0704行审260号','(2020)粤0606行审345号','(2020)粤0606行审445号']
rv=cases[cases['规范案号'].isin(review_ids)][['规范案号','融合簇','申请事项证据','主文证据']].copy();rv['初读结论']='已阅读对应文号、事实、申请与主文，未见明显冲突；非法律专家全量复核，不能估计总体准确率';save('B1跨源融合申请画像_12件初读样本',rv)
# Representative cases nearest the fitted cluster means; do not choose on outcomes.
means=read('B1跨源融合申请画像_全特征簇均值').set_index('簇');cols=M['B1融合聚类']['特征'];reps=[]
for cl,g in cases.groupby('融合簇'):
 dist=((g[cols]-means.loc[cl,cols])**2).sum(axis=1)
 for idx in dist.sort_values().head(4).index:
  r=cases.loc[idx];reps.append({'簇':cl,'画像描述':bn[cl],'案号':r['规范案号'],'原始标签':r['结果类型'],'主文候选':r['主文候选标签'],'申请事项证据':r['申请事项证据'],'主文证据':r['主文证据']})
save('B1跨源融合申请画像_代表案例',pd.DataFrame(reps))
checks=[]
assert M['最终不同案号']==M['补全文成功案号']==11141;checks.append('最终保留案号均补齐原文，未纳入最终清单外案号')
assert int(A['全期本簇记录'].sum())==M['A聚类']['样本']==19833;assert int(A['观察窗口处罚记录'].sum())==M['A主比较样本'];checks.append('处罚聚类与观察窗口合计一致')
assert int(B['案件数'].sum())==M['B1融合聚类']['样本']==len(cases);checks.append('融合申请画像案件合计一致')
assert len(set(cases['规范案号']))==len(cases);checks.append('融合样本按案号唯一')
assert not set(M['未输入聚类的字段'])&set(M['A聚类']['特征']+M['B聚类']['特征']+M['B1融合聚类']['特征']);checks.append('关联与裁判结果不作为聚类特征')
for name,sha in M['输入'].items():assert hashlib.file_digest((ROOT/name).open('rb'),'sha256').hexdigest()==sha
checks.append('全部输入哈希未变')
(OUT/'交付核验.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
def percent_table(d,columns):
 d=d.copy()
 for col in columns:d[col]=d[col].map(lambda x:f'{100*x:.2f}%' if pd.notna(x) else '—')
 return table(d)
sections=[]
def section(title,body):sections.append((title,body))
section('结论与适用范围','<p><strong>已实际构建两组探索性画像。第一组是处罚与公开司法记录的可观察关联画像，不能视作真实司法进入概率；第二组是483件较严格规则关联候选且事项、主文可提取的融合申请画像，另有3,746件裁判作为扩大样本对照。</strong></p><p>最重要的限制：类型差异与法院、年份高度重叠；不能据某簇100%准予就作普遍预测。处罚聚类分离度较弱、随机初始化稳定性有限，当前不是已经验证的天然分类。</p>')
section('样本与关联过程',table(pd.DataFrame([{'阶段':k,'案号数':v} for k,v in M['B样本漏斗'].items()]))+table(read('关联_分层统计'))+'<p>以1106最终保留Excel界定裁判范围，按规范化案号补入合并CSV原文。重复案号选择最长原文版本并保留源标签冲突标记；四个源标签冲突案号不进入结果比较。完整文号、同市、时序和处罚端唯一性构成A/B规则候选，A另要求未匿名主体一致；C不进入主比较。A/B共724对，681条处罚、723个案号；仍不是全量人工确认的真链接。</p>')
section('第一组：行政处罚的观察关联画像',percent_table(A[['簇','画像描述','全期本簇记录','观察窗口处罚记录','两年内规则关联记录','两年内观察关联比例','严格主体一致关联比例','观察期望比']],['两年内观察关联比例','严格主体一致关联比例'])+'<p>使用全部19,833条处罚的措施、事实词语提及和主体线索聚类，之后才附加关联标签。主比较限定处罚日期不晚于2023年且能抽取文号的16,213条记录，给出截至2025年的两年窗口；这只避免日历右截尾，不能补足司法公开缺失。未匹配表示未观察到，不等于没有司法程序。</p><p>拆除恢复型在宽口径下24.88%观察关联，但要求主体文字一致后为2.29%；组织退还罚款型则为3.44%和2.99%。排序对匿名化和匹配口径敏感，不能直接宣称拆除类真实进入司法概率最高。严格口径也会漏掉大量匿名化真链接，不能把它当作准确率。</p>')
section('第二组：原处罚与执行申请融合画像',percent_table(B[['簇','画像描述','案件数','纯准予候选数','纯准予候选比例','最大来源法院','该院案件数','该院占比','观察期望比']],['纯准予候选比例','该院占比'])+'<p>聚类同时输入原表处罚类别拆分指示、裁判前叙述中识别的申请措施、事实提及及主体线索；未输入主文、理由、结果、法院、年份和关联标签。画像名称是对簇中心的描述，不是法律定性。原表类别与正文内容可能不一致，需进一步核对，不能把原类别指示视为原处罚的权威法律结构。</p><p>住宅拆除恢复簇58/58准予，但55件来自化州市法院，且57件在2020年；多项申请簇38/39准予，33件来自电白法院；没收申请为主簇56/66准予，45件来自顺德法院。这些首先是特定样本组合，不能转成新案件的预测概率。</p>')
section('法院年份对照与稳健性',table(read('B1跨源融合申请画像_同法院年标准化'))+table(read('B1跨源融合申请画像_同院年对照覆盖'))+table(read('B1跨源融合申请画像_原标签一致敏感性'))+'<p>观察期望比以本样本同法院同年结果比例为基线，已统一法院名称中的广东省前缀。多数高准予簇接近1；同院年全是准予或缺乏异结果对照时，该比值没有识别类型效应的能力。这不是因果调整，也不是显著性检验。另提供3,746件扩大裁判样本及原标签—主文一致子样本对照。</p>')
section('主文重提取及排除样本',table(read('裁判_原标签与主文候选交叉'))+'<p>主文候选标注为纯准予、混合、不准予、驳回、不予受理、撤回/撤销、未提取。混合568件、未可靠提取43件等不进入纯准予二分类比较。原始结果标签完整保留，候选不自动覆盖原表。全表主文提取和申请证据CSV便于复核；12件融合样本已初读，但不是独立专家准确率测试。</p>')
section('算法、特征与聚类质量',table(pd.DataFrame([{'实验':name,'样本':M[key]['样本'],'K':M[key]['k'],'轮廓系数':M[key]['轮廓系数'],'不同随机种子ARI':str(M[key]['不同随机种子ARI'])} for name,key in [('处罚全样本','A聚类'),('扩大裁判样本','B聚类'),('处罚裁判融合','B1融合聚类')]]))+'<p>K-means使用0/1特征，剔除发生率低于1%或高于99%的特征，不对稀有二值特征做单位方差放大。K=2—7按轮廓系数和最小簇占比选择，结果标签不参与选择；固定随机种子，比较另三个初始化。事实词语仅为提及，不是人工确认用途、地类或规划符合性。数字金额面积在本轮未进入聚类，以免候选歧义制造假画像。</p><p>Wilson区间只展示记录规模导致的比例不确定性，不能覆盖非随机公开偏差、关联误差或原文标签误差。当前结果仅为探索性构建，尚未训练预测器。</p>')
section('证据、文件与下一步使用','<p>每条输出保留处罚源行、案号、关联依据、申请句和主文证据。数据与统计目录及明细ZIP含完整特征、聚类标签、K选择、法院年份构成、关联分层、原标签交叉和代表案例。原始文件未修改。</p><p>若用于研究报告，建议第一问写“公开处罚的司法关联可见度与类型差异”，第二问写“原处罚—申请措施组合与司法处理分布”。要进一步声称真实进入概率或泛化预测，须扩充公开覆盖审计和人工链接/标签复核，采用法院、年份独立留出验证。</p>')
imgs=[]
for p in sorted(F.glob('*.png')):imgs.append(f'<figure><img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"><figcaption>{html.escape(p.stem)}</figcaption></figure>')
body=''.join(f'<section><h2>{html.escape(t)}</h2>{b}</section>' for t,b in sections)
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>处罚司法关联与执行申请聚类画像</title><style>body{font-family:Microsoft YaHei,sans-serif;background:#f3f6f8;color:#243846;max-width:1400px;margin:30px auto;padding:0 24px;line-height:1.8}h1,h2{color:#174e65}section,figure{background:white;border-radius:10px;padding:22px;margin:20px 0;overflow:auto}table{border-collapse:collapse;font-size:13px;width:100%;white-space:nowrap}td,th{padding:8px;border-bottom:1px solid #dde5e9;text-align:left}th{background:#e8f0f4}img{max-width:100%}strong{color:#154d64}</style><body><h1>土地违法处罚司法关联与执行申请：聚类画像试验</h1><p>2026年11月6日 · 最终保留清单控制范围 · 原文补全 · 结果不参与聚类</p>'+body+''.join(imgs)+'</body></html>'
(OUT/'聚类画像报告.html').write_text(page,encoding='utf-8')
md='# 处罚司法关联与执行申请聚类画像\n\n'+'\n\n'.join('## '+t+'\n\n'+html.unescape(re.sub('<[^>]+>',' ',b.replace('</p>','\n\n').replace('</tr>','\n').replace('</td>',' | ').replace('</th>',' | '))) for t,b in sections)
(OUT/'聚类画像报告_文字版.md').write_text(md,encoding='utf-8')
with zipfile.ZipFile(OUT/'聚类画像与证据明细.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
 for p in T.glob('*.csv'):z.write(p,p.relative_to(OUT))
 for p in OUT.glob('*.json'):z.write(p,p.name)
from PIL import Image
tiles=[]
for p in [F/'A处罚_特征.png',F/'A处罚_结果.png',F/'B1跨源申请_特征.png',F/'B1跨源申请_结果.png']:
 im=Image.open(p).convert('RGB');im.thumbnail((850,520));tile=Image.new('RGB',(870,540),'white');tile.paste(im,((870-im.width)//2,10));tiles.append(tile)
canvas=Image.new('RGB',(1740,1080),'#e5edf0')
for i,tile in enumerate(tiles):canvas.paste(tile,((i%2)*870,(i//2)*540))
canvas.save(OUT/'图表核验.jpg',quality=90)
print(json.dumps({'report':str(OUT/'聚类画像报告.html'),'csv':len(list(T.glob('*.csv'))),'A':len(A),'B融合':len(B),'融合样本':len(cases),'核验':checks},ensure_ascii=False),flush=True)
