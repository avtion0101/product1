import copy
import json
import unittest

from modules.unit_conversion.logic import Engine


class UnitConversionEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_example_is_nonempty_and_serializable(self):
        payload = self.engine.example()
        self.assertIsInstance(payload, dict)
        self.assertGreaterEqual(len(payload["records"]), 5)
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertIn("样品-苯甲酸-01", encoded)

    def test_same_dimension_exact_conversion(self):
        payload = {
            "records": [
                {
                    "id": "苯甲酸",
                    "value": "0.125",
                    "source_unit": "g/kg",
                    "target_unit": "mg/kg",
                    "significant_digits": 4,
                    "rounding": "HALF_UP",
                }
            ]
        }
        original = copy.deepcopy(payload)
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(payload, original)
        self.assertEqual(row["处理状态"], "换算成功")
        self.assertEqual(row["舍入值"], "125")
        self.assertEqual(row["换算因子"], "1000")
        self.assertEqual(result["series"][0]["value"], 125.0)

    def test_fraction_to_concentration_with_density(self):
        payload = {
            "records": [
                {
                    "id": "脱氢乙酸",
                    "value": "420",
                    "source_unit": "mg/kg",
                    "target_unit": "mg/L",
                    "density_g_ml": "1.08",
                    "density_confirmed": True,
                    "significant_digits": 3,
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["处理状态"], "换算成功")
        self.assertEqual(row["舍入值"], "454")
        self.assertAlmostEqual(
            result["series"][0]["value"],
            420 * 1.08,
            delta=1.0,
        )
        self.assertIn("经确认密度", row["上下文依据"])

    def test_missing_density_goes_to_manual_review(self):
        payload = {
            "records": [
                {
                    "id": "山梨酸",
                    "value": "50",
                    "source_unit": "mg/kg",
                    "target_unit": "mg/L",
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["处理状态"], "待人工复核")
        self.assertEqual(row["舍入值"], "不可计算")
        self.assertIn("未假设密度为1", row["异常原因"])
        self.assertEqual(result["series"][0]["value"], 0.0)

    def test_unknown_unit_goes_to_manual_review(self):
        payload = {
            "records": [
                {
                    "id": "未知单位记录",
                    "value": 10,
                    "source_unit": "盎司",
                    "target_unit": "mg",
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["量纲校验"], "不通过")
        self.assertEqual(row["处理状态"], "待人工复核")
        self.assertIn("原单位不在白名单", row["异常原因"])

    def test_mass_concentration_to_mass_uses_volume(self):
        payload = {
            "records": [
                {
                    "id": "浸提液",
                    "value": "2.50",
                    "source_unit": "mg/L",
                    "target_unit": "mg",
                    "volume_ml": "200",
                    "significant_digits": 3,
                }
            ]
        }
        result = self.engine.calculate(payload)
        row = result["rows"][0]
        self.assertEqual(row["舍入值"], "0.5")
        self.assertEqual(row["处理状态"], "换算成功")
        self.assertIn("200", row["上下文依据"])

    def test_zero_and_rounding_boundary(self):
        payload = {
            "records": [
                {
                    "id": "零值",
                    "value": 0,
                    "source_unit": "mg",
                    "target_unit": "g",
                    "significant_digits": 2,
                },
                {
                    "id": "舍入边界",
                    "value": "1.245",
                    "source_unit": "mg/L",
                    "target_unit": "mg/L",
                    "significant_digits": 3,
                    "rounding": "HALF_UP",
                },
            ]
        }
        result = self.engine.calculate(payload)
        self.assertEqual(result["rows"][0]["舍入值"], "0")
        self.assertEqual(result["rows"][1]["舍入值"], "1.25")

    def test_invalid_boolean_value_is_rejected(self):
        payload = {
            "records": [
                {
                    "id": "非法布尔值",
                    "value": True,
                    "source_unit": "mg",
                    "target_unit": "g",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "不得为布尔值"):
            self.engine.validate(payload)

    def test_inconsistent_context_is_rejected(self):
        payload = {
            "records": [
                {
                    "id": "上下文冲突",
                    "value": "10",
                    "source_unit": "mg/kg",
                    "target_unit": "mg/L",
                    "sample_mass_g": "100",
                    "volume_ml": "100",
                    "density_g_ml": "1.2",
                    "density_confirmed": True,
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "偏差超过1%"):
            self.engine.calculate(payload)

    def test_invalid_significant_digits_is_rejected(self):
        payload = {
            "records": [
                {
                    "id": "有效数字非法",
                    "value": "1",
                    "source_unit": "mg",
                    "target_unit": "g",
                    "significant_digits": 0,
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "必须在1至15之间"):
            self.engine.validate(payload)


if __name__ == "__main__":
    unittest.main()
