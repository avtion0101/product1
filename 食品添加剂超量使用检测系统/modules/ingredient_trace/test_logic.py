import copy
import json
import unittest

from modules.ingredient_trace.logic import Engine


class IngredientTraceEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_example_contribution_and_input_unchanged(self):
        payload = self.engine.example()
        original = copy.deepcopy(payload)
        result = self.engine.calculate(payload)
        expected = 0.15 * 0.40 * 0.70
        self.assertEqual(payload, original)
        self.assertEqual(result['path_count'], 1)
        self.assertAlmostEqual(
            result['rows'][0]['理论带入比例'],
            expected,
            places=12,
        )
        self.assertEqual(
            result['metrics']['理论带入百分比合计'],
            '4.2%',
        )
        self.assertEqual(result['rows'][0]['计算状态'], '可计算')
        self.assertTrue(result['edges'])
        json.dumps(result, ensure_ascii=False, allow_nan=False)

    def test_missing_ratio_makes_contribution_unavailable(self):
        payload = self.engine.example()
        payload['relations'][4]['ratio'] = None
        result = self.engine.calculate(payload)
        self.assertEqual(result['path_count'], 1)
        self.assertEqual(
            result['rows'][0]['理论带入比例'],
            '不可计算',
        )
        self.assertEqual(result['rows'][0]['计算状态'], '不可计算')
        self.assertEqual(result['metrics']['缺失配比关系数'], 1)
        self.assertEqual(
            result['metrics']['理论带入比例合计'],
            '不可完整计算',
        )
        self.assertIn('不对缺失比例作推定', result['summary'])

    def test_cycle_stops_related_contribution(self):
        payload = {
            'product_id': 'P',
            'target_additive': 'A',
            'batch_id': 'B1',
            'formula_version': 'V1',
            'nodes': [
                {'id': 'P', 'name': '成品', 'type': 'product'},
                {'id': 'C1', 'name': '复配料一', 'type': 'compound'},
                {'id': 'C2', 'name': '复配料二', 'type': 'compound'},
                {'id': 'A', 'name': '目标添加剂', 'type': 'additive'},
            ],
            'relations': [
                {'parent': 'P', 'child': 'C1', 'ratio': 1.0},
                {'parent': 'C1', 'child': 'C2', 'ratio': 0.5},
                {'parent': 'C1', 'child': 'A', 'ratio': 0.5},
                {'parent': 'C2', 'child': 'C1', 'ratio': 1.0},
            ],
        }
        result = self.engine.calculate(payload)
        self.assertEqual(result['metrics']['循环数量'], 1)
        self.assertEqual(result['cycle_nodes'], ['C1', 'C2'])
        self.assertEqual(result['rows'][0]['计算状态'], '不可计算')
        self.assertIn('循环引用', result['summary'])
        self.assertGreaterEqual(len(result['series']), 2)

    def test_incomplete_layer_total_is_not_calculated(self):
        payload = self.engine.example()
        payload['relations'][3]['ratio'] = 0.50
        result = self.engine.calculate(payload)
        self.assertEqual(result['metrics']['异常配比层数'], 1)
        self.assertEqual(result['rows'][0]['计算状态'], '不可计算')
        self.assertIn(
            '同层配比合计不是100%',
            result['rows'][0]['判定依据'],
        )

    def test_invalid_ratio_and_duplicate_relation_rejected(self):
        payload = self.engine.example()
        payload['relations'][0]['ratio'] = 1.01
        with self.assertRaisesRegex(ValueError, '不能大于1'):
            self.engine.validate(payload)
        duplicate = self.engine.example()
        duplicate['relations'].append(
            copy.deepcopy(duplicate['relations'][0])
        )
        with self.assertRaisesRegex(ValueError, '配料关系重复'):
            self.engine.calculate(duplicate)

    def test_invalid_empty_field_and_boolean_ratio_rejected(self):
        payload = self.engine.example()
        payload['batch_id'] = '   '
        with self.assertRaisesRegex(ValueError, '不能为空'):
            self.engine.validate(payload)
        payload = self.engine.example()
        payload['relations'][0]['ratio'] = True
        with self.assertRaisesRegex(ValueError, '必须是数字'):
            self.engine.validate(payload)

    def test_no_path_still_has_standard_fields_and_series(self):
        payload = self.engine.example()
        payload['target_additive'] = 'A002'
        payload['relations'] = [
            relation
            for relation in payload['relations']
            if relation['child'] != 'A002'
        ]
        payload['relations'][5]['ratio'] = 1.0
        result = self.engine.calculate(payload)
        self.assertEqual(result['path_count'], 0)
        self.assertEqual(result['rows'], [])
        self.assertEqual(
            result['series'],
            [{'label': '未发现来源路径', 'value': 0.0}],
        )
        for field in (
            'summary',
            'metrics',
            'rows',
            'series',
            'chart_title',
        ):
            self.assertIn(field, result)


if __name__ == '__main__':
    unittest.main()
