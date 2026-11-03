"""独立检查可发布数据、来源闭包、分数/排名边界。只依赖标准库。"""
from pathlib import Path
from collections import Counter
import json,hashlib,re
ROOT=Path(__file__).resolve().parents[1]
def main():
    db=json.loads((ROOT/'data/查询数据.json').read_text(encoding='utf-8'));rows=db['records'];ss={s['id']:s for s in db['sources']}
    assert len({r['id'] for r in rows})==len(rows)
    checked=[]
    for s in ss.values():
        p=(ROOT/s['local']).resolve();assert p.is_relative_to(ROOT) and p.is_file(),s['id']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256'],s['id']
        checked.append(s['id'])
    for r in rows:
        assert r['name'] and r['school'] and r['aliases'],r['id']
        assert all(x['source'] in ss and 1<=x['page']<=ss[x['source']]['pages'] for x in r['refs']+r.get('registration_refs',[])),r['id']
        if r['competition']=='IMO':
            assert r['rank']>0 and sum(r['problem_scores'])==r['score'] and 0<=r['score']<=42
        else:assert r['rank'] is None and r['score'] is None
        if r['award'] in ['报名未见获奖','报名匹配待核','考生名单']:
            assert r['year'] in [2020,2024,2025,2026] and r['list_order'] is None and not r['team']
            assert all(ss[x['source']]['kind'] in ['报名名单','考场安排'] for x in r['refs'])
    hl=Counter((r['year'],r['award']) for r in rows if r['competition']=='高联' and r['award'])
    expected={2020:(88,257,319),2021:(89,291,378),2022:(99,307,407),2023:(93,357,410),2024:(90,390,546),2025:(102,465,530),2026:(99,720,738)}
    for y,counts in expected.items():
        assert tuple(hl[(y,k)] for k in ['一等奖','二等奖','三等奖'])==counts,(y,counts)
        positions=sorted(r['list_order'] for r in rows if r['year']==y and r['competition']=='高联' and r['award'] in ['一等奖','二等奖','三等奖'])
        assert positions==list(range(1,sum(counts)+1)),y
    assert Counter(r['year'] for r in rows if r['competition']=='CMO')=={2020:25,2021:31,2022:34,2023:34,2024:38,2025:38}
    assert sum(r['competition']=='IMO' for r in rows)==4
    twins=[r for r in rows if r['year']==2026 and r['competition']=='高联' and r['name']=='黄梓睿' and r['award']=='二等奖']
    assert {r['marker'] for r in twins}=={'1','2'}
    pp={p['id']:p for p in db['people']}
    assert len(pp)==len(db['people'])
    memberships=Counter(rid for p in pp.values() for rid in p['record_ids'])
    assert memberships==Counter(r['id'] for r in rows), '每一条成绩必须且只属于一个档案'
    byid={r['id']:r for r in rows}
    for p in pp.values():
        assert all(byid[rid]['person_id']==p['id'] and byid[rid]['name']==p['name'] for rid in p['record_ids'])
        assert set(p['years'])=={byid[rid]['year'] for rid in p['record_ids']}
    def persons(name):return [p for p in pp.values() if p['name']==name]
    xue=persons('薛浩琛');assert len(xue)==1 and xue[0]['years']==[2025,2026]
    feng=persons('冯晨旭');assert len(feng)==1 and {byid[rid]['competition'] for rid in feng[0]['record_ids']}=={'高联','CMO','IMO'}
    li=persons('李泽熙');assert len(li)==2 and {p['school'] for p in li}=={'深圳中学','华南师范大学附属中学'}
    assert len({r['person_id'] for r in twins})==2, '同场次同名数字标记不能合为一人'
    wang=persons('王梓墨');assert len(wang)==1 and wang[0]['years']==[2024,2025,2026]
    guan=persons('官浩楠');assert len(guan)==1
    gs=[byid[x] for x in guan[0]['record_ids']]
    assert {(r['year'],r['competition'],r['award']) for r in gs}=={(2024,'广东初赛','三等奖'),(2025,'广东初赛','二等奖'),(2025,'高联','报名未见获奖')}
    assert next(r for r in gs if r['competition']=='高联')['grade']=='高三'
    yang=persons('杨奕辰');assert len(yang)==1 and len(yang[0]['record_ids'])==6
    initial=Counter(r['year'] for r in rows if r['competition']=='广东初赛')
    assert initial=={2024:2569,2025:2800,2026:2123}
    for a,b in zip(db['people'],db['people'][1:]):
        assert (-a['tier'],-a['score'],a['imo_rank'])<=(-b['tier'],-b['score'],b['imo_rank'])
    assert {rid for s in db['schools'] for pid in s['person_ids'] for rid in pp[pid]['record_ids']}==set(byid)
    assert Counter(rid for c in db['contests'] for rid in c['record_ids'])==Counter(byid.keys())
    text=(ROOT/'广东数学竞赛成绩查询.html').read_text(encoding='utf-8')
    embedded=re.search(r'<script id="dataset" type="application/json">(.*?)</script>',text,re.S).group(1)
    assert json.loads(embedded)==db
    # 页面必须离线自足，不能依靠外部JS/CSS网络请求加载查询。
    assert not re.search(r'<script[^>]+src=|<link[^>]+rel=["\']stylesheet',text,re.I)
    report=dict(status='passed',records=len(rows),people=len(pp),merged_people=sum(len(p['record_ids'])>1 for p in pp.values()),sources=len(ss),years=db['years'],competition_counts=dict(Counter(r['competition'] for r in rows)),
                verified_source_ids=checked,hashes=dict(html=hashlib.sha256((ROOT/'广东数学竞赛成绩查询.html').read_bytes()).hexdigest(),data=hashlib.sha256((ROOT/'data/查询数据.json').read_bytes()).hexdigest()),
                pending_name_count=sum(bool(r.get('name_uncertain')) for r in rows),
                registration_status_counts=dict(Counter(r['award'] for r in rows if r['award'] in ['报名未见获奖','报名匹配待核','考生名单'])),
                boundaries=['仅IMO四条有官方分数与世界名次；高联CMO为名单顺位，初赛未给全省名次','扫描件不是全部字段逐字人工校勘；姓名有疑者标记待核','已比对2020、2025、2026报名表，2024仅专项核对1名考生，其他年份报名资料未完整入库','报名差集不区分未获奖与缺考；匹配有疑者另列待核','评分为本站自定义参考规则，并非官方积分或客观含金量测量'])
    out=ROOT/'evidence/数据与交付核验.json';out.parent.mkdir(exist_ok=True,parents=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','records','sources','competition_counts','pending_name_count']},ensure_ascii=False))
if __name__=='__main__':main()
