from pathlib import Path
import json,re,argparse
from collections import defaultdict
ROOT=Path(__file__).resolve().parents[1]

def refine(year):
    rows=json.loads((ROOT/f'data/报名{year}候选.json').read_text(encoding='utf-8'))
    old=json.loads((ROOT/f'data/报名{year}单元格输入.json').read_text(encoding='utf-8'))
    cells=json.loads((ROOT/f'data/报名{year}单元格.json').read_text(encoding='utf-8'))
    index={r['id']:r for r in old};count=0;pending=0
    by_location=defaultdict(list)
    for k,v in cells.items():
        if k in index:by_location[(index[k]['page'],index[k]['column'])].append((v,index[k]))
    for r in rows:
        candidates=[(v,old_r) for v,old_r in by_location[(r['page'],r['column'])] if abs(sum(old_r['y'])-sum(r['y']))<8]
        if not candidates:pending+=1;continue
        c,old_r=candidates[0]
        cn=re.sub(r'\s+','',c['name']);cs=re.sub(r'\s+','',c['school'])
        r['cell_reading']=c
        if re.fullmatch(r'[\u3400-\u9fff·]{2,6}\d*',cn) and (r['cell_recovery'] or c['name_confidence']>r['confidence']):
            r['name']=re.sub(r'\d+$','',cn);r['raw_name']=cn;r['confidence']=c['name_confidence']
        if cs and (r['cell_recovery'] or c['school_confidence']>=.96):r['school']=cs
        name_agrees=r['name'] in r['name_variants'] and r['name']==re.sub(r'\d+$','',cn)
        school_agrees=cs in r['school_variants']
        r['identity_fields_consistent']=name_agrees and school_agrees and min(r['confidence'],c['name_confidence'],c['school_confidence'])>=.96
        r['review']+='；姓名和学校单元格另行复识'
        count+=1
    (ROOT/f'data/报名{year}候选.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('单元格校对',year,count,'新增定位待复核',pending,'一致',sum(r['identity_fields_consistent'] for r in rows))
    return rows
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,required=True);args=ap.parse_args();refine(args.year)
