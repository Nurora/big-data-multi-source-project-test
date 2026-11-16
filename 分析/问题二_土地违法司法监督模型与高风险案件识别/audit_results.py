from pathlib import Path
import csv,json,hashlib,zipfile,xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[2] / "支撑文件" / "问题二"
N={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def main():
 rows=[]
 for f in sorted((ROOT/'data').rglob('*.xlsx')):
  with zipfile.ZipFile(f) as z:
   wb=E.fromstring(z.read('xl/workbook.xml'));rels=E.fromstring(z.read('xl/_rels/workbook.xml.rels'));lookup={e.get('Id'):e.get('Target') for e in rels}
   for sh in wb.findall('.//m:sheet',N):
    rid=sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id');target=lookup[rid];target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
    xml=E.fromstring(z.read(target));rr=[r for r in xml.findall('.//m:row',N) if any(c.find('m:v',N) is not None or c.find('m:is',N) is not None for c in r.findall('m:c',N))]
    rows.append({'文件':f.relative_to(ROOT).as_posix(),'工作表':sh.get('name'),'非空行数_含表头':len(rr),'扣除一行表头':max(0,len(rr)-1)})
 with (ROOT/'docs/数据表核验.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (ROOT/'data/integrated/现有数据核验.json').write_text(json.dumps({'说明':'按实际非空行统计，表头或注释多行时需人工核对；不重新生成原评分','最终成果口径':{'完整评分记录':616,'候选记录':101,'候选去重案号':98},'表结构':rows},ensure_ascii=False,indent=2),encoding='utf-8')
 checks=[]
 for f in sorted(ROOT.rglob('*')):
  if not f.is_file() or '__pycache__' in f.parts or f.name=='提交文件校验.csv':continue
  checks.append([f.relative_to(ROOT).as_posix(),f.stat().st_size,hashlib.sha256(f.read_bytes()).hexdigest()])
 with (ROOT/'docs/提交文件校验.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['相对路径','字节数','SHA256']);w.writerows(checks)
 print('核验完成：',len(rows),'张工作表，',len(checks),'个文件。')
if __name__=='__main__':main()
