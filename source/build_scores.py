"""公开且可复现的荣誉排序；同一晋级赛季只计最高记录。"""
from pathlib import Path
from collections import defaultdict
import json
ROOT=Path(__file__).resolve().parents[1]

def record_score(r,config):
    key=r['competition']+':'+('省队' if r['competition']=='高联' and r.get('team') else r['award'])
    return next((w for w in config['weights'] if w['key']==key),dict(key=key,tier=0,points=0,label='无计分奖项'))

def profile_score(records,config):
    seasons={}
    for r in records:
        w=record_score(r,config)
        season=r['year']-(r['competition']=='IMO')
        if w['points'] and (season not in seasons or (w['tier'],w['points'])>(seasons[season]['tier'],seasons[season]['points'])):
            seasons[season]=dict(season=season,record_id=r['id'],tier=w['tier'],points=w['points'],label=w['label'])
    contributions=sorted(seasons.values(),key=lambda v:(-v['tier'],-v['points'],v['season']))
    return dict(tier=max([v['tier'] for v in contributions],default=0),
                score=round(sum(v['points']*config['decay']**i for i,v in enumerate(contributions)),4),
                best=contributions[0]['label'] if contributions else '无计分奖项',contributions=contributions,
                imo_rank=min([r['rank'] for r in records if r['competition']=='IMO' and r.get('rank')],default=999999))

def build_scores(db):
    config=json.loads((ROOT/'data/评分规则.json').read_text(encoding='utf-8'))
    db['scoring']=config
    byid={r['id']:r for r in db['records']}
    for p in db['people']:
        p.update(profile_score([byid[rid] for rid in p['record_ids']],config))
    db['people'].sort(key=lambda p:(-p['tier'],-p['score'],p['imo_rank'],p['name'],p['id']))
    last_key=None;rank=0
    for i,p in enumerate(db['people']):
        key=(p['tier'],p['score'],p['imo_rank'])
        if key!=last_key:rank=i+1
        p['db_rank']=rank;last_key=key
    grouped=defaultdict(list)
    for p in db['people']:grouped[p['school']].append(p)
    db['schools']=[dict(name=name,person_ids=[p['id'] for p in ps],people=len(ps),
                        score=round(sum(sorted((p['score'] for p in ps),reverse=True)[:10]),4),
                        best_tier=max(p['tier'] for p in ps),
                        years=sorted({year for p in ps for year in p['years']})) for name,ps in grouped.items()]
    db['schools'].sort(key=lambda s:(-s['score'],-s['best_tier'],s['name']))
    for i,s in enumerate(db['schools']):s['rank']=i+1
    contests=defaultdict(list)
    for r in db['records']:contests[(r['competition'],r['year'])].append(r)
    db['contests']=[dict(id=c+':'+str(y),competition=c,year=y,record_ids=[r['id'] for r in rs],
                         people=len({r['person_id'] for r in rs}),records=len(rs),
                         awards=sum(r['award'] in ['一等奖','二等奖','三等奖','金牌','银牌','铜牌'] for r in rs)) for (c,y),rs in contests.items()]
    priority={'IMO':0,'CMO':1,'高联':2,'广东初赛':3}
    db['contests'].sort(key=lambda c:(priority[c['competition']],-c['year']))
    return db
