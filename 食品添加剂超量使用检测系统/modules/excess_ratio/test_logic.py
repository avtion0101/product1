import copy
import json
import unittest
from decimal import Decimal

from modules.excess_ratio.logic import Engine


class EngineTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def numeric_payload(self, detected='1.2004', limit='1.0', places=2):
        return {
            'as_of_date': '2026-09-23',
            'rounding_places': places,
            'records': [
                {
                    'record_id': 'T001',
                    'food_name': '酱油',
                    'additive_name': '苯甲酸',
                    'detected_value': detected,
                    'unit': 'g/kg',
                    'detection_limit': '0.001',
                    'matched_rules': [
                        {
                            'rule_id': 'RULE-1',
                            'limit_type': '数值限量',
                            'limit_value': limit,
                            'comparison_basis': '成品残留量',
                            'unit': 'g/kg',
                            'effective_date': '2025-01-01',
                            'expiry_date': None,
                        }
                    ],
                }
            ],
        }

    def test_example_is_nonempty_and_has_five_domain_records(self):
        payload = self.engine.example()
        self.assertIsInstance(payload, dict)
        self.assertGreaterEqual(len(payload['records']), 5)
        self.assertIsNone(self.engine.validate(payload))
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertIn('苯甲酸', encoded)
        self.assertIn('禁止使用', encoded)

    def test_numeric_ratio_expected_values_and_input_unchanged(self):
        payload = self.numeric_payload()
        original = copy.deepcopy(payload)
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        expected_ratio = Decimal('1.2004') / Decimal('1.0')
        expected_percent = (expected_ratio - Decimal('1')) * Decimal('100')
        self.assertEqual(row['超量比值'], '1.20')
        self.assertEqual(row['超出百分比'], '20.04%')
        self.assertEqual(row['边界距离'], '0.20')
        self.assertEqual(row['未经舍入比值'], '1.2004')
        self.assertEqual(row['初筛标签'], '超量预警')
        self.assertEqual(expected_percent, Decimal('20.0400'))
        self.assertEqual(result['metrics']['数值超量数'], 1)
        self.assertEqual(result['series'][0]['value'], 1.2004)
        self.assertEqual(payload, original)

    def test_rounding_does_not_change_boundary_decision(self):
        payload = self.numeric_payload(
            detected='1.0004',
            limit='1.0',
            places=2,
        )
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['超量比值'], '1.00')
        self.assertEqual(row['超出百分比'], '0.04%')
        self.assertEqual(row['边界距离'], '0.00')
        self.assertEqual(row['未经舍入边界距离'], '0.0004')
        self.assertEqual(row['初筛标签'], '超量预警')
        self.assertEqual(row['边界方向'], '高于限量')

    def test_maximum_usage_is_not_compared_to_product_concentration(self):
        payload = self.numeric_payload()
        payload['records'][0]['matched_rules'][0]['comparison_basis'] = '最大使用量'
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['初筛标签'], '待人工复核')
        self.assertEqual(row['超量比值'], '不适用')
        self.assertEqual(result['metrics']['可计算数值比值数'], 0)
        self.assertEqual(result['series'][0]['value'], 0.0)
        self.assertIn('不能直接', row['预警依据'])

    def test_missing_comparison_basis_requires_review(self):
        payload = self.numeric_payload()
        del payload['records'][0]['matched_rules'][0]['comparison_basis']
        result = self.engine.calculate(payload)
        self.assertEqual(result['rows'][0]['初筛标签'], '待人工复核')
        self.assertEqual(result['metrics']['待人工复核数'], 1)

    def test_exact_boundary_is_distinguished(self):
        payload = self.numeric_payload(
            detected='0.5000',
            limit='0.5',
            places=3,
        )
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['超量比值'], '1.000')
        self.assertEqual(row['超出百分比'], '0.000%')
        self.assertEqual(row['初筛标签'], '等于限量')
        self.assertEqual(result['metrics']['恰好等于限量数'], 1)

    def test_prohibited_rule_never_uses_zero_denominator(self):
        payload = self.numeric_payload(detected='0.02')
        rule = payload['records'][0]['matched_rules'][0]
        rule['limit_type'] = '禁止使用'
        del rule['limit_value']
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['超量比值'], '不适用')
        self.assertEqual(row['超出百分比'], '不适用')
        self.assertEqual(row['初筛标签'], '禁止使用项目检出')
        self.assertEqual(result['series'][0]['value'], 1.0)
        self.assertIn('不进行除法', row['计算表达式'])

    def test_prohibited_below_detection_limit_is_not_detected(self):
        payload = self.numeric_payload(detected='0.0005')
        rule = payload['records'][0]['matched_rules'][0]
        rule['limit_type'] = '禁止使用'
        del rule['limit_value']
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['初筛标签'], '禁止使用项目未检出')
        self.assertEqual(result['metrics']['禁止使用项目未检出数'], 1)
        self.assertEqual(result['series'][0]['value'], 0.0)

    def test_as_needed_limit_requires_review(self):
        payload = self.numeric_payload(detected='2.5')
        rule = payload['records'][0]['matched_rules'][0]
        rule['limit_type'] = '按生产需要适量使用'
        rule['qualitative_text'] = '按生产需要适量使用'
        del rule['limit_value']
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['初筛标签'], '待人工复核')
        self.assertEqual(row['超量比值'], '不适用')
        self.assertEqual(result['metrics']['非数值待复核数'], 1)

    def test_multiple_rules_are_rejected(self):
        payload = self.numeric_payload()
        rule = copy.deepcopy(payload['records'][0]['matched_rules'][0])
        rule['rule_id'] = 'RULE-2'
        payload['records'][0]['matched_rules'].append(rule)
        with self.assertRaisesRegex(ValueError, '只能匹配一条'):
            self.engine.validate(payload)

    def test_unit_mismatch_is_rejected(self):
        payload = self.numeric_payload()
        payload['records'][0]['matched_rules'][0]['unit'] = 'mg/kg'
        with self.assertRaisesRegex(ValueError, '单位不兼容'):
            self.engine.calculate(payload)

    def test_zero_numeric_limit_is_rejected(self):
        payload = self.numeric_payload(limit='0')
        with self.assertRaisesRegex(ValueError, '不能为0'):
            self.engine.validate(payload)

    def test_expired_rule_is_rejected(self):
        payload = self.numeric_payload()
        rule = payload['records'][0]['matched_rules'][0]
        rule['expiry_date'] = '2026-09-22'
        with self.assertRaisesRegex(ValueError, '已经失效'):
            self.engine.validate(payload)

    def test_duplicate_record_ids_are_rejected(self):
        payload = self.numeric_payload()
        duplicate = copy.deepcopy(payload['records'][0])
        payload['records'].append(duplicate)
        with self.assertRaisesRegex(ValueError, '不能重复'):
            self.engine.validate(payload)

    def test_negative_detection_is_rejected(self):
        payload = self.numeric_payload(detected='-0.001')
        with self.assertRaisesRegex(ValueError, '不能为负数'):
            self.engine.validate(payload)

    def test_nonfinite_detection_is_rejected(self):
        payload = self.numeric_payload(detected='NaN')
        with self.assertRaisesRegex(ValueError, '有限十进制数'):
            self.engine.validate(payload)

    def test_result_has_required_structure_and_json_encoding(self):
        result = self.engine.calculate(self.numeric_payload())
        required = {
            'summary',
            'metrics',
            'rows',
            'series',
            'chart_title',
        }
        self.assertTrue(required.issubset(result))
        self.assertGreater(len(result['rows']), 0)
        self.assertGreater(len(result['series']), 0)
        encoded = json.dumps(
            result,
            ensure_ascii=False,
            allow_nan=False,
        )
        self.assertIn('超量比值', encoded)


if __name__ == '__main__':
    unittest.main()
