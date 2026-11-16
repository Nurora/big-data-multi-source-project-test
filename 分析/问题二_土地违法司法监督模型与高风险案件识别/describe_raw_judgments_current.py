"""Inventory and structure-only description of current local judgment originals."""
from pathlib import Path
from collections import Counter
import ast,re,json,hashlib,unicodedata,sys
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
import openpyxl,pandas as pd
OUT=ROOT/'reports/全面描述性分析_最新版_20261106';T=OUT/'统计表'
tree=ast.parse((ROOT/'scripts/screen_pkulaw.py').read_text(encoding='utf-8'))
subset=ast.Module(body=[x for x in tree.body if isinstance(x,(ast.Import,ast.ImportFrom)) or isinstance(x,ast.FunctionDef) and x.name in ['ole_streams','doc_text']],type_ignores=[])
ns={};exec(compile(subset,'legacy_doc_reader','exec'),ns)
def norm(v):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(v or '')))
f=next(ROOT.glob('*1106*裁判文书.xlsx'));w=openpyxl.load_workbook(f,read_only=True,data_only=True);it=w['最终保留'].values;h=next(it);records=[dict(zip(h,r)) for r in it];w.close()
keys={norm(r['案号']) for r in records};labels={norm(r['案号']):r['结果类型'] for r in records}
rows=[];errors=[];quotes=Counter();reasons=Counter();hashes=Counter();conflicts=[]
for i,path in enumerate(sorted((ROOT/'裁判文书').glob('*.doc'))):
    key=norm(path.stem.split('__')[-2]) if '__' in path.stem else ''
    if key not in keys:
        candidates=re.findall(r'\(\d{4}\)[^_]{1,65}?号',norm(path.stem));key=next((s for s in candidates if s in keys),'')
    b=path.read_bytes();sha=hashlib.sha256(b).hexdigest();hashes[sha]+=1
    try:
        raw=ns['doc_text'](b);text=re.sub(r'\x13[^\x14]*\x14','',raw).replace('\x15','')
        text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','\n',text)
        # Exclude publisher recommendations and all footers before counting.
        end=re.search(r'本案法律依据|同案由重要案例|同法院同类案例|本法院同类案例|©北大法宝|法宝快讯',text)
        body=text[:end.start()] if end else text
        m=re.search(r'本院认为|本院经审查认为|本院审查认为',body)
        a=body[m.start():] if m else ''
        cut=re.search(r'裁定如下[：:]?|判决如下[：:]?|裁判结果',a)
        reason=a[:cut.start()] if cut else a
        result=a[cut.end():] if cut else ''
        result=re.split(r'审\s*判\s*长|审\s*判\s*员|落款',result)[0]
        if key:
            for title in set(re.findall(r'《([^》\n]{2,100})》',body)):quotes[title]+=1
            for term in ['强制执行权','不属于','主要证据不足','送达','催告','申请期限','超过','不符合受理条件','已经履行','规划']:
                if term in reason:reasons[term]+=1
        mixed=bool(re.search(r'不准予|不予强制执行',result) and re.search(r'(?<!不)准予|准许',result))
        if mixed and key:conflicts.append({'案号':key,'原表结果标签':labels[key],'文件':path.name,'主文混合提示':'同时出现准予和不准予候选，需人工复核'})
        rows.append({'文件':path.name,'字节':len(b),'SHA256':sha,'匹配当前案号':key,'属于当前表':bool(key),'解析字符数':len(text),'排除推荐页脚后字符数':len(body),'审查理由字符数':len(reason),'主文字符数':len(result),'找到理由段':bool(m),'找到主文段':bool(cut),'主文准予不准予混合候选':mixed})
    except Exception as e:errors.append({'文件':path.name,'错误':str(e)})
    if (i+1)%1000==0:print('RAW DOC',i+1,flush=True)
d=pd.DataFrame(rows);d.to_csv(T/'裁判原文_逐文件结构与当前表映射.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(errors,columns=['文件','错误']).to_csv(T/'裁判原文_解析失败.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(conflicts,columns=['案号','原表结果标签','文件','主文混合提示']).to_csv(T/'裁判原文_主文混合结果候选.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(quotes.most_common(),columns=['书名号标题','提及当前原文数']).to_csv(T/'裁判原文_书名号标题提及.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(reasons.most_common(),columns=['理由词语','提及当前原文数']).to_csv(T/'裁判原文_理由词语提及_非原因分类.csv',index=False,encoding='utf-8-sig')
matched=d[d['属于当前表']]
if len(matched):matched[['解析字符数','排除推荐页脚后字符数','审查理由字符数','主文字符数']].describe(percentiles=[.05,.25,.5,.75,.95]).reset_index().to_csv(T/'裁判原文_文本长度描述.csv',index=False,encoding='utf-8-sig')
info={'本地DOC文件':len(rows)+len(errors),'解析成功':len(rows),'解析失败':len(errors),'逐字节重复差额':sum(v-1 for v in hashes.values()),'映射当前表文件':len(matched),'覆盖当前不同案号':int(matched['匹配当前案号'].nunique()),'当前表不同案号':len(keys),'有理由段的当前文件':int(matched['找到理由段'].sum()),'有主文段的当前文件':int(matched['找到主文段'].sum()),'主文混合结果候选':len(conflicts),'限制':'按文件名案号映射；段落和词语提取仅结构描述，不是全量人工法律结果重标。正文长度仍可能含平台前置信息。'}
(OUT/'原文统计摘要.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(info,ensure_ascii=False),flush=True)
