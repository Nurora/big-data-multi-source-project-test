from pathlib import Path
import json,csv,collections as C
from PIL import Image,ImageDraw,ImageFont
P=Path('reports/裁判文书初步分析_20261102');S=json.loads((P/'统计摘要.json').read_text('utf8'));im=Image.new('RGB',(1500,1550),'#eef3f8');d=ImageDraw.Draw(im);fp='C:/Windows/Fonts/msyh.ttc';font=ImageFont.truetype(fp,22);small=ImageFont.truetype(fp,18);big=ImageFont.truetype(fp,38)
d.text((45,32),'8,705份土地违法裁判文书 · 初步画像',font=big,fill='#17364b');d.text((48,95),'2012—2026年公开样本  |  2026-11-02  |  文书统计与规则候选',font=font,fill='#486275')
def panel(x,y,w,h,title,items):
 d.rounded_rectangle((x,y,x+w,y+h),radius=16,fill='white');d.text((x+20,y+18),title,font=font,fill='#17364b');items=list(items);mx=max(v for k,v in items);step=min(40,(h-70)/len(items))
 for j,(label,v) in enumerate(items):
  yy=y+62+j*step;d.text((x+20,yy),str(label),font=small,fill='#17364b');start=x+210;bw=(w-320)*v/mx;d.rounded_rectangle((start,yy+3,start+max(1,bw),yy+24),radius=3,fill='#287c84');d.text((start+bw+8,yy),str(v),font=small,fill='#17364b')
panel(40,155,1420,440,'年份分布（按审结日期，缺失按案号辅助归年）',sorted(S['years'].items()))
panel(40,620,695,425,'法院城市前8（不等于涉案地）',list(S['court_cities'].items())[:8])
panel(760,620,700,425,'主文结果（规则分类）',S['outcomes'].items())
panel(40,1070,695,360,'被执行主体（规则候选）',list(S['respondent_types'].items())[:6])
panel(760,1070,700,360,'事实段地类提及（非互斥）',[(k[5:],v) for k,v in S['bool_counts'].items() if k.startswith('land_')])
d.text((45,1460),'准予执行不等于实际履行；样本数量不等于违法发生率；用途、地类及理由需抽样复核。',font=font,fill='#486275');im.save(P/'分析概览.png')
rs=list(csv.DictReader((P/'全量特征表_规则候选.csv').open(encoding='utf-8-sig')))
assert len(rs)==8705 and len({r['id'] for r in rs})==8705
assert sum(S['years'].values())==sum(S['outcomes'].values())==sum(S['court_cities'].values())==8705
assert not S['parse_errors'] and not S['catalog_hash_mismatches']
print('CHECKS PASSED',S['outcomes']);print('same name groups',json.loads((P/'补充统计.json').read_text('utf8'))['multiple_name_groups'])
