import unittest
from build_scores import profile_score,ROOT
import json
CONFIG=json.loads((ROOT/'data/评分规则.json').read_text(encoding='utf-8'))
def row(id,year,competition,award,team=False):return dict(id=id,year=year,competition=competition,award=award,team=team,rank=None)
class ScoreTests(unittest.TestCase):
    def test_same_season_not_stacked(self):
        rows=[row('1',2024,'广东初赛','一等奖'),row('2',2024,'高联','一等奖',True),row('3',2024,'CMO','金牌'),row('4',2025,'IMO','金牌')]
        result=profile_score(rows,CONFIG)
        self.assertEqual(result['score'],10000)
        self.assertEqual(len(result['contributions']),1)
    def test_year_does_not_discount(self):
        self.assertEqual(profile_score([row('1',2020,'CMO','金牌')],CONFIG)['score'],profile_score([row('2',2026,'CMO','金牌')],CONFIG)['score'])
    def test_repeat_seasons_have_diminishing_contribution(self):
        rows=[row('1',2023,'高联','一等奖'),row('2',2024,'高联','一等奖')]
        self.assertAlmostEqual(profile_score(rows,CONFIG)['score'],1400*1.4)
    def test_participation_does_not_count_as_prize(self):
        self.assertEqual(profile_score([row('1',2024,'高联','考生名单')],CONFIG)['score'],0)
    def test_tier_overrides_many_low_awards(self):
        a=profile_score([row(str(y),y,'高联','一等奖') for y in range(2020,2027)],CONFIG)
        b=profile_score([row('9',2020,'CMO','铜牌')],CONFIG)
        self.assertGreater(b['tier'],a['tier'])
if __name__=='__main__':unittest.main()
