"""报名与同年高联奖项比对；年级只作来源差异记录，不作排除条件。"""
from pathlib import Path
from collections import defaultdict,Counter
import json,re
from build_people import school_key
ROOT=Path(__file__).resolve().parents[1]

def classify(r,awards):
    key=school_key(r['school']);same_name=[a for a in awards if a['year']==r['year'] and a['name']==r['name']]
    exact=[a for a in same_name if school_key(a['school'])==key]
    if len(exact)==1:return 'matched',exact
    if exact or same_name:return '报名匹配待核',exact or same_name
    if not r.get('identity_fields_consistent'):return '报名匹配待核',[]
    # 防止一个错字把原本获奖者变成“未获奖/缺考”。
    signatures={r['name'][:i]+r['name'][i+1:] for i in range(len(r['name']))}
    for a in awards:
        if a['year']!=r['year'] or school_key(a['school'])!=key:continue
        if signatures.intersection(a['name'][:i]+a['name'][i+1:] for i in range(len(a['name']))):return '报名匹配待核',[a]
    return '报名未见获奖',[]

def main():
    from build_data import make_aliases
    db=json.loads((ROOT/'data/查询数据.json').read_text(encoding='utf-8'))
    awards=[r for r in db['records'] if r['competition']=='高联' and (r.get('team') or r['award'] in ['一等奖','二等奖','三等奖'])]
    meta=json.loads((ROOT/'data/报名来源清单.json').read_text(encoding='utf-8'))
    records=[];sources=[];links=[];coverage=[];summaries=[]
    for year in [2020,2025]:
        audit=json.loads((ROOT/f'evidence/报名{year}提取核对.json').read_text(encoding='utf-8'))
        assert not audit['missing_pages'], '不能用未读完的报名表作差集'
        rows=json.loads((ROOT/f'data/报名{year}候选.json').read_text(encoding='utf-8'))
        src=next(s.copy() for s in meta if s['year']==year);sources.append(src)
        counts=Counter()
        for r in rows:
            status,matches=classify(r,awards);counts[status]+=1
            if status=='matched':
                target=matches[0]
                links.append(dict(record_id=target['id'],source=src['id'],page=r['page'],reported_grade=r['grade'],grade_difference=bool(r['grade'] and target['grade'] and r['grade']!=target['grade'])))
                continue
            py,aliases=make_aliases(r['name'])
            records.append(dict(id=r['id'],year=year,competition='高联',name=r['name'],marker=r.get('marker',''),school=r['school'],grade=r['grade'],
                                award=status,awards=[],team=False,name_uncertain=not r['identity_fields_consistent'],rank=None,list_order=None,rank_label='',
                                rank_note='报名名单不提供分数或竞赛名次',refs=[dict(source=src['id'],page=r['page'])],code='',score=None,status='报名比对',
                                confidence=r['confidence'],pinyin=py,aliases=aliases,review=r['review']+'；未获奖与缺考没有签到信息区分；年级差异不用于排除匹配',
                                possible_award_matches=[m['id'] for m in matches]))
        summaries.append(dict(year=year,rows=len(rows),counts=dict(counts),grade_differences=sum(l['grade_difference'] for l in links if l['record_id'] in {a['id'] for a in awards if a['year']==year})))
        coverage.append(dict(year=year,label='已比对报名表；未获奖 / 缺考未区分，识别或身份有疑者待核'))
    result=dict(records=records,sources=sources,links=links,coverage=coverage)
    (ROOT/'data/报名补充记录.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'evidence/新增报名比对.json').write_text(json.dumps(dict(status='passed',summaries=summaries,method='同年姓名和规范校名；不按年级排除；存在近似错字或多重匹配则保留待核，不直接标缺考'),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summaries,ensure_ascii=False))
if __name__=='__main__':main()
