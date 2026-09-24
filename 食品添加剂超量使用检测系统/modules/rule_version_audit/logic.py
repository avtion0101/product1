import copy
import datetime
import math
import re
import unicodedata
from collections import defaultdict


class Engine:
    REQUIRED_TOP = (
        'old_version',
        'new_version',
        'history_reports',
        'scope',
        'administrator_confirmed',
    )
    VERSION_FIELDS = (
        'version_id',
        'version_name',
        'status',
        'verified',
        'effective_date',
        'source',
        'reviewer',
        'rules',
    )
    RULE_FIELDS = (
        'food_code',
        'additive_name',
        'condition',
        'limit_type',
        'limit_value',
        'unit',
        'effective_date',
        'source',
        'reviewer',
        'verified',
    )
    HISTORY_FIELDS = (
        'batch_id',
        'report_id',
        'report_date',
        'food_code',
        'additive_name',
        'condition',
        'measured_value',
        'unit',
        'original_conclusion',
    )
    LIMIT_TYPES = {
        'maximum': '最大使用量',
        'minimum': '最低要求量',
        'prohibited': '禁止使用',
        'gmp': '按生产需要适量使用',
    }
    VERSION_STATUSES = {
        'draft': '草稿',
        'pending': '待核验',
        'verified': '已核验',
        'effective': '当前有效',
        'inactive': '已停用',
        'archived': '已归档',
    }
    CONCLUSIONS = {
        'pass': '合格',
        'fail': '不合格',
        'manual': '人工复核',
        'unknown': '未知',
    }
    PRIORITY_ORDER = {
        '紧急': 0,
        '高': 1,
        '中': 2,
        '低': 3,
    }
    CHANGE_ORDER = {
        '修改': 0,
        '删除': 1,
        '新增': 2,
    }
    FIELD_LABELS = {
        'limit_type': '限量类型',
        'limit_value': '限量数值',
        'unit': '计量单位',
        'effective_date': '生效日期',
        'source': '规则来源',
        'condition': '适用条件',
        'reviewer': '录入审核人',
        'verified': '核验状态',
    }
    UNIT_DIMENSIONS = {
        'mg/kg': '质量比',
        'g/kg': '质量比',
        'ug/kg': '质量比',
        'μg/kg': '质量比',
        'mg/l': '质量浓度',
        'g/l': '质量浓度',
        'ug/l': '质量浓度',
        'μg/l': '质量浓度',
        'ppm': '质量比',
        '%': '质量分数',
        'none': '无量纲',
    }
    UNIT_FACTORS = {
        'mg/kg': 1.0,
        'g/kg': 1000.0,
        'ug/kg': 0.001,
        'μg/kg': 0.001,
        'ppm': 1.0,
        '%': 10000.0,
        'mg/l': 1.0,
        'g/l': 1000.0,
        'ug/l': 0.001,
        'μg/l': 0.001,
        'none': 1.0,
    }
    SEVERITY_WEIGHTS = {
        'limit_type': 5,
        'limit_value': 5,
        'unit': 4,
        'effective_date': 3,
        'condition': 3,
        'source': 2,
        'reviewer': 1,
        'verified': 5,
    }
    HIGH_RISK_TYPES = {
        'prohibited',
        'maximum',
    }
    SPACE_RE = re.compile(r'\s+')
    CODE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$')

    def example(self):
        old_rules = [
            self._example_rule(
                '01.01', '苯甲酸', '普通食品', 'maximum',
                1.0, 'g/kg', '2025-01-01', 'GB 2760-2024', '李审'
            ),
            self._example_rule(
                '01.02', '山梨酸', '非发酵制品', 'maximum',
                0.5, 'g/kg', '2025-01-01', 'GB 2760-2024', '王审'
            ),
            self._example_rule(
                '02.01', '糖精钠', '以糖精计', 'maximum',
                0.15, 'g/kg', '2025-01-01', 'GB 2760-2024', '赵审'
            ),
            self._example_rule(
                '03.01', '苏丹红', '所有产品', 'prohibited',
                None, 'none', '2025-01-01', '公告2024-8', '钱审'
            ),
            self._example_rule(
                '04.01', '柠檬酸', '按工艺需要', 'gmp',
                None, 'none', '2025-01-01', 'GB 2760-2024', '周审'
            ),
        ]
        new_rules = copy.deepcopy(old_rules)
        new_rules[0]['limit_value'] = 0.8
        new_rules[0]['effective_date'] = '2026-07-01'
        new_rules[0]['source'] = 'GB 2760-2026'
        new_rules.pop(1)
        new_rules.append(
            self._example_rule(
                '05.01', '脱氢乙酸', '腌渍蔬菜', 'maximum',
                0.3, 'g/kg', '2026-07-01', 'GB 2760-2026', '郑审'
            )
        )
        reports = [
            self._example_report(
                'B001', 'R001', '2026-07-02', '01.01',
                '苯甲酸', '普通食品', 0.9, 'g/kg', 'pass'
            ),
            self._example_report(
                'B002', 'R002', '2026-07-03', '01.02',
                '山梨酸', '非发酵制品', 0.6, 'g/kg', 'fail'
            ),
            self._example_report(
                'B003', 'R003', '2026-07-04', '02.01',
                '糖精钠', '以糖精计', 0.1, 'g/kg', 'pass'
            ),
            self._example_report(
                'B004', 'R004', '2026-07-05', '03.01',
                '苏丹红', '所有产品', 0.0, 'mg/kg', 'pass'
            ),
            self._example_report(
                'B005', 'R005', '2026-07-06', '05.01',
                '脱氢乙酸', '腌渍蔬菜', 0.35, 'g/kg', 'pass'
            ),
        ]
        return {
            'old_version': {
                'version_id': 'V2024',
                'version_name': '食品添加剂规则2024版',
                'status': 'inactive',
                'verified': True,
                'effective_date': '2025-01-01',
                'source': 'GB 2760-2024',
                'reviewer': '陈审核',
                'rules': old_rules,
                'status_history': [
                    {
                        'status': 'effective',
                        'date': '2025-01-01',
                        'operator': '陈审核',
                    },
                    {
                        'status': 'inactive',
                        'date': '2026-07-01',
                        'operator': '陈审核',
                    },
                ],
            },
            'new_version': {
                'version_id': 'V2026',
                'version_name': '食品添加剂规则2026版',
                'status': 'effective',
                'verified': True,
                'effective_date': '2026-07-01',
                'source': 'GB 2760-2026',
                'reviewer': '陈审核',
                'rules': new_rules,
                'status_history': [
                    {
                        'status': 'verified',
                        'date': '2026-06-20',
                        'operator': '陈审核',
                    },
                    {
                        'status': 'effective',
                        'date': '2026-07-01',
                        'operator': '系统管理员',
                    },
                ],
            },
            'history_reports': reports,
            'scope': {
                'date_from': '2026-07-01',
                'date_to': '2026-12-31',
                'food_codes': [],
                'additives': [],
            },
            'administrator_confirmed': False,
        }

    def validate(self, payload):
        self._validate_mapping(payload, '输入')
        self._validate_required(payload, self.REQUIRED_TOP, '输入')
        self._validate_bool(
            payload['administrator_confirmed'],
            'administrator_confirmed',
        )
        old_version = payload['old_version']
        new_version = payload['new_version']
        self._validate_version(old_version, 'old_version')
        self._validate_version(new_version, 'new_version')
        self._validate_version_relation(old_version, new_version)
        self._validate_history_reports(payload['history_reports'])
        self._validate_scope(payload['scope'])
        self._validate_unique_report_ids(payload['history_reports'])
        self._validate_status_history(old_version, 'old_version')
        self._validate_status_history(new_version, 'new_version')
        self._validate_current_version(new_version)
        return None

    def calculate(self, payload):
        self.validate(payload)
        data = copy.deepcopy(payload)
        old_version = data['old_version']
        new_version = data['new_version']
        scope = data['scope']
        old_rules = self._rules_in_scope(old_version['rules'], scope)
        new_rules = self._rules_in_scope(new_version['rules'], scope)
        old_index = self._build_rule_index(old_rules)
        new_index = self._build_rule_index(new_rules)
        strict_changes = self._strict_set_difference(old_index, new_index)
        reconciled = self._reconcile_condition_changes(strict_changes)
        modifications = self._find_modifications(old_index, new_index)
        modifications.extend(reconciled['modifications'])
        modifications = self._deduplicate_modifications(modifications)
        additions = self._remove_reconciled(
            strict_changes['additions'],
            reconciled['new_keys'],
        )
        deletions = self._remove_reconciled(
            strict_changes['deletions'],
            reconciled['old_keys'],
        )
        changes = self._assemble_changes(
            additions,
            deletions,
            modifications,
        )
        history = self._history_in_scope(data['history_reports'], scope)
        reverse_index = self._build_history_index(history)
        affected = self._find_affected_reports(changes, reverse_index)
        affected = self._sort_affected(affected)
        rows = self._build_matrix_rows(changes)
        if not rows:
            rows = [self._unchanged_row(old_version, new_version)]
        metrics = self._build_metrics(
            old_rules,
            new_rules,
            changes,
            history,
            affected,
        )
        series = self._build_series(changes, affected)
        audit_records = self._build_audit_records(
            old_version,
            new_version,
            changes,
            affected,
            data['administrator_confirmed'],
        )
        summary = self._build_summary(
            old_version,
            new_version,
            changes,
            affected,
            data['administrator_confirmed'],
        )
        return {
            'summary': summary,
            'metrics': metrics,
            'rows': rows,
            'series': series,
            'chart_title': '规则版本字段级差异与历史影响矩阵',
            'added_rules': self._rule_list(additions, '新增'),
            'deleted_rules': self._rule_list(deletions, '删除'),
            'affected_batches': affected,
            'recalculation_queue': affected,
            'audit_records': audit_records,
            'write_policy': self._write_policy(
                data['administrator_confirmed']
            ),
            'limitations': [
                '仅依据已录入且已核验的两个规则版本进行比较',
                '公告解释、过渡条款和复杂适用条件仍需专业人员确认',
                '本结果只生成待重算清单，不改写既有报告结论',
            ],
        }

    def _example_rule(
        self,
        food_code,
        additive_name,
        condition,
        limit_type,
        limit_value,
        unit,
        effective_date,
        source,
        reviewer,
    ):
        return {
            'food_code': food_code,
            'additive_name': additive_name,
            'condition': condition,
            'limit_type': limit_type,
            'limit_value': limit_value,
            'unit': unit,
            'effective_date': effective_date,
            'source': source,
            'reviewer': reviewer,
            'verified': True,
        }

    def _example_report(
        self,
        batch_id,
        report_id,
        report_date,
        food_code,
        additive_name,
        condition,
        measured_value,
        unit,
        conclusion,
    ):
        return {
            'batch_id': batch_id,
            'report_id': report_id,
            'report_date': report_date,
            'food_code': food_code,
            'additive_name': additive_name,
            'condition': condition,
            'measured_value': measured_value,
            'unit': unit,
            'original_conclusion': conclusion,
        }

    def _validate_mapping(self, value, name):
        if not isinstance(value, dict):
            raise ValueError(name + '必须为对象')

    def _validate_list(self, value, name):
        if not isinstance(value, list):
            raise ValueError(name + '必须为数组')

    def _validate_required(self, value, fields, name):
        missing = [field for field in fields if field not in value]
        if missing:
            raise ValueError(name + '缺少字段：' + '、'.join(missing))

    def _validate_string(self, value, name, max_length=200):
        if not isinstance(value, str):
            raise ValueError(name + '必须为字符串')
        if not value.strip():
            raise ValueError(name + '不能为空')
        if len(value) > max_length:
            raise ValueError(name + '长度超过限制')

    def _validate_optional_string(self, value, name, max_length=200):
        if value is None:
            return
        self._validate_string(value, name, max_length)

    def _validate_bool(self, value, name):
        if type(value) is not bool:
            raise ValueError(name + '必须为布尔值')

    def _validate_number(self, value, name, allow_none=False):
        if value is None and allow_none:
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(name + '必须为数字')
        if not math.isfinite(value):
            raise ValueError(name + '必须为有限数字')
        if value < 0:
            raise ValueError(name + '不能为负数')

    def _parse_date(self, value, name):
        self._validate_string(value, name, 10)
        try:
            parsed = datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(name + '必须为YYYY-MM-DD日期') from exc
        if parsed.isoformat() != value:
            raise ValueError(name + '必须使用补零的YYYY-MM-DD格式')
        return parsed

    def _validate_version(self, version, name):
        self._validate_mapping(version, name)
        self._validate_required(version, self.VERSION_FIELDS, name)
        self._validate_string(version['version_id'], name + '.version_id', 50)
        self._validate_string(
            version['version_name'],
            name + '.version_name',
            100,
        )
        self._validate_status(version['status'], name + '.status')
        self._validate_bool(version['verified'], name + '.verified')
        self._parse_date(
            version['effective_date'],
            name + '.effective_date',
        )
        self._validate_string(version['source'], name + '.source', 200)
        self._validate_string(version['reviewer'], name + '.reviewer', 50)
        self._validate_list(version['rules'], name + '.rules')
        if not version['rules']:
            raise ValueError(name + '.rules不能为空')
        for index, rule in enumerate(version['rules']):
            self._validate_rule(rule, name + '.rules[' + str(index) + ']')
        self._validate_unique_rule_keys(version['rules'], name)

    def _validate_status(self, status, name):
        self._validate_string(status, name, 20)
        if status not in self.VERSION_STATUSES:
            raise ValueError(name + '不是允许的版本状态')

    def _validate_rule(self, rule, name):
        self._validate_mapping(rule, name)
        self._validate_required(rule, self.RULE_FIELDS, name)
        self._validate_food_code(rule['food_code'], name + '.food_code')
        self._validate_string(
            rule['additive_name'],
            name + '.additive_name',
            100,
        )
        self._validate_string(rule['condition'], name + '.condition', 300)
        self._validate_limit_type(rule['limit_type'], name + '.limit_type')
        self._validate_number(
            rule['limit_value'],
            name + '.limit_value',
            allow_none=True,
        )
        self._validate_unit(rule['unit'], name + '.unit')
        self._parse_date(rule['effective_date'], name + '.effective_date')
        self._validate_string(rule['source'], name + '.source', 200)
        self._validate_string(rule['reviewer'], name + '.reviewer', 50)
        self._validate_bool(rule['verified'], name + '.verified')
        self._validate_limit_combination(rule, name)

    def _validate_food_code(self, value, name):
        self._validate_string(value, name, 40)
        if not self.CODE_RE.fullmatch(value.strip()):
            raise ValueError(name + '格式非法')

    def _validate_limit_type(self, value, name):
        self._validate_string(value, name, 20)
        if value not in self.LIMIT_TYPES:
            raise ValueError(name + '不是允许的限量类型')

    def _validate_unit(self, value, name):
        self._validate_string(value, name, 20)
        normalized = self._normalize_unit(value)
        if normalized not in self.UNIT_DIMENSIONS:
            raise ValueError(name + '不是支持的计量单位')

    def _validate_limit_combination(self, rule, name):
        limit_type = rule['limit_type']
        value = rule['limit_value']
        unit = self._normalize_unit(rule['unit'])
        if limit_type in {'maximum', 'minimum'}:
            if value is None:
                raise ValueError(name + '的数值限量必须填写limit_value')
            if value <= 0:
                raise ValueError(name + '的数值限量必须大于零')
            if unit == 'none':
                raise ValueError(name + '的数值限量必须填写有效单位')
        if limit_type in {'prohibited', 'gmp'} and value is not None:
            raise ValueError(name + '的非数值限量不得填写limit_value')
        if limit_type in {'prohibited', 'gmp'} and unit != 'none':
            raise ValueError(name + '的非数值限量单位必须为none')

    def _validate_unique_rule_keys(self, rules, name):
        seen = set()
        for rule in rules:
            key = self._identity_key(rule)
            if key in seen:
                raise ValueError(name + '存在重复的规则身份键：' + self._key_text(key))
            seen.add(key)

    def _validate_version_relation(self, old_version, new_version):
        if old_version['version_id'] == new_version['version_id']:
            raise ValueError('两个比较版本的version_id不能相同')
        old_date = self._parse_date(
            old_version['effective_date'],
            'old_version.effective_date',
        )
        new_date = self._parse_date(
            new_version['effective_date'],
            'new_version.effective_date',
        )
        if new_date < old_date:
            raise ValueError('新版本生效日期不能早于旧版本')
        if not old_version['verified'] or not new_version['verified']:
            raise ValueError('只能比较已核验的规则版本')
        if old_version['rules'] is new_version['rules']:
            raise ValueError('不同版本不得共享同一个规则列表对象')

    def _validate_current_version(self, version):
        if version['status'] == 'effective' and not version['verified']:
            raise ValueError('未完成核验的版本不得设为当前有效版本')
        if version['status'] == 'effective':
            if not version['source'].strip():
                raise ValueError('当前有效版本必须记录来源')
            if not version['reviewer'].strip():
                raise ValueError('当前有效版本必须记录录入审核人')

    def _validate_status_history(self, version, name):
        if 'status_history' not in version:
            return
        history = version['status_history']
        self._validate_list(history, name + '.status_history')
        previous_date = None
        effective_seen = False
        for index, item in enumerate(history):
            item_name = name + '.status_history[' + str(index) + ']'
            self._validate_mapping(item, item_name)
            self._validate_required(
                item,
                ('status', 'date', 'operator'),
                item_name,
            )
            self._validate_status(item['status'], item_name + '.status')
            item_date = self._parse_date(item['date'], item_name + '.date')
            self._validate_string(
                item['operator'],
                item_name + '.operator',
                50,
            )
            if previous_date is not None and item_date < previous_date:
                raise ValueError(name + '.status_history必须按日期升序')
            previous_date = item_date
            if item['status'] == 'effective':
                effective_seen = True
        if version['status'] == 'inactive' and not effective_seen:
            raise ValueError('停用版本必须保留曾经有效的状态记录')
        if history and history[-1]['status'] != version['status']:
            raise ValueError(name + '当前状态与最后一条状态记录不一致')

    def _validate_history_reports(self, reports):
        self._validate_list(reports, 'history_reports')
        for index, report in enumerate(reports):
            name = 'history_reports[' + str(index) + ']'
            self._validate_history_report(report, name)

    def _validate_history_report(self, report, name):
        self._validate_mapping(report, name)
        self._validate_required(report, self.HISTORY_FIELDS, name)
        self._validate_string(report['batch_id'], name + '.batch_id', 80)
        self._validate_string(report['report_id'], name + '.report_id', 80)
        self._parse_date(report['report_date'], name + '.report_date')
        self._validate_food_code(report['food_code'], name + '.food_code')
        self._validate_string(
            report['additive_name'],
            name + '.additive_name',
            100,
        )
        self._validate_string(report['condition'], name + '.condition', 300)
        self._validate_number(
            report['measured_value'],
            name + '.measured_value',
        )
        self._validate_unit(report['unit'], name + '.unit')
        conclusion = report['original_conclusion']
        self._validate_string(conclusion, name + '.original_conclusion', 20)
        if conclusion not in self.CONCLUSIONS:
            raise ValueError(name + '.original_conclusion不是允许值')

    def _validate_unique_report_ids(self, reports):
        seen = set()
        for report in reports:
            report_id = report['report_id'].strip()
            if report_id in seen:
                raise ValueError('history_reports存在重复report_id：' + report_id)
            seen.add(report_id)

    def _validate_scope(self, scope):
        self._validate_mapping(scope, 'scope')
        self._validate_required(
            scope,
            ('date_from', 'date_to', 'food_codes', 'additives'),
            'scope',
        )
        date_from = self._parse_date(scope['date_from'], 'scope.date_from')
        date_to = self._parse_date(scope['date_to'], 'scope.date_to')
        if date_from > date_to:
            raise ValueError('scope.date_from不能晚于date_to')
        self._validate_string_list(
            scope['food_codes'],
            'scope.food_codes',
            code_mode=True,
        )
        self._validate_string_list(
            scope['additives'],
            'scope.additives',
            code_mode=False,
        )

    def _validate_string_list(self, values, name, code_mode):
        self._validate_list(values, name)
        normalized = set()
        for index, value in enumerate(values):
            item_name = name + '[' + str(index) + ']'
            if code_mode:
                self._validate_food_code(value, item_name)
                token = self._normalize_code(value)
            else:
                self._validate_string(value, item_name, 100)
                token = self._normalize_text(value)
            if token in normalized:
                raise ValueError(name + '包含规范化后重复项')
            normalized.add(token)

    def _normalize_text(self, value):
        value = unicodedata.normalize('NFKC', value)
        value = self.SPACE_RE.sub(' ', value.strip())
        return value.casefold()

    def _normalize_code(self, value):
        value = unicodedata.normalize('NFKC', value)
        return value.strip().upper()

    def _normalize_unit(self, value):
        value = unicodedata.normalize('NFKC', value)
        value = value.strip().lower().replace(' ', '')
        value = value.replace('mcg', 'ug')
        return value

    def _normalize_condition(self, value):
        value = self._normalize_text(value)
        replacements = {
            '；': ';',
            '，': ',',
            '。': '.',
            '（': '(',
            '）': ')',
        }
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value

    def _identity_key(self, rule):
        return (
            self._normalize_code(rule['food_code']),
            self._normalize_text(rule['additive_name']),
            self._normalize_condition(rule['condition']),
        )

    def _base_key(self, rule):
        return (
            self._normalize_code(rule['food_code']),
            self._normalize_text(rule['additive_name']),
        )

    def _history_identity_key(self, report):
        return (
            self._normalize_code(report['food_code']),
            self._normalize_text(report['additive_name']),
            self._normalize_condition(report['condition']),
        )

    def _history_base_key(self, report):
        return (
            self._normalize_code(report['food_code']),
            self._normalize_text(report['additive_name']),
        )

    def _key_text(self, key):
        return ' / '.join(key)

    def _rules_in_scope(self, rules, scope):
        code_filter = {
            self._normalize_code(value)
            for value in scope['food_codes']
        }
        additive_filter = {
            self._normalize_text(value)
            for value in scope['additives']
        }
        selected = []
        for rule in rules:
            code = self._normalize_code(rule['food_code'])
            additive = self._normalize_text(rule['additive_name'])
            if code_filter and code not in code_filter:
                continue
            if additive_filter and additive not in additive_filter:
                continue
            selected.append(rule)
        return selected

    def _history_in_scope(self, reports, scope):
        date_from = self._parse_date(scope['date_from'], 'scope.date_from')
        date_to = self._parse_date(scope['date_to'], 'scope.date_to')
        code_filter = {
            self._normalize_code(value)
            for value in scope['food_codes']
        }
        additive_filter = {
            self._normalize_text(value)
            for value in scope['additives']
        }
        selected = []
        for report in reports:
            report_date = self._parse_date(
                report['report_date'],
                'report_date',
            )
            code = self._normalize_code(report['food_code'])
            additive = self._normalize_text(report['additive_name'])
            if report_date < date_from or report_date > date_to:
                continue
            if code_filter and code not in code_filter:
                continue
            if additive_filter and additive not in additive_filter:
                continue
            selected.append(report)
        return selected

    def _build_rule_index(self, rules):
        return {self._identity_key(rule): rule for rule in rules}

    def _strict_set_difference(self, old_index, new_index):
        old_keys = set(old_index)
        new_keys = set(new_index)
        additions = [new_index[key] for key in new_keys - old_keys]
        deletions = [old_index[key] for key in old_keys - new_keys]
        return {
            'additions': additions,
            'deletions': deletions,
            'common_keys': old_keys & new_keys,
        }

    def _find_modifications(self, old_index, new_index):
        modifications = []
        common = sorted(set(old_index) & set(new_index))
        for key in common:
            old_rule = old_index[key]
            new_rule = new_index[key]
            fields = self._compare_rule_fields(old_rule, new_rule)
            if fields:
                modifications.append(
                    self._modification_record(old_rule, new_rule, fields)
                )
        return modifications

    def _reconcile_condition_changes(self, strict_changes):
        old_groups = defaultdict(list)
        new_groups = defaultdict(list)
        for rule in strict_changes['deletions']:
            old_groups[self._base_key(rule)].append(rule)
        for rule in strict_changes['additions']:
            new_groups[self._base_key(rule)].append(rule)
        modifications = []
        old_keys = set()
        new_keys = set()
        for base_key in sorted(set(old_groups) & set(new_groups)):
            old_rules = old_groups[base_key]
            new_rules = new_groups[base_key]
            pairs = self._pair_condition_candidates(old_rules, new_rules)
            for old_rule, new_rule in pairs:
                fields = self._compare_rule_fields(old_rule, new_rule)
                modifications.append(
                    self._modification_record(old_rule, new_rule, fields)
                )
                old_keys.add(self._identity_key(old_rule))
                new_keys.add(self._identity_key(new_rule))
        return {
            'modifications': modifications,
            'old_keys': old_keys,
            'new_keys': new_keys,
        }

    def _pair_condition_candidates(self, old_rules, new_rules):
        candidates = []
        for old_index, old_rule in enumerate(old_rules):
            for new_index, new_rule in enumerate(new_rules):
                distance = self._condition_distance(
                    old_rule['condition'],
                    new_rule['condition'],
                )
                candidates.append(
                    (distance, old_index, new_index, old_rule, new_rule)
                )
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        used_old = set()
        used_new = set()
        pairs = []
        for distance, old_index, new_index, old_rule, new_rule in candidates:
            if old_index in used_old or new_index in used_new:
                continue
            if distance > 0.75:
                continue
            used_old.add(old_index)
            used_new.add(new_index)
            pairs.append((old_rule, new_rule))
        return pairs

    def _condition_distance(self, left, right):
        left_tokens = self._condition_tokens(left)
        right_tokens = self._condition_tokens(right)
        union = left_tokens | right_tokens
        if not union:
            return 0.0
        intersection = left_tokens & right_tokens
        return 1.0 - len(intersection) / len(union)

    def _condition_tokens(self, value):
        normalized = self._normalize_condition(value)
        separators = ';,./()[]{}:：-'
        for separator in separators:
            normalized = normalized.replace(separator, ' ')
        tokens = set(normalized.split())
        if tokens:
            return tokens
        return {normalized}

    def _remove_reconciled(self, rules, reconciled_keys):
        return [
            rule
            for rule in rules
            if self._identity_key(rule) not in reconciled_keys
        ]

    def _compare_rule_fields(self, old_rule, new_rule):
        fields = []
        comparable = (
            'limit_type',
            'limit_value',
            'unit',
            'effective_date',
            'source',
            'condition',
            'reviewer',
            'verified',
        )
        for field in comparable:
            old_value = self._comparable_value(field, old_rule[field])
            new_value = self._comparable_value(field, new_rule[field])
            if old_value != new_value:
                fields.append(
                    {
                        'field': field,
                        'label': self.FIELD_LABELS[field],
                        'old': old_rule[field],
                        'new': new_rule[field],
                        'severity': self.SEVERITY_WEIGHTS[field],
                    }
                )
        return fields

    def _comparable_value(self, field, value):
        if field == 'unit':
            return self._normalize_unit(value)
        if field == 'condition':
            return self._normalize_condition(value)
        if field in {'source', 'reviewer'}:
            return self._normalize_text(value)
        if field == 'limit_value' and value is not None:
            return round(float(value), 12)
        return value

    def _modification_record(self, old_rule, new_rule, fields):
        return {
            'change_type': '修改',
            'old_rule': old_rule,
            'new_rule': new_rule,
            'fields': fields,
            'severity_score': sum(item['severity'] for item in fields),
        }

    def _deduplicate_modifications(self, modifications):
        unique = {}
        for item in modifications:
            pair = (
                self._identity_key(item['old_rule']),
                self._identity_key(item['new_rule']),
            )
            unique[pair] = item
        return list(unique.values())

    def _assemble_changes(self, additions, deletions, modifications):
        changes = []
        for rule in additions:
            changes.append(
                {
                    'change_type': '新增',
                    'old_rule': None,
                    'new_rule': rule,
                    'fields': self._all_new_fields(rule),
                    'severity_score': self._addition_severity(rule),
                }
            )
        for rule in deletions:
            changes.append(
                {
                    'change_type': '删除',
                    'old_rule': rule,
                    'new_rule': None,
                    'fields': self._all_deleted_fields(rule),
                    'severity_score': self._deletion_severity(rule),
                }
            )
        changes.extend(modifications)
        return sorted(changes, key=self._change_sort_key)

    def _all_new_fields(self, rule):
        return [
            {
                'field': 'rule',
                'label': '整条规则',
                'old': None,
                'new': self._rule_signature(rule),
                'severity': self._addition_severity(rule),
            }
        ]

    def _all_deleted_fields(self, rule):
        return [
            {
                'field': 'rule',
                'label': '整条规则',
                'old': self._rule_signature(rule),
                'new': None,
                'severity': self._deletion_severity(rule),
            }
        ]

    def _addition_severity(self, rule):
        if rule['limit_type'] == 'prohibited':
            return 8
        if rule['limit_type'] == 'maximum':
            return 6
        return 4

    def _deletion_severity(self, rule):
        if rule['limit_type'] in self.HIGH_RISK_TYPES:
            return 7
        return 5

    def _rule_signature(self, rule):
        value = self._format_limit(rule)
        return (
            rule['food_code']
            + '|'
            + rule['additive_name']
            + '|'
            + rule['condition']
            + '|'
            + value
        )

    def _format_limit(self, rule):
        label = self.LIMIT_TYPES[rule['limit_type']]
        if rule['limit_value'] is None:
            return label
        return label + ' ' + self._short_number(rule['limit_value']) + rule['unit']

    def _short_number(self, value):
        if isinstance(value, int):
            return str(value)
        text = format(float(value), '.12g')
        return text

    def _change_sort_key(self, change):
        rule = change['new_rule'] or change['old_rule']
        return (
            self.CHANGE_ORDER[change['change_type']],
            self._normalize_code(rule['food_code']),
            self._normalize_text(rule['additive_name']),
            self._normalize_condition(rule['condition']),
        )

    def _build_history_index(self, reports):
        strict = defaultdict(list)
        base = defaultdict(list)
        for report in reports:
            strict[self._history_identity_key(report)].append(report)
            base[self._history_base_key(report)].append(report)
        return {
            'strict': strict,
            'base': base,
        }

    def _find_affected_reports(self, changes, reverse_index):
        affected_by_report = {}
        for change in changes:
            candidates = self._candidate_reports(change, reverse_index)
            for report in candidates:
                if not self._report_after_change_start(report, change):
                    continue
                assessment = self._assess_report(change, report)
                report_id = report['report_id']
                current = affected_by_report.get(report_id)
                if current is None:
                    affected_by_report[report_id] = assessment
                    continue
                if assessment['priority_score'] > current['priority_score']:
                    affected_by_report[report_id] = assessment
        return list(affected_by_report.values())

    def _candidate_reports(self, change, reverse_index):
        old_rule = change['old_rule']
        new_rule = change['new_rule']
        strict_keys = set()
        base_keys = set()
        if old_rule is not None:
            strict_keys.add(self._identity_key(old_rule))
            base_keys.add(self._base_key(old_rule))
        if new_rule is not None:
            strict_keys.add(self._identity_key(new_rule))
            base_keys.add(self._base_key(new_rule))
        reports = {}
        for key in strict_keys:
            for report in reverse_index['strict'].get(key, []):
                reports[report['report_id']] = report
        condition_changed = self._field_changed(change, 'condition')
        if change['change_type'] == '新增' or condition_changed:
            for key in base_keys:
                for report in reverse_index['base'].get(key, []):
                    reports[report['report_id']] = report
        return list(reports.values())

    def _field_changed(self, change, field):
        return any(item['field'] == field for item in change['fields'])

    def _report_after_change_start(self, report, change):
        report_date = self._parse_date(report['report_date'], 'report_date')
        relevant_dates = []
        if change['old_rule'] is not None:
            relevant_dates.append(
                self._parse_date(
                    change['old_rule']['effective_date'],
                    'old effective_date',
                )
            )
        if change['new_rule'] is not None:
            relevant_dates.append(
                self._parse_date(
                    change['new_rule']['effective_date'],
                    'new effective_date',
                )
            )
        return report_date >= min(relevant_dates)

    def _assess_report(self, change, report):
        old_result = self._evaluate_against_rule(report, change['old_rule'])
        new_result = self._evaluate_against_rule(report, change['new_rule'])
        conclusion_flip = self._is_conclusion_flip(old_result, new_result)
        score = self._priority_score(
            change,
            report,
            old_result,
            new_result,
            conclusion_flip,
        )
        priority = self._priority_label(score)
        reason = self._priority_reason(
            change,
            old_result,
            new_result,
            conclusion_flip,
        )
        rule = change['new_rule'] or change['old_rule']
        return {
            '批次号': report['batch_id'],
            '报告编号': report['report_id'],
            '报告日期': report['report_date'],
            '食品分类代码': report['food_code'],
            '添加剂名称': report['additive_name'],
            '原报告结论': self.CONCLUSIONS[report['original_conclusion']],
            '旧规则复核结果': old_result,
            '新规则试算结果': new_result,
            '变更类型': change['change_type'],
            '规则身份键': self._key_text(self._identity_key(rule)),
            '重算优先级': priority,
            'priority_score': score,
            '优先级依据': reason,
            '仅列入待重算': '是',
        }

    def _evaluate_against_rule(self, report, rule):
        if rule is None:
            return '无对应规则，需人工确认'
        limit_type = rule['limit_type']
        if limit_type == 'gmp':
            return '无法仅凭数值判定，需工艺复核'
        if limit_type == 'prohibited':
            if report['measured_value'] > 0:
                return '不合格'
            return '合格'
        converted = self._convert_measurement(
            report['measured_value'],
            report['unit'],
            rule['unit'],
        )
        if converted is None:
            return '单位维度不一致，需人工确认'
        limit_value = float(rule['limit_value'])
        tolerance = max(1e-12, abs(limit_value) * 1e-12)
        if limit_type == 'maximum':
            return '合格' if converted <= limit_value + tolerance else '不合格'
        if limit_type == 'minimum':
            return '合格' if converted + tolerance >= limit_value else '不合格'
        return '需人工确认'

    def _convert_measurement(self, value, from_unit, to_unit):
        source = self._normalize_unit(from_unit)
        target = self._normalize_unit(to_unit)
        source_dimension = self.UNIT_DIMENSIONS[source]
        target_dimension = self.UNIT_DIMENSIONS[target]
        if source_dimension != target_dimension:
            return None
        base_value = float(value) * self.UNIT_FACTORS[source]
        converted = base_value / self.UNIT_FACTORS[target]
        if not math.isfinite(converted):
            return None
        return converted

    def _is_conclusion_flip(self, old_result, new_result):
        decisive = {'合格', '不合格'}
        return (
            old_result in decisive
            and new_result in decisive
            and old_result != new_result
        )

    def _priority_score(
        self,
        change,
        report,
        old_result,
        new_result,
        conclusion_flip,
    ):
        score = min(change['severity_score'], 10)
        if conclusion_flip:
            score += 8
        if new_result == '不合格':
            score += 5
        if old_result == '不合格' and new_result == '合格':
            score += 3
        if '人工确认' in new_result or '复核' in new_result:
            score += 2
        if change['change_type'] == '删除':
            score += 3
        if change['change_type'] == '新增':
            score += 2
        if report['original_conclusion'] == 'pass' and new_result == '不合格':
            score += 4
        return int(score)

    def _priority_label(self, score):
        if score >= 18:
            return '紧急'
        if score >= 12:
            return '高'
        if score >= 7:
            return '中'
        return '低'

    def _priority_reason(
        self,
        change,
        old_result,
        new_result,
        conclusion_flip,
    ):
        reasons = [change['change_type'] + '规则']
        if conclusion_flip:
            reasons.append('新旧试算结论相反')
        if new_result == '不合格':
            reasons.append('新规则试算为不合格')
        if change['change_type'] == '删除':
            reasons.append('原规则已删除')
        if change['change_type'] == '新增':
            reasons.append('历史报告可能漏用新规则')
        if '人工确认' in new_result or '复核' in new_result:
            reasons.append('存在自动判定盲区')
        return '；'.join(reasons)

    def _sort_affected(self, affected):
        return sorted(
            affected,
            key=lambda item: (
                self.PRIORITY_ORDER[item['重算优先级']],
                -item['priority_score'],
                item['报告日期'],
                item['报告编号'],
            ),
        )

    def _build_matrix_rows(self, changes):
        rows = []
        for change in changes:
            old_rule = change['old_rule']
            new_rule = change['new_rule']
            display_rule = new_rule or old_rule
            for field in change['fields']:
                rows.append(
                    {
                        '变更类型': change['change_type'],
                        '食品分类代码': display_rule['food_code'],
                        '添加剂名称': display_rule['additive_name'],
                        '适用条件': display_rule['condition'],
                        '比较字段': field['label'],
                        '旧值': self._display_value(field['old']),
                        '新值': self._display_value(field['new']),
                        '风险权重': field['severity'],
                    }
                )
        return rows

    def _display_value(self, value):
        if value is None:
            return '无'
        if type(value) is bool:
            return '是' if value else '否'
        if isinstance(value, float):
            return self._short_number(value)
        return str(value)

    def _unchanged_row(self, old_version, new_version):
        return {
            '变更类型': '无变化',
            '食品分类代码': '-',
            '添加剂名称': '-',
            '适用条件': '-',
            '比较字段': '全部规则字段',
            '旧值': old_version['version_name'],
            '新值': new_version['version_name'],
            '风险权重': 0,
        }

    def _build_metrics(
        self,
        old_rules,
        new_rules,
        changes,
        history,
        affected,
    ):
        additions = self._count_change(changes, '新增')
        deletions = self._count_change(changes, '删除')
        modifications = self._count_change(changes, '修改')
        field_changes = sum(len(item['fields']) for item in changes)
        urgent = sum(
            1 for item in affected if item['重算优先级'] == '紧急'
        )
        high = sum(1 for item in affected if item['重算优先级'] == '高')
        coverage = 0.0
        if history:
            coverage = len(affected) * 100.0 / len(history)
        return {
            '旧版范围内规则数': len(old_rules),
            '新版范围内规则数': len(new_rules),
            '新增规则数': additions,
            '删除规则数': deletions,
            '修改规则数': modifications,
            '字段差异数': field_changes,
            '范围内历史报告数': len(history),
            '潜在受影响报告数': len(affected),
            '影响覆盖率': self._short_number(coverage) + '%',
            '紧急待重算数': urgent,
            '高优先级待重算数': high,
        }

    def _count_change(self, changes, change_type):
        return sum(
            1
            for change in changes
            if change['change_type'] == change_type
        )

    def _build_series(self, changes, affected):
        values = [
            ('新增规则', self._count_change(changes, '新增')),
            ('删除规则', self._count_change(changes, '删除')),
            ('修改规则', self._count_change(changes, '修改')),
            ('潜在受影响报告', len(affected)),
        ]
        return [
            {
                'label': label,
                'value': float(value),
            }
            for label, value in values
        ]

    def _rule_list(self, rules, change_type):
        ordered = sorted(
            rules,
            key=lambda rule: (
                self._normalize_code(rule['food_code']),
                self._normalize_text(rule['additive_name']),
                self._normalize_condition(rule['condition']),
            ),
        )
        return [
            {
                '变更类型': change_type,
                '食品分类代码': rule['food_code'],
                '添加剂名称': rule['additive_name'],
                '适用条件': rule['condition'],
                '限量要求': self._format_limit(rule),
                '生效日期': rule['effective_date'],
                '来源': rule['source'],
                '审核人': rule['reviewer'],
            }
            for rule in ordered
        ]

    def _build_audit_records(
        self,
        old_version,
        new_version,
        changes,
        affected,
        confirmed,
    ):
        records = []
        records.append(
            {
                '步骤': '版本资格核验',
                '结论': '通过',
                '说明': '两个版本均已核验且版本编号不同',
            }
        )
        records.append(
            {
                '步骤': '规则身份键构造',
                '结论': '完成',
                '说明': '按食品分类代码、添加剂名称和适用条件规范化',
            }
        )
        records.append(
            {
                '步骤': '集合差分及字段比较',
                '结论': '完成',
                '说明': '识别变更' + str(len(changes)) + '项',
            }
        )
        records.append(
            {
                '步骤': '历史报告反向索引',
                '结论': '完成',
                '说明': '筛得潜在受影响报告' + str(len(affected)) + '份',
            }
        )
        records.append(
            {
                '步骤': '既有报告保护',
                '结论': '未改写',
                '说明': self._confirmation_text(confirmed),
            }
        )
        records.append(
            {
                '步骤': '版本链路',
                '结论': '已记录',
                '说明': (
                    old_version['version_id']
                    + ' -> '
                    + new_version['version_id']
                ),
            }
        )
        return records

    def _confirmation_text(self, confirmed):
        if confirmed:
            return '已记录管理员确认，但本模块仍只生成待重算清单'
        return '管理员未确认，只生成待重算清单'

    def _write_policy(self, confirmed):
        return {
            'administrator_confirmed': confirmed,
            'existing_reports_modified': False,
            'allowed_action': '生成待重算清单',
            'forbidden_action': '批量改写既有报告结论',
        }

    def _build_summary(
        self,
        old_version,
        new_version,
        changes,
        affected,
        confirmed,
    ):
        additions = self._count_change(changes, '新增')
        deletions = self._count_change(changes, '删除')
        modifications = self._count_change(changes, '修改')
        method = (
            '采用规范化规则身份键执行集合差分，并对同键规则逐字段比较；'
            '再按规则键和报告日期建立历史反向索引进行影响筛选。'
        )
        conclusion = (
            '版本'
            + old_version['version_id']
            + '与'
            + new_version['version_id']
            + '相比，新增'
            + str(additions)
            + '项、删除'
            + str(deletions)
            + '项、修改'
            + str(modifications)
            + '项，识别潜在受影响报告'
            + str(len(affected))
            + '份。'
        )
        protection = self._confirmation_text(confirmed) + '。'
        return conclusion + method + protection
