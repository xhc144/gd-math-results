from pathlib import Path
import json,re,time,hashlib
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/浏览器验收';OUT.mkdir(parents=True,exist_ok=True)
def main():
    checks=[];errors=[]
    def check(name,ok):
        checks.append(dict(name=name,passed=bool(ok)))
        assert ok,name
    with sync_playwright() as w:
        b=w.chromium.launch(headless=True,channel='msedge')
        ctx=b.new_context(viewport={'width':1440,'height':1000},offline=True,accept_downloads=True)
        p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
        p.goto((ROOT/'广东数学竞赛成绩查询.html').as_uri());expect(p.locator('#summary')).to_contain_text('条记录')
        db=json.loads((ROOT/'data/查询数据.json').read_text(encoding='utf-8'))
        def count():return int(re.search(r'[\d,]+',p.locator('#summary').inner_text()).group().replace(',',''))
        def search(q):p.locator('#query').fill(q);p.locator('#searchForm button').click()
        check('离线加载全部真实记录',count()==len(db['records']))
        p.screenshot(path=str(OUT/'桌面-首页.png'))
        p.locator('#next').click();check('翻页后显示41起',p.locator('#range').inner_text().startswith('显示 41'))
        p.locator('#prev').click()
        search('李泽熙');n=count();check('中文姓名可查询',n>=3)
        chinese=p.locator('.records tbody').inner_text()
        for q in ['lizexi','LI ZE XI','lzx']:
            search(q);check('拼音检索 '+q,'李泽熙' in p.locator('#result').inner_text())
            if q!='lzx':check('全拼与中文结果一致 '+q,count()==n)
        search('冯晨旭');p.locator('#competition').select_option('IMO');check('IMO冯晨旭官方世界17名31分',count()==1 and '17' in p.locator('#result').inner_text() and '31' in p.locator('#result').inner_text())
        p.locator('.name').click();expect(p.locator('#detail')).to_be_visible();check('跨赛事同名历年记录',p.locator('#detailBody').inner_text().count('CMO')>=1)
        p.screenshot(path=str(OUT/'桌面-选手详情.png'));p.locator('#closeDetail').click()
        p.locator('#reset').click();p.locator('#year').select_option('2026');p.locator('#award').select_option('省队');check('2026省队38条',count()==38)
        p.locator('#reset').click();p.locator('#competition').select_option('CMO');p.locator('#year').select_option('2024');check('2024CMO广东38条',count()==38)
        p.locator('#reset').click();search('黄梓睿');p.locator('#year').select_option('2026');p.locator('#award').select_option('二等奖');check('同校同名原始标记不合并',count()==2 and '[1]' in p.locator('#result').inner_text() and '[2]' in p.locator('#result').inner_text())
        with p.expect_download() as dl:p.locator('#export').click()
        fn=OUT/'筛选导出.csv';dl.value.save_as(fn);data=fn.read_text(encoding='utf-8-sig');check('导出当前筛选含名次顺位和同名标记',len(data.strip().splitlines())==3 and '官方名次' in data)
        p.locator('#reset').click();p.locator('#award').select_option('报名未见获奖');check('报名比对分类仅2026且未区分缺考',count()>0 and all(x.inner_text()=='2026' for x in p.locator('.year').all()) and '未区分' in p.locator('#result').inner_text())
        search('abcdefxyznotexists');check('无结果且不推断未获奖',count()==0 and '不代表' in p.locator('#result').inner_text())
        p.locator('#reset').click();search('李泽熙');p.locator('#year').select_option('2026');p.locator('.src button').first.click()
        anchor=p.locator('#detailBody a').first;href=anchor.get_attribute('href')
        with p.expect_popup() as pop:anchor.click()
        popup=pop.value;popup.wait_for_timeout(1000);print('PDF POPUP',popup.url,'LINK',href,flush=True);check('实际点击打开对应本地PDF页',popup.url.startswith('file:') and '.pdf' in popup.url and '#page=' in popup.url);popup.close();p.locator('#closeDetail').click()
        p.locator('[data-tab="coverage"]').click();check('年度矩阵包含高联CMO与IMO',all(x in p.locator('#coverage').inner_text() for x in ['2020','2026','CMO','IMO']))
        p.screenshot(path=str(OUT/'桌面-年度收录.png'))
        p.locator('[data-tab="sources"]').click();check('全部来源可见',p.locator('.sourceitem').count()==len(db['sources']))
        p.locator('[data-tab="records"]').click();p.locator('#reset').click()
        p.set_viewport_size({'width':390,'height':844});p.screenshot(path=str(OUT/'窄屏-首页.png'))
        check('390窄屏无页面横向溢出',p.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        search('冯晨旭');p.locator('.name').first.click();p.screenshot(path=str(OUT/'窄屏-选手详情.png'));check('窄屏详情可打开关闭',p.locator('#detail').is_visible());p.keyboard.press('Escape')
        check('无JavaScript运行错误',not errors)
        report=dict(status='passed',browser='Microsoft Edge headless',offline=True,checks=checks,check_count=len(checks),errors=errors,
                    html_sha256=hashlib.sha256((ROOT/'广东数学竞赛成绩查询.html').read_bytes()).hexdigest(),screenshots=[f.name for f in OUT.glob('*.png')])
        (OUT/'浏览器检查.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print('PASS',len(checks),'checks');b.close()
if __name__=='__main__':main()
