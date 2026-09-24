import copy
import json
import math
import unittest

from modules.repeat_consistency.logic import Engine


class RepeatConsistencyEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_example_and_expected_statistics(self):
        payload = self.engine.example()
        original = copy.deepcopy(payload)
        result = self.engine.calculate(payload)
        self.assertEqual(payload, original)
        self.assertEqual(result["metrics"]["有效测定次数"], 5)
        self.assertAlmostEqual(result["metrics"]["平均值"], 10.82, places=3)
        self.assertAlmostEqual(result["metrics"]["中位数"], 10.1, places=3)
        self.assertAlmostEqual(result["metrics"]["极差"], 4.2, places=3)
        expected_variance = (
            sum((value - 10.82) ** 2 for value in [10.0, 10.2, 9.8, 10.1, 14.0])
            / 4
        )
        expected_sd = math.sqrt(expected_variance)
        expected_rsd = expected_sd / 10.82 * 100
        self.assertAlmostEqual(
            result["metrics"]["样本标准差"],
            expected_sd,
            places=3,
        )
        self.assertAlmostEqual(
            result["metrics"]["相对标准差(%)"],
            expected_rsd,
            places=3,
        )
        self.assertEqual(result["metrics"]["可疑点数量"], 1)
        self.assertEqual(result["rows"][4]["可疑点"], "是")
        self.assertEqual(
            result["metrics"]["一致性状态"],
            "存在可疑点，需人工复核",
        )
        self.assertEqual(len(result["series"]), 5)
        json.dumps(result, ensure_ascii=False, allow_nan=False)

    def test_two_equal_values_are_consistent(self):
        payload = {
            "sample_id": "S-2",
            "additive_name": "苯甲酸",
            "unit": "mg/kg",
            "method_id": "M-2",
            "rsd_threshold_percent": 2.0,
            "measurements": [
                {"measurement_id": "A", "value": 5.0},
                {"measurement_id": "B", "value": 5.0},
            ],
        }
        result = self.engine.calculate(payload)
        self.assertEqual(result["metrics"]["样本标准差"], 0.0)
        self.assertEqual(result["metrics"]["相对标准差(%)"], 0.0)
        self.assertEqual(result["metrics"]["可疑点数量"], 0)
        self.assertEqual(
            result["metrics"]["一致性状态"],
            "重复测定一致",
        )
        self.assertEqual(
            result["rows"][0]["稳健偏离分数"],
            "样本量不足，未计算",
        )

    def test_single_value_reports_insufficient_data(self):
        payload = {
            "sample_id": "S-ONE",
            "additive_name": "亚硝酸盐",
            "unit": "mg/kg",
            "method_id": "M-ONE",
            "rsd_threshold_percent": 5.0,
            "measurements": [
                {"measurement_id": "ONLY", "value": 1.25},
            ],
        }
        result = self.engine.calculate(payload)
        self.assertEqual(
            result["metrics"]["一致性状态"],
            "资料不足，提交人工复核",
        )
        self.assertEqual(
            result["metrics"]["样本标准差"],
            "测定次数不足",
        )
        self.assertIn("少于两次", result["review_items"][0]["事项"])
        self.assertEqual(result["series"][0]["value"], 1.25)

    def test_zero_mad_marks_nonmedian_value_without_deleting(self):
        payload = {
            "sample_id": "S-MAD",
            "additive_name": "甜蜜素",
            "unit": "g/kg",
            "method_id": "M-MAD",
            "rsd_threshold_percent": 10.0,
            "measurements": [
                {"measurement_id": "R1", "value": 2.0},
                {"measurement_id": "R2", "value": 2.0},
                {"measurement_id": "R3", "value": 2.0},
                {"measurement_id": "R4", "value": 3.0},
            ],
        }
        result = self.engine.calculate(payload)
        self.assertEqual(result["metrics"]["中位数绝对偏差"], 0.0)
        self.assertEqual(result["metrics"]["可疑点数量"], 1)
        self.assertEqual(len(result["rows"]), 4)
        self.assertEqual(result["rows"][3]["可疑点"], "是")
        self.assertIn("MAD为0", result["rows"][3]["稳健偏离分数"])
        self.assertEqual(
            result["metrics"]["剔除可疑点后平均值"],
            2.0,
        )

    def test_zero_mean_makes_rsd_undefined(self):
        payload = {
            "sample_id": "S-ZERO",
            "additive_name": "测试物",
            "unit": "mg/kg",
            "method_id": "M-ZERO",
            "rsd_threshold_percent": 5.0,
            "measurements": [
                {"measurement_id": "N", "value": -1.0},
                {"measurement_id": "P", "value": 1.0},
            ],
        }
        result = self.engine.calculate(payload)
        self.assertEqual(
            result["metrics"]["相对标准差(%)"],
            "均值为0或测定次数不足",
        )
        self.assertEqual(
            result["metrics"]["一致性状态"],
            "无法判定，提交人工复核",
        )

    def test_invalid_inputs_raise_value_error(self):
        invalid_cases = []
        missing_threshold = self.engine.example()
        del missing_threshold["rsd_threshold_percent"]
        invalid_cases.append(missing_threshold)
        duplicate_ids = self.engine.example()
        duplicate_ids["measurements"][1]["measurement_id"] = "R1"
        invalid_cases.append(duplicate_ids)
        non_finite = self.engine.example()
        non_finite["measurements"][0]["value"] = float("nan")
        invalid_cases.append(non_finite)
        bad_bounds = self.engine.example()
        bad_bounds["value_min"] = 20.0
        bad_bounds["value_max"] = 10.0
        invalid_cases.append(bad_bounds)
        boolean_value = self.engine.example()
        boolean_value["measurements"][0]["value"] = True
        invalid_cases.append(boolean_value)
        zero_threshold = self.engine.example()
        zero_threshold["rsd_threshold_percent"] = 0
        invalid_cases.append(zero_threshold)
        for payload in invalid_cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.engine.validate(payload)


if __name__ == "__main__":
    unittest.main()
