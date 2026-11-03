"""从成绩行建立可追溯的个人档案；不把姓名相同直接当作身份相同。仅用标准库。"""
from pathlib import Path
from collections import defaultdict, Counter
import hashlib, json, re, unicodedata
from functools import lru_cache

ROOT = Path(__file__).resolve().parents[1]
SCHOOL_ALIASES = {
    '广东省深圳中学': '深圳中学',
    '深圳高级中学': '深圳市高级中学',
    '深圳市高级中学中心校区': '深圳市高级中学',
    '深圳高级中学(集团)': '深圳市高级中学',
    '深圳高级中学(集团)中心校区': '深圳市高级中学',
    '佛山南海区石门中学': '佛山市南海区石门中学',
    '佛山市南海区石门中学高中部': '佛山市南海区石门中学',
    '广东省珠海市第一中学': '珠海市第一中学',
    '湛江第一中学': '湛江市第一中学',
    '中山纪念中学': '中山市中山纪念中学',
    '宝安中学集团高中部': '深圳市宝安中学(集团)高中部',
    '潮阳实验学校': '汕头市潮阳实验学校',
    '华大实验学校': '汕尾市华大实验学校',
    '广东省化州市第一中学': '化州市第一中学',
    '东莞市东华高级中学(东城校区)': '东莞市东华高级中学',
    '深圳外国语学校(包含集团校及高中园)': '深圳外国语学校',
}

@lru_cache(maxsize=16384)
def school_key(s):
    s = re.sub(r'\s+', '', unicodedata.normalize('NFKC', s))
    # OCR 将相邻的准考证号粘入学校列；只改索引，不覆盖原始校名。
    s = re.sub(r'^[MN]\d{6,}', '', s, flags=re.I)
    return SCHOOL_ALIASES.get(s, s)

def grade_number(r):
    return {'高一': 1, '高二': 2, '高三': 3}.get(r.get('grade'))

def cohort(r):
    g = grade_number(r)
    return r['year'] - g if g else None

def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]

def build_people(db, write_report=True):
    rows = db['records']
    if write_report:
        # 这些前缀只用于本项目可重建的补充行。重建时替换，避免旧候选滞留。
        rows[:]=[r for r in rows if not r['id'].startswith(('prelim-','reg-','supp-'))]
        db['sources'][:]=[s for s in db['sources'] if s['kind'] not in ['广东初赛','考场安排'] and not(s['kind']=='报名名单' and s['year']!=2026)]
        for r in rows:r.pop('registration_refs',None)
        db['supplementalCoverage']=[]
    for supplemental_path in ([ROOT/'data/补充考生记录.json',ROOT/'data/广东初赛记录.json',ROOT/'data/报名补充记录.json'] if write_report else []):
        if not supplemental_path.exists():continue
        extra=json.loads(supplemental_path.read_text(encoding='utf-8'))
        ids={r['id'] for r in rows}
        for r in extra['records']:
            if r['id'] not in ids:rows.append(r.copy());ids.add(r['id'])
        source_ids={s['id'] for s in db['sources']}
        for s in extra['sources']:
            if s['id'] not in source_ids:db['sources'].append(s.copy());source_ids.add(s['id'])
        if extra.get('coverage'):db['supplementalCoverage'].extend(extra['coverage'])
        for link in extra.get('links',[]):
            target=next((r for r in rows if r['id']==link['record_id']),None)
            if target:target.setdefault('registration_refs',[]).append(link)
    if write_report:
        db['registrationNote']='已比对2020、2025、2026报名表；2024仅专项核对1名考生，其他年份报名资料尚未完整入库。未见获奖记录不证明实际缺考；OCR或身份匹配有疑者另列待核。年级按原表保留，不据年级差异排除报名匹配。'
    groups = defaultdict(list)
    for r in rows:
        r['school_key'] = school_key(r['school'])
        groups[(r['name'], r['school_key'])].append(r)
    profiles = []
    for (name, school), rs in sorted(groups.items()):
        # 同校同名同年同场次出现两行时，不假定数字标记跨年仍指同一人。
        events = Counter((r['year'], r['competition'], cohort(r)) for r in rs)
        blocked = [r for r in rs if events[(r['year'], r['competition'], cohort(r))] > 1]
        clean = [r for r in rs if r not in blocked]
        tracks = defaultdict(list)
        unknown = []
        for r in clean:
            c = cohort(r)
            if c is None: unknown.append(r)
            else: tracks[c].append(r)
        bundles = [(v, '同校同名，年级逐年对应', False) for _, v in sorted(tracks.items())]
        # 同校连续记录偶有留级/原表年级误差。无同场次冲突、学段不逆行，
        # 且总跨度不超过三个学年时统一归档，并保留年级差异提醒。
        if len(bundles) > 1 and not blocked:
            known = sorted(clean, key=lambda r: r['year'])
            years = sorted({r['year'] for r in known})
            by_year = defaultdict(set)
            for r in known:
                if grade_number(r): by_year[r['year']].add(grade_number(r))
            gs = [next(iter(by_year[y])) for y in years if len(by_year[y]) == 1]
            if (years[-1]-years[0] <= 2 and all(len(v) == 1 for v in by_year.values())
                    and len({(r['year'], r['competition']) for r in clean}) == len(clean)
                    and gs == sorted(gs)):
                bundles = [(clean[:], '同校同名的连续学年；原表年级进度有差异', True)]
                unknown = []
        for r in unknown:
            candidates = [b for b in bundles if min(z['year'] for z in b[0])-1 <= r['year'] <= max(z['year'] for z in b[0])+1
                          and max(z['year'] for z in b[0]+[r])-min(z['year'] for z in b[0]+[r]) <= 2
                          and not any(z['year'] == r['year'] and z['competition'] == r['competition'] for z in b[0])]
            if len(candidates) == 1:
                candidates[0][0].append(r)
            else:
                bundles.append(([r], '年级未列，暂按独立记录建档', True))
        for r in blocked:
            bundles.append(([r], '同年同校同名出现多条；跨年数字标记未核实，暂不关联', True))
        for items, reason, review in bundles:
            items.sort(key=lambda r: (-r['year'], {'IMO': 0, 'CMO': 1, '高联': 2,'广东初赛':3}[r['competition']], r['id']))
            cohorts = sorted({cohort(r) for r in items if cohort(r) is not None})
            anchor = str(cohorts) if cohorts and not any(r in blocked for r in items) else items[-1]['id']
            pid = 'person-' + digest(name+'|'+school+'|'+anchor)
            profile = dict(id=pid, name=name, pinyin=items[0]['pinyin'], school=school,
                           schools=sorted({r['school'] for r in items}), record_ids=[r['id'] for r in items],
                           years=sorted({r['year'] for r in items}), rule=reason,
                           review=review, same_name_count=1)
            profiles.append(profile)
            for r in items: r['person_id'] = pid
    # 支持带来源说明的人工关联。默认空表，不凭转校猜测身份。
    overrides_path = ROOT/'data/个人关联更正.json'
    overrides = json.loads(overrides_path.read_text(encoding='utf-8')) if overrides_path.exists() else []
    for o in overrides:
        assert o.get('reason') and o.get('evidence'), '人工关联必须保留理由与依据'
        requested = set(o['record_ids'])
        matched = [p for p in profiles if requested.intersection(p['record_ids'])]
        assert len(matched) > 1 and {p['name'] for p in matched} == {o['name']}
        all_ids = {rid for p in matched for rid in p['record_ids']}
        assert requested <= all_ids
        items = [r for r in rows if r['id'] in all_ids]
        p = matched[0].copy()
        p.update(record_ids=[r['id'] for r in items], schools=sorted({r['school'] for r in items}),
                 years=sorted({r['year'] for r in items}), rule=o['reason'], evidence=o['evidence'], review=False)
        profiles = [p0 for p0 in profiles if p0 not in matched] + [p]
        for r in items: r['person_id'] = p['id']
    name_counts = Counter(p['name'] for p in profiles)
    row_index = {r['id']: i for i, r in enumerate(rows)}
    profiles.sort(key=lambda p: min(row_index[rid] for rid in p['record_ids']))
    for p in profiles: p['same_name_count'] = name_counts[p['name']]
    db['people'] = profiles
    db['schemaVersion'] = 2
    db['identityPolicy'] = '同校同名及相容学年关联个人档案；学校别名归一；同场次重名、跨校身份不明者分开，个人页提供待关联入口。原始成绩行与来源全部保留。'
    report = dict(status='passed', records=len(rows), profiles=len(profiles),
                  merged_profiles=sum(len(p['record_ids']) > 1 for p in profiles),
                  records_in_merged_profiles=sum(len(p['record_ids']) for p in profiles if len(p['record_ids']) > 1),
                  review_profiles=sum(p['review'] for p in profiles),
                  school_aliases=SCHOOL_ALIASES,
                  groups=[{k:p[k] for k in ['id','name','school','record_ids','rule','review','same_name_count']} for p in profiles if len(p['record_ids']) > 1 or p['review']])
    if write_report:
        (ROOT/'evidence/个人档案关联.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return db

if __name__ == '__main__':
    p = ROOT/'data/查询数据.json'
    db = build_people(json.loads(p.read_text(encoding='utf-8')))
    p.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')
    print('个人档案', len(db['people']), '成绩行', len(db['records']))
