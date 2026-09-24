import copy
import json
import unittest

from modules.warning_grading.logic import Engine


class WarningGradingEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_example_and_exact_grade_calculation(self):
        payload = self.engine.example()
        self.assertGreaterEqual(len(payload['records']), 5)
        before = copy.deepcopy(payload)
        result = self.engine.calculate(payload)
        self.assertEqual(payload, before)
        self.assertEqual(result['metrics']['记录总数'], 5)
        self.assertEqual(result['metrics']['待人工复核数'], 1)
        self.assertEqual(result['metrics']['检测值高于限量数'], 2)
        rows = {row['记录编号']: row for row in result['rows']}
        self.assertEqual(rows['S-001']['超量比值'], '0.72')
        self.assertEqual(rows['S-001']['最终等级'], '正常')
        self.assertEqual(rows['S-002']['基础等级'], '关注')
        self.assertEqual(rows['S-002']['最终等级'], '严重')
        self.assertIn('累计加重3级', rows['S-002']['说明'])
        self.assertEqual(rows['S-003']['最终等级'], '警告')
        self.assertEqual(rows['S-004']['最终等级'], '严重')
        self.assertEqual(rows['S-005']['最终等级'], '待人工复核')
        self.assertEqual(result['review_queue'][0]['记录编号'], 'S-005')
        self.assertEqual(
            sum(item['value'] for item in result['series']),
            5,
        )
        json.dumps(result, ensure_ascii=False)

    def test_threshold_boundary_and_single_aggravation(self):
        payload = self.engine.example()
        payload['records'] = [payload['records'][0]]
        record = payload['records'][0]
        record['id'] = 'BOUNDARY'
        record['measured_value'] = 90.0
        record['uncertainty'] = 0.0
        record['uncertainty_relation'] = '整体未超限'
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['超量比值'], '0.9')
        self.assertEqual(row['基础等级'], '关注')
        self.assertEqual(row['最终等级'], '关注')
        self.assertEqual(row['命中决策表行'], 'R-02')
        record['uncertainty'] = 10.0
        record['uncertainty_relation'] = '交叠'
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['最终等级'], '警告')
        self.assertIn('不确定度区间跨越限量', row['加重因素'])

    def test_multiple_aggravators_are_cumulative_and_capped(self):
        payload = self.engine.example()
        payload['records'] = [payload['records'][1]]
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['基础等级'], '关注')
        self.assertEqual(row['最终等级'], '严重')
        self.assertIn('重复测定临界', row['加重因素'])
        self.assertIn('配料来源证据部分缺失', row['加重因素'])
        self.assertEqual(result['series'][3]['value'], 1)

    def test_blocker_has_priority_over_high_ratio(self):
        payload = self.engine.example()
        payload['records'] = [payload['records'][2]]
        record = payload['records'][0]
        record['id'] = 'BLOCKED-HIGH'
        record['measured_value'] = 300.0
        record['uncertainty'] = 10.0
        record['uncertainty_relation'] = '整体超限'
        record['rule_status'] = '缺失'
        result = self.engine.calculate(payload)
        row = result['rows'][0]
        self.assertEqual(row['超量比值'], '3')
        self.assertEqual(row['最终等级'], '待人工复核')
        self.assertEqual(row['命中决策表行'], 'B-阻断')
        self.assertIn('规则缺失', row['阻断因素'])
        self.assertEqual(result['series'][-1]['value'], 1)

    def test_invalid_relation_and_duplicate_id(self):
        payload = self.engine.example()
        payload['records'][0]['uncertainty_relation'] = '交叠'
        with self.assertRaisesRegex(ValueError, '不确定度关系与数值不一致'):
            self.engine.calculate(payload)
        payload = self.engine.example()
        payload['records'][1]['id'] = payload['records'][0]['id']
        with self.assertRaisesRegex(ValueError, 'id不得重复'):
            self.engine.validate(payload)

    def test_invalid_numbers_and_version_configuration(self):
        payload = self.engine.example()
        payload['records'][0]['limit_value'] = 0
        with self.assertRaisesRegex(ValueError, '限量值必须大于0'):
            self.engine.validate(payload)
        payload = self.engine.example()
        payload['threshold_version']['thresholds'][1]['min_ratio'] = 0
        with self.assertRaisesRegex(ValueError, '严格递增'):
            self.engine.validate(payload)
        payload = self.engine.example()
        payload['records'][0]['measured_value'] = float('nan')
        with self.assertRaisesRegex(ValueError, '有限数字'):
            self.engine.validate(payload)

    def test_missing_measurement_requires_insufficient_relation(self):
        payload = self.engine.example()
        payload['records'] = [payload['records'][0]]
        record = payload['records'][0]
        record['measured_value'] = None
        record['uncertainty_relation'] = '整体未超限'
        with self.assertRaisesRegex(ValueError, '关系必须为不足'):
            self.engine.validate(payload)
        record['uncertainty_relation'] = '不足'
        result = self.engine.calculate(payload)
        self.assertEqual(result['rows'][0]['最终等级'], '待人工复核')
        self.assertIn('检测值缺失', result['rows'][0]['阻断因素'])

    def test_unknown_fields_and_input_are_rejected(self):
        payload = self.engine.example()
        payload['extra'] = '非法字段'
        with self.assertRaisesRegex(ValueError, '未知字段'):
            self.engine.validate(payload)
        with self.assertRaisesRegex(ValueError, '必须是对象'):
            self.engine.validate([])


if __name__ == '__main__':
    unittest.main()
