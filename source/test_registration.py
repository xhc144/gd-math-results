import unittest
from build_registration_supplements import classify
class RegistrationTests(unittest.TestCase):
 def test_grade_difference_does_not_drop_registration(self):
  r=dict(year=2025,name='测试甲',school='深圳中学',grade='高三',identity_fields_consistent=True)
  a=dict(year=2025,name='测试甲',school='深圳中学',grade='高一')
  self.assertEqual(classify(r,[a])[0],'matched')
 def test_missing_award_not_absence_assertion(self):
  r=dict(year=2025,name='测试乙',school='深圳中学',identity_fields_consistent=True)
  self.assertEqual(classify(r,[])[0],'报名未见获奖')
 def test_uncertain_ocr_is_pending(self):
  r=dict(year=2025,name='测试乙',school='深圳中学',identity_fields_consistent=False)
  self.assertEqual(classify(r,[])[0],'报名匹配待核')
 def test_one_character_mismatch_is_not_false_negative(self):
  r=dict(year=2025,name='测试乙',school='深圳中学',identity_fields_consistent=True)
  self.assertEqual(classify(r,[dict(year=2025,name='测试己',school='深圳中学')])[0],'报名匹配待核')
if __name__=='__main__':unittest.main()
