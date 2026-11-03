"""仅依赖 Python 标准库，从已核验的规范化数据重新生成独立离线页面。"""
from pathlib import Path
import json,csv
from build_people import build_people
from build_scores import build_scores
ROOT=Path(__file__).resolve().parents[1]

def write_csv(db):
    with (ROOT/'data/广东数学竞赛记录.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f)
        w.writerow(['选手档案ID','赛事','年份','姓名','原名单同名标记','姓名拼音','学校','年级','奖项','省队资格','状态','编号','分数','官方名次','名单顺位','顺位口径'])
        for r in db['records']:
            w.writerow([r['person_id'],r['competition'],r['year'],r['name'],r.get('marker',''),r['pinyin'],r['school'],r['grade'],r['award'],'是' if r['team'] else '否',r['status'],r['code'],r['score'] if r['score'] is not None else '未公布',r['rank'] or '',r['list_order'] or '',r['rank_label']])
def main():
    db=json.loads((ROOT/'data/查询数据.json').read_text(encoding='utf-8'))
    db=build_people(db)
    db=build_scores(db)
    (ROOT/'data/查询数据.json').write_text(json.dumps(db,ensure_ascii=False,indent=2),encoding='utf-8')
    template=(ROOT/'source/查询页模板.html').read_text(encoding='utf-8')
    html=template.replace('{{DATA}}',json.dumps(db,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    html=html.replace('{{DIRECTORY_JS}}',(ROOT/'source/目录与评分.js').read_text(encoding='utf-8'))
    (ROOT/'广东数学竞赛成绩查询.html').write_text(html,encoding='utf-8')
    write_csv(db)
    print('Rendered',len(db['records']),'records')
if __name__=='__main__':main()
