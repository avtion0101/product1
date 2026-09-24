import copy
import json
import unittest

from modules.rule_version_audit.logic import Engine


class RuleVersionAuditEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.payload = self.engine.example()

    def test_example_and_expected_difference_counts(self):
        self.assertIsNone(self.engine.validate(self.payload))
        result = self.engine.calculate(self.payload)
        self.assertEqual(result['metrics']['新增规则数'], 1)
        self.assertEqual(result['metrics']['删除规则数'], 1)
        self.assertEqual(result['metrics']['修改规则数'], 1)
        self.assertEqual(result['metrics']['字段差异数'], 5)
        self.assertEqual(result['metrics']['潜在受影响报告数'], 3)
        self.assertEqual(len(result['rows']), 5)
        self.assertGreater(len(result['series']), 0)
        self.assertEqual(result['series'][0]['label'], '新增规则')
        self.assertEqual(result['series'][0]['value'], 1.0)
        self.assertFalse(result['write_policy']['existing_reports_modified'])
        json.dumps(result, ensure_ascii=False, allow_nan=False)

    def test_limit_tightening_changes_expected_conclusion(self):
        result = self.engine.calculate(self.payload)
        affected = {
            item['报告编号']: item
            for item in result['affected_batches']
        }
        report = affected['R001']
        self.assertEqual(report['旧规则复核结果'], '合格')
        self.assertEqual(report['新规则试算结果'], '不合格')
        self.assertEqual(report['重算优先级'], '紧急')
        self.assertEqual(report['仅列入待重算'], '是')
        self.assertEqual(
            self.payload['history_reports'][0]['original_conclusion'],
            'pass',
        )

    def test_calculate_does_not_mutate_input(self):
        before = copy.deepcopy(self.payload)
        self.engine.calculate(self.payload)
        self.assertEqual(self.payload, before)

    def test_boundary_value_equal_to_maximum_is_qualified(self):
        payload = copy.deepcopy(self.payload)
        payload['history_reports'][0]['measured_value'] = 0.8
        result = self.engine.calculate(payload)
        affected = {
            item['报告编号']: item
            for item in result['affected_batches']
        }
        self.assertEqual(affected['R001']['新规则试算结果'], '合格')
        self.assertEqual(affected['R001']['旧规则复核结果'], '合格')

    def test_unit_conversion_is_used_for_recalculation(self):
        payload = copy.deepcopy(self.payload)
        payload['history_reports'][0]['measured_value'] = 900.0
        payload['history_reports'][0]['unit'] = 'mg/kg'
        result = self.engine.calculate(payload)
        affected = {
            item['报告编号']: item
            for item in result['affected_batches']
        }
        self.assertEqual(affected['R001']['旧规则复核结果'], '合格')
        self.assertEqual(affected['R001']['新规则试算结果'], '不合格')

    def test_invalid_unverified_effective_version_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload['new_version']['verified'] = False
        with self.assertRaisesRegex(ValueError, '只能比较已核验'):
            self.engine.validate(payload)

    def test_invalid_numeric_rule_without_value_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload['new_version']['rules'][0]['limit_value'] = None
        with self.assertRaisesRegex(ValueError, '必须填写limit_value'):
            self.engine.validate(payload)

    def test_invalid_date_range_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload['scope']['date_from'] = '2026-12-31'
        payload['scope']['date_to'] = '2026-01-01'
        with self.assertRaisesRegex(ValueError, '不能晚于'):
            self.engine.validate(payload)

    def test_duplicate_normalized_rule_identity_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        duplicate = copy.deepcopy(payload['new_version']['rules'][0])
        duplicate['additive_name'] = '  苯甲酸  '
        payload['new_version']['rules'].append(duplicate)
        with self.assertRaisesRegex(ValueError, '重复的规则身份键'):
            self.engine.validate(payload)

    def test_no_changes_still_has_required_nonempty_outputs(self):
        payload = copy.deepcopy(self.payload)
        payload['new_version']['rules'] = copy.deepcopy(
            payload['old_version']['rules']
        )
        result = self.engine.calculate(payload)
        self.assertEqual(result['metrics']['新增规则数'], 0)
        self.assertEqual(result['metrics']['删除规则数'], 0)
        self.assertEqual(result['metrics']['修改规则数'], 0)
        self.assertEqual(result['rows'][0]['变更类型'], '无变化')
        self.assertEqual(len(result['series']), 4)
        self.assertTrue(all(item['value'] == 0.0 for item in result['series']))


if __name__ == '__main__':
    unittest.main()
