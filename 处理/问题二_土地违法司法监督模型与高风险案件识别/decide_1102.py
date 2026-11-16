import sys,json,re,collections,difflib
sys.path.insert(0,'scripts');import review_1102 as m
D=json.loads((m.O/'审查决定.json').read_text('utf8'));old=json.loads((m.O/'现有目录.json').read_text('utf8'));idx={d['id']:d for d in old};seen={};flags=[]
out={'553180009':'仅殡葬管理拆墓决定，不是土地用途行政处罚','554052378':'责令改正通知书经行政判决确认后的执行，非行政处罚审查','553026463':'责令改正通知书经行政判决确认后的执行，非行政处罚审查','553595374':'责令改正通知书经行政判决确认后的执行，非行政处罚审查','560863946':'公租房退出和租金执行','575712782':'财政补助资金追回','112217713':'交地行政决定组织执行','561056170':'正文未披露土地违法事实或处罚内容，证据不足'}
for d in D:
 if d['decision']!='待复核':continue
 if d['id'] in out:d.update(decision='不相关删除',reason=out[d['id']]);continue
 if re.search('审复|执复|执异',d['case']):d.update(decision='不相关删除',reason='复议/执行异议程序，超出既有研究范围');continue
 if not d['evidence'] or '处罚' not in d['core']:flags.append(d['id']);continue
 d.update(decision='新增保留',reason='广东土地违法行政处罚非诉执行审查；正文有土地事实、处罚和审查事项')
 k=m.norm(d['case']) if d['case'] else d['id'];match=idx.get(d['case_match']) or seen.get(k)
 if match:
  r=difflib.SequenceMatcher(None,m.norm(d['core']),m.norm(match['core']),autojunk=False).ratio()
  if r<.95:flags.append((d['id'],match['id'],r));d['decision']='待复核';continue
  d.update(decision='重复剔除',duplicate=match['id'],reason=f'同案号及正文一致或高度相似({r:.6f})，保留{match["id"]}')
 else:seen[k]=d
m.save('审查决定.json',D);print(collections.Counter(d['decision'] for d in D));print('FLAGS',flags)
