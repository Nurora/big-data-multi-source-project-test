"""Additional corpus diagnostics, evidence review pack, and readable report."""
from __future__ import annotations
import collections as C,csv,datetime as dt,html,json,pathlib,re,statistics
ROOT=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
P=ROOT/'reports/裁判文书全量画像_20261028'
R=list(csv.DictReader((P/'全量特征表_规则候选.csv').open(encoding='utf-8-sig')))
D={d['id']:d for d in map(json.loads,(P/'清洗正文.jsonl').read_text('utf8').splitlines())}
E={d['id']:d for d in map(json.loads,(P/'证据片段.jsonl').read_text('utf8').splitlines())}
S=json.loads((P/'统计摘要.json').read_text('utf8'));N=len(R)
yes=lambda r,k:r[k]=='True'
pct=lambda n:f'{n/N*100:.1f}%'
def dump(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def table(header,rows):return '\n'.join(['|'+'|'.join(header)+'|','|'+'|'.join('---' for _ in header)+'|']+['|'+'|'.join(str(x).replace('|','／').replace('\n',' ') for x in row)+'|' for row in rows])
def csvout(n,rows):
    with (P/n).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

scope_issues={
 '44823601':'湖北武汉案件；正文有湖北法院、武汉机关及鄂案号，与深圳法院头部信息冲突，建议排除广东口径',
 '45514725':'江苏海安案件；正文有江苏法院、海安机关及苏案号，与中山法院头部信息冲突，建议排除广东口径',
 '67330980':'含土地与采矿双行为，但本次申请和裁定只处理地下热水采矿处罚事项二；建议排除纯土地执行口径',
}
for r in R:
    r['scope_audit']='建议暂排并复核' if r['id'] in scope_issues else '本次未发现上述范围冲突'
    r['scope_audit_note']=scope_issues.get(r['id'],'仍须保留规则标签的候选性质')
    if r['id'] in ('44823601','45514725'):r['court_city']='外省（元数据冲突）'
csvout('全量特征表_规则候选.csv',R)
eligible=[r for r in R if r['id'] not in scope_issues]
dump('范围冲突与建议纳入统计.json',{'original_documents':N,'issues':[{'id':i,'reason':v,'file':E[i]['file']} for i,v in scope_issues.items()],
 'provisionally_eligible_n':len(eligible),'provisionally_eligible_raw_bytes':sum(int(r['raw_bytes']) for r in eligible),
 'provisionally_eligible_subjects':dict(C.Counter(r['respondent_type_rule'] for r in eligible)),
 'provisionally_eligible_outcomes':dict(C.Counter(r['court_outcome_rule'] for r in eligible)),
 'provisionally_eligible_court_cities':dict(C.Counter(r['court_city'] for r in eligible).most_common()),
 'note':'No original file deleted; subsequent analyses should apply scope flag, not silently reuse old accepted catalog.'})
S['court_cities']=dict(C.Counter(r['court_city'] for r in R).most_common())
S['scope_audit_issues']=scope_issues
S['provisionally_eligible_n']=len(eligible)
dump('统计摘要.json',S)

# Extra diagnostics never turn a reference mention into a judicial fact.
corethemes={k:sum(bool(re.search(v,re.sub(r'\s','',d['core']))) for d in D.values()) for k,v in {
    '租赁出租':r'租赁|出租|承租|租用|租金|转租|租地',
    '损失停产搬迁':r'停产|停业|搬迁|经营损失|经济损失|损失赔偿|赔偿损失',
    '项目备案立项':r'立项|备案|招商引资|投资项目|重点项目|项目审批',
    '环评排污':r'环评|环境影响评价|排污许可|环保验收',
    '招聘就业':r'招聘|就业|失业|劳动合同|工资',
    '资产债务':r'抵押|破产|拍卖|债权|债务|借款|贷款',
}.items()}
roles=C.Counter(r['respondent_source'] for r in R)
company=[r for r in R if r['respondent_type_rule']=='企业或经营组织']
repeated=C.defaultdict(list)
for r in R:
    if r['respondents'] and not yes(r,'respondent_anonymized'):repeated[r['respondents']].append(r)
repeatrows=[{'respondent':k,'documents':len(v),'years':'；'.join(sorted({r['year'] for r in v})),'ids':'；'.join(r['id'] for r in v),'penalty_number_candidates':'；'.join(sorted({r['penalty_number_candidates'] for r in v if r['penalty_number_candidates']}))} for k,v in repeated.items() if len(v)>1]
repeatrows.sort(key=lambda r:(-r['documents'],r['respondent']));csvout('同名主体多文书候选.csv',repeatrows)
csvout('企业经营组织子样本.csv',company)
cross=[]
for y in sorted({r['year'] for r in R}):
    g=[r for r in R if r['year']==y]
    cross.append({'year':y,'documents':len(g),**dict(C.Counter(r['court_outcome_rule'] for r in g)),**{'subject_'+k:sum(r['respondent_type_rule']==k for r in g) for k in S['respondent_types']}})
dump('年份结果主体交叉.json',cross)
reasonpatterns={
 '送达催告线索':r'送达|催告|告知|听证',
 '事实证据线索':r'证据不足|事实不清|事实不楚|缺乏.{0,10}证据|未.{0,12}证据证明|证据.{0,8}不足',
 '主体认定线索':r'主体|当事人.{0,15}不一致|法定代表人.{0,30}被处罚',
 '执行权限或受理范围线索':r'强制执行权|自行.{0,10}(?:执行|实施)|不具备.{0,10}执行|不具有.{0,10}执行|不予受理|不受理|无权',
 '法律适用线索':r'适用法律.{0,8}错误|援引.{0,20}(?:删除|修改)|适用.{0,10}不当',
 '申请期限线索':r'超过.{0,15}期限|超过.{0,10}申请|申请.{0,10}逾期|申请期限',
 '补正实施材料线索':r'补正|实施预案|风险评估|实施主体',
}
negative=[r for r in R if r['court_outcome_rule']!='准予执行']
reasoncounts={k:sum(bool(re.search(p,re.sub(r'\s','',D[r['id']]['reasoning']))) for r in negative) for k,p in reasonpatterns.items()}
dump('补充诊断.json',{'full_core_theme_mentions_not_findings':corethemes,'party_extraction_basis':dict(roles),
 'company_documents':len(company),'company_unique_name_strings':len({r['respondents'] for r in company}),
 'company_documents_2018plus':sum(r['year']>='2018' for r in company),'company_documents_with_code':sum(bool(r['respondent_credit_codes']) for r in company),
 'company_documents_anonymized':sum(yes(r,'respondent_anonymized') for r in company),
 'multiple_document_name_groups':len(repeatrows),'documents_in_multiple_name_groups':sum(r['documents'] for r in repeatrows),
 'no_use_keyword':sum(not any(yes(r,k) for k in r if k.startswith('use_')) for r in R),
 'reason_mentions_in_611_nonfullapproval_documents_not_reason_attribution':reasoncounts,
 'case_number_duplicate_extras':sum(v-1 for v in C.Counter((r['court_body'],r['case_number']) for r in R).values()),
 '2018_2020_n':sum('2018'<=r['year']<='2020' for r in R)})

# Explicit human-read evidence checks from this session; not a random accuracy estimate.
review=[
 ('105405640','住宅/建房','事实记载住宅建设，支持用途线索'),
 ('90265617','住宅/建房','建房明确；旅游公路为相邻地物，不能据此认定旅游用途'),
 ('105377225','住宅/建房','明确建设房屋，未进一步确认自住或出租'),
 ('77219395','住宅/建房','明确建设房屋，不能推断家庭住房需求'),
 ('309815815','住宅/建房','记载耕地建房及罚款；不把法院准予视为已经拆除'),
 ('84190423','住宅/建房','记载建房和基础柱头'),
 ('75533087','宅基地转让','涉及宅基地转让，不等同住宅自建'),
 ('565178913','混合土地','房屋建设同时涉及宅基地与耕地'),
 ('311384388','厂房','主文申请事项明确厂房'),
 ('311384393','厂房','申请事项明确厂房，工业园区不是识别用途的唯一依据'),
 ('22624834','厂房','村委会建设工业厂房，不能把自然人/企业当全部违法主体'),
 ('554346559','厂房','厂房占地同时涉及公路用地、草地、有林地'),
 ('21242221','加工场','预制件加工场，现状建设用地，仍涉及未经批准'),
 ('56573881','混合土地','农用地、未利用地及建设用地混合，不可单一归类'),
 ('565839935','厂房','2009年建设，2024年立案；裁判年份不等于违法发生年份'),
 ('114004229','厂房','明确厂房；文中规划地类不等于土地现状'),
 ('89553652','农业用途误判','鱼塘为四至相邻地物，实际记载兴建住房'),
 ('550233581','养殖','明确林地搭棚养殖'),
 ('85469976','养殖','明确养猪场、猪舍'),
 ('550252656','养殖','明确看守房、铁棚从事养殖'),
 ('96794281','复合用途','房屋、道路、鱼塘混合占用林地，不是单一养殖用途'),
 ('561014817','养殖','申请事项明确鸡舍'),
 ('552437517','养殖','明确建设养殖场'),
 ('311384398','农业用途误判','旧猪场是地段名称，实际建设厂房'),
 ('41520813','旅游用途误判','篮球场是送达地址参照物'),
 ('21148969','旅游','明确旅游项目配套设施，且此前已拆除并缴款，申请仅退地'),
 ('111935428','旅游用途误判','球场是宗地名称参照，不能据此确认文体用途'),
 ('105390700','文体','明确建设篮球场，但设施农用地为现状地类不是实际农业用途'),
 ('105352400','文体','明确文化室和篮球场'),
 ('577107826','旅游用途误判','休闲园为相邻地物'),
 ('105310827','旅游','明确旅游配套停车场'),
 ('44905579','土地流转链','公开投标、亲属转让及出租均有记载，未办理建设用地审批'),
 ('18288531','租赁','明确厂房出租，存在土地权属认定与证据问题'),
 ('22962331','租赁','明确租用土地建设，未记载租赁民事赔偿'),
 ('579013267','租赁','租用林地建设车辆保管场并转让，不能推断已发生经营损失'),
 ('22963847','租赁','明确租用土地建设棚顶厂房'),
 ('315799657','经营后果','明确停产搬迁注销，但不能将所有后果归因为本次处罚'),
 ('115698395','不准予执行','处罚把法定代表人与村委会主体混同；并非认定没有违法占地'),
 ('37924235','不准予执行','送达程序及证据问题'),
 ('43322427','不准予执行','留置送达问题'),
 ('316783575','不准予执行','裁判认为援引已修改删除法条；只是本案裁判理由'),
 ('89333373','不准予执行','土地及规划处理衔接、执行权限问题'),
 ('78548839','不准予执行','遗漏其他使用主体，事实及证据问题'),
 ('317293620','部分准予','罚款准予，拆除事项因补正实施材料问题驳回'),
 ('43083092','部分准予','退地准予，没收事项驳回'),
 ('119139656','部分准予','罚款准予，没收事项驳回'),
 ('115113205','部分准予','罚款准予，其他事项不准予'),
 ('112185471','部分准予','罚款及加处罚款准予，其他申请驳回'),
 ('316079729','主体识别','正文名称被截短，但有企业信用代码；旧匿名化筛查不可用'),
 ('111936956','主体提取','被执行人标识位于审理经过，不能仅依当事人段'),
 ('44823601','范围冲突','武汉案件被广东法院元数据污染，建议暂排'),
 ('45514725','范围冲突','江苏案件被广东法院元数据污染，建议暂排'),
 ('67330980','范围冲突','此次执行仅为采矿事项，建议从土地执行口径暂排'),
]
reviewrows=[{'id':i,'topic':topic,'review_note':note,'file':E[i]['file']} for i,topic,note in review if i in E]
csvout('人工证据复核记录.csv',reviewrows)

lines=['# 现有3385份裁判文书：全量画像与拓展方向','',
'2026年10月28日。对象是当前“裁判文书”目录全部文件；原压缩包与历史处理目录不重复计数。原始文件只读，逐件重新解析并核对历史目录哈希。',
'', '## 先说结论','',
'这是一批以土地违法行政处罚非诉执行审查为主的公开裁定样本。它最厚的内容是自然人及村社主体、建房和不同非农用途、土地现状/规划表述、拆除退地恢复等处理事项及执行责任分配。它不能直接提供完整处罚总体、真实拆除结果、企业损失或就业变化。企业招聘、上市公司、文旅经营和资产处置目前均没有足够样本依据作为整批主线。','',
f'本次全量复核新发现3条范围冲突：44823601为湖北武汉案件，45514725为江苏海安案件，67330980本次只执行采矿处罚事项。原文件全部保留，特征表已有scope_audit标记。建议暂排后为{len(eligible)}份、{sum(int(r["raw_bytes"]) for r in eligible)/1e6:.2f}MB。以下以全部3385份说明现有材料结构；正式广东土地非诉分析应按范围标记过滤，分母及统计另见“范围冲突与建议纳入统计.json”。','',
'## 一 文件、年份与收集口径','',
table(['项目','结果'],[
 ['当前文件、成功解析',f'{N}份；无解析错误'],['原始文件大小',f"{S['raw_bytes']:,} bytes＝{S['raw_bytes']/1e6:.2f} MB＝{S['raw_bytes']/2**20:.2f} MiB"],
 ['重复检查',f"文件哈希重复{S['raw_hash_duplicate_extras']}份；清洗正文完全重复{S['core_hash_duplicate_extras']}份。不是近似模板去重结论"],
 ['2018年及之后',f"{S['2018_plus']['n']}份，{S['2018_plus']['raw_bytes']/1e6:.2f} MB"],
 ['清洗正文长度',f"中位数{S['core_chars']['median']}字；最短{S['core_chars']['min']}字，最长{S['core_chars']['max']}字（含标点，不是汉字净数）"],
 ['人工证据复核',f'{len(reviewrows)}条案件—主题检查，有针对性抽取；不是随机准确率评估'],
 ]),'',table(['裁判归年','份数','占全体'],[(y,n,pct(n)) for y,n in sorted(S['years'].items())]),'',
'2018—2020年合计2230份，占65.9%；2019—2020年合计1897份，占56.0%。后期少不能解释为违法下降。这里的年份沿用已核验目录的裁判归年，不等于处罚或违法发生年份；其中7份以案号辅助归年。部分元数据日期与正文落款不一致，应在时间研究前逐条核定。','',
'已知收集过程专门筛选了土地违法处罚非诉执行审查，排除了纯采矿、规划、征收交地等案件。当前看不到租赁赔偿、劳动争议或刑事案件，不等于现实中没有这些纠纷，而是这批资料的收集口径不覆盖。','',
'## 二 地区覆盖与代表性','',
table(['法院所在城市','文书数','占全体'],[(k,v,pct(v)) for k,v in S['court_cities'].items()]),'',
'法院城市来自正文法院名称并结合案号作映射，已将两条省份冲突标出，不能把它当成违法发生城市。中山931份，茂名508份、佛山398份，前三城市法院合计1837份，占54.3%。广州没有样本，深圳等城市极少，不适合直接做广东21市违法风险排名。跨区管辖真实存在：兴宁法院的文书可以审查丰顺、五华等地机关作出的处罚。必须另取涉案地址或处罚机关辖区。','',
'## 三 被执行主体与企业匹配条件','',
table(['规则分类','文书数','占全体'],[(k,v,pct(v)) for k,v in S['respondent_types'].items()]),'',
f"主体提取依据：当事人段{roles['当事人段']}份，正文角色标识{roles['正文角色标识']}份，标题补充候选{roles['标题补充候选']}份，未提取{roles['未提取']}份。类型是名称与组织代码辅助规则，并非工商核实。自然人共同被执行不意味着同一家庭。",'',
f"企业或经营组织子样本共{len(company)}份，{len({r['respondents'] for r in company})}个不同名称字符串；2018年后{sum(r['year']>='2018' for r in company)}份；{sum(bool(r['respondent_credit_codes']) for r in company)}份被执行人行中有信用代码候选，{sum(yes(r,'respondent_anonymized') for r in company)}份名称含匿名化标记。代码未做工商实体验证；相同简称、历史名称和分公司不能直接合并。",'',
'此前“正文含某…公司”的匿名化筛查容易命中推荐案例或地址。本次仅统计主体字段，旧数值不应再用于判断企业匹配可行性。村社参与也要分清角色：村社可能是被处罚人、原土地所有者、出租者，或只出现在退地对象及地址中。947份事实段提到村社集体，不等于947份村社违法。','',
'同名主体多文书候选见独立CSV。同名多份裁定可能是不同处罚、不同执行事项或重复申请，不能直接称“屡罚屡犯”。','',
'## 四 实际用途、地类与主题：必须以候选方式解读','',
'下表只数清洗后的事实段关键词提及；标签重叠，不能相加，也不能直接当作互斥用途分布。事实段包括申请人陈述及所引处罚内容，并不全是法院确认。未写用途不是未使用。','',
table(['用途/情境关键词','提及文书数'],[(k[4:],v) for k,v in S['bool_counts'].items() if k.startswith('use_')]),'',
f"{sum(not any(yes(r,k) for k in r if k.startswith('use_')) for r in R)}份没有命中上述用途词，不能强行分入住宅或工业。住宅标签包含建房、宅基地转让；厂房建设者也可能是个人或村委会。",'',
'复核发现：鱼塘可以只是四至地物；旧猪场可能是地段名而新建的是厂房；球场可以是送达地点参照。小类表中的农业、旅游等命中仍须逐条判断用途，不宜据其直接构建监督学习真值。已移除“鱼塘”和“设施农用地”等易混词的农业用途触发，但旧猪场等地名仍须人工排除。','',
table(['土地类型表述','事实段提及数'],[(k[5:],v) for k,v in S['bool_counts'].items() if k.startswith('land_')]),'',
'地类表述同时可能涉及现状、规划、混合地块及法条，不能相加为“耕地与林地占比”。建设用地482份并非无效样本：例如21242221记载建设用地上的加工场未经批准建设；56573881为农用地、未利用地和建设用地混合。不能把全部样本概括为只占耕地或林地。','',
table(['可扩展主题','事实段提及数'],[(k[6:],v) for k,v in S['bool_counts'].items() if k.startswith('theme_')]),'',
table(['扩大至清洗后完整正文的二次检索','提及数（不是事实认定）'],corethemes.items()),'',
'完整正文检索用于避免本院认为部分包含事实而被遗漏；也会命中法条或主体名称，不能替代逐案分类。经营损失、就业、融资、环评和项目备案在这批材料中没有形成足够内容。','',
'## 五 法院结果、事项与执行责任','',
table(['主文规则识别','份数','占全体'],[(k,v,pct(v)) for k,v in S['outcomes'].items()]),'',
'准予执行2774份（81.9%），不准予或驳回494份（14.6%），混合主文117份（3.5%）。混合主文可出现罚款准予而退地、拆除或没收事项驳回。分类单位为一份文书，不是一个处罚事项，不能据此计算拆除执行率。','',
table(['主文明确提及事项/责任','份数（可重叠）'],[(label,S['bool_counts'][key]) for label,key in [('拆除','decision_mentions_demolition'),('罚款','decision_mentions_fine'),('退还土地','decision_mentions_return'),('没收','decision_mentions_confiscation'),('恢复/复垦','decision_mentions_restoration'),('政府或管委会组织实施','decision_implementation_by_gov')]]),'',
'很多主文只写“准予执行某处罚决定”，未重复逐项列出。因此主文未命中罚款不意味着原处罚没有罚款。2166份主文涉及政府或管委会组织实施，说明执行分工是值得保留的分析维度；不等于这些文书对应的建筑已经拆除。','',
table(['611份非全部准予文书：理由段主题线索','命中数（有引用、可重叠，不是归因分类）'],reasoncounts.items()),'',
'复核的真实差异包括：115698395处罚对象与村委会法定代表人混同；37924235送达问题；78548839遗漏其他使用人；316783575法律适用问题；317293620缺少实施主体、风险评估及实施预案等材料。故不准予执行不能统一解释为处罚过重、法院保护企业或违法不存在。','',
'## 六 可提取字段与不能推断的指标','',
table(['字段/分析维度','当前支持程度','限制'],[
 ['法院、裁判年、主文','较好','仍需日期及标题匿名化核对'],
 ['被执行人及类型','较好，候选级','不能自动识别集体企业、国企及完整股权关系'],
 ['处罚文号','可生成候选','需规范括号、地名简称并复核；不保证对应独立公开处罚库'],
 ['处罚日期→裁判日期','可生成候选','同文有告知、处罚、催告多时点；不能把正则间隔称为执法效率'],
 ['违法发生时间','部分可取','早于处罚、裁判多年，不能用裁判年替代'],
 ['面积',f"{S['bool_counts']['area_mentioned']}份事实段出现数值面积",'同文反复、分地类、分栋、平方米/亩/公顷混用；本次不发布面积合计'],
 ['罚款',f"{S['bool_counts']['fine_amount_context_candidate']}份有罚款与数字邻近线索",'单价、总额、复垦费、加处罚款、已缴额须分开；本次不发布罚款合计'],
 ['镇级地点',f"{S['bool_counts']['town_location_candidate']}份有候选",'可能是机关地址、退地对象或四至；匿名地名不能用于地块定位'],
 ['实际履行、拆除、损失','明显不足','法院准予不是履行结果，赔偿主张不是实际赔偿'],
 ]),'',
'## 七 基于样本重新筛选拓展方向','',
table(['方向','这批文书的支撑','值得寻找的独立来源','当前判断'],[
 ['农村建房与集体土地使用/交易','自然人、建房、村社线索较厚','农村集体资产资源交易公告；村级工程招投标；人口住房及乡镇统计','与样本最贴近；交易与工程数据实际整包及200MB尚未核实'],
 ['非农使用情境与复垦/拆除实施需求','面积、恢复、退地、实施责任较厚','复垦拆除修复采购公告与合同；项目验收/绩效报告；地区财政及建设统计','可用地区×年份关联，但处罚和项目不可仅凭同地区认定因果或同一事件'],
 ['村社经营性资产及收益风险','集体被执行人、集体公司及少量出租转让链','集体厂房商铺交易；资产公开；经营组织登记；租赁合同民事裁判','可作较有社会经济含义的专题，必须补充民事样本与交易记录'],
 ['处罚企业跨领域合规','企业子样本存在且部分代码可用','工商登记；环保处罚/许可；采购合同','仅适合子样本；先核共同主体和年份再扩量'],
 ['企业招聘、融资、拍卖、上市公司披露','当前经营后果与财务记录稀薄','需新的主样本及完整企业关联','暂不作为整批主线，不能用全省大库弥补缺少交集'],
 ['民宿文旅经营风险','真实旅游用途少，地名误命中明显','平台经营记录、评论与历史许可','当前不优先'],
 ]),'',
'如果坚持以社会经济大数据为主体、保留这批裁判、避免地理主导，最值得先核验的是“农村集体资产交易及工程采购”数据，而不是继续下载大量上市公司年报。资料已经告诉我们需要关注个人、村社及集体资产，而非预设全部是工业企业。','',
'## 八 可试验的递进主线（尚未通过数据验收）','',
'候选现实问题：**农村集体土地及地上资产在建设、交易和处置过程中，哪些用途与主体组合反复出现合规障碍，怎样改进交易前核查和后续实施准备？**','',
'1. 裁判＋集体资产交易公告：识别建房、村社公共设施、经营资产等情境及交易披露特征。连接须有可复核村社、项目、地点及时间；只有地区年份时限于结构比较，不称同宗交易。','2. 复用第一问分类，加入村级工程采购/合同及统计：检查建设、经营、交易环节是否对应不同的公开纠纷和处置结构。采用文本分类、关联分析或情境聚类；不能以未匹配作为没有审批或没有交易。','3. 复用前两问情境，融合裁判理由、交易披露及项目实施材料：验证哪些缺失字段或实施准备与反复出现的障碍相对应，形成有证据支撑的核查字段与实施材料清单。留出年份/地区验证，不做企业违法自动判定。','',
'这个主线需要先拿到交易与工程数据的样本并测匹配率。若无法取得，不能继续把它写成定题；题目与方法都应随数据验收调整。','',
'## 九 逐项对照作业的硬约束','',
table(['条件','本次分析后的真实状态'],[
 ['5—8独立数据源','现有裁判仍只算1源；内部字段、年份、各类文书不能重复计源'],
 ['至少4个主源，各>200MB','司法181.03MB、2018年后135.80MB，尚未达标；新增交易/工程源未核实'],
 ['有效Raw总量>=2GB、单源<=80%','未通过。没有为凑体量下载无关全文；本次CSV和JSONL是派生文件，不与原文重复计Raw'],
 ['至少3类来源/形态','可设计司法、市场交易/采购及官方统计，地理仅辅助；实际新增尚未完成'],
 ['至少2关联维度','地区和时间可用；村社、主体、项目须核匹配，法院所在地不能充当涉案地'],
 ['每问至少2源、三问递进','上节为条件设计，不是已执行分析'],
 ['挖掘方法及时间/空间/网络分析','现有阶段为全量规则提取和交叉描述；没有伪称训练过聚类/预测模型'],
 ['Raw/Cleaned/Integrated、质量与复现','原文保留；清洗正文、特征表、证据及规则脚本已生成。多源Integrated尚未形成'],
 ['>=5幅有效可视化','本次生成7幅描述性SVG；正式多源作业仍应围绕问题重新制图'],
 ]),'',
'## 十 复现与文件','',
'运行 scripts/profile_current_judgments.py 后运行 scripts/enrich_judgment_profile.py。两者只写本画像目录，不修改原始裁判。','',
'- 全量特征表_规则候选.csv：全部文件及可追溯字段。','- 清洗正文.jsonl、证据片段.jsonl：逐条清洗文本与原文依据，含公开当事人信息，仅供本地研究。','- 企业经营组织子样本.csv、同名主体多文书候选.csv：专题核验入口。','- 人工证据复核记录.csv：本次具体复核记录，不提供未经统计抽样支持的准确率。','- 统计摘要.json、补充诊断.json：机器可读汇总。','- 画像图表.html、01—07 SVG：无需联网的描述性图表。','',
'本报告全部统计来自本地原文，不需要网络法律解释来替代案件内容。规则标签有意保留候选属性；后续用于模型训练、违法认定或定量结论前，需要专门标注与抽样验证。']
(P/'全量分析与拓展方向.md').write_text('\n'.join(lines),encoding='utf8')
# Regenerate all figures after scope audit; PNG companions are useful outside a browser.
from PIL import Image,ImageDraw,ImageFont
fontpath='C:/Windows/Fonts/msyh.ttc'
def renderbars(title,pairs,name):
    pairs=list(pairs);w=1200;h=110+len(pairs)*40;maximum=max(v for k,v in pairs)
    im=Image.new('RGB',(w,h),'white');draw=ImageDraw.Draw(im);font=ImageFont.truetype(fontpath,18);big=ImageFont.truetype(fontpath,25)
    draw.text((22,18),title,font=big,fill='#16324f')
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="white"/><g font-family="Microsoft YaHei,sans-serif" fill="#16324f"><text x="22" y="42" font-size="25">{html.escape(title)}</text>']
    for j,(label,n) in enumerate(pairs):
        y=75+j*40;bw=710*n/maximum
        draw.text((22,y),str(label),font=font,fill='#16324f');draw.rounded_rectangle((310,y,310+max(1,bw),y+25),radius=3,fill='#2c7896');draw.text((325+bw,y),str(n),font=font,fill='#16324f')
        svg.append(f'<text x="22" y="{y+20}" font-size="18">{html.escape(str(label))}</text><rect x="310" y="{y}" width="{max(1,bw):.2f}" height="25" rx="3" fill="#2c7896"/><text x="{325+bw:.2f}" y="{y+20}" font-size="18">{n}</text>')
    svg.append('</g></svg>');(P/(name+'.svg')).write_text(''.join(svg),encoding='utf8');im.save(P/(name+'.png'))
figs=[('裁判归年：当前3385份文件',sorted(S['years'].items()),'01_年份'),('法院城市：另标两条外省元数据冲突',S['court_cities'].items(),'02_法院城市'),('主体类型：规则候选、全部文件',S['respondent_types'].items(),'03_主体'),('事实段用途关键词：非互斥用途分类',[(k[4:],v) for k,v in S['bool_counts'].items() if k.startswith('use_')],'04_用途'),('事实段地类表述：非实际占用面积比例',[(k[5:],v) for k,v in S['bool_counts'].items() if k.startswith('land_')],'05_地类'),('法院主文：全部文件的规则识别',S['outcomes'].items(),'06_主文'),('主题关键词线索：非事实认定',[(k[6:],v) for k,v in S['bool_counts'].items() if k.startswith('theme_')],'07_主题')]
for title,pairs,name in figs:renderbars(title,pairs,name)
page='<!doctype html><html lang="zh"><meta charset="utf-8"><title>裁判文书全量画像</title><style>body{max-width:1100px;margin:30px auto;font-family:Microsoft YaHei,sans-serif;background:#f1f5f9;color:#16324f}section{padding:20px;margin:20px 0;background:white;border-radius:10px}img{width:100%}p{line-height:1.8}</style><h1>裁判文书全量画像</h1><p>当前3385份文件；建议暂排3条范围冲突后3382份。图中保持全文件盘点口径，正式分析需按scope_audit过滤。用途、地类、主题为多标签关键词线索，含地名、引用等误命中，不能视作人工分类结果。已完成53条有针对性的证据检查。</p>'
for title,pairs,name in figs:page+=f'<section><img src="{name}.svg" alt="{html.escape(title)}"></section>'
page+='<p>解释见全量分析与拓展方向.md。原文未修改。</p></html>'
(P/'画像图表.html').write_text(page,encoding='utf8')
print(json.dumps({'report':str(P/'全量分析与拓展方向.md'),'company_n':len(company),'subject_counts':S['respondent_types'],'review_checks':len(reviewrows),'full_core_themes':corethemes,'reason_counts':reasoncounts,'repeat_groups':len(repeatrows)},ensure_ascii=False,indent=2))
