import copy
import datetime
import math
import re
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation


class Engine:
    REQUIRED_FIELDS = (
        'batch_no',
        'sample_no',
        'food_name',
        'food_category',
        'sampling_date',
        'test_date',
        'entry_date',
        'additive_name',
        'measured_value',
        'unit',
        'measurement_no',
        'sampler',
        'analyst',
        'recorder',
    )
    TEXT_FIELDS = (
        'batch_no',
        'sample_no',
        'food_name',
        'food_category',
        'sampling_date',
        'test_date',
        'entry_date',
        'additive_name',
        'unit',
        'sampler',
        'analyst',
        'recorder',
    )
    DATE_FIELDS = (
        'sampling_date',
        'test_date',
        'entry_date',
    )
    PERSON_FIELDS = (
        'sampler',
        'analyst',
        'recorder',
    )
    ALLOWED_UNITS = (
        'mg/kg',
        'g/kg',
        'μg/kg',
        'mg/L',
        'g/L',
        'μg/L',
    )
    FIELD_NAMES = {
        'batch_no': '批次号',
        'sample_no': '样品号',
        'food_name': '食品名称',
        'food_category': '食品类别',
        'sampling_date': '采样日期',
        'test_date': '检测日期',
        'entry_date': '录入日期',
        'additive_name': '添加剂名称',
        'measured_value': '检测值',
        'unit': '单位',
        'measurement_no': '测定序号',
        'sampler': '采样人员',
        'analyst': '检测人员',
        'recorder': '录入人员',
    }
    ERROR_NAMES = {
        'E001_FIELD_MISSING': '必填字段缺失',
        'E002_TEXT_EMPTY': '文本字段为空',
        'E003_TEXT_TYPE': '文本字段类型错误',
        'E004_DATE_FORMAT': '日期格式错误',
        'E005_DATE_ORDER_SAMPLE_TEST': '检测日期早于采样日期',
        'E006_DATE_ORDER_TEST_ENTRY': '录入日期早于检测日期',
        'E007_VALUE_MISSING': '检测值缺失',
        'E008_VALUE_TYPE': '检测值无法解析',
        'E009_VALUE_NONFINITE': '检测值不是有限数',
        'E010_VALUE_NEGATIVE': '检测值为负数',
        'E011_UNIT_INVALID': '单位不受支持',
        'E012_MEASUREMENT_NO_TYPE': '测定序号类型错误',
        'E013_MEASUREMENT_NO_RANGE': '测定序号超出范围',
        'E014_BATCH_MISMATCH': '记录批次号与目标批次不一致',
        'E015_DUPLICATE_CONFLICT': '复合键记录内容冲突',
        'E016_DUPLICATE_IDENTICAL': '复合键记录完全重复',
        'E017_SAMPLE_FOOD_CONFLICT': '同一样品食品信息不一致',
        'E018_SAMPLE_DATE_CONFLICT': '同一样品采样日期不一致',
        'E019_ANALYST_RECORDER_SAME': '检测与录入人员相同',
        'E020_VALUE_TOO_LARGE': '检测值超过系统校验上限',
        'E021_IDENTIFIER_FORMAT': '标识符格式不规范',
        'E022_NAME_TOO_LONG': '文本长度超过限制',
    }
    BLOCKING_CODES = {
        'E001_FIELD_MISSING',
        'E002_TEXT_EMPTY',
        'E003_TEXT_TYPE',
        'E004_DATE_FORMAT',
        'E005_DATE_ORDER_SAMPLE_TEST',
        'E006_DATE_ORDER_TEST_ENTRY',
        'E007_VALUE_MISSING',
        'E008_VALUE_TYPE',
        'E009_VALUE_NONFINITE',
        'E010_VALUE_NEGATIVE',
        'E011_UNIT_INVALID',
        'E012_MEASUREMENT_NO_TYPE',
        'E013_MEASUREMENT_NO_RANGE',
        'E014_BATCH_MISMATCH',
        'E015_DUPLICATE_CONFLICT',
        'E017_SAMPLE_FOOD_CONFLICT',
        'E018_SAMPLE_DATE_CONFLICT',
        'E020_VALUE_TOO_LARGE',
    }
    WARNING_CODES = {
        'E016_DUPLICATE_IDENTICAL',
        'E019_ANALYST_RECORDER_SAME',
        'E021_IDENTIFIER_FORMAT',
        'E022_NAME_TOO_LONG',
    }
    IDENTIFIER_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')
    MAX_TEXT_LENGTH = 100
    MAX_VALUE = Decimal('1000000000')
    MAX_MEASUREMENT_NO = 9999

    def example(self):
        records = [
            self._example_record(
                'SP-001',
                '酱腌菜',
                '蔬菜制品',
                '苯甲酸',
                '0.42',
                1,
                '李敏',
                '周强',
                '王芳',
            ),
            self._example_record(
                'SP-002',
                '草莓果酱',
                '水果制品',
                '山梨酸',
                '0.68',
                1,
                '李敏',
                '陈洁',
                '王芳',
            ),
            self._example_record(
                'SP-003',
                '熟肉制品',
                '肉制品',
                '亚硝酸钠',
                '18.5',
                1,
                '赵磊',
                '周强',
                '王芳',
            ),
            self._example_record(
                'SP-004',
                '碳酸饮料',
                '饮料',
                '安赛蜜',
                '0.12',
                1,
                '赵磊',
                '陈洁',
                '孙宁',
            ),
            self._example_record(
                'SP-005',
                '蜜饯',
                '蜜饯凉果',
                '二氧化硫',
                '0.31',
                1,
                '李敏',
                '周强',
                '孙宁',
            ),
        ]
        return {
            'batch_no': 'B20260923-01',
            'records': records,
            'options': {
                'require_separation_of_duties': False,
                'identical_duplicate_is_blocking': False,
            },
        }

    def _example_record(
        self,
        sample_no,
        food_name,
        food_category,
        additive_name,
        measured_value,
        measurement_no,
        sampler,
        analyst,
        recorder,
    ):
        return {
            'batch_no': 'B20260923-01',
            'sample_no': sample_no,
            'food_name': food_name,
            'food_category': food_category,
            'sampling_date': '2026-09-20',
            'test_date': '2026-09-21',
            'entry_date': '2026-09-22',
            'additive_name': additive_name,
            'measured_value': measured_value,
            'unit': 'mg/kg',
            'measurement_no': measurement_no,
            'sampler': sampler,
            'analyst': analyst,
            'recorder': recorder,
        }

    def validate(self, payload):
        self._validate_payload_type(payload)
        self._validate_top_level_keys(payload)
        self._validate_batch_no(payload['batch_no'])
        self._validate_records_container(payload['records'])
        self._validate_options(payload.get('options', {}))
        for index, record in enumerate(payload['records']):
            self._validate_record_container(record, index)
            self._validate_record_keys(record, index)
        return None

    def _validate_payload_type(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('输入必须为JSON对象')

    def _validate_top_level_keys(self, payload):
        required = {'batch_no', 'records'}
        missing = sorted(required - set(payload))
        if missing:
            joined = '、'.join(missing)
            raise ValueError('缺少顶层字段：' + joined)
        allowed = {'batch_no', 'records', 'options'}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            joined = '、'.join(unknown)
            raise ValueError('存在未知顶层字段：' + joined)

    def _validate_batch_no(self, batch_no):
        if not isinstance(batch_no, str):
            raise ValueError('batch_no必须为字符串')
        if not batch_no.strip():
            raise ValueError('batch_no不能为空')
        if len(batch_no.strip()) > self.MAX_TEXT_LENGTH:
            raise ValueError('batch_no长度不能超过100')

    def _validate_records_container(self, records):
        if not isinstance(records, list):
            raise ValueError('records必须为数组')
        if not records:
            raise ValueError('records不能为空')
        if len(records) > 10000:
            raise ValueError('单批次记录数不能超过10000')

    def _validate_options(self, options):
        if not isinstance(options, dict):
            raise ValueError('options必须为对象')
        allowed = {
            'require_separation_of_duties',
            'identical_duplicate_is_blocking',
        }
        unknown = sorted(set(options) - allowed)
        if unknown:
            joined = '、'.join(unknown)
            raise ValueError('存在未知选项：' + joined)
        for key, value in options.items():
            if not isinstance(value, bool):
                raise ValueError(key + '必须为布尔值')

    def _validate_record_container(self, record, index):
        if not isinstance(record, dict):
            location = str(index + 1)
            raise ValueError('第' + location + '条记录必须为对象')

    def _validate_record_keys(self, record, index):
        allowed = set(self.REQUIRED_FIELDS)
        unknown = sorted(set(record) - allowed)
        if unknown:
            location = str(index + 1)
            joined = '、'.join(unknown)
            raise ValueError(
                '第' + location + '条记录存在未知字段：' + joined
            )

    def calculate(self, payload):
        self.validate(payload)
        source = copy.deepcopy(payload)
        records = source['records']
        options = source.get('options', {})
        findings = self._inspect_records(
            records,
            source['batch_no'],
            options,
        )
        duplicate_groups = self._find_duplicate_groups(records)
        self._apply_duplicate_findings(
            records,
            findings,
            duplicate_groups,
            options,
        )
        sample_conflicts = self._find_sample_conflicts(records)
        self._apply_sample_conflicts(findings, sample_conflicts)
        states = self._build_states(records, findings, options)
        rows = self._build_rows(records, findings, states)
        conflicts = self._build_conflict_output(
            records,
            duplicate_groups,
        )
        matrix = self._build_matrix(findings, states)
        metrics = self._build_metrics(
            records,
            findings,
            states,
            conflicts,
        )
        series = self._build_series(states)
        summary = self._build_summary(metrics)
        return {
            'summary': summary,
            'metrics': metrics,
            'rows': rows,
            'series': series,
            'chart_title': '检测批次数据质量矩阵',
            'errors': self._flatten_findings(findings),
            'conflict_groups': conflicts,
            'matrix': matrix,
            'limitations': (
                '本结果仅验证数据结构与内部逻辑，不能证明实验室操作、'
                '仪器状态或原始检测报告真实有效。'
            ),
        }

    def _inspect_records(self, records, target_batch, options):
        findings = defaultdict(list)
        for index, record in enumerate(records):
            self._inspect_required_fields(record, index, findings)
            self._inspect_text_fields(record, index, findings)
            self._inspect_identifiers(record, index, findings)
            self._inspect_dates(record, index, findings)
            self._inspect_value(record, index, findings)
            self._inspect_unit(record, index, findings)
            self._inspect_measurement_no(record, index, findings)
            self._inspect_batch(record, index, target_batch, findings)
            self._inspect_people(record, index, findings, options)
        return findings

    def _inspect_required_fields(self, record, index, findings):
        for field in self.REQUIRED_FIELDS:
            if field not in record:
                self._add_finding(
                    findings,
                    index,
                    field,
                    'E001_FIELD_MISSING',
                    '字段不存在',
                )

    def _inspect_text_fields(self, record, index, findings):
        for field in self.TEXT_FIELDS:
            if field not in record:
                continue
            value = record[field]
            if not isinstance(value, str):
                self._add_finding(
                    findings,
                    index,
                    field,
                    'E003_TEXT_TYPE',
                    '应为字符串',
                )
                continue
            if not value.strip():
                self._add_finding(
                    findings,
                    index,
                    field,
                    'E002_TEXT_EMPTY',
                    '去除空白后为空',
                )
                continue
            if len(value.strip()) > self.MAX_TEXT_LENGTH:
                self._add_finding(
                    findings,
                    index,
                    field,
                    'E022_NAME_TOO_LONG',
                    '长度超过100个字符',
                )

    def _inspect_identifiers(self, record, index, findings):
        for field in ('batch_no', 'sample_no'):
            value = record.get(field)
            if not self._is_nonempty_text(value):
                continue
            if not self.IDENTIFIER_PATTERN.fullmatch(value.strip()):
                self._add_finding(
                    findings,
                    index,
                    field,
                    'E021_IDENTIFIER_FORMAT',
                    '仅建议使用字母、数字、下划线或连字符',
                )

    def _inspect_dates(self, record, index, findings):
        parsed = {}
        for field in self.DATE_FIELDS:
            value = record.get(field)
            if not self._is_nonempty_text(value):
                continue
            date_value = self._parse_date(value)
            if date_value is None:
                self._add_finding(
                    findings,
                    index,
                    field,
                    'E004_DATE_FORMAT',
                    '必须使用YYYY-MM-DD且为真实日期',
                )
            else:
                parsed[field] = date_value
        self._inspect_date_order(parsed, index, findings)

    def _inspect_date_order(self, parsed, index, findings):
        sampling = parsed.get('sampling_date')
        testing = parsed.get('test_date')
        entry = parsed.get('entry_date')
        if sampling is not None and testing is not None:
            if testing < sampling:
                self._add_finding(
                    findings,
                    index,
                    'test_date',
                    'E005_DATE_ORDER_SAMPLE_TEST',
                    '检测日期不得早于采样日期',
                )
        if testing is not None and entry is not None:
            if entry < testing:
                self._add_finding(
                    findings,
                    index,
                    'entry_date',
                    'E006_DATE_ORDER_TEST_ENTRY',
                    '录入日期不得早于检测日期',
                )

    def _inspect_value(self, record, index, findings):
        if 'measured_value' not in record:
            return
        value = record['measured_value']
        if value is None or value == '':
            self._add_finding(
                findings,
                index,
                'measured_value',
                'E007_VALUE_MISSING',
                '检测值缺失，必须人工复核',
            )
            return
        number, error = self._decimal_value(value)
        if error == 'type':
            self._add_finding(
                findings,
                index,
                'measured_value',
                'E008_VALUE_TYPE',
                '检测值必须为数字或数字字符串',
            )
            return
        if error == 'nonfinite':
            self._add_finding(
                findings,
                index,
                'measured_value',
                'E009_VALUE_NONFINITE',
                '检测值不得为NaN或无穷值',
            )
            return
        if number < 0:
            self._add_finding(
                findings,
                index,
                'measured_value',
                'E010_VALUE_NEGATIVE',
                '检测值不得为负数',
            )
            return
        if number > self.MAX_VALUE:
            self._add_finding(
                findings,
                index,
                'measured_value',
                'E020_VALUE_TOO_LARGE',
                '检测值超过系统上限1000000000',
            )

    def _inspect_unit(self, record, index, findings):
        value = record.get('unit')
        if not self._is_nonempty_text(value):
            return
        if value.strip() not in self.ALLOWED_UNITS:
            allowed = '、'.join(self.ALLOWED_UNITS)
            self._add_finding(
                findings,
                index,
                'unit',
                'E011_UNIT_INVALID',
                '允许单位为：' + allowed,
            )

    def _inspect_measurement_no(self, record, index, findings):
        if 'measurement_no' not in record:
            return
        value = record['measurement_no']
        if isinstance(value, bool) or not isinstance(value, int):
            self._add_finding(
                findings,
                index,
                'measurement_no',
                'E012_MEASUREMENT_NO_TYPE',
                '测定序号必须为整数',
            )
            return
        if value < 1 or value > self.MAX_MEASUREMENT_NO:
            self._add_finding(
                findings,
                index,
                'measurement_no',
                'E013_MEASUREMENT_NO_RANGE',
                '测定序号必须在1至9999之间',
            )

    def _inspect_batch(
        self,
        record,
        index,
        target_batch,
        findings,
    ):
        value = record.get('batch_no')
        if not self._is_nonempty_text(value):
            return
        if value.strip() != target_batch.strip():
            self._add_finding(
                findings,
                index,
                'batch_no',
                'E014_BATCH_MISMATCH',
                '应与顶层批次号一致',
            )

    def _inspect_people(self, record, index, findings, options):
        analyst = record.get('analyst')
        recorder = record.get('recorder')
        if not self._is_nonempty_text(analyst):
            return
        if not self._is_nonempty_text(recorder):
            return
        if analyst.strip() != recorder.strip():
            return
        detail = '检测人员与录入人员相同'
        if options.get('require_separation_of_duties', False):
            detail += '，本批次要求职责分离'
        self._add_finding(
            findings,
            index,
            'recorder',
            'E019_ANALYST_RECORDER_SAME',
            detail,
        )

    def _parse_date(self, value):
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        if len(stripped) != 10:
            return None
        try:
            parsed = datetime.datetime.strptime(
                stripped,
                '%Y-%m-%d',
            ).date()
        except ValueError:
            return None
        if parsed.isoformat() != stripped:
            return None
        return parsed

    def _decimal_value(self, value):
        if isinstance(value, bool):
            return None, 'type'
        if not isinstance(value, (int, float, str, Decimal)):
            return None, 'type'
        if isinstance(value, str) and not value.strip():
            return None, 'type'
        try:
            number = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            return None, 'type'
        if not number.is_finite():
            return None, 'nonfinite'
        return number, None

    def _is_nonempty_text(self, value):
        return isinstance(value, str) and bool(value.strip())

    def _add_finding(
        self,
        findings,
        index,
        field,
        code,
        detail,
    ):
        item = {
            'record_index': index,
            'record_no': index + 1,
            'field': field,
            'field_name': self.FIELD_NAMES.get(field, field),
            'code': code,
            'message': self.ERROR_NAMES[code],
            'detail': detail,
        }
        findings[index].append(item)

    def _composite_key(self, record):
        parts = (
            record.get('batch_no'),
            record.get('sample_no'),
            record.get('additive_name'),
            record.get('measurement_no'),
        )
        if not all(self._key_part_valid(part) for part in parts):
            return None
        return (
            str(parts[0]).strip(),
            str(parts[1]).strip(),
            str(parts[2]).strip(),
            int(parts[3]),
        )

    def _key_part_valid(self, part):
        if isinstance(part, bool):
            return False
        if isinstance(part, int):
            return part >= 1
        return self._is_nonempty_text(part)

    def _find_duplicate_groups(self, records):
        grouped = defaultdict(list)
        for index, record in enumerate(records):
            key = self._composite_key(record)
            if key is not None:
                grouped[key].append(index)
        result = []
        for key in sorted(grouped, key=self._sortable_key):
            indexes = grouped[key]
            if len(indexes) < 2:
                continue
            signatures = {
                self._record_signature(records[index])
                for index in indexes
            }
            result.append(
                {
                    'key': key,
                    'indexes': indexes,
                    'conflict': len(signatures) > 1,
                }
            )
        return result

    def _sortable_key(self, key):
        return tuple(str(part) for part in key)

    def _record_signature(self, record):
        pairs = []
        for field in self.REQUIRED_FIELDS:
            value = record.get(field, '<缺失>')
            pairs.append((field, self._stable_value(value)))
        return tuple(pairs)

    def _stable_value(self, value):
        if isinstance(value, float):
            if math.isnan(value):
                return 'NaN'
            if math.isinf(value):
                return 'Infinity' if value > 0 else '-Infinity'
        if isinstance(value, (str, int, float, bool)):
            return repr(value)
        if value is None:
            return 'None'
        return type(value).__name__ + ':' + repr(value)

    def _apply_duplicate_findings(
        self,
        records,
        findings,
        groups,
        options,
    ):
        for group in groups:
            if group['conflict']:
                code = 'E015_DUPLICATE_CONFLICT'
                detail = '同一复合键存在内容不同的记录，需人工选择'
            else:
                code = 'E016_DUPLICATE_IDENTICAL'
                detail = '同一复合键存在内容完全相同的重复记录'
            for index in group['indexes']:
                self._add_finding(
                    findings,
                    index,
                    'measurement_no',
                    code,
                    detail,
                )

    def _sample_key(self, record):
        batch = record.get('batch_no')
        sample = record.get('sample_no')
        if not self._is_nonempty_text(batch):
            return None
        if not self._is_nonempty_text(sample):
            return None
        return batch.strip(), sample.strip()

    def _find_sample_conflicts(self, records):
        grouped = defaultdict(list)
        for index, record in enumerate(records):
            key = self._sample_key(record)
            if key is not None:
                grouped[key].append(index)
        conflicts = []
        for key in sorted(grouped, key=self._sortable_key):
            indexes = grouped[key]
            food_values = self._distinct_fields(
                records,
                indexes,
                ('food_name', 'food_category'),
            )
            date_values = self._distinct_fields(
                records,
                indexes,
                ('sampling_date',),
            )
            if len(food_values) > 1:
                conflicts.append(
                    {
                        'indexes': indexes,
                        'field': 'food_name',
                        'code': 'E017_SAMPLE_FOOD_CONFLICT',
                    }
                )
            if len(date_values) > 1:
                conflicts.append(
                    {
                        'indexes': indexes,
                        'field': 'sampling_date',
                        'code': 'E018_SAMPLE_DATE_CONFLICT',
                    }
                )
        return conflicts

    def _distinct_fields(self, records, indexes, fields):
        values = set()
        for index in indexes:
            parts = []
            complete = True
            for field in fields:
                value = records[index].get(field)
                if not self._is_nonempty_text(value):
                    complete = False
                    break
                parts.append(value.strip())
            if complete:
                values.add(tuple(parts))
        return values

    def _apply_sample_conflicts(self, findings, conflicts):
        for conflict in conflicts:
            for index in conflict['indexes']:
                self._add_finding(
                    findings,
                    index,
                    conflict['field'],
                    conflict['code'],
                    '同一批次样品的基础信息必须保持一致',
                )

    def _effective_blocking_codes(self, options):
        codes = set(self.BLOCKING_CODES)
        if options.get('identical_duplicate_is_blocking', False):
            codes.add('E016_DUPLICATE_IDENTICAL')
        if options.get('require_separation_of_duties', False):
            codes.add('E019_ANALYST_RECORDER_SAME')
        return codes

    def _build_states(self, records, findings, options):
        blocking = self._effective_blocking_codes(options)
        states = []
        for index in range(len(records)):
            codes = {item['code'] for item in findings[index]}
            blocked = bool(codes & blocking)
            if blocked:
                status = '待人工复核'
            elif codes:
                status = '可计算但有警告'
            else:
                status = '可计算'
            states.append(
                {
                    'status': status,
                    'calculable': not blocked,
                    'blocking_count': len(codes & blocking),
                    'warning_count': len(codes - blocking),
                }
            )
        return states

    def _safe_text(self, record, field):
        value = record.get(field)
        if value is None:
            return '缺失'
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else '空值'
        return str(value)

    def _display_value(self, record):
        value = record.get('measured_value')
        number, error = self._decimal_value(value)
        if error is not None:
            return '不可用'
        return self._decimal_text(number)

    def _decimal_text(self, value):
        normalized = value.normalize()
        text = format(normalized, 'f')
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
        return text or '0'

    def _build_rows(self, records, findings, states):
        rows = []
        for index, record in enumerate(records):
            codes = [item['code'] for item in findings[index]]
            messages = [item['message'] for item in findings[index]]
            rows.append(
                {
                    '记录序号': index + 1,
                    '批次号': self._safe_text(record, 'batch_no'),
                    '样品号': self._safe_text(record, 'sample_no'),
                    '食品名称': self._safe_text(record, 'food_name'),
                    '添加剂名称': self._safe_text(
                        record,
                        'additive_name',
                    ),
                    '检测值': self._display_value(record),
                    '单位': self._safe_text(record, 'unit'),
                    '测定序号': self._safe_text(
                        record,
                        'measurement_no',
                    ),
                    '状态': states[index]['status'],
                    '错误数': states[index]['blocking_count'],
                    '警告数': states[index]['warning_count'],
                    '错误码': '、'.join(codes) if codes else '无',
                    '问题说明': '；'.join(messages) if messages else '通过',
                }
            )
        return rows

    def _build_conflict_output(self, records, groups):
        output = []
        number = 1
        for group in groups:
            if not group['conflict']:
                continue
            key = group['key']
            indexes = group['indexes']
            variants = []
            for index in indexes:
                record = records[index]
                variants.append(
                    {
                        '记录序号': index + 1,
                        '食品名称': self._safe_text(
                            record,
                            'food_name',
                        ),
                        '检测值': self._display_value(record),
                        '单位': self._safe_text(record, 'unit'),
                        '检测日期': self._safe_text(
                            record,
                            'test_date',
                        ),
                        '检测人员': self._safe_text(
                            record,
                            'analyst',
                        ),
                    }
                )
            output.append(
                {
                    '冲突组号': number,
                    '复合键': '|'.join(str(part) for part in key),
                    '记录序号': [index + 1 for index in indexes],
                    '差异记录': variants,
                    '处理要求': '保留全部冲突记录并由人工选择',
                }
            )
            number += 1
        return output

    def _matrix_dimensions(self):
        return (
            ('必填与类型', {
                'E001_FIELD_MISSING',
                'E002_TEXT_EMPTY',
                'E003_TEXT_TYPE',
                'E012_MEASUREMENT_NO_TYPE',
            }),
            ('日期逻辑', {
                'E004_DATE_FORMAT',
                'E005_DATE_ORDER_SAMPLE_TEST',
                'E006_DATE_ORDER_TEST_ENTRY',
                'E018_SAMPLE_DATE_CONFLICT',
            }),
            ('数值与单位', {
                'E007_VALUE_MISSING',
                'E008_VALUE_TYPE',
                'E009_VALUE_NONFINITE',
                'E010_VALUE_NEGATIVE',
                'E011_UNIT_INVALID',
                'E013_MEASUREMENT_NO_RANGE',
                'E020_VALUE_TOO_LARGE',
            }),
            ('跨记录一致性', {
                'E014_BATCH_MISMATCH',
                'E015_DUPLICATE_CONFLICT',
                'E016_DUPLICATE_IDENTICAL',
                'E017_SAMPLE_FOOD_CONFLICT',
            }),
            ('人员与格式', {
                'E019_ANALYST_RECORDER_SAME',
                'E021_IDENTIFIER_FORMAT',
                'E022_NAME_TOO_LONG',
            }),
        )

    def _build_matrix(self, findings, states):
        matrix = []
        dimensions = self._matrix_dimensions()
        for index in range(len(states)):
            codes = {item['code'] for item in findings[index]}
            cells = []
            for name, dimension_codes in dimensions:
                matched = sorted(codes & dimension_codes)
                if matched:
                    result = '异常'
                else:
                    result = '通过'
                cells.append(
                    {
                        '维度': name,
                        '结果': result,
                        '问题数': len(matched),
                        '错误码': '、'.join(matched) if matched else '无',
                    }
                )
            matrix.append(
                {
                    '记录序号': index + 1,
                    '最终状态': states[index]['status'],
                    '校验维度': cells,
                }
            )
        return matrix

    def _flatten_findings(self, findings):
        output = []
        for index in sorted(findings):
            ordered = sorted(
                findings[index],
                key=lambda item: (item['field'], item['code']),
            )
            output.extend(ordered)
        return output

    def _build_metrics(
        self,
        records,
        findings,
        states,
        conflicts,
    ):
        total = len(records)
        calculable = sum(1 for state in states if state['calculable'])
        review = total - calculable
        clean = sum(
            1
            for index in range(total)
            if not findings[index]
        )
        complete_fields = self._count_complete_fields(records)
        expected_fields = total * len(self.REQUIRED_FIELDS)
        completeness = self._percentage(
            complete_fields,
            expected_fields,
        )
        quality = self._percentage(clean, total)
        code_counts = Counter(
            item['code']
            for items in findings.values()
            for item in items
        )
        return {
            '记录总数': total,
            '可计算记录数': calculable,
            '待复核记录数': review,
            '完全通过记录数': clean,
            '批次完整率': completeness,
            '记录通过率': quality,
            '字段级问题数': sum(code_counts.values()),
            '冲突组数': len(conflicts),
            '涉及错误码种类': len(code_counts),
        }

    def _count_complete_fields(self, records):
        count = 0
        for record in records:
            for field in self.REQUIRED_FIELDS:
                if field not in record:
                    continue
                value = record[field]
                if value is None:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                count += 1
        return count

    def _percentage(self, numerator, denominator):
        if denominator == 0:
            return '0.00%'
        value = Decimal(numerator) * Decimal('100')
        value /= Decimal(denominator)
        rounded = value.quantize(Decimal('0.01'))
        return format(rounded, 'f') + '%'

    def _build_series(self, states):
        clean = sum(
            1
            for state in states
            if state['status'] == '可计算'
        )
        warning = sum(
            1
            for state in states
            if state['status'] == '可计算但有警告'
        )
        review = sum(
            1
            for state in states
            if state['status'] == '待人工复核'
        )
        return [
            {'label': '完全通过', 'value': clean},
            {'label': '可计算但有警告', 'value': warning},
            {'label': '待人工复核', 'value': review},
        ]

    def _build_summary(self, metrics):
        total = metrics['记录总数']
        calculable = metrics['可计算记录数']
        review = metrics['待复核记录数']
        conflicts = metrics['冲突组数']
        completeness = metrics['批次完整率']
        return (
            '采用模式、必填、标准日期、有限数值、范围及跨记录复合键'
            '校验，共检查'
            + str(total)
            + '条记录；可计算'
            + str(calculable)
            + '条，待人工复核'
            + str(review)
            + '条，发现冲突组'
            + str(conflicts)
            + '个，批次字段完整率为'
            + completeness
            + '。冲突记录均被保留，未发生静默覆盖。'
        )
