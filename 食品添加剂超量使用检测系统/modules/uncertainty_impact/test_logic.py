import copy
import json
import math
import unittest

from modules.uncertainty_impact.logic import Engine


class TestUncertaintyImpactEngine(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_example_is_serializable_and_has_five_records(self):
        payload = self.engine.example()
        self.assertIsInstance(payload, dict)
        self.assertGreaterEqual(len(payload["records"]), 5)
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertIn("苯甲酸", encoded)
        self.assertIsNone(self.engine.validate(payload))

    def test_standard_relative_uncertainty_conversion(self):
        payload = {
            "records": [
                {
                    "sample_id": "A-1",
                    "additive": "山梨酸",
                    "result": 100.0,
                    "limit": 105.0,
                    "unit": "mg/kg",
                    "uncertainty": 3.0,
                    "uncertainty_type": "标准不确定度",
                    "uncertainty_form": "相对",
                    "coverage_factor": 2.0,
                    "coverage_factor_source": "方法确认报告-01",
                }
            ],
            "relative_uncertainty_unit": "%",
            "digits": 4,
        }
        before = copy.deepcopy(payload)
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(payload, before)
        self.assertEqual(row["标准不确定度绝对值"], 3.0)
        self.assertEqual(row["扩展不确定度绝对值"], 6.0)
        self.assertEqual(row["区间下界"], 94.0)
        self.assertEqual(row["区间上界"], 106.0)
        self.assertEqual(row["下界限量比"], round(94 / 105, 4))
        self.assertEqual(row["上界限量比"], round(106 / 105, 4))
        self.assertEqual(row["交叠关系"], "边界重叠")
        self.assertEqual(result["series"][1]["value"], 1)

    def test_boundary_upper_equal_limit_not_triggered(self):
        payload = {
            "records": [
                {
                    "sample_id": "B-1",
                    "additive": "苯甲酸",
                    "result": 0.9,
                    "limit": 1.0,
                    "unit": "g/kg",
                    "uncertainty": 0.1,
                    "uncertainty_type": "扩展不确定度",
                    "uncertainty_form": "绝对",
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["区间上界"], 1.0)
        self.assertEqual(row["交叠关系"], "未触发边界")
        self.assertEqual(row["判定裕量"], 0.0)

    def test_lower_above_limit_is_strong_risk(self):
        payload = {
            "records": [
                {
                    "sample_id": "C-1",
                    "additive": "脱氢乙酸",
                    "result": 1.3,
                    "limit": 1.0,
                    "unit": "g/kg",
                    "uncertainty": 0.2,
                    "uncertainty_type": "扩展不确定度",
                    "uncertainty_form": "绝对",
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["区间下界"], 1.1)
        self.assertEqual(row["区间上界"], 1.5)
        self.assertEqual(row["交叠关系"], "较强超量风险")
        self.assertAlmostEqual(row["判定裕量"], 0.1)

    def test_missing_uncertainty_requires_review(self):
        payload = {
            "records": [
                {
                    "sample_id": "D-1",
                    "additive": "亚硝酸盐",
                    "result": 31.0,
                    "limit": 30.0,
                    "unit": "mg/kg",
                    "uncertainty": None,
                    "uncertainty_type": "未知",
                    "uncertainty_form": "未知",
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["交叠关系"], "不确定度不足")
        self.assertEqual(row["区间下界"], "无法计算")
        self.assertIn("待人工复核", row["复核建议"])
        self.assertNotEqual(row["交叠关系"], "较强超量风险")

    def test_direct_asymmetric_interval(self):
        payload = {
            "records": [
                {
                    "sample_id": "E-1",
                    "additive": "糖精钠",
                    "result": 0.15,
                    "limit": 0.16,
                    "unit": "g/kg",
                    "lower_bound": 0.13,
                    "upper_bound": 0.18,
                    "interval_source": "实验室非对称分布评定报告",
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["交叠关系"], "边界重叠")
        self.assertEqual(row["区间宽度"], 0.05)
        self.assertEqual(row["不确定度类型"], "人工非对称区间")

    def test_negative_uncertainty_is_invalid(self):
        payload = {
            "records": [
                {
                    "sample_id": "F-1",
                    "additive": "苯甲酸",
                    "result": 0.8,
                    "limit": 1.0,
                    "unit": "g/kg",
                    "uncertainty": -0.1,
                    "uncertainty_type": "扩展不确定度",
                    "uncertainty_form": "绝对",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "不得为负"):
            self.engine.validate(payload)

    def test_standard_uncertainty_requires_factor_source(self):
        payload = {
            "records": [
                {
                    "sample_id": "G-1",
                    "additive": "山梨酸",
                    "result": 0.8,
                    "limit": 1.0,
                    "unit": "g/kg",
                    "uncertainty": 0.05,
                    "uncertainty_type": "标准不确定度",
                    "uncertainty_form": "绝对",
                    "coverage_factor": 2.0,
                    "coverage_factor_source": "",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "必须记录来源"):
            self.engine.validate(payload)

    def test_nonfinite_number_and_duplicate_id_are_invalid(self):
        payload = self.engine.example()
        payload["records"][0]["result"] = math.inf
        with self.assertRaisesRegex(ValueError, "有限数字"):
            self.engine.validate(payload)
        duplicate = self.engine.example()
        duplicate["records"][1]["sample_id"] = "SP-001"
        with self.assertRaisesRegex(ValueError, "不得重复"):
            self.engine.validate(duplicate)

    def test_unknown_type_does_not_create_boundary(self):
        payload = {
            "records": [
                {
                    "sample_id": "H-1",
                    "additive": "亚硫酸盐",
                    "result": 120.0,
                    "limit": 100.0,
                    "unit": "mg/kg",
                    "uncertainty": 5.0,
                    "uncertainty_type": "未知",
                    "uncertainty_form": "绝对",
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["交叠关系"], "不确定度不足")
        self.assertEqual(row["区间上界"], "无法计算")


if __name__ == "__main__":
    unittest.main()
