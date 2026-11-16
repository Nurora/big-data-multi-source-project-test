"""Read every current judgment; preserve evidence and conservative rule labels.
No legal prediction, no network, no modification of source files.
"""
from __future__ import annotations
import ast, collections as C, csv, datetime as dt, hashlib, html, json, pathlib, re, statistics, struct, unicodedata, zipfile, io

ROOT = pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
OUT = ROOT/'reports'/'裁判文书初步分析_20261102'
OUT.mkdir(exist_ok=True)
# Reuse audited binary Word decoder without importing its output-directory side effects.
tree = ast.parse((ROOT/'scripts/screen_pkulaw.py').read_text('utf8'))
ns = {'struct':struct}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('ole_streams','doc_text')],type_ignores=[]),'<word-decoder>','exec'),ns)

def norm(s): return re.sub(r'\s+','',unicodedata.normalize('NFKC',s))
def writej(name,v): (OUT/name).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
def csvout(name,rows):
    if not rows:return
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def fld(t,label):
    m=re.search(label+r'\s*[：:]\s*([^\n]+)',t)
    return m[1].strip() if m else ''
def split_core(t):
    b=re.split(r'(?m)^\s*//\s*$',t,maxsplit=1)[-1]
    return re.split(r'©北大法宝|附法律依据|附[：:]本裁定|附[：:]相关法律|附[：:]法律|附本裁定|本案法律依据|同案由重要案例|本法院同类案例',b,maxsplit=1)[0].strip()
def hits(text,pattern,n=3):
    out=[]
    for m in re.finditer(pattern,text):
        s=text[max(0,m.start()-65):min(len(text),m.end()+95)].replace('\n',' ')
        if s not in out:out.append(s)
        if len(out)>=n:break
    return out

USES={
 '住宅住房':r'自建房|住宅|住房|宅基地|居住|建(?:设|造|筑|起|好)?(?:一[栋幢座]|[二三四五六七八九十\d]+[栋幢座])?房屋|兴建房屋|建房',
 '厂房加工':r'厂房|生产车间|加工厂|加工场|工厂|工业厂区|生产厂',
 '仓储物流':r'仓库|仓储|物流|堆场|堆放场',
 '商业餐饮住宿':r'商铺|商店|门店|商场|酒店|旅馆|宾馆|饭店|餐饮|酒楼|餐馆|农庄|农家乐|民宿|商住',
 '驾校训练':r'驾驶.{0,6}(?:培训|训练)|驾校|练车场|教练场',
 '停车汽修':r'停车场|修理厂|汽修|汽车维修|洗车场',
 '农业养殖设施':r'养殖(?!水面)|养猪|猪舍|猪场|鸡舍|鸡场|牛棚|牛场|农用设施|农业设施|种养',
 '旅游休闲文体':r'旅游|景区|度假|休闲|球场|游乐|游泳池|体育|露营',
 '基础设施公共服务':r'公路|道路工程|铁路|高速公路|供水|水厂|污水|供电|变电站|输电|燃气|天然气|学校|幼儿园|养老院|卫生院|医院|垃圾',
 '硬化围墙临建':r'硬底化|硬化|水泥地|围墙|临时建筑|临时搭建|铁皮棚|铁棚|简易棚|建筑材料',
}
LAND={
 '耕地水田旱地':r'耕地|水田|旱地|水浇地',
 '基本农田':r'基本农田',
 '林地':r'林地|有林地|灌木林',
 '园地':r'园地|果园|茶园',
 '其他农用地':r'其他农用地|养殖水面|坑塘水面|鱼塘|农用地',
 '建设用地':r'建设用地|城镇村及工矿用地',
 '未利用地':r'未利用地|荒地|草地|裸地',
}
THEMES={
 '出租租赁':r'租赁|出租|承租|租用|租金|转租|租地',
 '土地转让买卖':r'转让|买卖|出卖|购买|购地',
 '集体参与':r'村民委员会|村委会|村民小组|经济合作社|经济联合社|股份合作|农民集体',
 '规划不符合':r'不符合.{0,35}(?:规划|土地利用)|违反.{0,20}规划',
 '规划符合':r'(?<!不)符合.{0,35}(?:总体规划|土地利用规划|土地利用总体规划)',
 '未批先建表述':r'未经.{0,10}批准|未取得.{0,12}(?:批准|许可)|未办理.{0,12}(?:审批|用地|批准)',
 '复垦恢复':r'复垦|恢复土地原状|恢复林地原状|恢复植被|复绿',
 '卫片巡查':r'卫片|卫星|巡查|遥感|图斑',
 '项目投资备案':r'立项|备案|招商引资|投资项目|重点项目|项目审批',
 '环评排污':r'环评|环境影响评价|排污许可|环保验收',
 '房屋租赁争议':r'租赁合同|租金|承租人|出租人',
 '经营损失表述':r'停产|停业|搬迁|经营损失|经济损失|损失赔偿|赔偿损失',
 '就业劳动表述':r'职工|(?<!人)员工|工资|劳动合同|失业|就业|招聘',
 '债务资产表述':r'抵押|破产|拍卖|债权|债务|借款|贷款',
 '旅游民宿表述':r'旅游|民宿|农家乐|露营|度假',
}
CITIES=['广州','韶关','深圳','珠海','汕头','佛山','江门','湛江','茂名','肇庆','惠州','梅州','汕尾','河源','阳江','清远','东莞','中山','潮州','揭阳','云浮']
CODECITY={'01':'广州','02':'韶关','03':'深圳','04':'珠海','05':'汕头','06':'佛山','07':'江门','08':'湛江','09':'茂名','12':'肇庆','13':'惠州','14':'梅州','15':'汕尾','16':'河源','17':'阳江','18':'清远','19':'东莞','20':'中山','51':'潮州','52':'揭阳','53':'云浮'}
def courtcity(court,case):
    for x in CITIES:
        if x in court:return x
    m=re.search(r'粤(\d{2})',case)
    if m:return CODECITY.get(m[1],'未知')
    for token,city in {'开平':'江门','揭西':'揭阳','海丰':'汕尾','高州':'茂名'}.items():
        if token in court:return city
    return '未知'
def party_type(s):
    if not s:return '未提取'
    if re.search(r'经济合作社|经济联合社|经济社|股份合作|村民小组|村委会|村民委员会|居民委员会|居民小组|股份经济|村民理事|社区.{0,12}民委员会|某.{0,10}民委员会|某.{0,10}民小组|村二组$|迁移新村$|进港村$',s):return '村社集体组织'
    if re.search(r'公司|企业|合伙|合作社|工厂|厂[，。]|厂$|分厂|经营部|商行|个体工商|加工场|加工部$|销售部$|回收店$|砂石场$',s):return '企业或经营组织'
    if re.search(r'人民政府|管理委员会|公安|交通警察|事业|供销|学校|小学|学院|医院|卫生院|委员会|局[，。]|局$|中心|寺|协会|基金会|管理总站|办公室',s):return '机关事业或其他组织'
    if len(s)>12 and re.search('县|镇|街道|社区',s):return '组织候选待细分'
    if re.search(r'[\u4e00-\u9fff某×＊*]{2,8}',s):return '自然人候选'
    return '待核对'

def main():
    catalog=json.loads((ROOT/'reports/1102两包审查/合并后文书目录.json').read_text('utf8'))
    cat={str(d['id']):d for d in catalog};rows=[];evidence=[];errors=[];fullrecords=[]
    for fileindex,p in enumerate(sorted((ROOT/'裁判文书').glob('*.doc*')),1):
        raw=p.read_bytes();m=re.search(r'__(\d+)\.docx?$',p.name);ident=m[1] if m else p.stem
        meta=cat.get(ident,{})
        try:
            if raw.startswith(b'PK'):
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    import xml.etree.ElementTree as ET
                    t='\n'.join(''.join(e.itertext()) for e in ET.fromstring(z.read('word/document.xml')).iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
            else:t=ns['doc_text'](raw)
            t=re.sub(r'\x13[^\x14]*\x14','',t).replace('\x15','');t=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','\n',t)
        except Exception as exc:errors.append({'file':str(p),'error':str(exc)});continue
        b=split_core(t);flat=norm(b)
        # Party names come only from party block, never website footer or metadata keywords.
        partyblock=re.split(r'审理经过|本院查明|本院认为|经审查|申请执行人.{0,80}(?:向本院|于\d{4}年)',b,maxsplit=1)[0]
        respondents=[]
        for line in partyblock.splitlines():
            mat=re.match(r'\s*(?:当事人\s*)?(?:被申请执行人|被执行人|被申请人)[：:]?\s*(.+)',line)
            if mat:
                val=re.split(r'[，,。；;（(]|住所地|住址|统一社会信用代码|法定代表人|身份证',mat[1])[0].strip()
                if val:respondents.append(val)
        # Inline party blocks may lack line boundaries.
        if not respondents:
            mat=re.search(r'(?<!申请执行人)(?:被申请执行人|被执行人|被申请人)[：:]?\s*([^\n，。；]{2,90})',partyblock)
            if mat:respondents=[mat[1].strip()]
        party_source='当事人段'
        if not respondents:
            mat=re.search(r'(?:审理经过\s*|\n\s*)(?:被申请执行人|被执行人|被申请人)[：:]?\s*([^\n，。；]{2,90})',b[:2000])
            if mat:
                respondents=[re.split(r'住所地|住址|统一社会信用代码|法定代表人|身份证',mat[1])[0].strip()]
                party_source='正文角色标识'
        if not respondents:
            title0=t.splitlines()[0].strip()
            mat=re.search(r'(?:与|、)([^\n]{2,90}?)(?:非诉|处罚类|执行裁定|其他行政|准[（(]|行政裁定|案$)',title0)
            if mat:respondents=[mat[1].strip('、')];party_source='标题补充候选'
        types={party_type(norm(s)) for s in respondents}
        ptype='混合主体' if len(types)>1 else next(iter(types),'未提取')
        am=re.search(r'(?:当事人\s*)?(?<!被)申请执行人[：:]?\s*([^\n，。；（(]{2,80})',partyblock)
        applicant=am[1].strip() if am else ''
        court=meta.get('court') or fld(t,'审理法院');case=meta.get('case') or fld(t,r'案\s*号')
        cm=re.search(r'(?m)^([^\n]{2,40}人民法院)\s*$',b)
        bodycourt=cm[1].strip().lstrip('/') if cm else ''
        city=courtcity(bodycourt or court,case)
        result_parts=re.split(r'裁定如下[：:]?|判决如下[：:]?',b)
        if len(result_parts)==1:result_parts=re.split(r'裁判结果',b)
        result_parts[-1]=result_parts[-1].replace('裁判结果','').replace('审理经过','')
        result=re.split(r'落款|审\s*判\s*长|审\s*判\s*员|本裁定为|本裁定送达|如不服|申请执行人.{0,5}不服',result_parts[-1],maxsplit=1)[0].strip() if len(result_parts)>1 else ''
        rf=norm(result)
        neg=bool(re.search(r'不(?:予|准予|准许)(?:强制)?执行|不予受理|驳回[^。；]{0,500}申请',rf))
        pos=bool(re.search(r'(?:准予|准许)(?:(?![。；]).){0,90}?(?:执行|强制拆除)',re.sub(r'不(?:予|准予|准许)(?:强制)?执行','',rf)))
        outcome='部分准予或混合主文' if pos and neg else '准予执行' if pos else '不准予或驳回' if neg else '其他或未识别'
        if '撤回' in rf:outcome='准许撤回申请'
        elif outcome=='其他或未识别' and re.search('组织实施',rf):outcome='裁定组织实施（待复核）'
        # Case facts preceding reasoning; statutory quotations largely occur in reasoning/annex.
        facts=re.split(r'本院认为',b,maxsplit=1)[0]
        facts=re.split(r'审理经过|本院查明',facts,maxsplit=1)[-1]
        facts=re.split(r'裁判结果|落款',facts,maxsplit=1)[0]
        # This scope still contains quoted penalty facts; all tags are disclosure candidates, not proven findings.
        ff=norm(facts)
        reasoning=re.split(r'本院认为',b,maxsplit=1)[-1] if '本院认为' in b else ''
        reasoning=re.split(r'裁判结果|裁定如下',reasoning,maxsplit=1)[0]
        uses={k:bool(re.search(v,ff)) for k,v in USES.items()}
        lands={k:bool(re.search(v,ff)) for k,v in LAND.items()}
        themes={k:bool(re.search(v,ff)) for k,v in THEMES.items()}
        # Support geographic linkage only as candidates, not exact offence location.
        locs=list(dict.fromkeys(re.findall(r'[\u4e00-\u9fff]{2,10}(?:县|区|市)[\u4e00-\u9fff]{1,10}(?:镇|街道|乡)',ff)))
        applicant_region=re.search(r'([\u4e00-\u9fff]{2,12}?(?:县|区|市))(?:自然资源|国土|林业|农林|城市|规划)',applicant)
        # Penalty documents: preserve broad candidates for later normalization/manual checking.
        pnos=list(dict.fromkeys(re.findall(r'[^，。；：:《》\s]{1,22}(?:罚|执|决)[^，。；：:《》\s]{0,8}[〔（(\[]\d{4}[〕）)\]][^，。；：:《》\s]{0,14}?号',facts)))
        date_candidates=[]
        for dm in re.finditer(r'(\d{4})年(\d{1,2})月(\d{1,2})日',ff):
            tail=ff[dm.end():dm.end()+90]
            if re.search(r'^.{0,10}作出',tail) and re.search(r'处罚|执法|决定书',tail):
                try:date_candidates.append(dt.date(*map(int,dm.groups())).isoformat())
                except ValueError:pass
        date_candidates=list(dict.fromkeys(date_candidates))
        cd=meta.get('date') or fld(t,'审结日期')
        lag=None
        if len(date_candidates)==1 and re.match(r'\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}',cd):
            try:
                cdate=dt.date(*map(int,re.split(r'[.\-/]',cd)[:3]));lag=(cdate-dt.date.fromisoformat(date_candidates[0])).days
            except ValueError:pass
        area=[{'value':m[1].replace(',',''),'unit':m[2],'context':ff[max(0,m.start()-30):m.end()+35]} for m in re.finditer(r'(\d[\d,]*(?:\.\d+)?)\s*(平方米|公顷|亩|m2)',ff)]
        totals=[a for a in area if not re.search(r'每|单价|元',a['context'][:30][-6:])]
        # Respondent identifiers only; agency identifiers must not be counted as matchable firms.
        targetblocks=[]
        for line in partyblock.splitlines():
            if re.search(r'^(?:当事人\s*)?\s*被(?:申请执行|执行|申请)人',line):targetblocks.append(line)
        targetcodes=list(dict.fromkeys(re.findall(r'(?<![A-Z0-9])[0-9A-Z]{18}(?![A-Z0-9])','\n'.join(targetblocks))))
        if ptype=='自然人候选' and any(x.startswith(('91','92','93')) for x in targetcodes):ptype='企业或经营组织'
        row={'id':ident,'file':str(p),'raw_bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
             'catalog_hash_match':hashlib.sha256(raw).hexdigest()==meta.get('sha256'),'title':t.splitlines()[0].strip(),'case_number':case,
             'court_metadata':court,'court_body':bodycourt,'court_city':city,'court_date':cd,'year':cd[:4] if re.match(r'\d{4}',cd) else (re.search(r'\d{4}',case)[0] if re.search(r'\d{4}',case) else '未知'),
             'year_basis':'审结日期' if re.match(r'\d{4}',cd) else '案号辅助归年，待复核','applicant':applicant,'applicant_region_candidate':applicant_region[1] if applicant_region else '',
             'respondents':'；'.join(respondents),'respondent_source':party_source if respondents else '未提取','respondent_type_rule':ptype,'respondent_anonymized':bool(re.search(r'某|×|\*|＊|[xX]{2}', norm(';'.join(respondents)))),
             'respondent_credit_codes':'；'.join(targetcodes),'court_outcome_rule':outcome,'result_excerpt':result[:1800],
             'core_chars':len(b),'fulltext_chars':len(t),'facts_chars':len(facts),'core_text_sha256':hashlib.sha256(norm(b).encode()).hexdigest(),
             'town_location_candidate':bool(locs),'town_location_examples':'；'.join(locs[:3]),'penalty_number_candidates':'；'.join(pnos[:6]),
             'penalty_date_candidates':'；'.join(date_candidates),'penalty_to_court_days_candidate':lag,
             'area_mentioned':bool(area),'distinct_area_numbers':len({(x['value'],x['unit']) for x in area}),
             'area_candidates_json':json.dumps(area,ensure_ascii=False),
             'decision_mentions_demolition':bool(re.search('拆除',rf)), 'decision_mentions_fine':bool(re.search('罚款|罚金',rf)),
             'decision_mentions_return':bool(re.search('退还|交还',rf)), 'decision_mentions_confiscation':bool(re.search('没收',rf)),
             'decision_mentions_restoration':bool(re.search('复垦|恢复|复绿',rf)),
             'fine_amount_context_candidate':bool(re.search(r'(?:罚款.{0,25}\d|\d.{0,20}罚款)',ff)),
             'decision_implementation_by_gov':bool(re.search(r'(?:政府|委员会).{0,15}(?:组织实施|实施|执行)|(?:组织实施|实施).{0,20}(?:政府|委员会)',rf)),
             **{'use_'+k:v for k,v in uses.items()},**{'land_'+k:v for k,v in lands.items()},**{'theme_'+k:v for k,v in themes.items()}}
        row.update({k:fld(t,v) for k,v in {'cause':'案由','document_type':'文书类型','procedure_metadata':'审理程序','public_type':'公开类型','reference_level':'参照级别','judges_metadata':'审理法官'}.items()})
        row['source_url']='；'.join(dict.fromkeys(re.findall(r'https?://(?:www\.)?pkulaw\.com/(?:pfnl|case|cli)/[^\s<>\"]+',t)))
        row['case_number_quality']='完整案号未核实' if not re.search('行审|行非|非审',case) else '案号字段可用'
        rows.append(row)
        ev={k:hits(ff,v) for k,v in {**{'use_'+k:v for k,v in USES.items()},**{'land_'+k:v for k,v in LAND.items()},**{'theme_'+k:v for k,v in THEMES.items()}}.items() if re.search(v,ff)}
        evidence.append({'id':ident,'case':case,'file':str(p),'respondents':respondents,'party_block':partyblock,'reasoning':reasoning,'result':result,'evidence':ev})
        fullrecords.append({'id':ident,'file':str(p),'core':b,'facts':facts,'reasoning':reasoning,'result':result})
        if fileindex%500==0:print(f'Parsed {fileindex}',flush=True)
    csvout('全量特征表_规则候选.csv',rows)
    with (OUT/'清洗正文.jsonl').open('w',encoding='utf8') as f:
        for x in fullrecords:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    with (OUT/'证据片段.jsonl').open('w',encoding='utf8') as f:
        for x in evidence:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    counts=lambda key:dict(C.Counter(str(r[key]) for r in rows).most_common())
    boolcounts={k:sum(r[k] for r in rows) for k in rows[0] if isinstance(rows[0][k],bool)}
    yearrows=[]
    for y in sorted({r['year'] for r in rows}):
        group=[r for r in rows if r['year']==y]
        yearrows.append({'year':y,'documents':len(group),'raw_bytes':sum(r['raw_bytes'] for r in group),**{k:sum(r[k] for r in group) for k in boolcounts if k.startswith(('use_','theme_'))}})
    csvout('年份交叉表.csv',yearrows)
    cityrows=[]
    for c,n in C.Counter(r['court_city'] for r in rows).most_common():
        group=[r for r in rows if r['court_city']==c]
        cityrows.append({'court_city':c,'documents':n,**{k:sum(r[k] for r in group) for k in boolcounts if k.startswith(('use_','theme_'))}})
    csvout('法院地区交叉表.csv',cityrows)
    rawhash=C.Counter(r['sha256'] for r in rows);corehash=C.Counter(r['core_text_sha256'] for r in rows)
    lagvals=[r['penalty_to_court_days_candidate'] for r in rows if r['penalty_to_court_days_candidate'] is not None]
    summary={'run_date':'2026-11-02','method':'Every current DOC parsed anew; annex/platform removed; conservative rule candidates, not manually verified labels.',
       'files_discovered':len(list((ROOT/'裁判文书').glob('*.doc*'))),'parsed':len(rows),'parse_errors':errors,
       'raw_bytes':sum(r['raw_bytes'] for r in rows),'catalog_hash_mismatches':[r['id'] for r in rows if not r['catalog_hash_match']],
       'raw_hash_duplicate_extras':sum(n-1 for n in rawhash.values()),'core_hash_duplicate_extras':sum(n-1 for n in corehash.values()),
       'years':counts('year'),'court_cities':counts('court_city'),'courts':counts('court_body'),'respondent_types':counts('respondent_type_rule'),
       'outcomes':counts('court_outcome_rule'),'bool_counts':boolcounts,
       '2018_plus':{'n':sum(r['year']>='2018' for r in rows),'raw_bytes':sum(r['raw_bytes'] for r in rows if r['year']>='2018')},
       'core_chars':{'total':sum(r['core_chars'] for r in rows),'median':statistics.median(r['core_chars'] for r in rows),'min':min(r['core_chars'] for r in rows),'max':max(r['core_chars'] for r in rows)},
       'date_lag_candidates':{'n':len(lagvals),'negative':sum(x<0 for x in lagvals),'median_all_candidates':statistics.median(lagvals) if lagvals else None},
       'repeated_respondents':C.Counter(r['respondents'] for r in rows if r['respondents'] and not r['respondent_anonymized']).most_common(30),
       'limitations':['Court city is not offence city; cross-district jurisdiction exists.','Tags count disclosures in facts, not exclusive actual land/use classifications.','Dates and area candidates can refer to multiple events/units; do not sum areas or infer processing efficiency.','Approval of enforcement is not observed demolition, payment, relocation, or business failure.','Already selected non-litigation enforcement sample does not represent all land offences.']}
    writej('统计摘要.json',summary)
    # Evidence-bearing stratified review: deterministic examples from every topic and unusual outcome.
    reviewids=[]
    for key in [k for k in boolcounts if k.startswith(('use_','theme_'))]:
        group=[r for r in rows if r[key]]
        for r in sorted(group,key=lambda x:hashlib.sha256((key+x['id']).encode()).hexdigest())[:3]:
            if r['id'] not in reviewids:reviewids.append(r['id'])
    for r in rows:
        if r['court_outcome_rule']!='准予执行' and r['id'] not in reviewids:reviewids.append(r['id'])
    evmap={x['id']:x for x in evidence}
    writej('分层复核样本.json',[evmap[i] for i in reviewids])
    # Browser-friendly standalone descriptive figures, no external libraries or assets.
    def bars(title,pairs,filename):
        pairs=list(pairs);w=1000;h=85+len(pairs)*32;maxn=max([v for k,v in pairs] or [1]);s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="white"/><g font-family="Microsoft YaHei, sans-serif" fill="#16324f"><text x="20" y="32" font-size="21">{html.escape(title)}</text>']
        for i,(k,v) in enumerate(pairs):
            y=55+i*32;bw=620*v/maxn
            s.append(f'<text x="20" y="{y+18}" font-size="14">{html.escape(str(k))}</text><rect x="260" y="{y}" width="{bw:.2f}" height="23" rx="3" fill="#2c7896"/><text x="{270+bw:.2f}" y="{y+17}" font-size="14">{v}</text>')
        s.append('</g></svg>');(OUT/filename).write_text(''.join(s),encoding='utf8')
    figs=[('裁判年份分布（现有公开样本）',sorted(summary['years'].items()),'01_年份.svg'),('法院所在城市（不等于涉案地）',summary['court_cities'].items(),'02_法院城市.svg'),('被执行主体：规则候选',summary['respondent_types'].items(),'03_主体.svg'),('事实段用途提及（多标签，不可相加）',[(k[4:],v) for k,v in boolcounts.items() if k.startswith('use_')],'04_用途.svg'),('事实段土地类型提及（多标签，含混合地块）',[(k[5:],v) for k,v in boolcounts.items() if k.startswith('land_')],'05_地类.svg'),('法院主文：规则识别',summary['outcomes'].items(),'06_主文.svg'),('可拓展主题的事实段提及（线索）',[(k[6:],v) for k,v in boolcounts.items() if k.startswith('theme_')],'07_主题.svg')]
    for title,pairs,f in figs:bars(title,pairs,f)
    page='<!doctype html><html lang="zh"><meta charset="utf-8"><title>裁判文书全量画像</title><style>body{max-width:1060px;margin:30px auto;font-family:Microsoft YaHei,sans-serif;background:#f1f5f9;color:#16324f}section{padding:20px;margin:20px 0;background:white;border-radius:10px}img{width:100%}p{line-height:1.8}</style><h1>现有裁判文书全量画像</h1><p>2026-11-02；全部当前文件重新解析。用途、地类、主题为事实段规则候选；多标签可重叠。公开非诉审查样本不能代表真实违法发生率。</p>'
    for title,pairs,f in figs:page+=f'<section><img src="{f}" alt="{title}"></section>'
    page+='<p>数据：统计摘要.json、全量特征表_规则候选.csv、证据片段.jsonl。完整解释见同目录分析报告。</p></html>'
    (OUT/'画像图表.html').write_text(page,encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
