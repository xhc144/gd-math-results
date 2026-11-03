"""广东省初赛与高联分别建档：原表未给分数/全省名次，不据地区分组行序编排名。"""
from pathlib import Path
from collections import Counter
import json,re,hashlib,fitz
from build_data import make_aliases
ROOT=Path(__file__).resolve().parents[1]

def main():
    pdf=ROOT/'原始资料/2024/2024-广东初赛获奖公示-3521.pdf'
    doc=fitz.open(pdf);records=[];audit=[]
    for ix,page in enumerate(doc):
        rows=[]
        for table in page.find_tables().tables:
            for j,cells in enumerate(table.extract()):
                cells=[re.sub(r'\s+','',c or '') for c in cells]
                if cells==['地区','姓名','准考证号','所在学校','获奖情况']:continue
                if len(cells)!=5 or not any(cells):continue
                city,name,code,school,award=cells
                assert re.fullmatch(r'\d{6,10}',code) and award in ['一等奖','二等奖','三等奖'] and name,(ix+1,cells)
                school_missing=not school
                if school_missing:school='（原表未列学校）'
                py,aliases=make_aliases(name)
                rec=dict(id='prelim-2024-'+code,year=2024,competition='广东初赛',name=name,marker='',school=school,grade='',
                         award=award,awards=[award],team=False,name_uncertain=False,rank=None,list_order=None,rank_label='',
                         rank_note='初赛原表按地区、奖项分组，未公布分数及全省名次',refs=[dict(source='广东初赛-2024-3521',page=ix+1)],
                         code=code,score=None,status='公示',confidence=1.0,pinyin=py,aliases=aliases,
                         review='原生表格提取；姓名、学校、准考证号、奖项与原表行对应；原表未列年级和分数',city=city,school_missing=school_missing)
                records.append(rec);rows.append(code)
        text_awards=len(re.findall(r'(?m)^[一二三]等奖$',page.get_text()))
        assert len(rows)==text_awards,(ix+1,len(rows),text_awards)
        audit.append(dict(page=ix+1,rows=len(rows),codes=rows,text_awards=text_awards))
    assert len({r['code'] for r in records})==len(records)
    yang=[r for r in records if r['name']=='杨奕辰' and r['school']=='深圳中学']
    assert len(yang)==1 and yang[0]['award']=='一等奖' and yang[0]['refs'][0]['page']==20
    page=doc[19];pos=page.search_for('杨奕辰');assert len(pos)==1
    clip=fitz.Rect(0,pos[0].y0-5,page.rect.width,pos[0].y1+5)
    out=ROOT/'evidence/杨奕辰专项复核'
    page.get_pixmap(matrix=fitz.Matrix(3,3),clip=clip,alpha=False).save(out/'2024初赛一等奖原行.png')
    page.get_pixmap(matrix=fitz.Matrix(1.8,1.8),alpha=False).save(out/'2024初赛第20页.png')
    source=dict(id='广东初赛-2024-3521',year=2024,kind='广东初赛',status='公示',title='广东省中学生数学奥林匹克竞赛公示名单-0701',
                article='https://math.sysu.edu.cn/article/3521',url='https://math.sysu.edu.cn/sites/default/files/2024-07/广东省中学生数学奥林匹克竞赛公示名单-0701.pdf',
                local=pdf.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),bytes=pdf.stat().st_size,
                pages=len(doc),retrieved='2026-11-02',publisher='广东省数学会（中山大学数学学院网站）',originNote='2024广东省初赛，区别于9月高联；官方公示')
    payload=dict(sources=[source],records=records)
    (ROOT/'data/广东初赛记录.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    report=dict(status='passed',year=2024,records=len(records),by_award=dict(Counter(r['award'] for r in records)),
                pages=audit,missing_grade=True,missing_score=True,rank_not_published=True,yang=yang)
    (ROOT/'evidence/广东初赛逐页核对.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','records','by_award']},ensure_ascii=False))
if __name__=='__main__':main()
