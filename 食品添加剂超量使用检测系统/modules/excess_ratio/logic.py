from copy import deepcopy
from datetime import date
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_UP
import json
import math


class Engine:
    LIMIT_NUMERIC = '数值限量'
    LIMIT_PROHIBITED = '禁止使用'
    LIMIT_AS_NEEDED = '按生产需要适量使用'
    LIMIT_QUALITATIVE = '其他非数值限量'
    LIMIT_TYPES = {
        LIMIT_NUMERIC,
        LIMIT_PROHIBITED,
        LIMIT_AS_NEEDED,
        LIMIT_QUALITATIVE,
    }
    LABEL_EXCESS = '超量预警'
    LABEL_WITHIN = '未超量'
    LABEL_EQUAL = '等于限量'
    LABEL_PROHIBITED_HIT = '禁止使用项目检出'
    LABEL_PROHIBITED_CLEAR = '禁止使用项目未检出'
    LABEL_REVIEW = '待人工复核'
    LABEL_INVALID = '不可计算'
    REQUIRED_PAYLOAD_FIELDS = {
        'records',
        'rounding_places',
        'as_of_date',
    }
    REQUIRED_RECORD_FIELDS = {
        'record_id',
        'food_name',
        'additive_name',
        'detected_value',
        'unit',
        'matched_rules',
    }
    REQUIRED_RULE_FIELDS = {
        'rule_id',
        'limit_type',
        'unit',
        'effective_date',
    }
    OPTIONAL_RECORD_FIELDS = {
        'detection_limit',
        'sample_batch',
        'laboratory',
    }
    OPTIONAL_RULE_FIELDS = {
        'limit_value',
        'expiry_date',
        'qualitative_text',
        'comparison_basis',
    }
    MAX_RECORDS = 1000
    MAX_TEXT_LENGTH = 200
    MAX_RULES_PER_RECORD = 20
    MAX_ABS_VALUE = Decimal('1E+30')
    MIN_ROUNDING_PLACES = 0
    MAX_ROUNDING_PLACES = 12

    def example(self):
        return {
            'as_of_date': '2026-09-23',
            'rounding_places': 3,
            'records': [
                {
                    'record_id': 'R001',
                    'food_name': '酱油',
                    'additive_name': '苯甲酸',
                    'detected_value': '1.20',
                    'unit': 'g/kg',
                    'detection_limit': '0.01',
                    'sample_batch': 'SY-20260901',
                    'laboratory': '示例实验室',
                    'matched_rules': [
                        {
                            'rule_id': 'DEMO-R001',
                            'limit_type': self.LIMIT_NUMERIC,
                            'limit_value': '1.0',
                            'comparison_basis': '成品残留量',
                            'unit': 'g/kg',
                            'effective_date': '2025-01-01',
                            'expiry_date': None,
                        }
                    ],
                },
                {
                    'record_id': 'R002',
                    'food_name': '果汁饮料',
                    'additive_name': '山梨酸',
                    'detected_value': '0.5004',
                    'unit': 'g/kg',
                    'detection_limit': '0.001',
                    'sample_batch': 'GZ-20260902',
                    'laboratory': '示例实验室',
                    'matched_rules': [
                        {
                            'rule_id': 'DEMO-R002',
                            'limit_type': self.LIMIT_NUMERIC,
                            'limit_value': '0.5',
                            'comparison_basis': '成品残留量',
                            'unit': 'g/kg',
                            'effective_date': '2025-01-01',
                            'expiry_date': None,
                        }
                    ],
                },
                {
                    'record_id': 'R003',
                    'food_name': '婴幼儿谷类食品',
                    'additive_name': '糖精钠',
                    'detected_value': '0.02',
                    'unit': 'g/kg',
                    'detection_limit': '0.005',
                    'sample_batch': 'YE-20260903',
                    'laboratory': '示例实验室',
                    'matched_rules': [
                        {
                            'rule_id': 'GB-R003',
                            'limit_type': self.LIMIT_PROHIBITED,
                            'unit': 'g/kg',
                            'effective_date': '2025-01-01',
                            'expiry_date': None,
                        }
                    ],
                },
                {
                    'record_id': 'R004',
                    'food_name': '糕点',
                    'additive_name': '柠檬酸',
                    'detected_value': '2.8',
                    'unit': 'g/kg',
                    'detection_limit': '0.01',
                    'sample_batch': 'GD-20260904',
                    'laboratory': '示例实验室',
                    'matched_rules': [
                        {
                            'rule_id': 'GB-R004',
                            'limit_type': self.LIMIT_AS_NEEDED,
                            'unit': 'g/kg',
                            'effective_date': '2025-01-01',
                            'expiry_date': None,
                            'qualitative_text': '按生产需要适量使用',
                        }
                    ],
                },
                {
                    'record_id': 'R005',
                    'food_name': '腌渍蔬菜',
                    'additive_name': '脱氢乙酸',
                    'detected_value': '0.24',
                    'unit': 'g/kg',
                    'detection_limit': '0.01',
                    'sample_batch': 'YC-20260905',
                    'laboratory': '示例实验室',
                    'matched_rules': [
                        {
                            'rule_id': 'DEMO-R005',
                            'limit_type': self.LIMIT_NUMERIC,
                            'limit_value': '0.3',
                            'comparison_basis': '成品残留量',
                            'unit': 'g/kg',
                            'effective_date': '2025-01-01',
                            'expiry_date': '2027-12-31',
                        }
                    ],
                },
            ],
        }

    def validate(self, payload):
        self._validate_payload_container(payload)
        self._validate_payload_fields(payload)
        self._validate_rounding_places(payload['rounding_places'])
        as_of_date = self._parse_date(
            payload['as_of_date'],
            'as_of_date',
        )
        records = payload['records']
        self._validate_records_container(records)
        seen_record_ids = set()
        for index, record in enumerate(records):
            path = 'records[%d]' % index
            self._validate_record(
                record,
                path,
                as_of_date,
                seen_record_ids,
            )
        return None

    def calculate(self, payload):
        self.validate(payload)
        snapshot = deepcopy(payload)
        places = payload['rounding_places']
        as_of_date = self._parse_date(
            payload['as_of_date'],
            'as_of_date',
        )
        rows = []
        series = []
        counters = self._new_counters()
        for record in payload['records']:
            rule = record['matched_rules'][0]
            row = self._calculate_record(
                record,
                rule,
                places,
                as_of_date,
            )
            rows.append(row)
            series.append(self._make_series_item(row))
            self._update_counters(counters, row)
        metrics = self._build_metrics(
            counters,
            len(rows),
            places,
        )
        result = {
            'summary': self._build_summary(counters, len(rows)),
            'metrics': metrics,
            'rows': rows,
            'series': series,
            'chart_title': '食品添加剂超量比值与专项判定',
            'method': {
                '边界原则': '用未经显示舍入的十进制数比较',
                '数值公式': '检测值÷限量值；超出百分比=(比值-1)×100%',
                '非数值原则': '禁止使用及定性限量不构造零分母',
                '结论范围': '结果仅为数学初筛，不构成法定合规结论',
            },
        }
        self._assert_json_serializable(result)
        if payload != snapshot:
            raise RuntimeError('计算过程改变了输入数据')
        return result

    def _validate_payload_container(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('payload必须是字典')

    def _validate_payload_fields(self, payload):
        missing = self.REQUIRED_PAYLOAD_FIELDS - set(payload)
        if missing:
            names = self._join_names(missing)
            raise ValueError('payload缺少字段：' + names)
        allowed = set(self.REQUIRED_PAYLOAD_FIELDS)
        extra = set(payload) - allowed
        if extra:
            names = self._join_names(extra)
            raise ValueError('payload包含未知字段：' + names)

    def _validate_rounding_places(self, value):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError('rounding_places必须是整数')
        if value < self.MIN_ROUNDING_PLACES:
            raise ValueError('rounding_places不能小于0')
        if value > self.MAX_ROUNDING_PLACES:
            raise ValueError('rounding_places不能大于12')

    def _validate_records_container(self, records):
        if not isinstance(records, list):
            raise ValueError('records必须是列表')
        if not records:
            raise ValueError('records不能为空')
        if len(records) > self.MAX_RECORDS:
            raise ValueError('records最多允许1000条记录')

    def _validate_record(
        self,
        record,
        path,
        as_of_date,
        seen_record_ids,
    ):
        if not isinstance(record, dict):
            raise ValueError(path + '必须是字典')
        self._validate_record_fields(record, path)
        record_id = self._validate_text(
            record['record_id'],
            path + '.record_id',
        )
        if record_id in seen_record_ids:
            raise ValueError(path + '.record_id不能重复')
        seen_record_ids.add(record_id)
        self._validate_text(
            record['food_name'],
            path + '.food_name',
        )
        self._validate_text(
            record['additive_name'],
            path + '.additive_name',
        )
        unit = self._validate_text(
            record['unit'],
            path + '.unit',
        )
        detected = self._parse_decimal(
            record['detected_value'],
            path + '.detected_value',
            allow_zero=True,
        )
        if detected < 0:
            raise ValueError(path + '.detected_value不能为负数')
        if 'detection_limit' in record:
            detection_limit = self._parse_decimal(
                record['detection_limit'],
                path + '.detection_limit',
                allow_zero=False,
            )
            if detection_limit <= 0:
                raise ValueError(path + '.detection_limit必须大于0')
        if 'sample_batch' in record:
            self._validate_text(
                record['sample_batch'],
                path + '.sample_batch',
            )
        if 'laboratory' in record:
            self._validate_text(
                record['laboratory'],
                path + '.laboratory',
            )
        rules = record['matched_rules']
        self._validate_rule_list(rules, path)
        rule = rules[0]
        self._validate_rule(
            rule,
            path + '.matched_rules[0]',
            unit,
            as_of_date,
        )

    def _validate_record_fields(self, record, path):
        missing = self.REQUIRED_RECORD_FIELDS - set(record)
        if missing:
            names = self._join_names(missing)
            raise ValueError(path + '缺少字段：' + names)
        allowed = self.REQUIRED_RECORD_FIELDS | self.OPTIONAL_RECORD_FIELDS
        extra = set(record) - allowed
        if extra:
            names = self._join_names(extra)
            raise ValueError(path + '包含未知字段：' + names)

    def _validate_rule_list(self, rules, path):
        if not isinstance(rules, list):
            raise ValueError(path + '.matched_rules必须是列表')
        if not rules:
            raise ValueError(path + '没有匹配到有效规则')
        if len(rules) > self.MAX_RULES_PER_RECORD:
            raise ValueError(path + '.matched_rules数量异常')
        if len(rules) != 1:
            raise ValueError(path + '必须且只能匹配一条有效规则')

    def _validate_rule(
        self,
        rule,
        path,
        record_unit,
        as_of_date,
    ):
        if not isinstance(rule, dict):
            raise ValueError(path + '必须是字典')
        self._validate_rule_fields(rule, path)
        self._validate_text(rule['rule_id'], path + '.rule_id')
        limit_type = self._validate_text(
            rule['limit_type'],
            path + '.limit_type',
        )
        if limit_type not in self.LIMIT_TYPES:
            raise ValueError(path + '.limit_type不是支持的限量类型')
        if 'comparison_basis' in rule:
            basis = self._validate_text(
                rule['comparison_basis'], path + '.comparison_basis'
            )
            if basis not in {'成品残留量', '最大使用量'}:
                raise ValueError(path + '.comparison_basis不是支持的比较口径')
        rule_unit = self._validate_text(
            rule['unit'],
            path + '.unit',
        )
        if rule_unit != record_unit:
            raise ValueError(path + '.unit与检测结果单位不兼容')
        effective = self._parse_date(
            rule['effective_date'],
            path + '.effective_date',
        )
        expiry = self._validate_expiry(rule, path, effective)
        if effective > as_of_date:
            raise ValueError(path + '在指定日期尚未生效')
        if expiry is not None and as_of_date > expiry:
            raise ValueError(path + '在指定日期已经失效')
        self._validate_limit_fields(rule, path, limit_type)

    def _validate_rule_fields(self, rule, path):
        missing = self.REQUIRED_RULE_FIELDS - set(rule)
        if missing:
            names = self._join_names(missing)
            raise ValueError(path + '缺少字段：' + names)
        allowed = self.REQUIRED_RULE_FIELDS | self.OPTIONAL_RULE_FIELDS
        extra = set(rule) - allowed
        if extra:
            names = self._join_names(extra)
            raise ValueError(path + '包含未知字段：' + names)

    def _validate_expiry(self, rule, path, effective):
        if 'expiry_date' not in rule:
            return None
        value = rule['expiry_date']
        if value is None:
            return None
        expiry = self._parse_date(
            value,
            path + '.expiry_date',
        )
        if expiry < effective:
            raise ValueError(path + '.expiry_date不能早于生效日期')
        return expiry

    def _validate_limit_fields(self, rule, path, limit_type):
        has_limit = 'limit_value' in rule
        if limit_type == self.LIMIT_NUMERIC:
            if not has_limit:
                raise ValueError(path + '.limit_value不能为空')
            limit = self._parse_decimal(
                rule['limit_value'],
                path + '.limit_value',
                allow_zero=False,
            )
            if limit <= 0:
                raise ValueError(path + '.limit_value必须大于0')
            if 'qualitative_text' in rule:
                raise ValueError(path + '数值限量不得带定性限量文本')
            return
        if has_limit:
            raise ValueError(path + '非数值限量不得提供limit_value')
        if limit_type == self.LIMIT_PROHIBITED:
            if 'qualitative_text' in rule:
                text = rule['qualitative_text']
                self._validate_text(text, path + '.qualitative_text')
            return
        if 'qualitative_text' not in rule:
            raise ValueError(path + '.qualitative_text不能为空')
        self._validate_text(
            rule['qualitative_text'],
            path + '.qualitative_text',
        )

    def _validate_text(self, value, path):
        if not isinstance(value, str):
            raise ValueError(path + '必须是字符串')
        stripped = value.strip()
        if not stripped:
            raise ValueError(path + '不能为空')
        if len(stripped) > self.MAX_TEXT_LENGTH:
            raise ValueError(path + '长度不能超过200个字符')
        if stripped != value:
            raise ValueError(path + '首尾不能包含空白字符')
        return stripped

    def _parse_date(self, value, path):
        if not isinstance(value, str):
            raise ValueError(path + '必须是YYYY-MM-DD字符串')
        if value.strip() != value or not value:
            raise ValueError(path + '不能为空且不能带首尾空白')
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(path + '不是有效的YYYY-MM-DD日期') from exc
        if parsed.isoformat() != value:
            raise ValueError(path + '必须使用YYYY-MM-DD格式')
        return parsed

    def _parse_decimal(self, value, path, allow_zero):
        if isinstance(value, bool):
            raise ValueError(path + '必须是有限十进制数')
        if not isinstance(value, (str, int, float, Decimal)):
            raise ValueError(path + '必须是有限十进制数')
        if isinstance(value, str):
            if not value or value.strip() != value:
                raise ValueError(path + '不能为空且不能带首尾空白')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(path + '必须是有限十进制数')
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(path + '必须是有限十进制数') from exc
        if not number.is_finite():
            raise ValueError(path + '必须是有限十进制数')
        if abs(number) > self.MAX_ABS_VALUE:
            raise ValueError(path + '绝对值过大')
        if not allow_zero and number == 0:
            raise ValueError(path + '不能为0')
        return number

    def _calculate_record(
        self,
        record,
        rule,
        places,
        as_of_date,
    ):
        limit_type = rule['limit_type']
        if limit_type == self.LIMIT_NUMERIC:
            if rule.get('comparison_basis') != '成品残留量':
                return self._calculate_incomparable(
                    record, rule, as_of_date
                )
            return self._calculate_numeric(
                record,
                rule,
                places,
                as_of_date,
            )
        if limit_type == self.LIMIT_PROHIBITED:
            return self._calculate_prohibited(
                record,
                rule,
                places,
                as_of_date,
            )
        return self._calculate_non_numeric(
            record,
            rule,
            places,
            as_of_date,
        )

    def _base_row(self, record, rule, as_of_date):
        return {
            '记录标识': record['record_id'],
            '食品名称': record['food_name'],
            '添加剂名称': record['additive_name'],
            '检测值': self._plain_decimal(
                self._parse_decimal(
                    record['detected_value'],
                    'detected_value',
                    True,
                )
            ),
            '统一单位': record['unit'],
            '规则标识': rule['rule_id'],
            '限量类型': rule['limit_type'],
            '比较口径': rule.get('comparison_basis', '未确认'),
            '判定日期': as_of_date.isoformat(),
        }

    def _calculate_incomparable(self, record, rule, as_of_date):
        basis = rule.get('comparison_basis', '未确认')
        reason = (
            '最大使用量是投入环节的用量，不能直接与成品检测浓度相除。'
            if basis == '最大使用量'
            else '未确认规则数值是成品残留量限量，不能直接与成品检测浓度相除。'
        )
        row = self._base_row(record, rule, as_of_date)
        row.update(
            {
                '适用限量': str(rule['limit_value']) + ' ' + rule['unit'],
                '超量比值': '不适用',
                '超出百分比': '不适用',
                '边界距离': '不适用',
                '边界方向': '比较口径不一致',
                '计算表达式': '比较口径未确认：不进行除法',
                '初筛标签': self.LABEL_REVIEW,
                '未经舍入比值': '不适用',
                '未经舍入边界距离': '不适用',
                '预警依据': reason + '请专业人员核对规则来源、计量基准和适用范围。',
            }
        )
        return row

    def _calculate_numeric(
        self,
        record,
        rule,
        places,
        as_of_date,
    ):
        detected = self._parse_decimal(
            record['detected_value'],
            'detected_value',
            True,
        )
        limit = self._parse_decimal(
            rule['limit_value'],
            'limit_value',
            False,
        )
        raw_ratio = detected / limit
        raw_excess_percent = (raw_ratio - Decimal('1')) * Decimal('100')
        raw_distance = detected - limit
        comparison = self._compare(detected, limit)
        label = self._numeric_label(comparison)
        row = self._base_row(record, rule, as_of_date)
        row.update(
            {
                '适用限量': self._plain_decimal(limit),
                '超量比值': self._format_decimal(raw_ratio, places),
                '超出百分比': self._format_percent(
                    raw_excess_percent,
                    places,
                ),
                '边界距离': self._format_decimal(raw_distance, places),
                '边界方向': self._boundary_direction(comparison),
                '计算表达式': self._numeric_expression(
                    detected,
                    limit,
                ),
                '初筛标签': label,
                '未经舍入比值': self._plain_decimal(raw_ratio),
                '未经舍入边界距离': self._plain_decimal(raw_distance),
                '预警依据': self._numeric_basis(
                    comparison,
                    detected,
                    limit,
                ),
            }
        )
        return row

    def _calculate_prohibited(
        self,
        record,
        rule,
        places,
        as_of_date,
    ):
        detected = self._parse_decimal(
            record['detected_value'],
            'detected_value',
            True,
        )
        detection_limit = self._optional_detection_limit(record)
        found = self._is_detected(detected, detection_limit)
        label = (
            self.LABEL_PROHIBITED_HIT
            if found
            else self.LABEL_PROHIBITED_CLEAR
        )
        row = self._base_row(record, rule, as_of_date)
        row.update(
            {
                '适用限量': '禁止使用（无数值分母）',
                '超量比值': '不适用',
                '超出百分比': '不适用',
                '边界距离': '不适用',
                '边界方向': '检出' if found else '未检出',
                '计算表达式': '禁止使用规则：不进行除法',
                '初筛标签': label,
                '未经舍入比值': '不适用',
                '未经舍入边界距离': '不适用',
                '预警依据': self._prohibited_basis(
                    detected,
                    detection_limit,
                    found,
                    places,
                ),
            }
        )
        return row

    def _calculate_non_numeric(
        self,
        record,
        rule,
        places,
        as_of_date,
    ):
        text = rule.get('qualitative_text', '需依据规则文本复核')
        row = self._base_row(record, rule, as_of_date)
        row.update(
            {
                '适用限量': text,
                '超量比值': '不适用',
                '超出百分比': '不适用',
                '边界距离': '不适用',
                '边界方向': '无法通过数值比值判断',
                '计算表达式': '非数值限量：不进行除法',
                '初筛标签': self.LABEL_REVIEW,
                '未经舍入比值': '不适用',
                '未经舍入边界距离': '不适用',
                '预警依据': self._non_numeric_basis(rule),
            }
        )
        return row

    def _optional_detection_limit(self, record):
        if 'detection_limit' not in record:
            return None
        return self._parse_decimal(
            record['detection_limit'],
            'detection_limit',
            False,
        )

    def _is_detected(self, detected, detection_limit):
        if detected <= 0:
            return False
        if detection_limit is None:
            return True
        return detected >= detection_limit

    def _compare(self, left, right):
        if left > right:
            return 1
        if left < right:
            return -1
        return 0

    def _numeric_label(self, comparison):
        if comparison > 0:
            return self.LABEL_EXCESS
        if comparison < 0:
            return self.LABEL_WITHIN
        return self.LABEL_EQUAL

    def _boundary_direction(self, comparison):
        if comparison > 0:
            return '高于限量'
        if comparison < 0:
            return '低于限量'
        return '恰好等于限量'

    def _numeric_expression(self, detected, limit):
        return (
            self._plain_decimal(detected)
            + ' ÷ '
            + self._plain_decimal(limit)
        )

    def _numeric_basis(self, comparison, detected, limit):
        left = self._plain_decimal(detected)
        right = self._plain_decimal(limit)
        if comparison > 0:
            relation = '大于'
        elif comparison < 0:
            relation = '小于'
        else:
            relation = '等于'
        return (
            '未经显示舍入的检测值'
            + left
            + relation
            + '限量值'
            + right
        )

    def _prohibited_basis(
        self,
        detected,
        detection_limit,
        found,
        places,
    ):
        detected_text = self._format_decimal(detected, places)
        if detection_limit is None:
            threshold_text = '未提供检出限，按检测值大于0识别检出'
        else:
            threshold_text = (
                '检出限为'
                + self._format_decimal(detection_limit, places)
            )
        state = '认定为检出' if found else '未认定为检出'
        return (
            '检测值为'
            + detected_text
            + '；'
            + threshold_text
            + '；'
            + state
        )

    def _non_numeric_basis(self, rule):
        if rule['limit_type'] == self.LIMIT_AS_NEEDED:
            return '按生产需要适量使用，须结合工艺必要性和实际用量复核'
        return '该规则没有可用于除法的数值限量，须依据规则文本复核'

    def _format_decimal(self, value, places):
        quantum = Decimal('1').scaleb(-places)
        rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
        return format(rounded, 'f')

    def _format_percent(self, value, places):
        return self._format_decimal(value, places) + '%'

    def _plain_decimal(self, value):
        text = format(value, 'f')
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
        if text in {'-0', ''}:
            return '0'
        return text

    def _new_counters(self):
        return {
            '数值记录': 0,
            '超量记录': 0,
            '等于限量记录': 0,
            '未超量记录': 0,
            '禁止使用检出记录': 0,
            '禁止使用未检出记录': 0,
            '待复核记录': 0,
            '比值合计': Decimal('0'),
            '最高比值': None,
        }

    def _update_counters(self, counters, row):
        label = row['初筛标签']
        if row['未经舍入比值'] != '不适用':
            counters['数值记录'] += 1
            ratio = Decimal(row['未经舍入比值'])
            counters['比值合计'] += ratio
            current_max = counters['最高比值']
            if current_max is None or ratio > current_max:
                counters['最高比值'] = ratio
        if label == self.LABEL_EXCESS:
            counters['超量记录'] += 1
        elif label == self.LABEL_EQUAL:
            counters['等于限量记录'] += 1
        elif label == self.LABEL_WITHIN:
            counters['未超量记录'] += 1
        elif label == self.LABEL_PROHIBITED_HIT:
            counters['禁止使用检出记录'] += 1
        elif label == self.LABEL_PROHIBITED_CLEAR:
            counters['禁止使用未检出记录'] += 1
        elif label == self.LABEL_REVIEW:
            counters['待复核记录'] += 1

    def _build_metrics(self, counters, total, places):
        numeric_count = counters['数值记录']
        average = self._average_ratio(counters, numeric_count)
        maximum = counters['最高比值']
        return {
            '记录总数': total,
            '可计算数值比值数': numeric_count,
            '数值超量数': counters['超量记录'],
            '恰好等于限量数': counters['等于限量记录'],
            '数值未超量数': counters['未超量记录'],
            '禁止使用项目检出数': counters['禁止使用检出记录'],
            '禁止使用项目未检出数': counters['禁止使用未检出记录'],
            '非数值待复核数': counters['待复核记录'],
            '待人工复核数': counters['待复核记录'],
            '平均超量比值': self._optional_metric(average, places),
            '最高超量比值': self._optional_metric(maximum, places),
        }

    def _average_ratio(self, counters, numeric_count):
        if numeric_count == 0:
            return None
        return counters['比值合计'] / Decimal(numeric_count)

    def _optional_metric(self, value, places):
        if value is None:
            return '不适用'
        return self._format_decimal(value, places)

    def _build_summary(self, counters, total):
        parts = [
            '共处理%d条记录' % total,
            '其中%d条完成数值比值计算' % counters['数值记录'],
            '发现%d条数值超量预警' % counters['超量记录'],
            '发现%d条禁止使用项目检出' % counters['禁止使用检出记录'],
            '另有%d条不可直接比较的记录待复核' % counters['待复核记录'],
        ]
        method = (
            '边界以未经显示舍入的十进制值判断，'
            '仅确认成品残留量口径时计算比值；其他情况不构造分母。'
        )
        limitation = (
            '该结果仅反映录入数据与所选规则的数学关系，'
            '不构成行政、司法或法定合规结论。'
        )
        return '；'.join(parts) + '。' + method + limitation

    def _make_series_item(self, row):
        label = row['记录标识'] + ' ' + row['添加剂名称']
        if row['未经舍入比值'] != '不适用':
            value = float(Decimal(row['未经舍入比值']))
        elif row['初筛标签'] == self.LABEL_PROHIBITED_HIT:
            value = 1.0
        else:
            value = 0.0
        if not math.isfinite(value):
            raise ValueError('图表数值必须为有限数字')
        return {
            'label': label,
            'value': value,
        }

    def _join_names(self, names):
        return '、'.join(sorted(names))

    def _assert_json_serializable(self, value):
        try:
            json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError('计算结果无法序列化为JSON') from exc
