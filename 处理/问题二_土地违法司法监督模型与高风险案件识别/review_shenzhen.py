import json,re,collections
from pathlib import Path
O=Path('reports/深圳审查'); ds=json.loads((O/'原文.json').read_text('utf8'))
for d in ds:
 t=d['clean'];i=d['index'];d['title']=t.splitlines()[0].strip();d['id']=re.search(r'CLI.ALE.(\d+)',t)[1]
 related=bool(re.search(r'土地管理法.{0,40}(?:第(?:七十[六七八]|7[678])条)|非法占|违法占|退还非法|未经批准.{0,12}占用|未依法取得用地许可',t))
 if re.search(r'不予(?:行政)?处罚|不予以行政处罚|不予处罚',t):decision='删除';reason='本件作出不予处罚决定，不属于实际行政处罚'
 elif i in [14,15,16,8,182]:decision='删除';reason='本次处罚为施工或规划违法，占地仅为背景或现场描述'
 elif i in [134,228,549,550,604,678,888,1123]:decision='删除';reason='土地闲置、改变已批用途或临时用地到期不归还，非未经批准非法占地处罚'
 elif related:decision='保留';reason='正文载明非法占地事实或退地处罚，适用土地管理法非法占地条款'
 else:decision='删除';reason='正文未证实本次处罚属于非法占用土地'
 d.update(decision=decision,reason=reason)
(O/'决定.json').write_text(json.dumps(ds,ensure_ascii=False),'utf8')
print(collections.Counter(d['decision'] for d in ds))
for d in ds:
 if d['decision']=='保留':print(d['index'],d['title'])
