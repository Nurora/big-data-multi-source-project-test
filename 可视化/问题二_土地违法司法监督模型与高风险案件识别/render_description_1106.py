"""Render the completed descriptive tables into a portable illustrated report."""
import sys,json,html,base64,zipfile,re,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
sys.path.insert(0,str(ROOT/'.local/feasibility_libs'))
os.environ['MPLCONFIGDIR']=str(ROOT/'.local/matplotlib_cache')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
OUT=ROOT/'reports/两类案件描述性分析_20261106'
T=OUT/'统计表';FIG=OUT/'图表';FIG.mkdir(exist_ok=True)
fontpath=Path('C:/Windows/Fonts/msyh.ttc')
font_manager.fontManager.addfont(str(fontpath))
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(fontpath)).get_name(),'axes.unicode_minus':False,'figure.dpi':130,'axes.spines.top':False,'axes.spines.right':False,'font.size':10,'savefig.facecolor':'white'})
S=json.loads((OUT/'统计摘要.json').read_text(encoding='utf-8'))
Q=json.loads((OUT/'补充质量核验.json').read_text(encoding='utf-8'))
def read(name):return pd.read_csv(T/(name+'.csv'))
plots=[]
def savefig(name,title):
    plt.tight_layout();plt.savefig(FIG/(name+'.png'),bbox_inches='tight');plt.close();plots.append((name,title))
def bar(name,title,limit=15):
    d=read(name).iloc[:limit];labels=d.iloc[:,0].astype(str);vals=d['记录数']
    plt.figure(figsize=(10,max(3.5,len(d)*.34)));plt.barh(labels[::-1],vals.iloc[::-1],color='#315a85')
    plt.xlabel('记录数');plt.title(title)
    for j,v in enumerate(vals.iloc[::-1]):plt.text(v,j,' '+format(int(v),','),va='center',fontsize=8)
    plt.margins(x=.18);savefig(name,title)
for tag in ['处罚','裁判']:
    for col in ['地市','月份','星期']:
        bar(f'03_{tag}_{col}分布',tag+col+'分布',21 if col=='地市' else 15)
for name,title in [('05_裁判_法院分布','裁判法院记录分布'),('05_裁判_结果分布','裁判结果分布'),('05_裁判_主体类型','裁判主体类型'),('07_清洗处罚_主体分布','清洗处罚表主体类型'),('07_处罚_机关分布','处罚机关记录分布'),('12_处罚措施组合分布','处罚措施组合候选'),('12_用途提及组合逐标签频数','处罚事实中的用途提及'),('12_地类提及组合逐标签频数','处罚事实中的地类提及'),('10_公开滞后分档','公开相对裁判日期的滞后')]:bar(name,title)
plt.figure(figsize=(11,4.5))
for tag,color in [('处罚','#315a85'),('裁判','#c46e3b'),('清洗处罚','#568369')]:
    d=read(f'03_{tag}_年份分布');d[d.columns[0]]=pd.to_numeric(d.iloc[:,0],errors='coerce');d=d.dropna().sort_values(d.columns[0]);plt.plot(d.iloc[:,0],d['记录数'],marker='o',label=tag,color=color)
plt.ylabel('记录数');plt.title('年度记录数量与口径比较');plt.legend();savefig('年度对比','年度记录数量与口径比较')
for name,title in [('04_处罚_地市年份','处罚地市与年份覆盖'),('04_裁判_地市年份','裁判地市与年份覆盖'),('06_裁判_年份与结果','裁判结果的年度构成')]:
    d=read(name).set_index(read(name).columns[0]);d=d.apply(pd.to_numeric,errors='coerce').fillna(0)
    plt.figure(figsize=(12,max(4,len(d)*.35)))
    im=plt.imshow(d.to_numpy(),aspect='auto',cmap='Blues');plt.colorbar(im,label='记录数')
    plt.xticks(range(len(d.columns)),d.columns,rotation=35,ha='right');plt.yticks(range(len(d)),d.index.astype(str));plt.title(title)
    if d.size<350:
        for i in range(len(d)):
            for j in range(len(d.columns)):
                if d.iloc[i,j]>0:plt.text(j,i,str(int(d.iloc[i,j])),ha='center',va='center',fontsize=7,color='white' if d.iloc[i,j]>d.to_numpy().max()*.6 else '#182b41')
    savefig(name,title)
# Result mix and public-date completeness reveal compositional changes.
d=read('06_裁判_年份与结果').set_index('年份');d=d.loc[d.index.astype(str)!='缺失'];d=d.div(d.sum(axis=1),axis=0)*100
ax=d.plot.bar(stacked=True,figsize=(12,5),colormap='tab20c');ax.set_ylabel('行内占比 %');ax.set_title('各裁判年份的结果构成');ax.legend(bbox_to_anchor=(1.01,1),loc='upper left',fontsize=8);savefig('裁判年度结果占比','各裁判年份的结果构成')
profile=read('01_全字段画像')
freq=read('02_全字段完整取值频数').fillna('')
def mdtable(df,maxrows=15):
    df=df.head(maxrows).fillna('缺失')
    def val(x):
        if isinstance(x,float):return f'{x:,.3f}'
        return str(x).replace('|','／').replace('\n',' ')[:180]
    return '| '+' | '.join(map(str,df.columns))+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(val(x) for x in r)+' |' for r in df.itertuples(index=False,name=None))
def top(name,n=8):return mdtable(read(name),n)
textq=S['文本质量'];delay=S['公开滞后_非负'];diff=S['处罚表差额']
paragraphs=[]
def section(title,body):paragraphs.append((title,body))
section('数据范围、统计单位与阅读口径',f'''本次读取11月6日三份工作簿的数据工作表。行政处罚保留清单为{S['处罚保留']['行数']:,}行、11字段，裁判保留清单为{S['裁判保留']['行数']:,}行、10字段，处罚清洗表为{S['处罚清洗']['行数']:,}行、13字段，共34个原始字段逐一统计。原文件摘要页、图示页不作为新增案件。

统计单位主要为记录行，另提供规范化案号及处罚文号主体键的重复敏感性结果。裁判案号规范化后为{S['裁判案号数']:,}个。跨表清洗主体类型与措施标签仅用于清洗表自身分母。日期从原字段解析，NULL、未知、未公开等标记按缺失处理。地区由原始地域归并为地市，不能把法院所在地当作违法发生地。

本轮分析覆盖Excel已有信息，并未重新通读全部原始裁判DOC。司法理由、申请事项、违法事实等不在新版裁判Excel字段中的内容，不从案件名称推断。公开记录数量受采集、筛选和公开范围影响。''')
section('主要发现',f'''处罚与裁判的年度和地区构成差异明显，两个样本的分母与覆盖范围应分别报告。行政处罚当前主要窗口为2019年以后，司法记录主要集中于2017—2020年。逐年数量变化可描述公开样本构成，无法单独衡量真实违法发生或执法绩效。

处罚保留清单和清洗表净差{diff['净差额']}行。按标题中平台ID核对，保留表有{diff['保留表未出现于清洗表行数']}行在清洗表未找到相同平台键，清洗表有{diff['清洗表未出现于保留表行数']}行在保留表未找到。净差额须结合逐键表和共同字段变化核查。

司法结果按原表标签统计，“准予执行”5,446行，“不准予执行”1,887行，“驳回执行申请”3,466行。后两类占47.8%，有足够数量开展分层描述，但标签含义与原文一致性仍需核验。驳回和不准予应分别展示。

处罚文本质量诊断发现，{textq['事由仅依据候选']:,}行处罚事由满足“主要为处罚依据”的规则，{textq['结果占位说明']:,}行处罚结果带占位说明，{textq['文号字段污染']:,}行处罚文号串入主体、处罚名称或信用代码字段词。内容与结果规范化后相同的有{textq['内容与结果一致']:,}行。字段填满不能代替事实信息完整。

公开滞后按非负且可计算的{delay.get('有效数',0):,}行统计，中位数{delay.get('中位数',0):,.0f}天、P95为{delay.get('P95',0):,.0f}天。具体异常及缺失日期均保留回查行号。''')
section('年度、月度、季度及日期集中情况','处罚与裁判按各自业务日期统计。提供年度、月份、季度、星期、逐年月频数以及年份—月份交叉表。月份合并分布受各年份样本量和不完整年度影响，因此不能直接解释为季节规律。\n\n'+top('03_处罚_年份分布',15)+'\n\n'+top('03_裁判_年份分布',15))
section('地区分布、覆盖与集中度','保留原始县市区名称分布，同时归并地市。覆盖表中的0表示当前记录集中没有观测，不证明真实零处罚或零司法案件。法院地域、机构地域和违法地址需要在正式研究中区别。\n\n'+top('03_处罚_地市分布',22)+'\n\n'+top('03_裁判_地市分布',23)+'\n\n地区集中度采用样本份额平方和HHI以及前一、前三地区占比，取决于公开样本覆盖。\n\n'+mdtable(pd.DataFrame([{'数据':k,**S[k+'地区集中度']} for k in ['处罚','裁判']]),10))
section('法院、法院层级与裁判结果','法院名称只删除空格和广东省前缀，保留不同法院。广州铁路运输法院等跨区域管辖机构的案件数不能直接归于法院所在城市的违法数量。法院分布和法院—结果交叉表用于描述审查样本构成。\n\n'+top('05_裁判_法院分布',20)+'\n\n'+top('05_裁判_结果分布',12)+'\n\n同时提供年份、地市、主体类型、法院层级与结果交叉表。涉及少量记录的法院或地区，其结果占比容易波动，描述时保留样本量。')
section('主体结构、匿名化与多记录主体','司法主体类型使用原表标签，处罚主体类型使用摸底清洗表原有标签，二者类别体系不同。清洗表自然人占比以12,461行为分母。\n\n'+top('05_裁判_主体类型',10)+'\n\n'+top('07_清洗处罚_主体分布',10)+'\n\n同名主体表按规范化名称统计记录数、涉及年份和地市，匿名化名称可能对应不同主体，同名多记录不能直接认定为再次违法。类型和主体名称需抽查脱敏、简称及多人共同主体的影响。')
section('处罚机关、处罚类别与措施组合','处罚机关、原始处罚类别均保留完整频数，机关年度与地域交叉表展示样本来源集中。机关更名未自动合并，以保留可追踪的机构口径。处罚措施从类别、内容、结果三个字段合并识别，同一记录同一措施计一次。\n\n'+top('07_处罚_机关分布',15)+'\n\n'+top('12_处罚措施组合分布',15)+'\n\n逐措施表、多措施共现表以及年度和地域交叉表详见CSV。标签可能包含“申请拆除”等语义，正式结论应核实是否为实际处罚措施。')
section('违法事实、用途、地类与法规提及','用途和地类按处罚事由关键词作多标签提及统计，同一记录可以涉及多种用途或地类。“未识别”保留为独立组。耕地、农用地、基本农田具有语义重叠，统计项不能相加作为总案件数。\n\n'+top('12_用途提及组合逐标签频数',12)+'\n\n'+top('12_地类提及组合逐标签频数',12)+'\n\n法规仅提取书名号内名称并按每记录去重。同一法律的空格、版本及简称可能形成多个名称，提供原文频数供标准化，条文提及不能直接当作违法行为分类。\n\n'+top('11_处罚法规提及频数',12))
section('面积与罚款金额的可提取性','金额和面积原本未设独立数值列，本轮仅提取有阿拉伯数字和明确单位的候选。金额限于处罚结果里靠近“罚款”的表达，并排除部分每平方米单价；面积来自处罚事由，公顷和亩统一换算平方米。上下文证据和源Excel行号保存于候选明细。\n\n一份记录可能包含非法总面积、不同地类面积或多项金额，以下统计采用“单记录候选最大值”，避免简单求和造成重复。该值仍可能是分项数、建筑面积或其他表述，不等同正式违法面积和最终罚款。中文大写数值和无单位表达本轮未抽取。\n\n'+mdtable(pd.DataFrame([{'指标':k,**v} for k,v in S['数量候选'].items()]),10)+'\n\n提供逐年数量候选覆盖、均值、中位数、极值和最大30条记录作为复核入口。未输出全样本罚款或涉地面积总额。')
section('公开日期、滞后与信息缺失','公开日期缺失率、文号缺失率按裁判年份计算，同时提供裁判年份—公开年份交叉表，避免把同批公开理解为同批裁判。公开滞后负值单列异常。\n\n'+top('15_裁判年度信息覆盖',15)+'\n\n'+top('10_公开滞后分档',12))
section('重复记录、字段冲突与两份处罚表的差额','重复案号以全半角、空白、括号规范化后相同为准。相同案号可能是同裁判副本或元数据冲突，未自动删除。处罚键使用文号、主体和处罚机关组合，仍可能受文号字段污染和匿名化影响。\n\n'+top('08_重复键汇总',10)+'\n\n重复案号的结果、法院和日期冲突详见08组统计表。16组给出去重首行后的结果敏感性，仅用于衡量重复对分布的影响。09组逐键核对处罚表差额及共同字段变化，不能仅凭净差额断言清洗删除原因。')
section('需要优先回查的具体问题',f'''51组重复司法案号中，{Q['重复案号结果冲突组数']}组结果标签不一致，{Q['重复案号日期冲突组数']}组裁判日期不一致。这些冲突会影响结果分布和年度统计，应回到相同案号的原文逐组核对。

主体字段有{Q['主体字段串入其他信息候选数']}行出现违法条款、法律依据或信用代码等字段词。主体文本统计和同名重复主体统计可能受此影响。

处罚保留表与清洗表相同平台ID的记录中，有{Q['跨表归并地市不一致行数']}行归并后的地市不一致。保留表归并后覆盖12个地市，清洗表显示13个地市，新增出现深圳1行。两表间地市重分配需查看20_跨表归并地市不一致.csv，不能将新增地市视为独立新增采集覆盖。

罚款候选极值在保留表Excel第11325行，原文写作“罚款119325.9万元”，按原单位换算为11.93亿元。这是本轮最大候选值，需核对原始公开记录的金额和单位，当前未擅自更正。面积最大候选同样可能涉及分项、文书复述或单位问题，保留上下文供复核。

公开日期中出现早于裁判的异常值，负值未纳入非负滞后描述。主体、文号、日期和金额问题均附来源Excel行号。''')
section('行政处罚与司法裁判的对照','两类样本的主体类别、地区、年份和数量分布均受来源和筛选差异影响。跨表比较使用原始数量及各表内比例。复用前轮文号规则候选，仅展示候选关联与裁判结果、年份、地域的构成，未重新确认事件链接。\n\n'+top('17_关联候选_方法',10)+'\n\n候选命中数不能作真实司法进入比例，未匹配记录可能是时间错位、文号缺失、匿名化或来源覆盖不足。')
section('逐字段完整画像','下表覆盖全部34个原始字段。高基数字段也提供完整取值频数CSV，HTML每个字段附前10取值。有效率仅扣除空值和缺失标记，文本信息质量见前述诊断。\n\n'+mdtable(profile[['数据表','字段','有效行数','缺失或缺失标记数','有效率','不同原始取值数','中位长度','P95长度','乱码行数','匿名化标记行数']],40))
section('可复查资料及计算说明','统计表目录保存所有分布、交叉表、异常、重复与文本候选明细。源Excel行号从2开始，表头占第1行。普通频数以对应数据表的记录行数为基础。12组逐标签频数的占比采用13,305条处罚记录为分母，多标签比例可合计超过100%。\n\n原始输入为【1106】广东省土地违法行政处罚保留清单(3).xlsx的最终保留、【1106】广东省土地违法裁判文书(3).xlsx的最终保留、【1106】行政处罚数据初步摸底(3).xlsx的清洗后数据。文件SHA256与统计摘要一起保存。派生地区映射借用本地土地覆盖包区县表及少量历史名称映射，历史边界未经全面审计。\n\n按scripts/describe_cases_1106.py、scripts/describe_supplement_1106.py、scripts/render_description_1106.py顺序复跑。未新增外部案件，规则标签和数量候选未经随机人工准确率评估。')
# Markdown report with relative figure links for folder-local reading.
md='# 裁判文书与行政处罚全字段描述性分析\n\n2026年11月6日\n\n'
for title,body in paragraphs:md+='## '+title+'\n\n'+body+'\n\n'
md+='## 图表\n\n'+''.join('### '+title+'\n\n!['+title+'](图表/'+name+'.png)\n\n' for name,title in plots)
(OUT/'描述性分析报告.md').write_text(md,encoding='utf-8')
# The HTML is fully offline and embeds every chart. User-controlled source text is escaped.
def basic_md(body):
    lines=body.splitlines();parts=[];tab=[]
    def flush():
        if not tab:return
        rows=[l for l in tab if not re.match(r'^\|[\s|:-]+\|$',l)]
        for i,l in enumerate(rows):
            cells=l.strip('|').split('|');tag='th' if i==0 else 'td';parts.append('<tr>'+''.join(f'<{tag}>'+html.escape(v.strip())+f'</{tag}>' for v in cells)+'</tr>')
        tab.clear()
    for line in lines:
        if line.startswith('|'):
            if not tab:parts.append('<div class="table"><table>')
            tab.append(line)
        else:
            if tab:flush();parts.append('</table></div>')
            if line.strip():parts.append('<p>'+html.escape(line)+'</p>')
    if tab:flush();parts.append('</table></div>')
    return ''.join(parts)
nav=''.join(f'<a href="#s{i}">{html.escape(title)}</a>' for i,(title,_) in enumerate(paragraphs))
body=''.join(f'<section id="s{i}"><h2>{html.escape(title)}</h2>{basic_md(b)}</section>' for i,(title,b) in enumerate(paragraphs))
fields=''
for _,r in profile.iterrows():
    d=freq[(freq['数据表']==r['数据表'])&(freq['字段']==r['字段'])].head(10).copy()
    d['字段取值']=d['字段取值'].map(lambda v:str(v)[:500])
    fields+='<details><summary>'+html.escape(r['数据表']+' · '+r['字段'])+'</summary>'+d[['字段取值','次数','占全部记录比例']].to_html(index=False,escape=True,border=0)+'</details>'
images=''.join('<figure><img alt="'+html.escape(title)+'" src="data:image/png;base64,'+base64.b64encode((FIG/(name+'.png')).read_bytes()).decode()+'"><figcaption>'+html.escape(title)+'</figcaption></figure>' for name,title in plots)
css='body{font:16px/1.8 "Microsoft YaHei",sans-serif;color:#26364b;background:#f4f6f9;margin:0}main{max-width:1120px;margin:40px auto;background:white;padding:42px}h1{font-size:30px}h2{font-size:23px;margin-top:40px;color:#24486d}nav{display:flex;gap:8px;flex-wrap:wrap}nav a{color:#315a85;font-size:13px;background:#edf2f8;padding:4px 8px;text-decoration:none}.table{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px;margin:16px 0}th,td{padding:8px 10px;text-align:left;border-bottom:1px solid #dfe5ed;vertical-align:top}th{background:#e9eff7;white-space:nowrap}td{max-width:600px;overflow-wrap:anywhere}figure{margin:25px 0}img{max-width:100%;height:auto}figcaption{font-size:13px;color:#617187}details{border-top:1px solid #dfe5ed;padding:10px}summary{cursor:pointer}section{scroll-margin-top:20px}@media print{main{margin:0;padding:10px}nav{display:none}section{break-inside:auto}figure{break-inside:avoid}}'
(OUT/'描述性分析报告.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>裁判与处罚描述性分析</title><style>'+css+'</style><main><h1>裁判文书与行政处罚全字段描述性分析</h1><p>2026年11月6日 · 原始34字段 · 记录分布、交叉比较和信息质量</p><nav>'+nav+'</nav>'+body+'<h2>逐字段高频取值</h2>'+fields+'<h2>图表</h2>'+images+'</main></html>',encoding='utf-8')
with zipfile.ZipFile(OUT/'描述性统计明细表.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in T.glob('*.csv'):z.write(p,'统计表/'+p.name)
print('tables',len(list(T.glob('*.csv'))),'plots',len(plots),'fields',len(profile))
