"""从保留坐标的表格生成逐来源记录、合并记录及内嵌网页。"""
from pathlib import Path
from collections import Counter,defaultdict
import fitz,json,re,hashlib,itertools,csv,argparse
from pypinyin import pinyin,Style,lazy_pinyin
from collect_sources import ROOT

def load(p): return json.loads((ROOT/p).read_text(encoding='utf-8'))
def save(p,v):
    f=ROOT/p; f.parent.mkdir(exist_ok=True,parents=True); f.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def clean(s): return re.sub(r'\s+','',s).strip('|')
def midpoint(poly): return sum(x[0] for x in poly)/4,sum(x[1] for x in poly)/4
def native_boxes(page,scale=2.5):
    result=[]
    for b in page.get_text('dict')['blocks']:
        for line in b.get('lines',[]):
            for sp in line['spans']:
                txt=clean(sp['text'])
                if not txt: continue
                x0,y0,x1,y1=sp['bbox']; result.append([[[x0*scale,y0*scale],[x1*scale,y0*scale],[x1*scale,y1*scale],[x0*scale,y1*scale]],txt,1.0])
    return result

EXCLUDE={'姓名','学生姓名','考生姓名','学校','学校名称','学校规范校名','学校全称','年级','性别','序号','编号','广东赛区','广东省队','广东省数学会','学生性别','考点'}
def as_boxes(boxes):
    return [dict(poly=b[0],text=clean(b[1]),confidence=float(b[2]),x=midpoint(b[0])[0],y=midpoint(b[0])[1]) for b in boxes]

def native_table_rows(s,doc):
    result=[];pages=[]
    for ix,p in enumerate(doc):
        count=0
        for table in p.find_tables().tables:
            data=table.extract();header=None
            for j,row in enumerate(data):
                cells=[clean(c or '') for c in row]
                if any(c in {'姓名','学生姓名','考生姓名'} for c in cells):
                    header=cells;continue
                if header is None:continue
                ni=next(i for i,c in enumerate(header) if c in {'姓名','学生姓名','考生姓名'})
                si=next(i for i,c in enumerate(header) if c in {'学校','学校全称','学校名称','学校规范校名'})
                gi=next((i for i,c in enumerate(header) if c.startswith('年级')),None)
                if len(cells)<=max(ni,si) or not cells[ni] or not cells[si]:continue
                raw=cells[ni];name=re.sub(r'\d+$','',raw)
                if not re.fullmatch(r'[\u3400-\u9fff·]{2,6}',name):raise RuntimeError('Unexpected native name '+raw)
                cell=table.rows[j].cells[ni];x0,y0,x1,y1=cell
                poly=[[x0*2.5,y0*2.5],[x1*2.5,y0*2.5],[x1*2.5,y1*2.5],[x0*2.5,y1*2.5]]
                result.append(dict(source=s['id'],page=ix+1,year=s['year'],kind=s['kind'],name=name,raw_name=raw,
                                   marker=raw[len(name):],
                                   school=cells[si],grade=cells[gi] if gi is not None else '',code=cells[0] if cells[0].startswith('M') else '',
                                   serial=cells[0],status=s['status'],confidence=1.0,poly=poly,native=True,source_row=j))
                count+=1
        pages.append(dict(page=ix+1,count=count,native=True))
    return result,pages

def parse_source(s, provisional=False):
    doc=fitz.open(ROOT/s['local']); result=[]; config=None; pages=[]
    if s['year']==2026:return native_table_rows(s,doc)
    for ix,p in enumerate(doc):
        native=len(p.get_text().strip())>100
        if native: boxes=as_boxes(native_boxes(p))
        else:
            f=ROOT/'data/OCRv6'/f"{s['id']}-p{ix+1:02}.json"
            if not f.exists() and provisional: f=ROOT/'data/OCR'/f"{s['id']}-p{ix+1:02}.json"
            if not f.exists(): raise RuntimeError('Missing OCR '+str(f))
            boxes=as_boxes(json.loads(f.read_text(encoding='utf-8'))['boxes'])
        # 2020 省队公示附件：只有第3页为入营名单，第4页起为一等奖表。
        if s['kind']=='省队及省一公示' and ix!=2: continue
        if s['kind']=='报名名单' and s['year']==2026 and ix==0: continue
        headers=[b for b in boxes if b['text'] in {'姓名','学生姓名','考生姓名'}]
        if headers:
            h=min(headers,key=lambda b:b['y']); config={'nx':h['x'],'hy':h['y']}
        if config is None:
            pages.append(dict(page=ix+1,count=0,reason='无姓名表头或已为空尾页')); continue
        nx=config['nx']; hy=config['hy'] if headers else 0
        for b in boxes:
            if abs(b['x']-nx)<90:
                b['raw_name']=b['text']
                b['text']=re.sub(r'([男女]高[一二三])$','',b['text'])
                b['text']=re.sub(r'\d+$','',b['text'])
        nameboxes=[b for b in boxes if abs(b['x']-nx)<90 and b['y']>hy+12 and 2<=len(b['text'])<=6
                   and b['text'] not in EXCLUDE and re.fullmatch(r'[\u3400-\u9fff·]+',b['text'])
                   and not re.fullmatch(r'[男女高一二三]+',b['text']) and '中学' not in b['text']]
        nameboxes.sort(key=lambda b:b['y'])
        # 公告正文不能当学生，页尾签章按姓名列之外/词典剔除。
        nameboxes=[b for b in nameboxes if not any(t in b['text'] for t in ['数学会','联系人','广东省'])]
        schools=[b for b in boxes if any(x in b['text'] for x in ['学','附中','高中','一中','书院','十七中']) and b['text'] not in EXCLUDE
                 and len(b['text'])>=4 and not any(t in b['text'] for t in ['数学奥林','数学联赛','学生名单','学校规范','学校名称','报名表','入营资格','学校包括'])]
        codes=[b for b in boxes if re.fullmatch(r'[MNｍＭ]\d{4,}',b['text'],flags=re.I)]
        grades=[b for b in boxes if re.fullmatch(r'高[一二三123—-]',b['text'])]
        gaps=[b['y']-a['y'] for a,b in zip(nameboxes,nameboxes[1:])]
        typical=sorted(gaps)[len(gaps)//2] if gaps else 45
        for j,b in enumerate(nameboxes):
            candidates=sorted(schools,key=lambda z:abs(z['y']-b['y']))
            sch=candidates[0] if candidates and abs(candidates[0]['y']-b['y'])<typical*.66 else None
            if sch is None:
                result.append(dict(source=s['id'],page=ix+1,name=b['text'],error='没有匹配学校',poly=b['poly']));continue
            g=min(grades,key=lambda z:abs(z['y']-b['y'])) if grades else None
            grade=g['text'].replace('—','一').replace('-','一') if g and abs(g['y']-b['y'])<typical*.55 else ''
            c=min(codes,key=lambda z:abs(z['y']-b['y'])) if codes else None
            code=c['text'] if c and abs(c['y']-b['y'])<typical*.55 else ''
            raw=b.get('raw_name',b['text']);marker=re.search(r'\d+$',raw)
            result.append(dict(source=s['id'],page=ix+1,year=s['year'],kind=s['kind'],name=b['text'],raw_name=raw,
                               marker=marker.group(0) if marker else '',school=sch['text'],
                               grade=grade,code=code,status=s['status'],confidence=b['confidence'],
                               poly=b['poly'],school_poly=sch['poly'],native=native,source_row=j+1))
        pages.append(dict(page=ix+1,count=len(nameboxes),native=native))
    return result,pages

SCHOOL_EQ={
 '深圳高级中学':'深圳市高级中学','深圳市高级中学中心校区':'深圳市高级中学',
 '佛山南海区石门中学':'佛山市南海区石门中学','佛山市南海区石门中学高中部':'佛山市南海区石门中学',
 '广东省珠海市第一中学':'珠海市第一中学','湛江第一中学':'湛江市第一中学',
}
def school_key(s): return SCHOOL_EQ.get(clean(s).replace('（','(').replace('）',')'),clean(s).replace('（','(').replace('）',')'))
def make_aliases(name):
    syll=pinyin(name,style=Style.NORMAL,heteronym=True,errors='default')
    # 姓氏常用读音优先，其他读音仍进入检索索引。
    surnames={'曾':'zeng','单':'shan','解':'xie','仇':'qiu','区':'ou','查':'zha','乐':'yue','朴':'piao','翟':'zhai'}
    default=lazy_pinyin(name)
    if name and name[0] in surnames: default[0]=surnames[name[0]]
    variants=set()
    for parts in itertools.islice(itertools.product(*syll),512):
        variants.add(''.join(parts));variants.add(''.join(x[0] for x in parts))
    variants.add(''.join(default));variants.add(''.join(x[0] for x in default))
    return ' '.join(default),sorted(variants)

def build(provisional=False):
    sources=load('data/PDF来源清单.json')
    # 2025 省一用11月11日正式评奖稿；10月31日稿保留在原始资料，不重复计数。
    sources=[s for s in sources if not (s['year']==2025 and s['kind']=='一等奖' and s['article'].endswith('3772'))]
    # 2026 两份用户文件为10月30日正文稿，官网对应附件的版式和条目另行比较。
    supplied={'省队':'决赛名单（广东）(1).pdf','一等奖':'一等奖名单（广东）(1).pdf'}
    for s in sources:
        if s['year']==2026 and s['kind'] in supplied:
            s['official_local']=s['local'];s['official_sha256']=s['sha256']
            s['local']='原始资料/2026/'+supplied[s['kind']]
            b=(ROOT/s['local']).read_bytes();s['sha256']=hashlib.sha256(b).hexdigest();s['bytes']=len(b)
            s['pages']=len(fitz.open(ROOT/s['local']));s['originNote']='用户提供的2026-10-30正式正文稿，已与官网附件逐条比较'
    sources += [s for s in load('data/报名来源清单.json') if s['year']==2026]
    details=[]; audits=[]
    corrections=load('data/人工更正.json') if (ROOT/'data/人工更正.json').exists() else []
    for s in sources:
        data,pages=parse_source(s,provisional)
        for c in corrections:
            if c.get('action')=='add':
                if c['source']!=s['id']:continue
                row=dict(c['record'],source=s['id'],year=s['year'],kind=s['kind'],status=s['status'],confidence=1.0,native=False,marker='',manual_note=c['note'])
                data.append(row)
                for pg in pages:
                    if pg['page']==row['page']:pg['count']+=1
                continue
            for r in data:
                if r['source']==c['source'] and r['page']==c['page'] and r['name']==c['old']:
                    r['name']=c['new'];r['manual_note']=c['note']
                    r['name_uncertain']=bool(c.get('uncertain',False))
        data.sort(key=lambda r:(r['page'],midpoint(r['poly'])[1]))
        for i,r in enumerate(data,1):r['list_order']=i;r['source_row']=i
        details.extend(data);audits.append(dict(source=s['id'],pages=pages,rows=len(data),errors=[r for r in data if 'error' in r]))
    save('data/逐来源条目.json',details);save('evidence/逐页结构核对.json',audits)
    errors=[r for r in details if 'error' in r]
    if errors: raise RuntimeError(f'{len(errors)} unmatched school rows; see 逐页结构核对.json')
    merged={}; conflicts=[]
    def basekey(r):return (r['year'],r['name'],school_key(r['school']),r.get('marker',''))
    def entry(r):
        return dict(year=r['year'],competition='高联',name=r['name'],marker=r.get('marker',''),school=r['school'],grade=r['grade'],award='',awards=[],team=False,
                    name_uncertain=r.get('name_uncertain',False),manual_note=r.get('manual_note',''),
                    rank=None,list_order=r['list_order'],rank_label='广东名单顺位',rank_note='按省一、省二、省三名单依次拼接后的行位置；不是含同分并列的官方成绩名次',
                    refs=[dict(source=r['source'],page=r['page'])],code=r.get('code',''),score=None,status=r['status'],native=r['native'],confidence=r['confidence'])
    # 每一条获奖名单行独立保留。同校同名且没有编号标记也不能自动合成一人。
    for r in details:
        if r['kind'] not in ['一等奖','二等奖','三等奖']:continue
        out=entry(r);out['award']=r['kind'];out['awards']=[r['kind']]
        previous=['一等奖','二等奖','三等奖'][:['一等奖','二等奖','三等奖'].index(r['kind'])]
        out['award_list_order']=r['list_order']
        out['list_order']+=sum(z['year']==r['year'] and z['kind'] in previous for z in details)
        key=basekey(r)+(r['source'],r['page'],r['source_row'])
        merged[key]=out
    groups=defaultdict(list)
    for out in merged.values():groups[basekey(out)].append(out)
    for key,group in groups.items():
        if len(group)>1:
            conflicts.append(dict(key=key,awards=[r['award'] for r in group],refs=[ref for r in group for ref in r['refs']],note='同校同名的多条记录；可能同名或名单重复，未推断为同一人'))
            for out in group:out['conflict']=True
    for r in details:
        if not r['kind'].startswith('省队'):continue
        candidates=groups.get(basekey(r),[])
        preferred=[z for z in candidates if z['grade']==r['grade']]
        if len(preferred)==1:candidates=preferred
        if len(candidates)==1:
            out=candidates[0];out['team']=True;out['refs'].append(dict(source=r['source'],page=r['page']));out['native'] &= r['native']
        else:
            out=entry(r);out['team']=True
            out['rank_label']='省队名单顺位'
            merged[basekey(r)+(r['source'],r['page'],r['source_row'])]=out
    # 报名差集只使用2026原生可提取文本。任何同名获奖者均进入待核对，避免校名差异制造假阴性。
    reg=[r for r in details if r['kind']=='报名名单']
    award_names={(r['year'],r['name']) for r in merged.values()}
    award_keys={basekey(z) for z in merged.values()}
    matched=0;uncertain=[];added=0;seen=set()
    for r in reg:
        k=(r['year'],r['name'],school_key(r['school']),r.get('marker',''))
        if k in seen: continue
        seen.add(k)
        if k in award_keys:matched+=1;continue
        if (r['year'],r['name']) in award_names:uncertain.append(r);continue
        merged[k]=dict(year=r['year'],competition='高联',name=r['name'],marker=r.get('marker',''),school=r['school'],grade=r['grade'],award='报名未见获奖',awards=[],team=False,
                       rank=None,list_order=None,rank_label='',rank_note='报名比对不能推断竞赛名次',
                       refs=[dict(source=r['source'],page=r['page'])],code='',score=None,status='报名比对',native=True,confidence=1.0)
        added+=1
    records=list(merged.values())
    save('evidence/奖项名单重叠.json',conflicts)
    ext=load('data/国际与决赛记录.json') if (ROOT/'data/国际与决赛记录.json').exists() else dict(records=[],sources=[])
    for r in ext['records']:r['native']=True
    records+=ext['records'];sources+=ext['sources']
    order={'一等奖':0,'二等奖':1,'三等奖':2,'报名未见获奖':3,'':4,'金牌':0,'银牌':1,'铜牌':2}
    records.sort(key=lambda r:(-r['year'],{'IMO':0,'CMO':1,'高联':2}[r['competition']],order[r['award']],not r['team'],r['list_order'] or 999999,r['name']))
    for i,r in enumerate(records):
        r['id']=f'gd-{i+1:05}';r['pinyin'],r['aliases']=make_aliases(r['name'])
        native=r.pop('native')
        if 'review' not in r:r['review']='原生文本；已检查行列与来源页码' if native else '扫描件经两轮自动识别及结构核验；不等于逐字人工校勘'
        if r.get('manual_note'):r['review']+='；'+r.pop('manual_note').replace('父代理实际查看','已查看')
    regsummary=[dict(year=2026,label='已比对；未获奖 / 缺考未区分',registered=len(reg),distinct=len(seen),matched=matched,unmatched=added,uncertain=len(uncertain))]
    save('evidence/报名比对.json',dict(summary=regsummary,uncertain=uncertain,method='同年姓名+规范化学校精确匹配；仅校名不一致的同名者不生成未获奖分类；未核验出席'))
    db=dict(schemaVersion=1,updated='2026-11-02',years=sorted(set(r['year'] for r in records)),records=records,sources=sources,
            registration=regsummary,registrationNote='“未获奖 / 缺考（未区分）”来自2026年报名公示-2与已收录奖项名单的差集；并非签到结果。2020—2025年暂不判断是否未获奖或缺考。')
    save('data/查询数据.json',db)
    template=(ROOT/'source/查询页模板.html').read_text(encoding='utf-8')
    html=template.replace('{{DATA}}',json.dumps(db,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    (ROOT/'广东数学竞赛成绩查询.html').write_text(html,encoding='utf-8')
    with (ROOT/'data/广东数学竞赛记录.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['赛事','年份','姓名','原名单同名标记','姓名拼音','学校','年级','奖项','省队资格','状态','编号','分数','官方名次','名单顺位','顺位口径'])
        for r in records:w.writerow([r['competition'],r['year'],r['name'],r.get('marker',''),r['pinyin'],r['school'],r['grade'],r['award'],'是' if r['team'] else '否',r['status'],r['code'],r['score'] if r['score'] is not None else '未公布',r['rank'] or '',r['list_order'] or '',r['rank_label']])
    counts=[dict(year=y,**{k:sum(r['year']==y and r['competition']=='高联' and (r['team'] if k=='省队' else r['award']==k) for r in records) for k in ['省队','一等奖','二等奖','三等奖','报名未见获奖']}) for y in db['years']]
    save('evidence/年度条目统计.json',counts)
    print(json.dumps(dict(records=len(records),sources=len(sources),years=counts,registration=regsummary),ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--provisional',action='store_true');args=ap.parse_args();build(args.provisional)
