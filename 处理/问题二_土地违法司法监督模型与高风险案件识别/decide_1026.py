import pathlib,json,re,collections
O=pathlib.Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"/'reports'/'1026审查'
D=json.loads((O/'候选原文.json').read_text('utf-8'))
manual_keep={'103519645':'非法出租划拨国有土地使用权处罚','42756758':'基本农田上违建拆除、恢复种植条件及罚款处罚','111276492':'没收非法出租地块所得及罚款的土地处罚','20899547':'没收非法出租地块所得及罚款的土地处罚','19459481':'原文标题明确土地行政处罚，主文准予执行该处罚','565023820':'未经批准占用林地建设，责令恢复林地现状','115782149':'未办理林地征占许可实施建设，责令恢复林地原状','309134908':'非法占6333平方米耕地并处罚款','85265492':'未办理征占林地许可建设，责令恢复原状'}
manual_out={'52071082':'虽有违法用地背景，本次仅申请执行非法开采地下热水处罚','42362229':'决定书虽名土地处罚，实际仅处罚无证开采矿产资源','45528704':'字段错误，正文为新疆乌鲁木齐法院案件，非广东','309467367':'字段错误，正文为吉林长春九台法院案件，非广东','565080202':'国有土地租赁行政协议解除、腾退执行','559863827':'国有土地租赁行政协议履约执行','112130470':'非法采矿处罚，偷采现场复绿不改变矿产处罚性质','105404591':'标题与正文不符，实际为交通运输处罚'}
for d in D:
 if d['duplicate']:
  d.update(decision='重复剔除',reason=d.get('reason') or '与现有文书法宝编号或规范化正文相同');continue
 b=d['core'];res=d['result'];reason='';decision=''
 if d['id'] in manual_out:decision='不相关删除';reason=manual_out[d['id']]
 elif re.search(r'交出被征土地|交出土地决定书|交出土地使用权决定书|交地通知书|征收补偿决定|补偿安置决定',res):decision='不相关删除';reason='征收补偿、征地交付执行，不是违法用地行政处罚'
 elif re.search(r'征缴土地闲置费|土地闲置费',res):decision='不相关删除';reason='土地闲置费征缴，不是土地违法行政处罚'
 elif re.search(r'补缴土地差价|土地出让金|土地出让价款',res):decision='不相关删除';reason='地价征缴执行，不是土地违法行政处罚'
 elif d['id'] in manual_keep:decision='新增保留';reason=manual_keep[d['id']]
 elif d['evidence'] and re.search(r'处罚',b) and re.search(r'(不准予|不予|准予|准许|不准许).{0,12}(强制)?执行',res):decision='新增保留';reason='广东法院对违法用地（含擅自改变林地用途）行政处罚的准予或不准予执行裁定'
 elif re.search(r'矿产资源法|矿产资源行政处罚|采矿许可证|非法采矿|偷采现场',b):decision='不相关删除';reason='矿产资源开采处罚，不是土地违法行政处罚'
 elif re.search(r'滥伐|盗伐|林木采伐|野生动物|猎获物|收缴实物：鸟',b):decision='不相关删除';reason='林木采伐或野生动物处罚，不是林地用途或土地违法处罚'
 elif re.search(r'城乡规划法|城乡规划条例',b):decision='不相关删除';reason='仅有建设规划违法处罚，无土地违法处罚事实'
 elif re.search(r'安全生产法|特种作业|建设工程质量管理条例|价格法|燃气经营|水质保护条例|河道采砂管理条例|严禁卖淫嫖娼',b):decision='不相关删除';reason='安全生产、工程质量、价格、燃气、环保、水务或治安处罚，与土地违法处罚无关'
 else:decision='证据不足排除';reason='原文仅载处罚决定编号及执行结论，未披露土地违法事实、处罚内容或依据，无法确认符合纳入标准'
 d.update(decision=decision,reason=reason)
(O/'审查决定.json').write_text(json.dumps(D,ensure_ascii=False,indent=2),'utf-8')
print(collections.Counter(d['decision'] for d in D))
for d in D:
 if d['decision']=='证据不足排除':print(d['id'],d['title'])
print('SUSPICIOUS_KEEP')
for d in D:
 if d['decision']=='新增保留' and (not d['evidence'] or re.search(r'矿产资源法|交出土地|安全生产法|野生动物|非法采矿|土地租赁合同',d['core'])):print(d['id'],d['reason'],d['result'][:100])
