from pathlib import Path
import requests,json,hashlib,concurrent.futures,fitz
from collect_sources import ROOT
URLS={2020:'https://www.cms.org.cn/upload/editor/file/20201129/29103613863.pdf',
2021:'https://www.cms.org.cn/upload/file/2112/27328.pdf',
2022:'https://www.cms.org.cn/ueditor/php/upload/file/20230108/1673139646538938.pdf',
2023:'https://www.cms.org.cn/Uploads/20231204/35b9db5826e4a542e5f2284414c1e735.pdf',
2024:'https://www.cms.org.cn/Uploads/20241213/d43493c9caf4455e10bb662cbbffde71.pdf',
2025:'https://old2026.cms.org.cn/upload/file/20260420/1776645923730547.xlsx'}

def fetch(job):
    year,url=job;ext=url.split('.')[-1];dest=ROOT/f'原始资料/CMO/{year}-CMO获奖名单.{ext}';dest.parent.mkdir(exist_ok=True,parents=True)
    used=url
    if not dest.exists():
        error=''
        for u in dict.fromkeys([url,url.replace('www.cms.org.cn','old2026.cms.org.cn'),url.replace('old2026.cms.org.cn','www.cms.org.cn')]):
            try:
                r=requests.get(u,timeout=20);r.raise_for_status()
                assert r.content.startswith(b'%PDF' if ext=='pdf' else b'PK')
                dest.write_bytes(r.content);used=u;break
            except Exception as e:error=str(e)
        else:raise RuntimeError(f'{year}: {error}')
    pages=len(fitz.open(dest)) if ext=='pdf' else 1
    meta=dict(id=f'CMO-{year}',year=year,kind='CMO',title=f'{year}年全国中学生数学奥林匹克竞赛（决赛）获奖名单',url=url,article=used,
              local=dest.relative_to(ROOT).as_posix(),pages=pages,status='公示' if year==2020 else '正式',
              sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),retrieved='2026-11-02',bytes=dest.stat().st_size)
    print(year,pages,dest.stat().st_size,flush=True)
    if ext=='pdf':
        d=fitz.open(dest);print(year,d[0].get_text()[:900],flush=True)
    return meta

if __name__=='__main__':
    ss=[]
    with concurrent.futures.ThreadPoolExecutor(3) as ex:
        for f in concurrent.futures.as_completed([ex.submit(fetch,j) for j in URLS.items()]):
            try:ss.append(f.result())
            except Exception as e:print('FAILED',str(e),flush=True)
    (ROOT/'data/CMO来源.json').write_text(json.dumps(ss,ensure_ascii=False,indent=2),encoding='utf-8')
