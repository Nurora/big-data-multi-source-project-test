"""同一监测范围内计算两源状态、跨期变化、逐案整改线索与范围敏感性。"""
from pathlib import Path
import csv,json
import numpy as np,rasterio
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题三"
SHORT={1:'季华路地块',2:'华南广场东侧',3:'群安公寓西南侧',5:'龙津小学西侧',6:'威达斯北侧',7:'隆新旧村北侧',8:'梧村南厅巷',9:'紫南澳边村',10:'紫南村头村',11:'贤德公寓北侧',12:'格塘村禅港西路',13:'石井村口',14:'东平路地块',15:'星光厂大雾岗',16:'白坭大滘沙',17:'大塘梅花村',18:'乐平少羊西村',19:'黄塘梁家晒场',20:'下灶白沙尾',21:'下灶街前塘',22:'土塘下新村',23:'永平中社'}
def csvout(name,rows):
    with (ROOT/'data/integrated'/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    records=list(csv.DictReader((ROOT/'data/cleaned/唯一地点22条.csv').open(encoding='utf-8-sig')))
    rows=[];periods=[];sens=[];groups={}
    for rec in records:
        i=int(rec['序号'])
        with rasterio.open(ROOT/'data/cleaned/aligned'/f'{i:02}_aligned.tif') as ds:
            a=ds.read();yy,xx=np.indices(ds.shape);dist=((xx+.5-ds.width/2)*ds.transform.a)**2+((yy+.5-ds.height/2)*ds.transform.e)**2
        p,c,v,q,d,w=a;p=p.astype(bool);q=q.astype(bool);c=c==8;d=d==8
        for radius in [150,200,250]:
            m=(dist<=radius**2)&(v>0)&(w>0);count=lambda z:int((m&z).sum())*100
            for phase,built,land in [('前期',p,c),('后期',q,d)]:
                counts=[count(built&land),count(built&~land),count(~built&land),count(~built&~land)]
                assert sum(counts)==int(m.sum())*100
                sens.append({'序号':i,'时期':phase,'半径_m':radius,'共同有效面积_m2':int(m.sum())*100,'差异面积_m2':counts[1]+counts[2],'差异比例':(counts[1]+counts[2])/(int(m.sum())*100)})
                if radius==200:periods.append({'序号':i,'时期':phase,'共同有效面积_m2':int(m.sum())*100,'共同建成_m2':counts[0],'仅S2建成_m2':counts[1],'仅CLCD不透水_m2':counts[2],'共同非建成_m2':counts[3],'IoU':counts[0]/sum(counts[:3]) if sum(counts[:3]) else ''})
            if radius!=200:continue
            new=~p&q;loss=p&~q;cn=~c&d;cl=c&~d
            parts=[count(new&cn),count(new&c&d),count(new&~c&~d),count(new&cl)]
            loss_parts=[count(loss&cl),count(loss&c&d),count(loss&~c&~d),count(loss&cn)]
            assert sum(parts)==count(new) and sum(loss_parts)==count(loss)
            label=rec['人工复核'];groups[label]=groups.get(label,0)+1
            state={'疑似已拆除':'疑似拆除','未发现明显变化':'未见明显变化','疑似新增建设':'疑似新增建设','无法判定（水体/水位变化）':'水体干扰'}[label]
            # Evidence categories describe monitoring-circle observations, not legal completion.
            evidence='水体干扰' if '无法判定' in label else ('疑似拆除伴监测圆净减' if label=='疑似已拆除' and count(loss)>count(new) else '疑似拆除伴监测圆净增' if label=='疑似已拆除' else '新增建设线索' if label=='疑似新增建设' else '未见明确拆除线索')
            rows.append({'序号':i,'简称':SHORT[i],'位置':rec['位置'],'区域':rec['区域'],'处罚日期':rec['处罚日期'],'目标核查日期':rec['核查日期'],'前影像日期':rec['前影像日期'],'后影像日期':rec['后影像日期'],'原人工判读':label,'初判类别':state,'跨源核查结果':evidence,'共同有效面积_m2':int(m.sum())*100,'S2新增_m2':count(new),'S2减少_m2':count(loss),'S2净变化_m2':count(new)-count(loss),'CLCD新增_m2':count(cn),'CLCD减少_m2':count(cl),'CLCD净变化_m2':count(cn)-count(cl),'两源同步新增_m2':parts[0],'新增中CLCD持续不透水_m2':parts[1],'新增中CLCD持续非不透水_m2':parts[2],'新增中CLCD反向变化_m2':parts[3],'两源同步减少_m2':loss_parts[0],'减少中CLCD持续不透水_m2':loss_parts[1],'减少中CLCD持续非不透水_m2':loss_parts[2],'减少中CLCD反向新增_m2':loss_parts[3]})
    assert len(rows)==22 and groups=={'未发现明显变化':15,'疑似已拆除':5,'无法判定（水体/水位变化）':1,'疑似新增建设':1}
    csvout('逐案跨源整改核查.csv',rows);csvout('逐期空间关联.csv',periods);csvout('监测范围敏感性.csv',sens)
    csvout('初判分类统计.csv',[{'类别':k,'地点数':v,'比例':v/22} for k,v in groups.items()])
    (ROOT/'data/integrated/一致性核验.json').write_text(json.dumps({'唯一地点数':len(rows),'逐期行数':len(periods),'敏感性行数':len(sens),'四类面积守恒':'通过','新增四组守恒':'通过','减少四组守恒':'通过','原标签统计':groups},ensure_ascii=False,indent=2),encoding='utf-8')
    print('输出22地点跨源核查、44期关联、132行敏感性和统计表。')
if __name__=='__main__':main()
