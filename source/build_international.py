import json,re,fitz,hashlib,unicodedata,requests
from collections import Counter
from pathlib import Path
import openpyxl
from bs4 import BeautifulSoup
from collect_sources import ROOT

def clean(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(s or '')))
def main():
    sources=json.loads((ROOT/'data/CMO来源.json').read_text(encoding='utf-8'));records=[];audit=[]
    for s in sorted(sources,key=lambda s:s['year']):
        year=s['year'];allrows=[];award='';header=None;seen=set()
        if s['local'].endswith('xlsx'):
            w=openpyxl.load_workbook(ROOT/s['local'],read_only=True,data_only=True)
            for row in w.active.iter_rows(min_row=3,values_only=True):
                code,name,gender,province,school,grade,a=row
                if not name:continue
                allrows.append(dict(name=clean(name),school=clean(school),grade=clean(grade),province=clean(province),award={'一等奖':'金牌','二等奖':'银牌','三等奖':'铜牌'}[a],code=clean(code),page=1))
        else:
            d=fitz.open(ROOT/s['local'])
            for ix,p in enumerate(d):
                headings=[]
                for block in p.get_text('dict')['blocks']:
                    for line in block.get('lines',[]):
                        text=clean(''.join(sp['text'] for sp in line['spans']))
                        for word,medal in [('一等奖','金牌'),('二等奖','银牌'),('三等奖','铜牌')]:
                            if word in text and len(text)<30:headings.append((line['bbox'][1],medal))
                for table in p.find_tables().tables:
                    for j,raw in enumerate(table.extract()):
                        cells=[clean(x) for x in raw]
                        joined=''.join(cells)
                        if '一等奖' in joined and '姓名' not in joined:award='金牌';continue
                        if '二等奖' in joined and '姓名' not in joined:award='银牌';continue
                        if '三等奖' in joined and '姓名' not in joined:award='铜牌';continue
                        if any(c=='姓名' for c in cells):header=cells;continue
                        if header is None:continue
                        ry=min(c[1] for c in table.rows[j].cells if c)
                        relevant=[h for h in headings if h[0]<ry+2]
                        if relevant:award=max(relevant)[1]
                        if not award:
                            text=clean(p.get_text())
                            award='金牌' if '一等奖' in text else '银牌' if '二等奖' in text else '铜牌' if '三等奖' in text else ''
                        if not award:raise RuntimeError('missing medal '+str(year))
                        ni=header.index('姓名');si=header.index('学校');pi=header.index('省份');gi=header.index('年级')
                        if len(cells)<=max(ni,si,pi,gi) or not cells[ni] or not cells[si]:continue
                        if not re.fullmatch(r'(?:M\d+|\d+)',cells[0]):continue
                        key=(award,cells[0],cells[ni],cells[si])
                        if key in seen:continue
                        seen.add(key)
                        allrows.append(dict(name=cells[ni],school=cells[si],grade=cells[gi],province=cells[pi],award=award,code=cells[0],page=ix+1))
        # 2020年奖项标题位于表格之外，从逐页文字中的标题切换，随后由序号/省份核验。
        for order,r in enumerate(allrows,1):
            if '广东' not in r['province']:continue
            records.append(dict(year=year,competition='CMO',name=r['name'],marker='',school=r['school'],grade=r['grade'],
                                award=r['award'],awards=[r['award']],team=False,score=None,rank=None,list_order=order,
                                rank_label='全国获奖名单顺位',rank_note='中国数学会获奖名单的排列位置；未公布分数及并列信息，不当作官方竞赛名次',
                                code=r['code'],refs=[dict(source=s['id'],page=r['page'])],status=s['status'],confidence=1,
                                review='中国数学会原生PDF/Excel表格提取；未公布分数与并列名次'))
        audit.append(dict(year=year,total=len(allrows),medals=dict(Counter(r['award'] for r in allrows)),guangdong=sum('广东' in r['province'] for r in allrows)))
    snapshot=ROOT/'原始资料/IMO/中国队个人成绩-官网快照.html'
    url='https://www.imo-official.org/results/individual/country/CHN/'
    if not snapshot.exists():snapshot.write_bytes(requests.get(url,timeout=30).content)
    s=BeautifulSoup(snapshot.read_bytes(),'html.parser')
    # 中文姓名与学校有学校官网/中国数学会公开资料支持；不单凭拼音自动认人。
    identity={
        (2020,'Rui Rao'):('饶睿','华南师范大学附属中学','https://www.hsfz.net.cn/list_68/4031.html'),
        (2021,'Yebo Peng'):('彭也博','深圳中学','https://www.shenzhong.net/textnewslist_87/15602.html'),
        (2021,'Chenxu Feng'):('冯晨旭','深圳中学','https://www.shenzhong.net/textnewslist_87/15602.html'),
        (2023,'Zhicheng Jiang'):('姜志城','深圳中学','https://www.shenzhong.net/textnewslist_24/16213.html'),
    }
    found=set();imorows=[]
    for tr in s.select('tr'):
        cells=[td.get_text(' ',strip=True) for td in tr.select('td')]
        if len(cells)<12 or not cells[0].isdigit():continue
        year=int(cells[0]);english=cells[1]
        if not 2020<=year<=2026:continue
        imorows.append(dict(year=year,english=english,rank=cells[2],award=cells[4],score=cells[5]))
        key=(year,english)
        if key not in identity:continue
        name,school,school_url=identity[key];found.add(key)
        records.append(dict(year=year,competition='IMO',name=name,english_name=english,marker='',school=school,grade='',award={'G':'金牌','S':'银牌','B':'铜牌'}[cells[4]],
                            awards=[{'G':'金牌','S':'银牌','B':'铜牌'}[cells[4]]],team=False,score=int(cells[5]),problem_scores=[int(x) for x in cells[6:12]],
                            rank=int(cells[2]),list_order=None,rank_label='世界名次（含并列）',rank_note='直接使用IMO官网Rank字段，保留官方并列名次',
                            code='',refs=[dict(source='IMO-CHN',page=1)],status='正式',confidence=1,identity_source=school_url,
                            review='英文成绩来自IMO官网；中文姓名与学校由学校官网校对'))
    assert found==set(identity),(found,set(identity))
    sources.append(dict(id='IMO-CHN',year=2026,kind='IMO',title='IMO官网中国队历年个人成绩（筛选2020—2026）',url=url,article=url,
                        local=snapshot.relative_to(ROOT).as_posix(),pages=1,status='正式',sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                        retrieved='2026-11-02',originNote='本地保存官网HTML快照；广东身份由学校官网交叉核对'))
    (ROOT/'data/国际与决赛记录.json').write_text(json.dumps(dict(records=records,sources=sources),ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'evidence/CMO与IMO提取核对.json').write_text(json.dumps(dict(cmo=audit,imo_china=imorows,included_guangdong=list(sorted(found))),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(cmo=audit,total_records=len(records),imo=list(sorted(found))),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
