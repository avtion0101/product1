from collections import Counter
from decimal import Decimal, InvalidOperation


class Engine:
    BLOCK_LEVEL = '待人工复核'
    LEVELS = ('正常', '关注', '警告', '严重')
    CATEGORY_STATUSES = ('明确', '不明')
    RULE_STATUSES = ('已匹配', '缺失')
    UNIT_STATUSES = ('兼容', '不兼容')
    RELATIONS = (
        '不交叠',
        '交叠',
        '整体超限',
        '整体未超限',
        '不足',
    )
    REPEAT_STATUSES = (
        '正常',
        '临界',
        '异常',
        '未评价',
    )
    EVIDENCE_STATUSES = (
        '充分',
        '部分',
        '缺失',
    )
    RECORD_FIELDS = (
        'id',
        'category_status',
        'rule_status',
        'unit_status',
        'measured_value',
        'limit_value',
        'uncertainty',
        'uncertainty_relation',
        'repeat_status',
        'ingredient_evidence',
        'ingredient_path',
    )
    VERSION_FIELDS = (
        'version',
        'configured_by',
        'effective_date',
        'fictional',
        'fictional_notice',
        'levels',
        'thresholds',
    )
    LIMITATION = (
        '预警等级仅用于内部排序和辅助复核，'
        '不等同于监管风险等级，也不得直接触发处罚或召回。'
    )

    def example(self):
        return {
            'threshold_version': self._example_version(),
            'records': self._example_records(),
        }

    def _example_version(self):
        return {
            'version': 'DEMO-2026-01',
            'configured_by': '演示管理员',
            'effective_date': '2026-01-01',
            'fictional': True,
            'fictional_notice': '本阈值为虚构演示配置',
            'levels': list(self.LEVELS),
            'thresholds': [
                {
                    'min_ratio': 0.0,
                    'level': '正常',
                },
                {
                    'min_ratio': 0.9,
                    'level': '关注',
                },
                {
                    'min_ratio': 1.0,
                    'level': '警告',
                },
                {
                    'min_ratio': 1.5,
                    'level': '严重',
                },
            ],
        }

    def _example_records(self):
        return [
            self._make_record(
                'S-001',
                72.0,
                100.0,
                3.0,
                '整体未超限',
                '正常',
                '充分',
                ['成品', '防腐剂A'],
            ),
            self._make_record(
                'S-002',
                95.0,
                100.0,
                8.0,
                '交叠',
                '临界',
                '部分',
                ['成品', '复配料B', '添加剂C'],
            ),
            self._make_record(
                'S-003',
                112.0,
                100.0,
                4.0,
                '整体超限',
                '正常',
                '充分',
                ['成品', '着色剂D'],
            ),
            self._make_record(
                'S-004',
                143.0,
                100.0,
                6.0,
                '整体超限',
                '异常',
                '部分',
                ['成品', '复配料E', '甜味剂F'],
            ),
            self._make_record(
                'S-005',
                None,
                100.0,
                5.0,
                '不足',
                '未评价',
                '缺失',
                ['成品', '来源待查'],
                category='不明',
            ),
        ]

    def _make_record(
        self,
        record_id,
        measured,
        limit_value,
        uncertainty,
        relation,
        repeat_status,
        evidence,
        path,
        category='明确',
    ):
        return {
            'id': record_id,
            'category_status': category,
            'rule_status': '已匹配',
            'unit_status': '兼容',
            'measured_value': measured,
            'limit_value': limit_value,
            'uncertainty': uncertainty,
            'uncertainty_relation': relation,
            'repeat_status': repeat_status,
            'ingredient_evidence': evidence,
            'ingredient_path': path,
        }

    def validate(self, payload):
        self._require_dict(payload, '输入')
        self._require_exact_fields(
            payload,
            ('threshold_version', 'records'),
            '输入',
        )
        version = payload['threshold_version']
        records = payload['records']
        self._validate_version(version)
        self._validate_records(records, version)
        return None

    def _validate_version(self, version):
        self._require_dict(version, '阈值版本')
        self._require_exact_fields(
            version,
            self.VERSION_FIELDS,
            '阈值版本',
        )
        self._require_text(version['version'], '阈值版本号')
        self._check_text_length(
            version['version'],
            64,
            '阈值版本号',
        )
        self._require_text(
            version['configured_by'],
            '配置管理员',
        )
        self._check_text_length(
            version['configured_by'],
            80,
            '配置管理员',
        )
        self._validate_date(version['effective_date'])
        self._require_bool(version['fictional'], 'fictional')
        self._validate_notice(version)
        self._validate_levels(version['levels'])
        self._validate_thresholds(
            version['thresholds'],
            version['levels'],
        )

    def _validate_notice(self, version):
        notice = version['fictional_notice']
        self._require_text(notice, '阈值性质声明')
        self._check_text_length(notice, 200, '阈值性质声明')
        if version['fictional'] and '虚构' not in notice:
            raise ValueError('演示阈值必须明确标注为虚构')

    def _validate_date(self, value):
        self._require_text(value, '生效日期')
        parts = value.split('-')
        if len(parts) != 3:
            raise ValueError('生效日期必须采用YYYY-MM-DD格式')
        if [len(part) for part in parts] != [4, 2, 2]:
            raise ValueError('生效日期必须采用YYYY-MM-DD格式')
        if not all(part.isdigit() for part in parts):
            raise ValueError('生效日期必须采用YYYY-MM-DD格式')
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        if year < 2000 or year > 2100:
            raise ValueError('生效日期年份超出允许范围')
        if month < 1 or month > 12:
            raise ValueError('生效日期月份无效')
        maximum = self._days_in_month(year, month)
        if day < 1 or day > maximum:
            raise ValueError('生效日期日期无效')

    def _days_in_month(self, year, month):
        values = {
            1: 31,
            2: 28,
            3: 31,
            4: 30,
            5: 31,
            6: 30,
            7: 31,
            8: 31,
            9: 30,
            10: 31,
            11: 30,
            12: 31,
        }
        if month == 2 and self._is_leap_year(year):
            return 29
        return values[month]

    def _is_leap_year(self, year):
        if year % 400 == 0:
            return True
        if year % 100 == 0:
            return False
        return year % 4 == 0

    def _validate_levels(self, levels):
        self._require_list(levels, '等级名称')
        if len(levels) < 2:
            raise ValueError('至少需要配置两个预警等级')
        if len(levels) > 10:
            raise ValueError('预警等级不得超过十个')
        seen = set()
        for level in levels:
            self._require_text(level, '等级名称')
            self._check_text_length(level, 12, '等级名称')
            if level == self.BLOCK_LEVEL:
                raise ValueError('配置等级不得占用待人工复核')
            if level in seen:
                raise ValueError('等级名称不得重复')
            seen.add(level)

    def _validate_thresholds(self, thresholds, levels):
        self._require_list(thresholds, '阈值表')
        if len(thresholds) != len(levels):
            raise ValueError('每个等级必须且只能配置一个阈值')
        previous = None
        found_levels = []
        for index, item in enumerate(thresholds):
            label = '阈值表第%d项' % (index + 1)
            self._require_dict(item, label)
            self._require_exact_fields(
                item,
                ('min_ratio', 'level'),
                label,
            )
            self._require_number(item['min_ratio'], label + '比值')
            ratio = self._decimal(item['min_ratio'])
            if ratio < 0:
                raise ValueError(label + '比值不得为负数')
            if ratio > Decimal('1000'):
                raise ValueError(label + '比值超出合理范围')
            self._require_text(item['level'], label + '等级')
            if previous is not None and ratio <= previous:
                raise ValueError('超量比值阈值必须严格递增')
            previous = ratio
            found_levels.append(item['level'])
        if found_levels != levels:
            raise ValueError('阈值表等级顺序必须与等级配置一致')
        first = self._decimal(thresholds[0]['min_ratio'])
        if first != Decimal('0'):
            raise ValueError('最低等级阈值必须为0')
        last = self._decimal(thresholds[-1]['min_ratio'])
        if last <= 0:
            raise ValueError('最高等级阈值必须大于0')

    def _validate_records(self, records, version):
        self._require_list(records, '检测记录')
        if not records:
            raise ValueError('检测记录不能为空')
        if len(records) > 10000:
            raise ValueError('单次检测记录不得超过10000条')
        seen = set()
        for index, record in enumerate(records):
            self._validate_record(record, index, version)
            record_id = record['id']
            if record_id in seen:
                raise ValueError('检测记录id不得重复：' + record_id)
            seen.add(record_id)

    def _validate_record(self, record, index, version):
        label = '第%d条检测记录' % (index + 1)
        self._require_dict(record, label)
        self._require_exact_fields(
            record,
            self.RECORD_FIELDS,
            label,
        )
        self._require_text(record['id'], label + 'id')
        self._validate_id(record['id'], label)
        self._require_choice(
            record['category_status'],
            self.CATEGORY_STATUSES,
            label + '分类状态',
        )
        self._require_choice(
            record['rule_status'],
            self.RULE_STATUSES,
            label + '规则状态',
        )
        self._require_choice(
            record['unit_status'],
            self.UNIT_STATUSES,
            label + '单位状态',
        )
        self._validate_measurement(record, label)
        self._validate_uncertainty(record, label)
        self._require_choice(
            record['uncertainty_relation'],
            self.RELATIONS,
            label + '不确定度关系',
        )
        self._require_choice(
            record['repeat_status'],
            self.REPEAT_STATUSES,
            label + '重复测定评价',
        )
        self._require_choice(
            record['ingredient_evidence'],
            self.EVIDENCE_STATUSES,
            label + '配料来源证据',
        )
        self._validate_path(record['ingredient_path'], label)
        self._validate_relation(record, label)
        self._validate_ratio_range(record, version, label)

    def _validate_id(self, value, label):
        self._check_text_length(value, 64, label + 'id')
        if any(ord(char) < 32 for char in value):
            raise ValueError(label + 'id含控制字符')

    def _validate_measurement(self, record, label):
        measured = record['measured_value']
        limit_value = record['limit_value']
        if measured is not None:
            self._require_number(measured, label + '检测值')
            measured_decimal = self._decimal(measured)
            if measured_decimal < 0:
                raise ValueError(label + '检测值不得为负数')
            if measured_decimal > Decimal('1E15'):
                raise ValueError(label + '检测值超出合理范围')
        self._require_number(limit_value, label + '限量值')
        limit_decimal = self._decimal(limit_value)
        if limit_decimal <= 0:
            raise ValueError(label + '限量值必须大于0')
        if limit_decimal > Decimal('1E15'):
            raise ValueError(label + '限量值超出合理范围')

    def _validate_uncertainty(self, record, label):
        value = record['uncertainty']
        if value is None:
            return
        self._require_number(value, label + '扩展不确定度')
        decimal_value = self._decimal(value)
        if decimal_value < 0:
            raise ValueError(label + '扩展不确定度不得为负数')
        if decimal_value > Decimal('1E15'):
            raise ValueError(label + '扩展不确定度超出合理范围')
        measured = record['measured_value']
        if measured is not None:
            upper = self._decimal(measured) + decimal_value
            if upper > Decimal('1E16'):
                raise ValueError(label + '不确定度上界超出合理范围')

    def _validate_path(self, path, label):
        self._require_list(path, label + '配料路径')
        if not path:
            raise ValueError(label + '配料路径不能为空')
        if len(path) > 30:
            raise ValueError(label + '配料路径层级过多')
        previous = None
        for node in path:
            self._require_text(node, label + '配料路径节点')
            self._check_text_length(
                node,
                80,
                label + '配料路径节点',
            )
            if node == previous:
                raise ValueError(label + '配料路径不得连续重复')
            previous = node

    def _validate_relation(self, record, label):
        measured = record['measured_value']
        uncertainty = record['uncertainty']
        relation = record['uncertainty_relation']
        if measured is None or uncertainty is None:
            if relation != '不足':
                raise ValueError(label + '缺少数值时关系必须为不足')
            return
        if relation == '不足':
            raise ValueError(label + '数值完整时关系不得为不足')
        expected = self._derive_relation(record)
        accepted = {expected}
        if expected in ('整体超限', '整体未超限'):
            accepted.add('不交叠')
        if relation not in accepted:
            message = label + '不确定度关系与数值不一致，应为'
            raise ValueError(message + expected)

    def _derive_relation(self, record):
        measured = self._decimal(record['measured_value'])
        uncertainty = self._decimal(record['uncertainty'])
        limit_value = self._decimal(record['limit_value'])
        lower = max(Decimal('0'), measured - uncertainty)
        upper = measured + uncertainty
        if lower > limit_value:
            return '整体超限'
        if upper < limit_value:
            return '整体未超限'
        return '交叠'

    def _validate_ratio_range(self, record, version, label):
        if record['measured_value'] is None:
            return
        ratio = self._ratio(record)
        if ratio > Decimal('1000000'):
            raise ValueError(label + '超量比值超过系统处理上限')
        highest = self._decimal(
            version['thresholds'][-1]['min_ratio']
        )
        if highest <= 0:
            raise ValueError('最高等级阈值必须大于0')

    def _require_dict(self, value, label):
        if not isinstance(value, dict):
            raise ValueError(label + '必须是对象')

    def _require_list(self, value, label):
        if not isinstance(value, list):
            raise ValueError(label + '必须是数组')

    def _require_text(self, value, label):
        if not isinstance(value, str):
            raise ValueError(label + '必须是字符串')
        if not value.strip():
            raise ValueError(label + '不能为空')

    def _require_bool(self, value, label):
        if not isinstance(value, bool):
            raise ValueError(label + '必须是布尔值')

    def _require_number(self, value, label):
        if isinstance(value, bool):
            raise ValueError(label + '必须是有限数字')
        if not isinstance(value, (int, float, Decimal)):
            raise ValueError(label + '必须是有限数字')
        try:
            decimal_value = self._decimal(value)
        except (InvalidOperation, ValueError, OverflowError):
            raise ValueError(label + '必须是有限数字')
        if not decimal_value.is_finite():
            raise ValueError(label + '必须是有限数字')

    def _require_choice(self, value, choices, label):
        self._require_text(value, label)
        if value not in choices:
            allowed = '、'.join(choices)
            raise ValueError(label + '必须是：' + allowed)

    def _require_exact_fields(self, data, fields, label):
        for field in fields:
            if field not in data:
                raise ValueError(label + '缺少字段：' + field)
        unknown = sorted(set(data) - set(fields))
        if unknown:
            raise ValueError(
                label + '包含未知字段：' + '、'.join(unknown)
            )

    def _check_text_length(self, value, maximum, label):
        if len(value) > maximum:
            raise ValueError(label + '不得超过%d个字符' % maximum)

    def _decimal(self, value):
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def calculate(self, payload):
        self.validate(payload)
        version = payload['threshold_version']
        evaluations = []
        for index, record in enumerate(payload['records']):
            evaluation = self._evaluate(record, version, index)
            evaluations.append(evaluation)
        rows = [self._make_row(item) for item in evaluations]
        counts = self._count_levels(evaluations, version)
        return {
            'summary': self._summary(evaluations, version),
            'metrics': self._metrics(evaluations, version),
            'rows': rows,
            'series': self._series(counts, version),
            'chart_title': '初筛预警等级分布',
            'review_queue': self._review_queue(evaluations),
            'decision_hits': self._decision_hits(evaluations),
            'blocker_statistics': self._blocker_stats(evaluations),
            'aggravator_statistics': self._aggravator_stats(evaluations),
            'threshold_version': self._version_snapshot(version),
            'limitations': self.LIMITATION,
        }

    def _evaluate(self, record, version, index):
        blockers = self._blockers(record)
        ratio = self._safe_ratio(record)
        interval = self._interval(record)
        base_level = self._base_level(ratio, version)
        aggravators = self._aggravators(record, interval)
        final_level = self._final_level(
            base_level,
            aggravators,
            blockers,
            version,
        )
        decision = self._decision(ratio, version, blockers)
        return {
            'index': index,
            'id': record['id'],
            'ratio': ratio,
            'interval': interval,
            'base_level': base_level,
            'final_level': final_level,
            'severity': self._severity(final_level, version),
            'blockers': blockers,
            'aggravators': aggravators,
            'decision': decision,
            'path': list(record['ingredient_path']),
            'explanation': self._explanation(
                ratio,
                base_level,
                final_level,
                blockers,
                aggravators,
            ),
        }

    def _blockers(self, record):
        result = []
        if record['category_status'] == '不明':
            result.append('分类不明')
        if record['rule_status'] == '缺失':
            result.append('规则缺失')
        if record['unit_status'] == '不兼容':
            result.append('单位不兼容')
        if record['measured_value'] is None:
            result.append('检测值缺失')
        if record['uncertainty'] is None:
            result.append('不确定度缺失')
        if record['uncertainty_relation'] == '不足':
            result.append('不确定度不足')
        return result

    def _safe_ratio(self, record):
        if record['measured_value'] is None:
            return None
        return self._ratio(record)

    def _ratio(self, record):
        measured = self._decimal(record['measured_value'])
        limit_value = self._decimal(record['limit_value'])
        return measured / limit_value

    def _interval(self, record):
        measured = record['measured_value']
        uncertainty = record['uncertainty']
        if measured is None or uncertainty is None:
            return None
        measured_value = self._decimal(measured)
        uncertainty_value = self._decimal(uncertainty)
        limit_value = self._decimal(record['limit_value'])
        lower_value = max(
            Decimal('0'),
            measured_value - uncertainty_value,
        )
        upper_value = measured_value + uncertainty_value
        return {
            'lower_ratio': lower_value / limit_value,
            'upper_ratio': upper_value / limit_value,
            'relation': record['uncertainty_relation'],
        }

    def _base_level(self, ratio, version):
        if ratio is None:
            return self.BLOCK_LEVEL
        selected = version['thresholds'][0]['level']
        for threshold in version['thresholds']:
            boundary = self._decimal(threshold['min_ratio'])
            if ratio < boundary:
                break
            selected = threshold['level']
        return selected

    def _aggravators(self, record, interval):
        result = []
        if record['uncertainty_relation'] == '交叠':
            result.append({
                'name': '不确定度区间跨越限量',
                'steps': 1,
            })
        if record['repeat_status'] == '临界':
            result.append({
                'name': '重复测定临界',
                'steps': 1,
            })
        if record['repeat_status'] == '异常':
            result.append({
                'name': '重复测定异常',
                'steps': 2,
            })
        if record['repeat_status'] == '未评价':
            result.append({
                'name': '重复测定未评价',
                'steps': 1,
            })
        if record['ingredient_evidence'] == '部分':
            result.append({
                'name': '配料来源证据部分缺失',
                'steps': 1,
            })
        if record['ingredient_evidence'] == '缺失':
            result.append({
                'name': '配料来源证据缺失',
                'steps': 2,
            })
        if interval is not None:
            width = (
                interval['upper_ratio']
                - interval['lower_ratio']
            )
            if width >= Decimal('0.5'):
                result.append({
                    'name': '相对不确定度区间过宽',
                    'steps': 1,
                })
        return result

    def _final_level(
        self,
        base_level,
        aggravators,
        blockers,
        version,
    ):
        if blockers:
            return self.BLOCK_LEVEL
        levels = version['levels']
        base_index = levels.index(base_level)
        total_steps = sum(
            factor['steps']
            for factor in aggravators
        )
        final_index = min(
            base_index + total_steps,
            len(levels) - 1,
        )
        return levels[final_index]

    def _decision(self, ratio, version, blockers):
        if blockers:
            return {
                'table_row': 'B-阻断',
                'condition': '存在阻断条件',
                'result': self.BLOCK_LEVEL,
            }
        selected_index = 0
        thresholds = version['thresholds']
        for index, threshold in enumerate(thresholds):
            boundary = self._decimal(threshold['min_ratio'])
            if ratio < boundary:
                break
            selected_index = index
        current = thresholds[selected_index]
        upper = None
        if selected_index + 1 < len(thresholds):
            upper = thresholds[selected_index + 1]['min_ratio']
        return {
            'table_row': 'R-%02d' % (selected_index + 1),
            'condition': self._interval_text(
                current['min_ratio'],
                upper,
            ),
            'result': current['level'],
        }

    def _interval_text(self, lower, upper):
        lower_text = self._short_number(lower)
        if upper is None:
            return '比值大于等于' + lower_text
        upper_text = self._short_number(upper)
        return '比值大于等于%s且小于%s' % (
            lower_text,
            upper_text,
        )

    def _severity(self, level, version):
        if level == self.BLOCK_LEVEL:
            return len(version['levels']) + 1
        return version['levels'].index(level) + 1

    def _explanation(
        self,
        ratio,
        base_level,
        final_level,
        blockers,
        aggravators,
    ):
        if blockers:
            return '因%s，优先转入人工复核。' % '、'.join(blockers)
        text = '超量比值%s，决策表基础等级为%s。' % (
            self._format_ratio(ratio),
            base_level,
        )
        if aggravators:
            names = [item['name'] for item in aggravators]
            steps = sum(item['steps'] for item in aggravators)
            text += '命中加重因素%s，累计加重%d级。' % (
                '、'.join(names),
                steps,
            )
        if final_level == base_level:
            text += '无更高严重度结果，维持%s。' % final_level
        else:
            text += '按只升不降原则合成为%s。' % final_level
        return text

    def _make_row(self, item):
        interval = item['interval']
        if interval is None:
            lower = '不可计算'
            upper = '不可计算'
            relation = '不足'
        else:
            lower = self._format_ratio(interval['lower_ratio'])
            upper = self._format_ratio(interval['upper_ratio'])
            relation = interval['relation']
        return {
            '记录编号': item['id'],
            '超量比值': self._format_optional(item['ratio']),
            '不确定度下界比值': lower,
            '不确定度上界比值': upper,
            '不确定度关系': relation,
            '基础等级': item['base_level'],
            '最终等级': item['final_level'],
            '命中决策表行': item['decision']['table_row'],
            '决策条件': item['decision']['condition'],
            '加重因素': self._factor_text(item['aggravators']),
            '阻断因素': self._list_text(item['blockers']),
            '配料路径': ' > '.join(item['path']),
            '说明': item['explanation'],
        }

    def _factor_text(self, factors):
        if not factors:
            return '无'
        return '、'.join(item['name'] for item in factors)

    def _list_text(self, values):
        if not values:
            return '无'
        return '、'.join(values)

    def _count_levels(self, evaluations, version):
        counter = Counter(
            item['final_level']
            for item in evaluations
        )
        result = {}
        for level in version['levels']:
            result[level] = counter.get(level, 0)
        result[self.BLOCK_LEVEL] = counter.get(
            self.BLOCK_LEVEL,
            0,
        )
        return result

    def _series(self, counts, version):
        result = []
        for level in version['levels']:
            result.append({
                'label': level,
                'value': counts[level],
            })
        result.append({
            'label': self.BLOCK_LEVEL,
            'value': counts[self.BLOCK_LEVEL],
        })
        return result

    def _metrics(self, evaluations, version):
        ratios = [
            item['ratio']
            for item in evaluations
            if item['ratio'] is not None
        ]
        blocked = sum(
            item['final_level'] == self.BLOCK_LEVEL
            for item in evaluations
        )
        aggravated = sum(
            bool(item['aggravators'])
            for item in evaluations
        )
        above = sum(
            ratio > Decimal('1')
            for ratio in ratios
        )
        maximum = max(ratios) if ratios else None
        average = self._average(ratios)
        return {
            '记录总数': len(evaluations),
            '待人工复核数': blocked,
            '存在加重因素数': aggravated,
            '可计算比值数': len(ratios),
            '检测值高于限量数': above,
            '最大超量比值': self._format_optional(maximum),
            '平均超量比值': self._format_optional(average),
            '最高处置等级': self._highest(evaluations, version),
            '阈值版本': version['version'],
            '阈值性质': self._version_nature(version),
        }

    def _average(self, values):
        if not values:
            return None
        total = sum(values, Decimal('0'))
        return total / Decimal(len(values))

    def _highest(self, evaluations, version):
        if any(item['blockers'] for item in evaluations):
            return self.BLOCK_LEVEL
        selected = max(
            evaluations,
            key=lambda item: item['severity'],
        )
        return selected['final_level']

    def _version_nature(self, version):
        if version['fictional']:
            return '虚构演示阈值'
        return '管理员正式配置'

    def _review_queue(self, evaluations):
        ordered = sorted(evaluations, key=self._queue_key)
        result = []
        for position, item in enumerate(ordered, 1):
            result.append({
                '顺序': position,
                '记录编号': item['id'],
                '等级': item['final_level'],
                '严重度分值': item['severity'],
                '复核重点': self._review_focus(item),
            })
        return result

    def _queue_key(self, item):
        blocker_priority = 1 if item['blockers'] else 0
        ratio = item['ratio']
        ratio_value = ratio if ratio is not None else Decimal('-1')
        return (
            -blocker_priority,
            -item['severity'],
            -sum(x['steps'] for x in item['aggravators']),
            -ratio_value,
            item['index'],
        )

    def _review_focus(self, item):
        if item['blockers']:
            return '补齐或纠正：' + '、'.join(item['blockers'])
        if item['aggravators']:
            names = [x['name'] for x in item['aggravators']]
            return '核查加重因素：' + '、'.join(names)
        if item['ratio'] > Decimal('1'):
            return '复核检测值、限量规则和不确定度'
        return '常规留档复核'

    def _decision_hits(self, evaluations):
        counter = Counter(
            item['decision']['table_row']
            for item in evaluations
        )
        return [
            {
                '决策表行': name,
                '命中数量': counter[name],
            }
            for name in sorted(counter)
        ]

    def _blocker_stats(self, evaluations):
        counter = Counter()
        for item in evaluations:
            counter.update(item['blockers'])
        return [
            {
                '阻断因素': name,
                '数量': counter[name],
            }
            for name in sorted(counter)
        ]

    def _aggravator_stats(self, evaluations):
        counter = Counter()
        for item in evaluations:
            counter.update(
                factor['name']
                for factor in item['aggravators']
            )
        return [
            {
                '加重因素': name,
                '数量': counter[name],
            }
            for name in sorted(counter)
        ]

    def _version_snapshot(self, version):
        decisions = []
        for item in version['thresholds']:
            decisions.append({
                '最低比值': self._short_number(item['min_ratio']),
                '等级': item['level'],
            })
        return {
            '版本号': version['version'],
            '配置管理员': version['configured_by'],
            '生效日期': version['effective_date'],
            '是否虚构': version['fictional'],
            '声明': version['fictional_notice'],
            '等级顺序': list(version['levels']),
            '决策阈值': decisions,
        }

    def _summary(self, evaluations, version):
        total = len(evaluations)
        blocked = sum(bool(item['blockers']) for item in evaluations)
        aggravated = sum(
            bool(item['aggravators'])
            for item in evaluations
        )
        highest = self._highest(evaluations, version)
        nature = self._version_nature(version)
        conclusion = (
            '共评估%d条，%d条待人工复核，%d条存在加重因素，'
            '最高处置等级为%s。'
        ) % (
            total,
            blocked,
            aggravated,
            highest,
        )
        version_text = '采用%s%s（%s）。' % (
            nature,
            version['version'],
            version['fictional_notice'],
        )
        method = (
            '先检查分类、规则、单位、检测值和不确定度等阻断条件；'
            '无阻断时按超量比值决策表确定基础等级，再将不确定度交叠、'
            '重复测定异常及配料来源证据不足的加重级数累计，'
            '结果只升不降并受最高配置等级封顶。'
        )
        return conclusion + version_text + method + self.LIMITATION

    def _format_optional(self, value):
        if value is None:
            return '不可计算'
        return self._format_ratio(value)

    def _format_ratio(self, value):
        rounded = value.quantize(Decimal('0.0001'))
        return self._short_number(rounded)

    def _short_number(self, value):
        decimal_value = self._decimal(value)
        if decimal_value == decimal_value.to_integral():
            return str(decimal_value.to_integral())
        text = format(decimal_value.normalize(), 'f')
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
        return text
