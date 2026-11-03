"""扫描初赛表：按准考证号/序号锚点定位，保留序号补位、双输入差异及人工修订证据。"""
from pathlib import Path
from collections import Counter
import json,re,hashlib,fitz,numpy as np,cv2,argparse
from build_data import make_aliases
ROOT=Path(__file__).resolve().parents[1]

def groups(indices,gap=3):
    result=[]
    for n in indices:
        if not result or n-result[-1][-1]>gap:result.append([n])
        else:result[-1].append(n)
    return [sum(g)/len(g) for g in result]

def grid(page,year,header=True):
    pix=page.get_pixmap(matrix=fitz.Matrix(2.5,2.5),alpha=False)
    rgb=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3)
    bw=cv2.threshold(cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY),145,255,cv2.THRESH_BINARY_INV)[1]
    small=cv2.resize(bw,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
    small=cv2.threshold(small,70,255,cv2.THRESH_BINARY)[1]
    raw=cv2.HoughLinesP(small,1,np.pi/360,threshold=50,minLineLength=pix.width*.15,maxLineGap=12)
    angles=[]
    for item in ([] if raw is None else raw[:,0]):
        x1,y1,x2,y2=[float(v)*2 for v in item]
        if abs(x2-x1)>pix.width*.3 and abs((y2-y1)/(x2-x1))<.05 and min(x1,x2)<pix.width*.4 and max(x1,x2)>pix.width*.6:
            angles.append(np.degrees(np.arctan((y2-y1)/(x2-x1))))
    angle=float(np.median(angles)) if angles else 0
    matrix=cv2.getRotationMatrix2D((pix.width/2,pix.height/2),angle,1)
    aligned=cv2.warpAffine(bw,matrix,(pix.width,pix.height),flags=cv2.INTER_NEAREST,borderValue=0)
    aligned=cv2.morphologyEx(aligned,cv2.MORPH_CLOSE,np.ones((2,2),np.uint8))
    horizontal=cv2.morphologyEx(aligned,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(pix.width//5,1)))
    ys=groups(np.flatnonzero((horizontal>0).sum(axis=1)>pix.width*.4).tolist(),gap=4)
    assert len(ys)>1,(year,'横线不足',ys,angle)
    top,bottom=int(ys[0]),int(ys[-1])+1
    vertical=cv2.morphologyEx(aligned[top:bottom],cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(25,int((bottom-top)*.55)))))
    xs=groups(np.flatnonzero((vertical>0).sum(axis=0)>(bottom-top)*.5).tolist(),gap=4)
    xs=[x for x in xs if 8<x<pix.width-8]
    expected=5 if year==2025 else 7
    if year==2026:
        if len(xs)!=7:
            calibrated=[.1095,.1912,.2728,.5955,.7114,.7920,.8890]
            xs=[v*pix.width for v in calibrated]
    assert len(xs)==expected,(year,'列边界异常',xs)
    # 2026表有跨列表名行；2025只有字段名行。
    start=2 if year==2026 else (1 if header else 0)
    return xs,list(zip(ys[start:],ys[start+1:])),ys,matrix

def clean(t):return re.sub(r'\s+','',t).replace('髙','高')

def horizontal(item):
    """正文行接近水平；官方灰色斜水印不是学生姓名或学校。原OCR缓存不改。"""
    box=item[0]
    return abs(box[1][1]-box[0][1])<=max(5,abs(box[1][0]-box[0][0])*.25)

def cell(boxes,x0,x1,y0,y1,matrix=None):
    hits=[]
    for box,t,confidence in boxes:
        x=sum(p[0] for p in box)/4;y=sum(p[1] for p in box)/4
        if matrix is not None:x,y=matrix@np.array([x,y,1])
        if x0+2<x<x1-2 and y0+2<y<y1-2:hits.append((y,x,clean(t),confidence))
    hits.sort()
    return ''.join(h[2] for h in hits),min([h[3] for h in hits],default=0)

def anchor_rows(variants,year,width):
    found=[]
    for vi,boxes in enumerate(variants):
        for box,t,confidence in boxes:
            x=sum(p[0] for p in box)/4;y=sum(p[1] for p in box)/4
            text=clean(t).translate(str.maketrans({'O':'0','I':'1','l':'1','L':'1'}))
            match=re.search(r'(\d{7,12})$',text) if year==2025 else re.match(r'(\d{1,4})(?:\D|$)',text)
            code=match.group(1) if match else ''
            left=min(p[0] for p in box)
            valid=(bool(code) and x<width*.5) if year==2025 else (bool(code) and width*.10<left<width*.20 and y>340)
            if valid:
                existing=next((a for a in found if abs(a['y']-y)<12),None)
                if existing is None:found.append(dict(x=x,y=y,code=code,variant=vi,name_hint=text[:match.start()] if year==2025 else ''))
    found.sort(key=lambda a:a['y'])
    if year==2025 and found:
        cx=float(np.median([a['x'] for a in found]))
        for vi,boxes in enumerate(variants):
            for box,t,confidence in boxes:
                x=sum(p[0] for p in box)/4;y=sum(p[1] for p in box)/4
                code=clean(t).translate(str.maketrans({'O':'0','I':'1','l':'1','L':'1'}))
                if re.fullmatch(r'\d{4,12}',code) and abs(x-cx)<85 and not any(abs(a['y']-y)<12 for a in found):found.append(dict(x=x,y=y,code=code,variant=vi,name_hint=''))
        found.sort(key=lambda a:a['y'])
    return found

def header_x(boxes,names,default):
    matches=[sum(p[0] for p in box)/4 for box,t,c in boxes if clean(t) in names]
    return matches[0] if matches else default

def parse(year,partial=False):
    meta=json.loads((ROOT/'data/广东初赛补充来源.json').read_text(encoding='utf-8'))
    s=next(s for s in meta if s['year']==year and s['pages']>1)
    doc=fitz.open(ROOT/s['local']);records=[];audits=[];review=[];missing=[]
    for ix,page in enumerate(doc):
        clean_path=ROOT/f'data/初赛OCR/{year}-clean/p{ix+1:03}.json'
        raw_path=ROOT/f'data/初赛OCR/{year}-raw/p{ix+1:03}.json'
        if not clean_path.exists() or not raw_path.exists():
            if partial:continue
            missing.append(ix+1);continue
        raw_variants=[json.loads(p.read_text(encoding='utf-8'))['boxes'] for p in [clean_path,raw_path]]
        variants=[[item for item in boxes if horizontal(item)] for boxes in raw_variants]
        width=page.rect.width*2.5
        anchors=anchor_rows(variants,year,width)
        assert anchors,(year,ix+1,'没有序号/准考证号锚点')
        if year==2026:
            expected=range(ix*31+1,ix*31+(15 if ix==68 else 31)+1)
            known={int(a['code']):a for a in anchors if int(a['code']) in expected}
            assert len(known)>=20 or ix==68,(year,ix+1,'序号缺口过多',list(known))
            slope,intercept=np.polyfit(list(known),[a['y'] for a in known.values()],1)
            for code in expected:
                if code not in known:known[code]=dict(x=width*.15,y=float(slope*code+intercept),code=str(code),variant=2,name_hint='',serial_inferred=True)
            anchors=[known[k] for k in sorted(known)]
        cx=float(np.median([a['x'] for a in anchors]))
        if year==2026:xs=[v*width for v in [.1095,.1912,.2728,.5955,.7114,.7920,.8890]]
        else:
            nx=header_x(variants[0],['姓名'],cx-175)
            award_x=[sum(pt[0] for pt in box)/4 for boxes in variants for box,t,sc in boxes if clean(t) in ['一等奖','二等奖','三等奖']]
            ax=float(np.median(award_x)) if award_x else header_x(variants[0],['奖项','获奖情况'],width*.85)
            xs=[max(0,nx-100),(nx+cx)/2,cx+80,ax-65,min(width,ax+100)]
        typical=float(np.median(np.diff([a['y'] for a in anchors]))) if len(anchors)>1 else 45
        typical=min(80,max(25,typical));bands=[(a['y']-typical*.44,a['y']+typical*.44) for a in anchors]
        matrix=None
        count=0
        for j,(y0,y1) in enumerate(bands):
            if y1-y0<20:continue
            fields=[[cell(boxes,*xs[k:k+2],y0,y1,matrix) for k in range(len(xs)-1)] for boxes in variants]
            ni,si,ai=(0,2,3) if year==2025 else (3,2,5)
            code_index=1 if year==2025 else 0
            name,nc=fields[0][ni];school,sc=fields[0][si];award,ac=fields[0][ai];code=anchors[j]['code'];cc=1
            # 印章或水印偶尔破坏字段，备用输入只在主输入缺失时补充。
            if not re.fullmatch(r'[\u3400-\u9fff·]{2,8}\d*',name) and fields[1][ni][0]:name,nc=fields[1][ni]
            if award not in ['一等奖','二等奖','三等奖'] and fields[1][ai][0] in ['一等奖','二等奖','三等奖']:award,ac=fields[1][ai]
            if not school and fields[1][si][0]:school,sc=fields[1][si]
            if award not in ['一等奖','二等奖','三等奖']:
                choices=[(clean(t),c) for boxes in variants for box,t,c in boxes if y0+2<sum(pt[1] for pt in box)/4<y1-2 and clean(t) in ['一等奖','二等奖','三等奖']]
                if choices:award,ac=max(choices,key=lambda z:z[1])
            name_choices=[]
            for vi,boxes in enumerate(variants):
                for box,t,c in boxes:
                    xx=sum(pt[0] for pt in box)/4;yy=sum(pt[1] for pt in box)/4;text=clean(t)
                    if xs[ni]+2<xx<xs[ni+1]-2 and y0+2<yy<y1-2 and re.fullmatch(r'[\u3400-\u9fff·]{2,6}\d*',text):name_choices.append((text,c,vi))
            if name_choices:name,nc,_=max(name_choices,key=lambda z:z[1])
            raw_name=name;marker=re.search(r'\d+$',name);name=re.sub(r'\d+$','',name)
            if anchors[j].get('name_hint') and re.fullmatch(r'[\u3400-\u9fff·]{2,6}',anchors[j]['name_hint']):name=anchors[j]['name_hint'];nc=.95
            issues=[]
            if not name or not school or award not in ['一等奖','二等奖','三等奖']:issues.append('字段缺失或奖项不完整')
            if fields[0][ni][0]!=fields[1][ni][0]:issues.append('姓名两种输入不一致')
            if min(nc,sc,ac)<.96:issues.append('字段识别置信度偏低')
            rid=f'prelim-{year}-p{ix+1:03}-r{j+1:02}'
            py,aliases=make_aliases(name or '姓名待核')
            records.append(dict(id=rid,year=year,competition='广东初赛',name=name or '姓名待核',raw_name=raw_name,marker=marker.group(0) if marker else '',
                                school=school or '（学校待核）',grade='',award=award,awards=[award],team=False,name_uncertain=(nc<.96 or fields[0][ni][0]!=fields[1][ni][0] or not name),
                                rank=None,list_order=None,rank_label='',rank_note='原表未给分数或全省成绩名次，不据分组序号换算名次',
                                refs=[dict(source=f'广东初赛-{year}',page=ix+1)],code=code,score=None,status='公示',confidence=nc,pinyin=py,aliases=aliases,
                                review='扫描表按序号或准考证号锚点逐行提取，比较去色水印与原图两种OCR输入；'+('；'.join(issues) if issues else '字段一致'),
                                source_row=j+1,ocr_y=[y0,y1],name_box=[xs[ni],y0,xs[ni+1],y1]))
            count+=1
            if issues:review.append(dict(id=rid,page=ix+1,row=j+1,fields=fields,issues=issues,box=[xs[0],y0,xs[-1],y1]))
        audits.append(dict(page=ix+1,anchor_rows=len(bands),parsed_rows=count,codes=[a['code'] for a in anchors],serial_inferred=[a['code'] for a in anchors if a.get('serial_inferred')],excluded_diagonal_boxes=[len(a)-len(b) for a,b in zip(raw_variants,variants)]))
        if ix%10==0:print(year,'page',ix+1,'rows',count,flush=True)
    repairs=[]
    valid={'一等奖','二等奖','三等奖'}
    for i,r in enumerate(records):
        if r['award'] in valid:continue
        left=next((z for z in reversed(records[:i]) if z['award'] in valid),None)
        right=next((z for z in records[i+1:] if z['award'] in valid),None)
        if left and right and left['award']==right['award'] and left['refs'][0]['page']==right['refs'][0]['page']:
            repairs.append(dict(id=r['id'],original=r['award'],award=left['award'],method='同页前后最近可读奖项一致；保留结构恢复记录'))
            r['award']=left['award'];r['awards']=[r['award']];r['award_structural_repair']=True
            r['review']+='；奖项文字不完整，按同页相邻同奖项段恢复'
        else:r['award']='奖项待核';r['awards']=[]
    corrections_path=ROOT/'data/初赛人工更正.json'
    corrections=json.loads(corrections_path.read_text(encoding='utf-8')) if corrections_path.exists() else []
    for c in corrections:
        for r in records:
            if r['id']==c['id']:
                r.update(c['fields']);r['awards']=[r['award']];r['review']+='；'+c['note'];r['name_uncertain']=False
    report=dict(year=year,missing_pages=missing,records=len(records),review=review,pages=audits,award_repairs=repairs)
    (ROOT/f'evidence/初赛{year}扫描核对.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/f'data/初赛{year}候选.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(year,'records',len(records),'review',len(review),'missing',len(missing),flush=True)
    return records,s,report

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,required=True);ap.add_argument('--partial',action='store_true');a=ap.parse_args();parse(a.year,a.partial)
