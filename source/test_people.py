"""个人档案关联的歧义回归。合成记录与正式数据分开，不写正式账本。"""
import unittest
from build_people import build_people

def row(id,year,grade,school='深圳中学',competition='高联',marker=''):
    return dict(id=id,year=year,grade=grade,school=school,competition=competition,
                marker=marker,name='测试学生',pinyin='ceshixuesheng')

def people(*rs):
    return build_people(dict(records=list(rs)),write_report=False)['people']

class IdentityTests(unittest.TestCase):
    def test_progression_and_cross_competition(self):
        ps=people(row('1',2024,'高一'),row('2',2025,'高二'),row('3',2025,'高二',competition='CMO'),row('4',2025,'',competition='IMO'))
        self.assertEqual(len(ps),1)
        self.assertEqual(set(ps[0]['record_ids']),{'1','2','3','4'})

    def test_same_name_different_schools(self):
        self.assertEqual(len(people(row('1',2024,'高一'),row('2',2025,'高二',school='华南师范大学附属中学'))),2)

    def test_generations_do_not_collapse(self):
        self.assertEqual(len(people(row('1',2020,'高三'),row('2',2025,'高一'),row('3',2026,'高二'))),2)

    def test_same_school_same_event_different_cohorts(self):
        ps=people(row('1',2025,'高一'),row('2',2025,'高二'),row('3',2026,'高二'),row('4',2026,'高三'))
        self.assertEqual({frozenset(p['record_ids']) for p in ps},{frozenset(['1','3']),frozenset(['2','4'])})

    def test_markers_are_not_cross_year_identity(self):
        ps=people(row('1',2025,'高一',marker='1'),row('2',2025,'高一',marker='2'),row('3',2026,'高二',marker='1'),row('4',2026,'高二',marker='2'))
        self.assertEqual(len(ps),4)
        self.assertTrue(all(p['review'] for p in ps))

    def test_unknown_grade_with_two_possible_people(self):
        ps=people(row('1',2025,'高一'),row('2',2025,'高二'),row('3',2025,'',competition='IMO'))
        self.assertEqual(len(ps),3)

    def test_school_alias_and_ocr_code(self):
        ps=people(row('1',2024,'高一',school='深圳高级中学'),row('2',2025,'高二',school='M325510123深圳市高级中学'))
        self.assertEqual(len(ps),1)

    def test_repeat_grade_keeps_visible_review(self):
        ps=people(row('1',2023,'高一'),row('2',2024,'高二'),row('3',2025,'高二'))
        self.assertEqual(len(ps),1)
        self.assertTrue(ps[0]['review'])

    def test_repeat_build_is_stable(self):
        rs=[row('1',2024,'高一'),row('2',2025,'高二')]
        db=dict(records=rs)
        p1=build_people(db,write_report=False)['people']
        p2=build_people(db,write_report=False)['people']
        self.assertEqual(p1,p2)

if __name__=='__main__':unittest.main()
