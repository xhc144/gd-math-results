"""保存官方公告及附件。直连失败时保存 Jina Reader 读取的官网文本，绝不冒充 PDF 原件。"""
from pathlib import Path
import requests, re, json, hashlib, time, concurrent.futures, shutil
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / '原始资料'
SNAP = RAW / '官网文本快照'
for p in [SNAP, ROOT/'data', ROOT/'evidence', RAW/'2026']:
    p.mkdir(parents=True, exist_ok=True)

def read_official(url, dest):
    if dest.exists():
        return dest.read_text(encoding='utf-8')
    err = None
    for attempt in range(3):
        try:
            r = requests.get('https://r.jina.ai/'+url, timeout=90)
            r.raise_for_status()
            assert 'Markdown Content:' in r.text and 'Access Forbidden' not in r.text
            dest.write_text(r.text, encoding='utf-8')
            return r.text
        except Exception as e:
            err = e
            time.sleep(1+attempt)
    raise RuntimeError(f'{url}: {err}')

ARTICLES = {2546:2020, 2501:2020, 2840:2021, 3130:2022, 3090:2022, 3114:2022, 3115:2022,
            3324:2023, 3325:2023, 3341:2023, 3583:2024, 3772:2025, 3781:2025,
            3977:2026, 3978:2026, 3979:2026, 3980:2026}

def article(item):
    aid, year = item
    url = f'https://math.sysu.edu.cn/article/{aid}'
    t = read_official(url, SNAP/f'公告-{aid}.md')
    links = re.findall(r'\[([^\n]+?)\]\((https?://[^\s]+?\.pdf)\)', t, flags=re.I)
    date = re.search(r'发布日期[：:]\s*(\d{4}-\d{2}-\d{2})', t)
    print('ARTICLE', aid, year, [(x[0], unquote(x[1]).split('/')[-1]) for x in links], flush=True)
    return [dict(year=year, article=url, article_snapshot=f'原始资料/官网文本快照/公告-{aid}.md',
                 published=date.group(1) if date else '', title=label, url=urlpdf,
                 status='公示' if aid==2501 else '正式') for label,urlpdf in links]

def fetch_attachment(s):
    title = unquote(s['url']).split('/')[-1]
    kind = next((k for k in ['一等奖','二等奖','三等奖'] if k in title), '省队')
    if '通知' in title and s['year']!=2020:
        return None
    sid=f"{s['year']}-{kind}-公告{s['article'].split('/')[-1]}"
    if s['year']==2020 and '通知' in title:
        sid='2020-省队公示'
    s.update(id=sid, kind=kind, publisher='广东省数学会（中山大学数学学院网站）',
             retrieval='Jina Reader 转读官方附件', retrieved='2026-11-02')
    dest=SNAP/(sid+'.md')
    t=read_official(s['url'],dest)
    s.update(snapshot=dest.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
             bytes=dest.stat().st_size)
    print('ATTACHMENT',sid,len(t),t[t.find('Markdown Content:')+17:t.find('Markdown Content:')+230].replace('\n',' '),flush=True)
    return s

def main():
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        lists=list(ex.map(article, ARTICLES.items()))
    links=[s for group in lists for s in group]
    (ROOT/'data/附件候选.json').write_text(json.dumps(links,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SAVED',len(links),'official attachment links. Run download_pdfs.py to save binary PDF originals.',flush=True)

if __name__=='__main__': main()
