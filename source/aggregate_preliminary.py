"""合并广东初赛各年正式来源；不把省初赛奖项混入高联奖项。"""
from pathlib import Path
import json,hashlib,fitz
ROOT=Path(__file__).resolve().parents[1]

def main():
    native=json.loads((ROOT/'data/广东初赛记录.json').read_text(encoding='utf-8'))
    records=[r for r in native['records'] if r['year']==2024]
    sources=[s for s in native['sources'] if s['year']==2024]
    meta=json.loads((ROOT/'data/广东初赛补充来源.json').read_text(encoding='utf-8'))
    for year in [2025,2026]:
        report=json.loads((ROOT/f'evidence/初赛{year}扫描核对.json').read_text(encoding='utf-8'))
        assert not report['missing_pages']
        rs=json.loads((ROOT/f'data/初赛{year}候选.json').read_text(encoding='utf-8'))
        assert all(r['award'] in ['一等奖','二等奖','三等奖'] for r in rs),'必须处理仍未辨认的奖项'
        m=next(s for s in meta if s['year']==year and s['pages']>1)
        pdf=ROOT/m['local']
        sources.append(dict(id=f'广东初赛-{year}',year=year,kind='广东初赛',status='公示',title=m['title'],article=m['article'],url=m['url'],
                            local=m['local'],sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),bytes=pdf.stat().st_size,
                            pages=len(fitz.open(pdf)),retrieved='2026-11-02',publisher='广东省数学会（中山大学数学学院网站）',
                            originNote='广东省初赛官方公示，区别于高联；扫描件逐行锚点提取，姓名待核者单独标记'))
        records.extend(rs)
    (ROOT/'data/广东初赛记录.json').write_text(json.dumps(dict(records=records,sources=sources),ensure_ascii=False,indent=2),encoding='utf-8')
    print('广东初赛合计',len(records),'条，来源',len(sources))
if __name__=='__main__':main()
