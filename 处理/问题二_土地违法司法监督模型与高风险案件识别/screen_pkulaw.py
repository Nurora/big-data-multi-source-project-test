import pathlib, zipfile, io, struct, hashlib, json, re, csv
ROOT=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
OUT=ROOT/'outputs'/'pkulaw_20261021'
OUT.mkdir(parents=True,exist_ok=True)
def ole_streams(b):
    ss=1<<struct.unpack_from('<H',b,30)[0]
    def sector(n): return b[(n+1)*ss:(n+2)*ss]
    dif=list(struct.unpack_from('<109I',b,76)); nxt,count=struct.unpack_from('<II',b,68)
    for _ in range(count):
        a=struct.unpack('<%dI'%(ss//4),sector(nxt));dif.extend(a[:-1]);nxt=a[-1]
    fat=[]
    for n in dif:
        if n<0xfffffffa:fat.extend(struct.unpack('<%dI'%(ss//4),sector(n)))
    def chain(n,table,reader):
        out=[];seen=set()
        while n<0xfffffffa and n not in seen:
            seen.add(n);out.append(reader(n));n=table[n]
        return b''.join(out)
    dirs=chain(struct.unpack_from('<I',b,48)[0],fat,sector);entries=[]
    for i in range(0,len(dirs),128):
        e=dirs[i:i+128];l=struct.unpack_from('<H',e,64)[0]
        if l:entries.append((e[:l-2].decode('utf-16le'),e[66],struct.unpack_from('<I',e,116)[0],struct.unpack_from('<Q',e,120)[0]))
    root=next(e for e in entries if e[1]==5);mini=chain(root[2],fat,sector)[:root[3]]
    mf=chain(struct.unpack_from('<I',b,60)[0],fat,sector);mt=list(struct.unpack('<%dI'%(len(mf)//4),mf)) if mf else []
    return {name:(chain(start,mt,lambda n:mini[n*64:n*64+64]) if size<4096 else chain(start,fat,sector))[:size] for name,t,start,size in entries if t==2}
def doc_text(b):
    s=ole_streams(b);w=s['WordDocument'];pos=32
    n=struct.unpack_from('<H',w,pos)[0];pos+=2+2*n
    n=struct.unpack_from('<H',w,pos)[0];pos+=2+4*n
    n=struct.unpack_from('<H',w,pos)[0];pos+=2
    fc,lcb=struct.unpack_from('<II',w,pos+33*8)
    table=s['1Table' if struct.unpack_from('<H',w,10)[0]&0x200 else '0Table'];clx=table[fc:fc+lcb];p=0
    while p<len(clx) and clx[p]==1:p+=3+struct.unpack_from('<H',clx,p+1)[0]
    if not clx or clx[p]!=2:raise ValueError('Missing piece table')
    size=struct.unpack_from('<I',clx,p+1)[0];plc=clx[p+5:p+5+size];n=(size-4)//12
    cps=struct.unpack_from('<%dI'%(n+1),plc);text=[]
    for i in range(n):
        f=struct.unpack_from('<I',plc,4*(n+1)+8*i+2)[0];cnt=cps[i+1]-cps[i]
        if f&0x40000000: off=(f&0x3fffffff)//2;text.append(w[off:off+cnt].decode('cp1252',errors='replace'))
        else:off=f&0x3fffffff;text.append(w[off:off+cnt*2].decode('utf-16le',errors='replace'))
    return ''.join(text).replace('\r','\n').replace('\x07','\n')
def walkzip(b,source):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        for e in z.infolist():
            if e.is_dir():continue
            raw=z.read(e)
            if e.filename.lower().endswith('.zip'):yield from walkzip(raw,source+' / '+e.filename)
            elif e.filename.lower().endswith('.doc'):yield source,e.filename,raw
def ingest():
    docs=[];seen={};dups=[];errs=[]
    for z in sorted(ROOT.glob('*.zip')):
        for source,name,raw in walkzip(z.read_bytes(),z.name):
            ident=re.search(r'FBMCLI\.C\.(\d+)',name);ident=ident[1] if ident else hashlib.sha256(raw).hexdigest()
            text=doc_text(raw)
            if ident in seen:dups.append({'id':ident,'source':source,'name':name});continue
            seen[ident]=True
            title=re.sub(r'\(FBMCLI.*','',pathlib.PurePosixPath(name).name)
            docs.append(dict(id=ident,title=title,source=source,name=name,text=text,sha256=hashlib.sha256(raw).hexdigest()))
            dest=OUT/'裁判文书';dest.mkdir(exist_ok=True)
            (dest/(ident+'.doc')).write_bytes(raw)
    (OUT/'文书解析.json').write_text(json.dumps(docs,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'重复记录.json').write_text(json.dumps(dups,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'unique':len(docs),'duplicates':len(dups)},ensure_ascii=False))
    for d in docs[:2]:print(d['id'],d['text'][:5500])
def prepare_review():
    docs=json.loads((OUT/'文书解析.json').read_text(encoding='utf-8'))
    for d in docs:
        t=re.sub(r'\x13[^\x14]*\x14','',d['text']);t=t.replace('\x15','');t=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','\n',t)
        d['text']=t
        m=re.search(r'案\s*号\s*[：:]\s*([^\n]+)',t);d['case']=m[1].strip() if m else ''
        m=re.search(r'审理法院\s*[：:]\s*([^\n]+)',t);d['court']=m[1].strip() if m else ''
        body=t.split('//',1)[-1].split('©北大法宝')[0].strip();d['body']=body
        result=re.split(r'裁定如下[：:，,]?|裁判结果',body)[-1]
        d['result']=result.split('审判长')[0].split('审判员')[0].strip()[:1600]
        d['land_evidence']=[x.strip() for x in re.split('[。\n]',body) if re.search(r'土地管理法|非法.{0,8}(占用|转让|买卖).{0,8}土地|擅自占用.{0,8}土地|土地.{0,8}(行政处罚|违法)|退还.{0,20}土地',x)]
    (OUT/'审查数据.json').write_text(json.dumps(docs,ensure_ascii=False,indent=2),encoding='utf-8')
    from collections import Counter
    print('cases missing',sum(not d['case'] for d in docs),'duplicate case',[(k,v) for k,v in Counter(d['case'] for d in docs).items() if v>1])
    print('strong land evidence',sum(bool(d['land_evidence']) for d in docs))
    atyp=[d for d in docs if not d['land_evidence'] or not re.search(r'(不予|不准予|准予|准许|不准许).{0,8}(强制)?执行',d['result']) or not any(x in d['title'] for x in ['国土','自然资源','规划土地'])]
    (OUT/'需细查.txt').write_text('\n\n'.join(d['id']+' '+d['title']+' '+d['case']+'\n'+d['body'] for d in atyp),encoding='utf-8')
    print('atypical',len(atyp))
    print('\n'.join(d['id']+' '+d['title']+' '+d['case']+' | '+d['result'][:150].replace('\n',' ')+' | land='+str(bool(d['land_evidence'])) for d in atyp))
def decide():
    from collections import defaultdict,Counter
    from difflib import SequenceMatcher
    ds=json.loads((OUT/'审查数据.json').read_text(encoding='utf-8'))
    groups=defaultdict(list)
    for d in ds:groups[re.sub(r'\s','',d['court'])+'|'+re.sub(r'\s','',d['case'])].append(d)
    duplicate={}
    for k,g in groups.items():
        if len(g)>1:
            norm=lambda t:re.sub(r'[^\w\u4e00-\u9fff]','',t)
            for d in g[1:]:
                a,b=g[0],d
                ratio=SequenceMatcher(None,norm(a['body'].split('当事人',1)[-1]),norm(b['body'].split('当事人',1)[-1]),autojunk=False).ratio()
                print('duplicate',a['id'],b['id'],a['case'],'similarity',round(ratio,5))
                assert ratio>.97
                duplicate[b['id']]=a['id']
    for d in ds:
        compact=re.sub(r'\s','',d['body'])
        d['decision']='保留';d['reason']='土地违法行政处罚非诉执行审查，裁定主文准予或不准予执行'
        if d['id'] in duplicate:
            d['decision']='重复删除';d['reason']='同法院同案号，事实及裁定内容相同；保留CLI.C.'+duplicate[d['id']]
        elif re.search(r'深人环罚|博环罚',compact):
            d['decision']='不符删除';d['reason']='环保行政处罚（排污、环评、水源保护等），不属于土地违法行政处罚'
        elif d['id'] in ['90857402','91427051','91695223']:
            d['decision']='不符删除';d['reason']='道路客运经营处罚；土地仅出现在企业名称中'
        elif d['id'] in ['44905631','52071082']:
            d['decision']='不符删除';d['reason']='非法开采矿产资源处罚，未审查土地违法处罚'
            if d['id']=='52071082':d['reason']='本次申请及裁定仅处理非法抽取地下热水的采矿处罚；违法用地仅是同一处罚决定中的另一事项'
        elif d['id']=='92128850':
            d['decision']='不符删除';d['reason']='未取得建设工程规划许可证的规划处罚；正文无违法用地处罚内容'
        elif d['id'] in ['101321207','101115935','59254703','99790203']:
            d['reason']='擅自改变林地用途、恢复林地原状的行政处罚执行审查，属于违法用地'
        if d['decision']=='保留':
            assert re.search(r'(准予|准许|不予|不准予|不准许).{0,8}(强制)?执行',re.sub(r'\s','',d['result'])),d['id']
            assert d['land_evidence'] or d['id'] in ['101321207','101115935','59254703','99790203','22179031'] or '茂南区国土环境' in d['title'],d['id']
        d['evidence']='；'.join(d['land_evidence'][:2])[:900] if d['decision']=='保留' else '；'.join(x.strip() for x in compact.split('。') if re.search(r'查明|存在|违反|处罚',x))[:900]
    (OUT/'筛选结果.json').write_text(json.dumps(ds,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'筛选记录.csv').open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.writer(f);wr.writerow(['法宝编号','标题','案号','处理','理由','正文证据','裁定主文','来源压缩包'])
        wr.writerows([d['id'],d['title'],d['case'],d['decision'],d['reason'],d['evidence'],d['result'],d['source']] for d in ds)
    print(dict(Counter(d['decision'] for d in ds)))
    print('\n'.join(d['id']+' '+d['case']+' '+d['reason'] for d in ds if d['decision']!='保留'))
def finalize():
    ds=json.loads((OUT/'筛选结果.json').read_text(encoding='utf-8'))
    folder=(OUT/'裁判文书').resolve()
    assert folder.is_relative_to(ROOT.resolve())
    for d in ds:
        p=folder/(d['id']+'.doc')
        assert p.resolve().parent==folder
        if d['decision']!='保留':
            if p.exists():p.unlink()
        else:
            safe=lambda s:re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',s)
            name=safe(d['title'][:65])+'__'+safe(d['case'])+'__'+d['id']+'.doc'
            target=folder/name
            if p.exists():p.rename(target)
            assert target.exists()
            assert hashlib.sha256(target.read_bytes()).hexdigest()==d['sha256']
            d['file']=str(target)
    kept=[d for d in ds if d['decision']=='保留']
    assert len(list(folder.glob('*.doc')))==len(kept)
    assert len({re.sub(r'\s','',d['court']+'|'+d['case']) for d in kept})==len(kept)
    (OUT/'最终目录数据.json').write_text(json.dumps(kept,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'保留裁判书目录.csv').open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.writer(f);wr.writerow(['裁判书标题','案号']);wr.writerows([d['title'],d['case']] for d in kept)
    odd=[d for d in kept if not re.search('行|法|诉',d['case'])]
    summary={'压缩包数量':len(list(ROOT.glob('*.zip'))),'解包文书总数':1495,'按法宝编号重复':396,'唯一法宝编号':1099,'同案异号重复':3,'不符范围删除':len(ds)-len(kept)-3,'最终保留':len(kept),'案号异常':[(d['id'],d['title'],d['case']) for d in odd]}
    (OUT/'处理统计.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    note='''# 裁判文书整理说明

范围：沿用本次1099篇候选集的研究要求，保留广东法院对土地违法行政处罚作出的非诉执行审查裁定，包括准予、不准予及部分准予执行。未另外按年份删减。林地违法占用、擅自改变林地用途保留；单纯环境污染、客运、采矿、建设工程规划许可处罚排除。

方法：递归展开23个根目录压缩包及其中的嵌套压缩包，读取1495个DOC的Word正文。按法宝编号去除396个重复文件，得到1099个记录；再以法院、案号和正文归一化对照，去除3个不同法宝编号的同案重复收录。逐份扫描正文中的违法事实、处罚事项和裁定主文，对缺少明确违法用地证据、非国土机关、非典型主文及同案重复记录作重点复核。排除26份不符合范围的裁定，保留1070份。

文件：裁判文书文件夹只含保留的原始DOC，正文没有改写。文件名包括标题（过长时截短）、原始案号和法宝编号。同名标题不会互相覆盖。全部原始压缩包保留。筛选记录.csv列出每个唯一法宝编号的保留/排除理由及正文证据；重复记录.json记录重复下载来源。

案号质量：以下4份原始文书的“案号”栏和正文抬头都未提供完整法院案号，表格照录原文，没有把处罚决定文号擅自补成案号。这些文书因内容相关而保留。使用时应回到数据库核验：
'''
    note+='\n'.join('- CLI.C.'+d['id']+'：'+d['title']+'；原文案号：'+d['case'] for d in odd)
    note+='\n\n此外，部分数据库标题与正文的申请机关不一致，例如CLI.C.22876525标题写安全生产监督管理局，正文实际为国土资源局的违法占地处罚，故按正文保留并照录数据库标题。\n'
    (OUT/'整理说明.md').write_text(note,encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
    import sys
    if 'review' in sys.argv:prepare_review()
    elif 'decide' in sys.argv:decide()
    elif 'finalize' in sys.argv:finalize()
    else:ingest()
