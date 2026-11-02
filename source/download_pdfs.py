from pathlib import Path
import requests,json,hashlib,concurrent.futures,shutil,os
import fitz
from collect_sources import ROOT

def fetch(s):
    kind=next((k for k in ['一等奖','二等奖','三等奖'] if k in s['title']),'省队')
    if s['year']==2020 and '通知' in s['title']: kind='省队及省一公示'
    sid=f"{s['year']}-{kind}-{s['article'].split('/')[-1]}"
    dest=ROOT/'原始资料'/str(s['year'])/(sid+'.pdf')
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():
        r=requests.get(s['url'],params={'download':'1'},headers={'User-Agent':'Mozilla/5.0','Referer':s['article']},timeout=60)
        r.raise_for_status()
        assert r.content.startswith(b'%PDF'), (sid,r.status_code,r.text[:100])
        dest.write_bytes(r.content)
    doc=fitz.open(dest)
    text='\n'.join(p.get_text() for p in doc)
    s.update(id=sid,kind=kind,local=dest.relative_to(ROOT).as_posix(),
             sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size,
             pages=len(doc),retrieved='2026-11-02',retrieval='官网原始 PDF（下载链接 download=1）',
             publisher='广东省数学会（中山大学数学学院网站）')
    if s['year']==2026 and kind in ['二等奖','三等奖']: s['status']='公示'
    out=ROOT/'data'/'提取文本'
    out.mkdir(exist_ok=True)
    (out/(sid+'.txt')).write_text(text,encoding='utf-8')
    print(sid,len(doc),len(text),text[:130].replace('\n',' '),flush=True)
    return s

if __name__=='__main__':
    sources=json.loads((ROOT/'data/附件候选.json').read_text(encoding='utf-8'))
    supplemental=ROOT/'data/补充附件候选.json'
    if supplemental.exists():sources+=json.loads(supplemental.read_text(encoding='utf-8'))
    sources=list({(s['article'],s['url']):s for s in sources}.values())
    with concurrent.futures.ThreadPoolExecutor(4) as ex:
        data=list(ex.map(fetch,sources))
    (ROOT/'data/PDF来源清单.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    # 本地输入路径由调用者显式提供；开源代码不包含个人聊天软件目录。
    user_dir=os.environ.get('GD_MATH_USER_INPUT_DIR')
    if not user_dir:
        print('PDFS',len(data),'No optional local input directory supplied')
        raise SystemExit(0)
    user=Path(user_dir)
    supplied={ '省队':'决赛名单（广东）(1).pdf','一等奖':'一等奖名单（广东）(1).pdf',
              '二等奖':'二等奖公示名单（广东）(1).pdf','三等奖':'三等奖公示名单（广东）(2).pdf'}
    compare=[]
    for s in data:
        if s['year']!=2026: continue
        f=user/supplied[s['kind']]
        compare.append(dict(id=s['id'],user_filename=f.name,official_sha256=s['sha256'],
                            user_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),
                            equal=hashlib.sha256(f.read_bytes()).hexdigest()==s['sha256']))
        shutil.copy2(f,ROOT/'原始资料/2026'/f.name)
    (ROOT/'evidence/用户文件与官网核对.json').write_text(json.dumps(compare,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PDFS',len(data),'USER_EQUALS',all(x['equal'] for x in compare))
