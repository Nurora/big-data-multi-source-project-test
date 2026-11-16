"""将已筛选的两批文书安全归并；复制校验成功后删除原文件和空目录。"""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
TARGET=ROOT/'裁判文书_合并去重_2718份'
SOURCES=[ROOT/'pkulaw_20261021/裁判文书',ROOT/'pkulaw_1023/整理结果/新增裁判文书']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    root=ROOT.resolve();target=TARGET.resolve()
    assert target.parent==root
    entries=[]
    for source in SOURCES:
        source=source.resolve()
        assert source.is_relative_to(root) and source!=root
        assert source.is_dir() and not source.is_symlink()
        files=list(source.iterdir())
        assert all(p.is_file() and p.suffix.lower() in ('.doc','.docx') and not p.is_symlink() for p in files)
        entries.extend((p,sha(p)) for p in files)
    assert len(entries)==2718,len(entries)
    assert len({p.name for p,h in entries})==2718,'重名需核查，尚未移动'
    target.mkdir(exist_ok=True)
    assert not any(p.name not in {s.name for s,h in entries} for p in target.iterdir())
    for p,h in entries:
        dest=target/p.name
        if dest.exists():assert sha(dest)==h,'目标同名文件内容不一致'
        else:shutil.copy2(p,dest)
    assert len(list(target.iterdir()))==2718
    for p,h in entries:assert sha(target/p.name)==h
    report=ROOT/'reports/2718份文书归并清单.json'
    report.write_text(json.dumps([{'original':str(p),'file':str(target/p.name),'sha256':h} for p,h in entries],ensure_ascii=False,indent=2),'utf-8')
    for p,h in entries:
        assert p.resolve().parent in [s.resolve() for s in SOURCES]
        assert sha(p)==h and sha(target/p.name)==h
        p.unlink()
    for source in SOURCES:
        assert source.resolve().is_relative_to(root)
        assert not list(source.iterdir())
        source.rmdir()
    # 修正供后续处理使用的主目录中的文书路径。
    lookup={p.name:str(target/p.name) for p,h in entries}
    for meta in [ROOT/'pkulaw_20261021/最终目录数据.json',ROOT/'pkulaw_1023/整理结果/新增保留目录.json']:
        rows=json.loads(meta.read_text('utf-8'))
        for row in rows:
            if row.get('file'):
                row['file']=lookup[Path(row['file']).name]
        meta.write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
    # 只清理此前解析脚本创建的已确认空输出目录，不递归删除任何有内容目录。
    for p in [ROOT/'outputs/pkulaw_20261021',ROOT/'outputs']:
        if p.exists() and p.resolve().is_relative_to(root) and not any(p.iterdir()):p.rmdir()
    print(json.dumps({'folder':str(target),'documents':len(list(target.glob('*.doc*'))),'source_folders_removed':[str(s) for s in SOURCES],'hashes_verified':2718},ensure_ascii=False))
if __name__=='__main__':run()
