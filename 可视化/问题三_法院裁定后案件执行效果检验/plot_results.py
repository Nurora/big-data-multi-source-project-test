"""由最终关联表和对齐栅格生成四类结果图。"""
from pathlib import Path
import os,csv
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题三"
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import numpy as np,rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch
from matplotlib.colors import ListedColormap
for path in ['C:/Windows/Fonts/msyh.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']:
    if Path(path).exists():font_manager.fontManager.addfont(path);plt.rcParams['font.family']=font_manager.FontProperties(fname=path).get_name();break
plt.rcParams.update({'axes.unicode_minus':False,'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
OUT=ROOT/'visualization/figures';OUT.mkdir(exist_ok=True)
def readrows():
    rows=list(csv.DictReader((ROOT/'data/integrated/逐案跨源整改核查.csv').open(encoding='utf-8-sig')))
    for r in rows:
        r['序号']=int(r['序号'])
        for k in list(r):
            if k.endswith('_m2'):r[k]=int(r[k])
    return rows
def save(fig,name):
    fig.savefig(OUT/(name+'.png'),dpi=180,facecolor='white');fig.savefig(OUT/(name+'.svg'),facecolor='white');plt.close(fig)
def main():
    rows=readrows();groups=[('疑似已拆除','疑似拆除','#27816a'),('未发现明显变化','未见明显变化','#607f9a'),('疑似新增建设','疑似新增','#d89037'),('无法判定（水体/水位变化）','水体干扰','#ac648f')]
    ordered=[r for g,_,_ in groups for r in rows if r['原人工判读']==g]
    fig,ax=plt.subplots(figsize=(11,6));fig.subplots_adjust(left=.23,right=.9,top=.86,bottom=.13)
    ax.set_title('佛山监测地点整改迹象分类',fontsize=19,pad=22)
    counts=[sum(r['原人工判读']==g for r in rows) for g,_,_ in groups]
    ax.barh(range(4),counts,color=[c for _,_,c in groups],height=.58);ax.set_yticks(range(4),[l for _,l,_ in groups]);ax.invert_yaxis();ax.set_xlim(0,18);ax.set_xticks([0,5,10,15]);ax.set_xlabel('地点数（去重后 n=22）');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    for j,n in enumerate(counts):ax.text(n+.25,j,f'{n}  ({n/22:.1%})',va='center',fontsize=12)
    save(fig,'图1_整改迹象分类')
    fig,axes=plt.subplots(1,2,figsize=(15,11),gridspec_kw={'width_ratios':[1.2,1]});fig.subplots_adjust(left=.19,right=.97,top=.88,bottom=.09,wspace=.25)
    fig.suptitle('逐地点建成候选变化与不透水面响应',fontsize=20,y=.97)
    y=np.arange(22)
    axes[0].barh(y,[-r['S2减少_m2']/10000 for r in ordered],color='#27816a',height=.65,label='S2减少');axes[0].barh(y,[r['S2新增_m2']/10000 for r in ordered],color='#d89037',height=.65,label='S2新增')
    axes[0].set_yticks(y,[f"#{r['序号']:02} {r['简称']}" for r in ordered]);axes[0].set_xlabel('减少 ← 面积（公顷）→ 新增')
    for key,col,marker,lab in [('S2净变化_m2','#4d7597','o','S2净变化'),('CLCD净变化_m2','#a85d8e','D','CLCD净变化')]:axes[1].scatter([r[key]/10000 for r in ordered],y,s=32,c=col,marker=marker,label=lab,zorder=3)
    for j,r in enumerate(ordered):axes[1].plot([r['S2净变化_m2']/10000,r['CLCD净变化_m2']/10000],[j,j],c='#c9d2db',lw=1)
    axes[1].set_yticks(y,[f"#{r['序号']:02}" for r in ordered]);axes[1].set_xlabel('净变化（公顷）')
    for a in axes:
        a.invert_yaxis();a.axvline(0,c='#718096',lw=.8);a.grid(axis='x',alpha=.12);a.legend(loc='upper left',bbox_to_anchor=(0,1.05),frameon=False,ncol=2,fontsize=9)
        for boundary in [4.5,19.5,20.5]:a.axhline(boundary,c='#c0cad6',ls='--',lw=.8)
    save(fig,'图2_逐地点增减变化')
    cmap=ListedColormap(['white','#e4e9ef','#6987a3','#27816a','#d89037'])
    for page,ids in enumerate([[8,3,7,20],[21,19,17]],1):
        fig,axes=plt.subplots(len(ids),4,figsize=(16,4*len(ids)+1.8),squeeze=False);fig.subplots_adjust(left=.055,right=.98,top=.89,bottom=.055,hspace=.36,wspace=.14)
        fig.suptitle(f'典型地点前后影像与地表覆盖转移（{page}/2）',fontsize=20,y=.985)
        fig.legend([Patch(color=c) for c in ['#6987a3','#27816a','#d89037','#e4e9ef']],['持续建成/不透水','减少','新增','持续非建成/非不透水'],loc='upper center',bbox_to_anchor=(.52,.96),ncol=4,frameon=False,fontsize=9)
        for j,i in enumerate(ids):
            r=next(r for r in rows if r['序号']==i)
            with rasterio.open(ROOT/'data/cleaned/aligned'/f'{i:02}_aligned.tif') as ds:
                a=ds.read();yy,xx=np.indices(ds.shape);dist=((xx+.5-ds.width/2)*ds.transform.a)**2+((yy+.5-ds.height/2)*ds.transform.e)**2
            m=(dist<=200**2)&(a[2]>0)&(a[5]>0)
            rgb=[]
            for phase in ['before','after']:
                with rasterio.open(ROOT/'data/raw/sentinel'/f'{i:02}_{phase}_stack.tif') as ds:rgb.append(np.moveaxis(ds.read([3,2,1]).astype(float),0,2))
            vals=np.concatenate([x[m] for x in rgb]);lo=np.percentile(vals,2,axis=0);hi=np.percentile(vals,98,axis=0)
            for k,img in enumerate(rgb):
                img=np.clip((img-lo)/np.maximum(hi-lo,1),0,1);img[~m]=1;axes[j,k].imshow(img,extent=[-500,500,-500,500],interpolation='nearest')
                axes[j,k].set_title(f"#{i:02} {r['简称']} {'前期' if k==0 else '后期'}\n{r['前影像日期' if k==0 else '后影像日期']}",fontsize=10)
            for k,p,q in [(2,a[0]>0,a[3]>0),(3,a[1]==8,a[4]==8)]:
                z=np.where(m,np.where(p&~q,3,np.where(~p&q,4,np.where(p&q,2,1))),0)
                axes[j,k].imshow(z,cmap=cmap,vmin=0,vmax=4,extent=[-500,500,-500,500],interpolation='nearest')
                axes[j,k].set_title(('S2建成候选转移' if k==2 else 'CLCD不透水转移')+f"\n减少 {int((m&p&~q).sum())*100:,} / 新增 {int((m&~p&q).sum())*100:,} m²",fontsize=9)
            for ax in axes[j]:ax.set_xlim(-220,220);ax.set_ylim(-220,220);ax.set_xticks([-200,0,200]);ax.set_yticks([-200,0,200]);ax.tick_params(labelsize=8)
        fig.text(.055,.018,'坐标：相对监测中心距离（米）   监测半径：200米   白色：范围外或无效像元',fontsize=9,color='#555555')
        save(fig,f'图3_典型地点空间转移_{page}')
    headers=['地点','目视初判','S2减少\n(m²)','S2新增\n(m²)','S2净变化\n(m²)','CLCD减少\n(m²)','跨源核查分类']
    cells=[[f"#{r['序号']:02} {r['简称']}",r['初判类别'],f"{r['S2减少_m2']:,}",f"{r['S2新增_m2']:,}",f"{r['S2净变化_m2']:+,}",f"{r['CLCD减少_m2']:,}",r['跨源核查结果'].replace('疑似拆除与周边新增并存','疑似拆除伴监测圆净增')] for r in ordered]
    fig,ax=plt.subplots(figsize=(18,11));fig.subplots_adjust(left=.025,right=.975,top=.9,bottom=.035);ax.axis('off');fig.suptitle('逐地点整改线索与跨源核查结果',fontsize=21,y=.97)
    t=ax.table(cellText=cells,colLabels=headers,colWidths=[.17,.12,.1,.1,.11,.1,.3],cellLoc='center',bbox=[0,0,1,1]);t.auto_set_font_size(False);t.set_fontsize(9)
    for (rr,cc),cell in t.get_celld().items():
        cell.set_linewidth(.4);cell.set_edgecolor('#d7dfe9')
        if rr==0:cell.set_facecolor('#24485f');cell.set_text_props(color='white',fontweight='bold');cell.set_height(cell.get_height()*1.4)
        else:cell.set_facecolor('#f0f5f8' if rr%2 else 'white')
    save(fig,'图4_逐地点整改核查矩阵')
    print('已生成四类结果图：5幅PNG及5幅SVG。')
if __name__=='__main__':main()
