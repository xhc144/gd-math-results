"""按报名表原列提取，不以高中/初中或年级是否相符排除考生。"""
from pathlib import Path
from collections import Counter
import json,re,fitz,numpy as np,argparse
from parse_preliminary_scans import cell,clean
ROOT=Path(__file__).resolve().parents[1]

def parse(year,partial=False):
    meta=json.loads((ROOT/'data/报名来源清单.json').read_text(encoding='utf-8'))
    source=next(s for s in meta if s['year']==year)
    doc=fitz.open(ROOT/source['local']);rows=[];pages=[];missing=[]
    for ix,page in enumerate(doc):
        files=[ROOT/f'data/报名OCR/{year}-{v}/p{ix+1:03}.json' for v in ['clean','raw']]
        if not files[0].exists() or (not partial and not files[1].exists()):missing.append(ix+1);continue
        variants=[json.loads(f.read_text(encoding='utf-8')) for f in files if f.exists()]
        scale=variants[0]['scale'];width=page.rect.width*scale
        # 列区间来自已实际查看的原表表头，2020为左右两个独立表格。
        layouts=([(.05,.27,.35,.395,.442),(.506,.738,.820,.865,.932)] if year==2020 else [(.08,.572,.728,.782,.875)])
        page_count=0
        for column,coords in enumerate(layouts):
            if year==2020:s0,n0,n1,g0,g1=[v*width for v in coords]
            else:
                s0,n0,n1,g0,g1=[v*width for v in coords]
            anchors=[]
            for vi,v in enumerate(variants):
                for box,t,c in v['boxes']:
                    x=sum(p[0] for p in box)/4;y=sum(p[1] for p in box)/4;t=clean(t)
                    if n0+2<x<n1-2 and re.fullmatch(r'[\u3400-\u9fff·]{2,6}\d*',t) and t not in ['学生姓名','姓名','学校','性别','年级']:
                        old=next((a for a in anchors if abs(a['y']-y)<(8 if year==2020 else 13)),None)
                        if old is None:anchors.append(dict(y=y,name=t,confidence=c,variants=[t]))
                        else:
                            old['variants'].append(t)
                            if c>old['confidence']:old.update(name=t,confidence=c)
            anchors.sort(key=lambda a:a['y'])
            for v in variants:
                for box,t,c in v['boxes']:
                    x=sum(pt[0] for pt in box)/4;y=sum(pt[1] for pt in box)/4;text=clean(t)
                    grade_hit=g0<x<g1 and re.fullmatch(r'(?:高|初)[一二三123]',text)
                    gender_hit=n1<x<g0 and text in ['男','女']
                    if (grade_hit or gender_hit) and not any(abs(z['y']-y)<(9 if year==2020 else 13) for z in anchors):
                        anchors.append(dict(y=y,name='姓名待核',confidence=0,variants=['姓名待核'],cell_recovery=True))
            anchors.sort(key=lambda a:a['y'])
            if not anchors:continue
            typical=float(np.median(np.diff([a['y'] for a in anchors]))) if len(anchors)>1 else 45
            for j,a in enumerate(anchors):
                lo,hi=a['y']-typical*.43,a['y']+typical*.43
                schools=[];grades=[]
                for v in variants:
                    # 学校列与城市列在2025表中分开。
                    school_right=(.407*width if year==2025 else n0)
                    schools.append(cell(v['boxes'],s0,school_right,lo,hi))
                    grades.append(cell(v['boxes'],g0,g1,lo,hi))
                school,sc=max(schools,key=lambda v:v[1]);grade,gc=max(grades,key=lambda v:v[1])
                name=re.sub(r'\d+$','',a['name']);marker=a['name'][len(name):]
                verified=(len(variants)==2 and len(set(a['variants']))==1 and a['confidence']>=.96 and sc>=.96 and len({s[0] for s in schools})==1)
                rows.append(dict(id=f'reg-{year}-p{ix+1:03}-c{column}-r{j+1:03}',year=year,name=name,raw_name=a['name'],marker=marker,
                                 school=school or '（学校待核）',grade=grade,source=source['id'],page=ix+1,
                                 confidence=a['confidence'],identity_fields_consistent=verified,
                                 name_variants=sorted(set(a['variants'])),school_variants=sorted({s[0] for s in schools}),
                                 review='报名原表姓名及学校两种输入一致' if verified else '报名已见；姓名或学校识别待核',
                                 y=[lo,hi],column=column,name_box=[n0,lo,n1,hi],school_box=[s0,lo,school_right,hi],cell_recovery=a.get('cell_recovery',False)))
                page_count+=1
        pages.append(dict(page=ix+1,rows=page_count))
        if ix%10==0:print('报名提取',year,ix+1,page_count,flush=True)
    report=dict(year=year,rows=len(rows),pages=pages,missing_pages=missing,consistent=sum(r['identity_fields_consistent'] for r in rows))
    (ROOT/f'data/报名{year}候选.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/f'evidence/报名{year}提取核对.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('报名提取完成',year,len(rows),'待处理页',missing,flush=True)
    return rows,source,report
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,required=True);ap.add_argument('--partial',action='store_true');a=ap.parse_args();parse(a.year,a.partial)
