"""仅依赖 Python 标准库，从已核验的规范化数据重新生成独立离线页面。"""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def main():
    db=json.loads((ROOT/'data/查询数据.json').read_text(encoding='utf-8'))
    template=(ROOT/'source/查询页模板.html').read_text(encoding='utf-8')
    html=template.replace('{{DATA}}',json.dumps(db,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    (ROOT/'广东数学竞赛成绩查询.html').write_text(html,encoding='utf-8')
    print('Rendered',len(db['records']),'records')
if __name__=='__main__':main()
