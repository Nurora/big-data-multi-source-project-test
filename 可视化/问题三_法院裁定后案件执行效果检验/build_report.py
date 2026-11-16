"""由最终结果生成问题三实验报告 DOCX 和 Markdown。"""
from pathlib import Path
import csv
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题三"
OUT=ROOT/'docs';FIG=ROOT/'visualization/figures'
rows=list(csv.DictReader((ROOT/'data/integrated/逐案跨源整改核查.csv').open(encoding='utf-8-sig')))
doc=Document();sec=doc.sections[0];sec.page_width=Cm(21);sec.page_height=Cm(29.7);sec.top_margin=Cm(2);sec.bottom_margin=Cm(2);sec.left_margin=Cm(2.2);sec.right_margin=Cm(2.2)
for name in ['Normal','Title','Subtitle','Heading 1','Heading 2']:
    s=doc.styles[name];s.font.name='宋体';s._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体');s.font.color.rgb=RGBColor(0,0,0)
normal=doc.styles['Normal'];normal.font.size=Pt(10.5);normal.paragraph_format.line_spacing=1.25;normal.paragraph_format.space_after=Pt(6)
for name,size in [('Title',22),('Heading 1',15),('Heading 2',12)]:
    s=doc.styles[name];s.font.name='黑体';s._element.rPr.rFonts.set(qn('w:eastAsia'),'黑体');s.font.size=Pt(size);s.paragraph_format.space_after=Pt(9);s.paragraph_format.space_before=Pt(8)
md=[]
def h(text,level=1):doc.add_heading(text,level);md.append('#'*(level+1)+' '+text+'\n')
def p(text,bold=False):
    para=doc.add_paragraph();run=para.add_run(text);run.bold=bold;md.append(text+'\n');return para
def table(headers,data,widths=None):
    t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    if widths:
        for col,w in zip(t.columns,widths):col.width=Cm(w)
    for c,text in zip(t.rows[0].cells,headers):c.text=str(text)
    prop=t.rows[0]._tr.get_or_add_trPr();repeat=OxmlElement('w:tblHeader');prop.append(repeat)
    for vals in data:
        for c,text in zip(t.add_row().cells,vals):c.text=str(text)
    for rr,row in enumerate(t.rows):
        trpr=row._tr.get_or_add_trPr();cant=OxmlElement('w:cantSplit');trpr.append(cant)
        for cc,c in enumerate(row.cells):
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if widths:c.width=Cm(widths[cc])
            pr=c._tc.get_or_add_tcPr();borders=OxmlElement('w:tcBorders')
            for edge in ['top','left','bottom','right']:
                el=OxmlElement('w:'+edge);el.set(qn('w:val'),'single');el.set(qn('w:sz'),'4');el.set(qn('w:color'),'D9D9D9');borders.append(el)
            pr.append(borders);shade=OxmlElement('w:shd');shade.set(qn('w:fill'),'E8EDF2' if rr==0 else 'F6F8FA' if rr%2 else 'FFFFFF');pr.append(shade)
            for para in c.paragraphs:
                para.paragraph_format.space_after=Pt(4);para.paragraph_format.space_before=Pt(4);para.paragraph_format.line_spacing=1.1
                for run in para.runs:run.font.size=Pt(9);run.bold=rr==0
    doc.add_paragraph().paragraph_format.space_after=Pt(0)
    md.append('| '+' | '.join(headers)+' |\n|'+ '|'.join(['---']*len(headers))+'|\n'+'\n'.join('| '+' | '.join(str(x) for x in row)+' |' for row in data)+'\n')
def image(name,caption,width=16):
    para=doc.add_paragraph();para.alignment=WD_ALIGN_PARAGRAPH.CENTER;para.add_run().add_picture(str(FIG/name),width=Cm(width));para.paragraph_format.space_after=Pt(3)
    c=doc.add_paragraph(caption);c.alignment=WD_ALIGN_PARAGRAPH.CENTER;c.paragraph_format.space_after=Pt(8)
    for run in c.runs:run.font.size=Pt(9)
    md.append(f'![{caption}](../visualization/figures/{name})\n')
def page():doc.add_page_break()

doc.add_paragraph('佛山违法占地地块整改遥感核查',style='Title');md.append('# 佛山违法占地地块整改遥感核查\n')
p('问题三实验报告  |  Sentinel 2与CLCD跨源分析  |  2026年11月12日')
h('摘要')
p('本实验针对佛山市禅城区、三水区违法占地处罚记录，将先前遥感核查的人工判读与同期CLCD土地覆盖相结合，检查拆除线索、周边新增建设和不透水面响应。23条记录去重后对应22个地点，保留44期Sentinel-2裁片与2016—2021年CLCD样本窗口，完成记录清洗、实际影像年份匹配、空间网格对齐和逐案变化统计。')
p('原报告的唯一地点分类为疑似拆除5处、未见明显变化15处、疑似新增1处、水体干扰1处。跨源分析显示，5处疑似拆除中，#8监测圆建成候选净减4,000平方米，另4处净增；5处均未见CLCD不透水面减少。结果支持将#8作为拆除清理线索较明确的地点，将其余4处作为局部拆除与周边新增并存的复核对象，并将#19列为新增建设核查重点。总体上，研究形成了可追溯的整改线索清单，未把地表变化直接等同于案件履行完成。')
h('一 研究问题')
p('处罚作出后，涉案地点附近是否出现拆除或场地清理迹象？这些变化是否伴随新的建设活动？CLCD能否从地表覆盖角度补充解释原目视结论？本实验以可观察的空间变化回答整改问题，区分建筑拆除、地表去硬化和案件履行三个层次。')
h('二 数据构成')
table(['资料','主要内容','本实验保留'],[
['广东建设用地数据.zip','1990—2025年CLCD及统计表','2016—2021年样本区原网格窗口'],
['非法违规建筑影像判读.zip','原报告、指标、裁片与对比图','共同内容核验，避免重复计入'],
['非法违规建筑影像判读(1).zip','上述资料及额外SAFE文件','44期唯一裁片、场景索引、报告和指标']], [4.7,5.4,6.1])

page();h('三 数据采集与来源追踪')
p('本轮采集入口为三个本地ZIP，不重新请求在线地理编码或遥感平台。先逐项记录包名、成员路径、字节数和CRC32，再计算源ZIP及保留文件的SHA256。两份影像包共有301个文件，按解压内容逐一比较完全一致；大包共396个文件，其中额外95个文件含2023年SAFE资料，与原核查时段无关，未纳入样本。')
p('先前实验报告记载，地址通过百度地理编码及方向偏移定位，建立200米缓冲区；以处罚时点和约一年后为两个目标日期，在±90天窗口内按云量与日期差选择影像。原研究称2017年后主要使用S2_SR_HARMONIZED，2016年使用L1C，并有Dynamic World辅助信息。本轮仅使用已提供的裁片和指标表，不另引入Dynamic World栅格；原研究的候选87景、最少21景等信息仅作为既有选片记录引用。')
p('CLCD按包内说明来自武汉大学杨杰、黄昕团队，说明记载Zenodo记录18180184、v1.0.5和CC BY 4.0许可。本实验保留该来源说明，未联网另行核验版本。编码8代表不透水面，作为建设地表的观测代理；没有使用原初步分析表提出的建设用地当量换算。')
h('四 数据清洗与样本抽取')
table(['处理环节','规则','结果'],[
['记录标准化','统一原编号、位置、日期、人工判读和重复标记','保留23条追踪记录'],
['同址去重','#3/#4位置及前后影像ID相同','22个唯一地点，删除#4重复影像副本'],
['影像抽样','每个唯一地点保留前后两期','44个六波段裁片及场景索引'],
['CLCD抽样','覆盖所有裁片并外扩2像元的原网格窗口','6期窗口，无重投影和地类修改'],
['质量筛选','波段正值和有限性、云掩膜、前后共同有效范围','有效与非建成像元分开处理']], [3.0,8.0,5.2])
p('#20和#21虽有重合监测范围，但处罚记录不同，分别展示，不合计其面积。原包没有处罚宗地或原始缓冲区矢量，本轮采用裁片几何中心重建监测圆，保留原编号对应关系和推定中心元数据。原报告自述定位精度约50—200米，此误差在后续解释中保留。')

page();h('五 跨源关联与变化分析方法')
h('空间和时间对齐',2)
p('Sentinel-2裁片为WGS84 UTM 49N投影（EPSG:32649）、10米网格。CLCD为WGS84 Albers投影、30米分类，本实验以最近邻方法变换到裁片网格，保证分类编码不被插值。两期裁片须具有相同网格和尺寸；没有进行控制点几何配准。CLCD年份按实际选中影像日期匹配，而非按处罚或目标核查日期匹配。')
h('建成候选提取',2)
p('按波段名称读取B02、B03、B04、B08、B11。有效观测要求五个波段均为有限正值；2017年及之后排除SCL类别0、1、3、8、9、10、11，2016年按原L1C口径不采用像元SCL筛选。采用以下指数和阈值：')
p('NDBI = (B11 − B08) / (B11 + B08)\nNDVI = (B08 − B04) / (B08 + B04)\nMNDWI = (B03 − B11) / (B03 + B11)\n建成候选：NDBI > 0，NDVI < 0.3，MNDWI < 0。')
p('阈值识别的是建成候选像元，并非建筑物轮廓。计算范围为半径200米监测圆与前后两期有效观测的交集，CLCD编码0不参加统计。原人工判读作为独立字段保留，没有用本轮面积统计改写。')
h('状态相交与跨期转移',2)
p('每期划分共同建成、仅S2建成、仅CLCD不透水、共同非建成四种状态。跨期中，S2前非建成后建成记新增，前建成后非建成记减少；CLCD以编码8的进入和退出定义新增与减少。净变化为新增减去减少，面积为10米对照网格像元数乘100平方米。')
p('对S2新增和减少像元分别关联CLCD前后状态，区分两源同步变化、CLCD持续不透水、CLCD持续非不透水和反向变化。只有同一位置两源均从不透水转为非不透水或从建成转为非建成，才列作同步减少；后期CLCD仍为不透水本身不能说明建筑未拆除。')
h('属性关联与核验',2)
p('原序号、位置和实际日期将人工判读、裁片和CLCD年份连接为逐案证据表。研究同时计算150、200、250米范围的差异比例，用于识别范围敏感性。核验包括23到22去重、四类状态面积守恒、新增和减少各分组守恒，以及新项目与先前结果的逐条一致性。')

page();h('六 整改迹象总体分布')
image('图1_整改迹象分类.png','图1 22个唯一地点的原目视整改迹象分类',15.5)
p('原报告共有6条疑似拆除记录，包含同址重复#3/#4，去重后为5个地点，占22.7%；其余为未见明显变化15处（68.2%）、疑似新增1处（4.5%）、水体干扰1处（4.5%）。本轮分类统计与原报告一致，原因是原人工标签被作为输入保留，统计一致不能视为一次独立的目视验证。')
table(['类别','编号','研究含义'],[
['疑似拆除','#3、#7、#8、#20、#21','存在目视拆除或清理线索，继续进行空间对照'],
['疑似新增','#19','出现新增建设线索，检查其变化位置和覆盖响应'],
['水体干扰','#17','水位或水体变化影响阈值结果，单独列出'],
['未见明显变化','其余15个地点','原目视未见明显变化，不由此判定未整改']], [2.5,6.3,7.4])
p('本批地点的整改表现并不一致：少数地点出现拆除清理线索，多数地点尚未形成明确的目视变化结论。图1回答的是整改迹象分布，不计算案件解决率。')

page();h('七 逐地点新增与减少')
image('图2_逐地点增减变化.png','图2 同一监测范围内的S2新增减少和CLCD净变化',16.1)
p('5处疑似拆除中，#8的S2减少候选为14,300平方米、新增为10,300平方米，净减4,000平方米；#3、#7、#20和#21则分别净增1,700、3,100、5,900和11,900平方米。拆除线索与监测圆净增可以并存，因为二者观察对象分别是局部目标和整个周边范围。')
p('22地点中，13个CLCD净变化为零，5个地点的两源净变化方向相反。CLCD在全部地点的本次共同有效范围内未出现不透水面减少。两源变化响应存在差异，不能用一个代理指标直接替代整改判断。')

page();h('八 典型地点空间核查')
image('图3_典型地点空间转移_1.png','图3a #8 #3 #7 #20的前后影像与覆盖转移',15.9)
p('#8在原报告中被识别为场地清理信号较强的地点；本轮同范围净减信号与其方向相符。#3、#7、#20可见新增和减少候选分布在不同位置，因此应定位变化斑块后解释，不能只用监测圆净值替代局部观察。')

page();h('典型地点空间核查续',1)
image('图3_典型地点空间转移_2.png','图3b #21 #19 #17的前后影像与覆盖转移',15.9)
p('#21同样保留原疑似拆除标签，监测圆新增候选较多。#19在2018年10月27日至2019年10月2日期间新增候选17,000平方米、减少6,800平方米，净增10,200平方米；其中8,500平方米为CLCD前后持续不透水，另8,500平方米持续非不透水，没有同位置的CLCD同步新增。该地点适合列为新增建设复核重点，而不是把17,000平方米直接认定为新增违法面积。')
p('#17受水体变化影响，虽有阈值减少候选，但不能将其解释为拆除。图3统一采用前后共同有效范围，每个地点前后真彩色使用相同逐通道2%—98%拉伸，减少显示差异对对比的影响。')

page();h('九 逐案证据整合')
p('逐案证据矩阵把原目视结论与本轮数值结果并列，不以任一单项覆盖另一项。表1摘录5处疑似拆除和2处重点对照；全部22地点见图4及核心CSV。')
table(['编号','原目视初判','S2减少 m²','S2新增 m²','S2净变化 m²','CLCD减少 m²'],[[f"#{r['序号']}",r['初判类别'],f"{int(r['S2减少_m2']):,}",f"{int(r['S2新增_m2']):,}",f"{int(r['S2净变化_m2']):+,}",r['CLCD减少_m2']] for r in rows if int(r['序号']) in [3,7,8,20,21,19,17]],[1.2,3.2,2.9,2.9,3.0,3.0])
p('表1 重点地点跨源变化。所有面积均为推定200米圆的共同有效范围。')
h('两源互补得到的认识',2)
p('第一，原目视判读提供局部场景语义，S2像元转移提供变化位置和规模，CLCD补充地表覆盖背景。#8的目视清理与范围净减相互支持，是本批地点中拆除清理线索较明确的一个。')
p('第二，#3、#7、#20、#21应保留局部疑似拆除线索，同时记录监测范围内新增较多的事实。这说明整改核查需要把局部目标与周边变化分开，而不是在原标签与净变化之间简单二选一。')
p('第三，5处疑似拆除地点未见CLCD去硬化响应，说明本次没有观察到同步的地表覆盖退出。建筑拆除后仍可保留硬化地面，30米分类也可能无法识别小范围变化，因而该结果不否定拆楼，但不支持进一步推断土地已恢复。')
p('第四，#19提供新增建设线索，#17反映水体干扰；这两类地点应与疑似拆除分别处理。原报告的15处未见明显变化也不能被自动解释为整改失败。')
h('与先前实验的关系',2)
p('本实验继承先前实验的地点和人工初判，增加了同范围变化统计、CLCD覆盖响应和完整来源追踪。原AOI和原处理脚本未提供，重建范围与掩膜实现会影响面积，因此本轮不声称精确复现原表面积。最终跨期比较统一采用共同有效像元，原表数值另行保留用于追踪。')

page();h('逐地点整改核查矩阵',1)
ordered=[]
for label in ['疑似已拆除','未发现明显变化','疑似新增建设','无法判定（水体/水位变化）']:
    ordered.extend(r for r in rows if r['原人工判读']==label)
table(['地点','目视初判','S2净变化 m²','CLCD减少 m²','跨源核查分类'],[[f"#{r['序号']} {r['简称']}",r['初判类别'],f"{int(r['S2净变化_m2']):+,}",r['CLCD减少_m2'],r['跨源核查结果']] for r in ordered],[3.3,2.3,2.2,2.2,6.2])
p('图4 逐地点证据矩阵的报告排版版。对应完整数值与新增、减少分量见核心结果表及独立矩阵图。分类结合原初判和监测圆变化，不表示案件结案状态。')

page();h('十 项目组织与可复现性')
p('项目按数据来源、清洗、融合、分析、绘图和文档分层保存。原始数据体量较大，因此提交原网格样本、完整成员索引与源文件校验值，无需重复保存全省36年栅格及额外2023年资料。')
tree='问题三/\n├─ data/raw/          原始样本 参考报告 指标 索引与校验\n├─ data/cleaned/      标准化记录 唯一地点 对齐栅格\n├─ data/integrated/   逐案结果 逐期关联 敏感性 统计\n├─ crawler/           本地ZIP索引与抽样代码\n├─ processing/        清洗 去重 分类和空间时间对齐\n├─ analysis/          变化分析与一致性核验\n├─ visualization/     绘图代码与figures图表\n├─ docs/              实验报告 字段说明与成果校验\n├─ data_sources.md    来源与provenance\n├─ AI_USAGE.md        AI使用与核验记录\n├─ requirements.txt   依赖版本\n└─ run.py             一键复现入口'
para=p(tree)
for run in para.runs:run.font.size=Pt(9)
h('复现步骤',2)
p('Python 3.12环境下，在项目根目录执行 python -m pip install -r requirements.txt，再执行 python run.py，即可从已保留样本重新生成标准化记录、空间对齐、分析表和四类图。若从源ZIP重建样本，执行 python run.py --extract --source-dir 原始资料目录。全部脚本以项目自身路径定位，不依赖旧outputs目录或旧绘图代码。')
table(['环节','输出'],[['清洗','23条追踪记录 22个唯一地点 22个六波段对齐栅格'],['融合分析','22行逐案结果 44行逐期关联 132行范围敏感性'],['可视化','四类图 共5幅PNG和5幅SVG'],['校验','源ZIP与成员索引 SHA256及面积守恒记录']], [3.2,13.0])
p('本项目完整复算后，22地点S2和CLCD新增、减少及净变化共六项主要指标均与整理前结果逐条一致。图表去除对话式解释，只保留结果标题、图例、单位、日期与必要坐标信息。')

page();h('十一 结论与局限')
p('本批22个地点显示整改迹象具有差异：5处保留疑似拆除或场地清理线索，15处目视未见明显变化，1处疑似新增建设，1处因水体干扰无法判断。#8同时具有原目视清理信号和监测圆净减信号，整改线索较明确；另外4处疑似拆除地点应结合减少斑块与周边新增继续复核。CLCD未显示这些地点同步去硬化，因此现有结果支持拆除线索筛查，不支持推断土地已恢复或案件已履行完毕。')
p('两源数据发挥了不同作用：S2突出短时段、局部建成候选变化，CLCD提供年度地表硬化背景。跨源分析的价值在于补充原目视判断的空间与覆盖证据，识别局部变化和范围变化之间的差别，而不是要求两源必须给出相同变化面积。')
p('主要局限包括：缺少处罚宗地与建筑边界、地址定位误差约50—200米；未进行控制点几何配准；S2阈值会受裸地、季节和水位影响；CLCD 30米分类与单景10米阈值提取在时点与尺度上不同；原报告也指出部分选片距目标日期较远。150—250米范围试验中，#15前期差异比例波动约13.8个百分点，#23后期约12.7个百分点，表明部分地点结果受范围选择影响。')
p('研究观察截至各地点后期影像，而非2026年现状。罚款缴纳、手续补办等履行方式无法从地表变化直接识别。基于现有材料可以明确报告整改线索和观测分歧，但不计算实际案件解决率。')
h('十二 AI使用与实验反思')
p('AI辅助编写数据提取、清洗、栅格分析、绘图和报告代码，并协助整理实验表述。原人工标签来自先前报告与指标表，未由本轮AI重新赋值。分析过程中纠正了两项容易混淆的处理：同址重复记录不重复计入；后期CLCD为不透水面不自动归为两源同步新增。最终同时保留原初判、定量结果和覆盖响应。')
p('实验表明，自动统计能提高处理一致性，但仍需区分观测代理与研究结论。通过源文件校验、可复算项目结构、面积守恒和图表检查，减少资料重复、口径混用和无依据推断。AI使用细节和方法修正分别记录在AI_USAGE.md和字段说明中。')
h('资料依据',2)
p('1 佛山市23处涉嫌违法占地地块拆除情况遥感核查报告，用户提供的影像ZIP内文档。\n2 变化检测指标.xlsx，原人工复核与选片指标。\n3 原始影像说明，用户提供的广东建设用地数据ZIP。\n4 本项目逐案跨源整改核查.csv、逐期空间关联.csv及监测范围敏感性.csv。')
for style in doc.styles:
    for border in list(style._element.iter(qn('w:pBdr'))):border.getparent().remove(border)
for para in doc.paragraphs:
    for border in list(para._p.iter(qn('w:pBdr'))):border.getparent().remove(border)
doc.core_properties.title='佛山违法占地地块整改遥感核查';doc.core_properties.subject='问题三实验报告';doc.core_properties.author='';doc.core_properties.comments=''
doc.save(OUT/'问题三实验报告.docx');(OUT/'问题三实验报告.md').write_text('\n'.join(md),encoding='utf-8')
print('已生成Word与Markdown实验报告。')
