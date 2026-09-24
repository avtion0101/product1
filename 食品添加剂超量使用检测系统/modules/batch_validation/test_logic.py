import copy
import json
import unittest

from modules.batch_validation.logic import Engine


class TestBatchValidationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_example_is_valid_and_fully_calculable(self):
        payload = self.engine.example()
        original = copy.deepcopy(payload)
        self.assertIsNone(self.engine.validate(payload))
        result = self.engine.calculate(payload)
        self.assertEqual(payload, original)
        self.assertEqual(result['metrics']['记录总数'], 5)
        self.assertEqual(result['metrics']['可计算记录数'], 5)
        self.assertEqual(result['metrics']['待复核记录数'], 0)
        self.assertEqual(result['metrics']['批次完整率'], '100.00%')
        self.assertEqual(result['metrics']['记录通过率'], '100.00%')
        self.assertEqual(result['metrics']['冲突组数'], 0)
        self.assertEqual(result['series'][0]['value'], 5)
        self.assertEqual(result['series'][2]['value'], 0)
        self.assertEqual(len(result['rows']), 5)
        json.dumps(result, ensure_ascii=False)

    def test_missing_value_and_date_order_require_review(self):
        payload = self.engine.example()
        payload['records'] = [copy.deepcopy(payload['records'][0])]
        record = payload['records'][0]
        record['measured_value'] = None
        record['sampling_date'] = '2026-09-22'
        record['test_date'] = '2026-09-21'
        record['entry_date'] = '2026-09-20'
        result = self.engine.calculate(payload)
        codes = {item['code'] for item in result['errors']}
        expected = {
            'E005_DATE_ORDER_SAMPLE_TEST',
            'E006_DATE_ORDER_TEST_ENTRY',
            'E007_VALUE_MISSING',
        }
        self.assertTrue(expected.issubset(codes))
        self.assertEqual(result['metrics']['可计算记录数'], 0)
        self.assertEqual(result['metrics']['待复核记录数'], 1)
        self.assertEqual(result['rows'][0]['状态'], '待人工复核')
        self.assertEqual(result['series'][2]['value'], 1)

    def test_conflicting_composite_key_is_preserved(self):
        payload = self.engine.example()
        first = copy.deepcopy(payload['records'][0])
        second = copy.deepcopy(first)
        second['measured_value'] = '0.91'
        second['analyst'] = '陈洁'
        payload['records'] = [first, second]
        result = self.engine.calculate(payload)
        self.assertEqual(result['metrics']['记录总数'], 2)
        self.assertEqual(result['metrics']['冲突组数'], 1)
        self.assertEqual(result['metrics']['待复核记录数'], 2)
        group = result['conflict_groups'][0]
        self.assertEqual(group['记录序号'], [1, 2])
        self.assertEqual(len(group['差异记录']), 2)
        self.assertEqual(
            [row['检测值'] for row in group['差异记录']],
            ['0.42', '0.91'],
        )
        conflict_errors = [
            item
            for item in result['errors']
            if item['code'] == 'E015_DUPLICATE_CONFLICT'
        ]
        self.assertEqual(len(conflict_errors), 2)

    def test_identical_duplicate_can_be_warning_or_blocking(self):
        payload = self.engine.example()
        record = copy.deepcopy(payload['records'][0])
        payload['records'] = [record, copy.deepcopy(record)]
        result = self.engine.calculate(payload)
        self.assertEqual(result['metrics']['可计算记录数'], 2)
        self.assertEqual(result['metrics']['冲突组数'], 0)
        self.assertEqual(
            [row['状态'] for row in result['rows']],
            ['可计算但有警告', '可计算但有警告'],
        )
        payload['options']['identical_duplicate_is_blocking'] = True
        blocked = self.engine.calculate(payload)
        self.assertEqual(blocked['metrics']['待复核记录数'], 2)

    def test_sample_information_conflict_blocks_all_related_rows(self):
        payload = self.engine.example()
        first = copy.deepcopy(payload['records'][0])
        second = copy.deepcopy(first)
        second['additive_name'] = '山梨酸'
        second['food_category'] = '调味品'
        payload['records'] = [first, second]
        result = self.engine.calculate(payload)
        codes = [item['code'] for item in result['errors']]
        self.assertEqual(codes.count('E017_SAMPLE_FOOD_CONFLICT'), 2)
        self.assertEqual(result['metrics']['待复核记录数'], 2)

    def test_invalid_number_boundaries(self):
        payload = self.engine.example()
        records = []
        values = ['NaN', '-0.01', '1000000000.01']
        expected_codes = [
            'E009_VALUE_NONFINITE',
            'E010_VALUE_NEGATIVE',
            'E020_VALUE_TOO_LARGE',
        ]
        for index, value in enumerate(values):
            record = copy.deepcopy(payload['records'][index])
            record['measured_value'] = value
            records.append(record)
        payload['records'] = records
        result = self.engine.calculate(payload)
        actual = {item['code'] for item in result['errors']}
        self.assertEqual(actual, set(expected_codes))
        self.assertEqual(result['metrics']['待复核记录数'], 3)

    def test_invalid_payloads_raise_value_error(self):
        invalid_payloads = [
            None,
            {},
            {'batch_no': '', 'records': []},
            {'batch_no': 'B1', 'records': 'not-list'},
            {'batch_no': 'B1', 'records': [1]},
            {
                'batch_no': 'B1',
                'records': [{}],
                'options': {'unknown': True},
            },
            {
                'batch_no': 'B1',
                'records': [{}],
                'options': {'require_separation_of_duties': 1},
            },
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.engine.validate(payload)

    def test_invalid_record_fields_are_reported_not_silenced(self):
        payload = self.engine.example()
        payload['records'] = [
            {
                'batch_no': 'OTHER',
                'sample_no': 'S 01',
                'food_name': '',
                'food_category': '饮料',
                'sampling_date': '2026-02-30',
                'test_date': '2026-03-01',
                'entry_date': '2026-03-02',
                'additive_name': '苯甲酸',
                'measured_value': 'abc',
                'unit': 'ppm',
                'measurement_no': 0,
                'sampler': '甲',
                'analyst': '乙',
                'recorder': '丙',
            }
        ]
        result = self.engine.calculate(payload)
        codes = {item['code'] for item in result['errors']}
        expected = {
            'E002_TEXT_EMPTY',
            'E004_DATE_FORMAT',
            'E008_VALUE_TYPE',
            'E011_UNIT_INVALID',
            'E013_MEASUREMENT_NO_RANGE',
            'E014_BATCH_MISMATCH',
            'E021_IDENTIFIER_FORMAT',
        }
        self.assertTrue(expected.issubset(codes))
        self.assertEqual(result['rows'][0]['状态'], '待人工复核')

    def test_separation_of_duties_option_changes_status(self):
        payload = self.engine.example()
        record = copy.deepcopy(payload['records'][0])
        record['recorder'] = record['analyst']
        payload['records'] = [record]
        result = self.engine.calculate(payload)
        self.assertEqual(
            result['rows'][0]['状态'],
            '可计算但有警告',
        )
        payload['options']['require_separation_of_duties'] = True
        strict_result = self.engine.calculate(payload)
        self.assertEqual(
            strict_result['rows'][0]['状态'],
            '待人工复核',
        )


if __name__ == '__main__':
    unittest.main()
