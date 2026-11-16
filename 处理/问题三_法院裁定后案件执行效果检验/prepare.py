"""标准化记录、去重、S2阈值分类和CLCD最近邻对齐。"""
from pathlib import Path
import csv,json
import numpy as np
import openpyxl,rasterio
from rasterio.warp import reproject,Resampling,transform
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题三"
def csvout(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
    raw=ROOT/'data/raw';out=ROOT/'data/cleaned';(out/'aligned').mkdir(exist_ok=True)
    book=openpyxl.load_workbook(raw/'references/变化检测指标.xlsx',read_only=True,data_only=True)
    values=list(book.active.values);records=[dict(zip(values[0],r)) for r in values[1:]]
    assert len(records)==23
    csvout(out/'原始23条记录标准化.csv',records)
    assert records[2]['位置']==records[3]['位置'] and records[2]['前影像ID']==records[3]['前影像ID'] and records[2]['后影像ID']==records[3]['后影像ID']
    unique=[r for r in records if r['是否重复']!='是'];assert len(unique)==22
    csvout(out/'唯一地点22条.csv',unique)
    metadata=[]
    for rec in unique:
        i=int(rec['序号']);bands=[];first=None
        for phase,datekey in [('before','前影像日期'),('after','后影像日期')]:
            with rasterio.open(raw/'sentinel'/f'{i:02}_{phase}_stack.tif') as ds:
                if first is None:first=(ds.transform,ds.crs,ds.shape)
                assert first==(ds.transform,ds.crs,ds.shape)
                a=ds.read().astype(float);names=ds.descriptions
                blue,g,r,n,s=[a[names.index(k)] for k in ['B02','B03','B04','B08','B11']]
                valid=np.all(np.isfinite(np.stack([blue,g,r,n,s]))&(np.stack([blue,g,r,n,s])>0),axis=0)
                year=int(rec[datekey][:4])
                if year>=2017 and 'SCL' in names:valid &= ~np.isin(a[names.index('SCL')],[0,1,3,8,9,10,11])
                nd=lambda x,y:np.divide(x-y,x+y,out=np.zeros_like(x),where=(x+y)!=0)
                built=(nd(s,n)>0)&(nd(n,r)<.3)&(nd(g,s)<0)
                land=np.zeros(ds.shape,dtype='uint8')
                with rasterio.open(raw/'clcd'/f'CLCD_{year}_佛山样本窗口.tif') as src:
                    reproject(rasterio.band(src,1),land,src_transform=src.transform,src_crs=src.crs,dst_transform=ds.transform,dst_crs=ds.crs,src_nodata=0,dst_nodata=0,resampling=Resampling.nearest)
                valid &= land>0;bands.extend([built.astype('uint8'),land,valid.astype('uint8')])
                profile=ds.profile.copy();profile.update(count=6,dtype='uint8',nodata=None,compress='deflate')
                lon,lat=transform(ds.crs,'EPSG:4326',[(ds.bounds.left+ds.bounds.right)/2],[(ds.bounds.top+ds.bounds.bottom)/2])
                metadata.append({'序号':i,'时期':phase,'日期':rec[datekey],'CLCD年份':year,'CRS':str(ds.crs),'变换':list(ds.transform),'推定中心经度':lon[0],'推定中心纬度':lat[0]})
        with rasterio.open(out/'aligned'/f'{i:02}_aligned.tif','w',**profile) as dst:
            dst.write(np.stack(bands));dst.descriptions=('S2_before_built','CLCD_before_class','before_valid','S2_after_built','CLCD_after_class','after_valid')
    (out/'空间与时间对齐.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print('标准化23条、去重22地点，输出22个六波段对齐栅格。')
if __name__=='__main__':main()
