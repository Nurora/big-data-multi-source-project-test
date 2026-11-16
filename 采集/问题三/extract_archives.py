"""从用户提供的三个本地压缩包提取研究样本，不进行网络采集。"""
from pathlib import Path
import argparse,zipfile,hashlib,csv,json,shutil
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import Window,from_bounds

ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题三"
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-dir',type=Path,default=ROOT.parents[1]);args=ap.parse_args()
    raw=ROOT/'data/raw';raw.mkdir(exist_ok=True)
    for sub in ['sentinel','clcd','references']:(raw/sub).mkdir(exist_ok=True)
    names=['广东建设用地数据.zip','非法违规建筑影像判读.zip','非法违规建筑影像判读(1).zip']
    zz={n:zipfile.ZipFile(args.source_dir/n) for n in names}
    manifest=[];archives=[]
    for n,z in zz.items():
        archives.append({'文件':n,'字节':(args.source_dir/n).stat().st_size,'SHA256':sha(args.source_dir/n)})
        for inf in z.infolist():
            if inf.is_dir():continue
            manifest.append({'源压缩包':n,'成员':inf.filename,'原始字节':inf.file_size,'CRC32':f'{inf.CRC:08x}','保留路径':'','处理':''})
    small,big=zz[names[1]],zz[names[2]]
    shared={i.filename for i in small.infolist() if not i.is_dir()}&{i.filename for i in big.infolist() if not i.is_dir()}
    diff=[n for n in shared if hashlib.sha256(small.read(n)).digest()!=hashlib.sha256(big.read(n)).digest()]
    assert not diff,'两个影像包同名成员内容不同，请先人工确认版本'
    selected=[]
    for n in big.namelist():
        base=Path(n).name
        if base.endswith('_stack.tif') and not base.startswith('04_'):
            dest=raw/'sentinel'/base;dest.write_bytes(big.read(n));selected.append((names[2],n,dest))
        elif base.endswith('_scene.txt') and not base.startswith('04_'):
            dest=raw/'sentinel'/base;dest.write_bytes(big.read(n));selected.append((names[2],n,dest))
        elif base.endswith(('.docx','.xlsx')):
            dest=raw/'references'/base;dest.write_bytes(big.read(n));selected.append((names[2],n,dest))
    bounds=[]
    z=zz[names[0]]
    cropmeta=[]
    for year in range(2016,2022):
        n=next(n for n in z.namelist() if n.endswith(f'_{year}.tif'))
        # MemoryFile retains original metadata while avoiding a second full-province copy.
        payload=z.read(n)
        with rasterio.io.MemoryFile(payload) as mem,mem.open() as src:
            bb=[]
            for p in sorted((raw/'sentinel').glob('*_stack.tif')):
                with rasterio.open(p) as ds:bb.append(transform_bounds(ds.crs,src.crs,*ds.bounds,densify_pts=21))
            left=min(b[0] for b in bb);bottom=min(b[1] for b in bb);right=max(b[2] for b in bb);top=max(b[3] for b in bb)
            w=from_bounds(left,bottom,right,top,src.transform)
            col=max(0,int(np.floor(w.col_off))-2);row=max(0,int(np.floor(w.row_off))-2)
            width=min(src.width-col,int(np.ceil(w.col_off+w.width))+2-col);height=min(src.height-row,int(np.ceil(w.row_off+w.height))+2-row)
            win=Window(col,row,width,height);a=src.read(window=win)
            prof=src.profile.copy();prof.update(width=width,height=height,transform=src.window_transform(win),compress='deflate')
            dest=raw/'clcd'/f'CLCD_{year}_佛山样本窗口.tif'
            with rasterio.open(dest,'w',**prof) as dst:dst.write(a)
            cropmeta.append({'年份':year,'源成员':n,'源成员SHA256':hashlib.sha256(payload).hexdigest(),'行列窗口':[row,col,height,width],'源CRS':str(src.crs),'输出':str(dest.relative_to(ROOT)),'抽样方式':'原网格矩形窗口；未重投影、未改分类'})
            selected.append((names[0],n,dest))
    n=next(n for n in z.namelist() if n.endswith('说明.txt'));dest=raw/'references/CLCD原始说明.txt';dest.write_bytes(z.read(n));selected.append((names[0],n,dest))
    selected_map={(a,b):(str(p.relative_to(ROOT)).replace('\\','/'),sha(p)) for a,b,p in selected}
    for r in manifest:
        key=(r['源压缩包'],r['成员'])
        if key in selected_map:r['保留路径']=selected_map[key][0];r['处理']='原样保留' if '/clcd/' not in r['保留路径'] else '原网格窗口抽样'
        elif r['源压缩包']==names[1]:r['处理']='与大包共同文件内容一致，去重不另存'
        elif '/04_' in r['成员']:r['处理']='#4与#3同址重复，不另存影像'
        else:r['处理']='与本研究时段或最终结果无关，不保留'
    with (raw/'压缩包成员索引.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(manifest[0]));w.writeheader();w.writerows(manifest)
    (raw/'来源校验与窗口.json').write_text(json.dumps({'压缩包':archives,'共同文件数':len(shared),'共同内容差异数':len(diff),'CLCD窗口':cropmeta,'原样文件及窗口SHA256':[{'路径':v[0],'SHA256':v[1]} for v in selected_map.values()]},ensure_ascii=False,indent=2),encoding='utf-8')
    print('已提取44期Sentinel裁片、6期CLCD原网格窗口及原报告/指标表，完成三个源包索引。')
if __name__=='__main__':main()
