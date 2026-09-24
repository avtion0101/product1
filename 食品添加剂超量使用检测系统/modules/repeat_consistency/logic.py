import copy
import math
import statistics
from collections import Counter
from decimal import Decimal, InvalidOperation


class Engine:
    REQUIRED_FIELDS = (
        "sample_id",
        "additive_name",
        "unit",
        "method_id",
        "rsd_threshold_percent",
        "measurements",
    )
    OPTIONAL_FIELDS = (
        "robust_score_threshold",
        "value_min",
        "value_max",
        "decimal_places",
        "analyst",
        "instrument_id",
        "batch_id",
        "notes",
    )
    MEASUREMENT_REQUIRED_FIELDS = (
        "measurement_id",
        "value",
    )
    MEASUREMENT_OPTIONAL_FIELDS = (
        "replicate_order",
        "measured_at",
        "dilution_factor",
        "status_note",
    )
    MAX_MEASUREMENTS = 10000
    MAX_TEXT_LENGTH = 200
    MAX_NOTE_LENGTH = 1000
    DEFAULT_ROBUST_THRESHOLD = 3.5
    MAD_SCALE = 0.6745
    EPSILON = 1e-12

    def __init__(self):
        self._version = "1.0"

    def example(self):
        return {
            "sample_id": "SP-2026-001",
            "additive_name": "山梨酸",
            "unit": "g/kg",
            "method_id": "LAB-METHOD-SA-01",
            "rsd_threshold_percent": 5.0,
            "robust_score_threshold": 3.5,
            "value_min": 0.0,
            "value_max": 100.0,
            "decimal_places": 3,
            "analyst": "检验员甲",
            "instrument_id": "HPLC-03",
            "batch_id": "BATCH-20260923",
            "notes": "阈值已依据受控方法文件核验",
            "measurements": [
                {
                    "measurement_id": "R1",
                    "replicate_order": 1,
                    "value": 10.0,
                    "measured_at": "2026-09-23 09:00",
                    "dilution_factor": 1.0,
                    "status_note": "原始重复测定",
                },
                {
                    "measurement_id": "R2",
                    "replicate_order": 2,
                    "value": 10.2,
                    "measured_at": "2026-09-23 09:10",
                    "dilution_factor": 1.0,
                    "status_note": "原始重复测定",
                },
                {
                    "measurement_id": "R3",
                    "replicate_order": 3,
                    "value": 9.8,
                    "measured_at": "2026-09-23 09:20",
                    "dilution_factor": 1.0,
                    "status_note": "原始重复测定",
                },
                {
                    "measurement_id": "R4",
                    "replicate_order": 4,
                    "value": 10.1,
                    "measured_at": "2026-09-23 09:30",
                    "dilution_factor": 1.0,
                    "status_note": "原始重复测定",
                },
                {
                    "measurement_id": "R5",
                    "replicate_order": 5,
                    "value": 14.0,
                    "measured_at": "2026-09-23 09:40",
                    "dilution_factor": 1.0,
                    "status_note": "需结合原始记录复核",
                },
            ],
        }

    def validate(self, payload):
        self._validate_payload_type(payload)
        self._validate_top_level_fields(payload)
        self._validate_required_text_fields(payload)
        self._validate_optional_text_fields(payload)
        self._validate_threshold(payload)
        self._validate_robust_threshold(payload)
        self._validate_value_bounds(payload)
        self._validate_decimal_places(payload)
        self._validate_measurement_container(payload)
        self._validate_measurement_records(payload)
        self._validate_measurement_identifiers(payload)
        self._validate_replicate_orders(payload)
        self._validate_measurement_values(payload)
        self._validate_values_against_bounds(payload)
        self._validate_dilution_factors(payload)
        self._validate_measurement_timestamps(payload)
        return None

    def calculate(self, payload):
        self.validate(payload)
        working = copy.deepcopy(payload)
        records = self._ordered_records(working["measurements"])
        values = [self._as_float(record["value"]) for record in records]
        threshold = self._as_float(working["rsd_threshold_percent"])
        robust_threshold = self._get_robust_threshold(working)
        places = working.get("decimal_places", 6)
        overall = self._describe(values)
        robust = self._robust_analysis(values, robust_threshold)
        suspicious_indexes = robust["suspicious_indexes"]
        retained_indexes = [
            index
            for index in range(len(values))
            if index not in suspicious_indexes
        ]
        retained_values = [values[index] for index in retained_indexes]
        retained = self._describe(retained_values)
        overall_comparison = self._compare_rsd(overall, threshold)
        retained_comparison = self._compare_rsd(retained, threshold)
        status = self._determine_status(
            len(values),
            suspicious_indexes,
            overall_comparison,
        )
        rows = self._build_rows(
            records,
            values,
            overall,
            robust,
            threshold,
            places,
        )
        series = self._build_series(records, values, places)
        metrics = self._build_metrics(
            overall,
            retained,
            robust,
            threshold,
            robust_threshold,
            status,
            places,
        )
        summary = self._build_summary(
            working,
            overall,
            retained,
            robust,
            threshold,
            status,
            places,
        )
        pairwise = self._pairwise_analysis(records, values, places)
        sensitivity = self._leave_one_out_analysis(
            records,
            values,
            threshold,
            places,
        )
        distribution = self._distribution_analysis(values, places)
        review_items = self._build_review_items(
            records,
            robust,
            status,
        )
        return {
            "summary": summary,
            "metrics": metrics,
            "rows": rows,
            "series": series,
            "chart_title": self._chart_title(working),
            "pairwise_rows": pairwise,
            "sensitivity_rows": sensitivity,
            "distribution": distribution,
            "review_items": review_items,
            "method_explanation": self._method_explanation(),
            "limitations": self._limitations(),
            "decision_basis": self._decision_basis(
                overall_comparison,
                retained_comparison,
                suspicious_indexes,
            ),
            "input_echo": self._safe_input_echo(working),
        }

    def _validate_payload_type(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("输入必须是JSON对象")

    def _validate_top_level_fields(self, payload):
        allowed = set(self.REQUIRED_FIELDS)
        allowed.update(self.OPTIONAL_FIELDS)
        missing = [
            field
            for field in self.REQUIRED_FIELDS
            if field not in payload
        ]
        if missing:
            names = "、".join(missing)
            raise ValueError("缺少必填字段：" + names)
        unknown = sorted(set(payload) - allowed)
        if unknown:
            names = "、".join(unknown)
            raise ValueError("存在未知顶层字段：" + names)

    def _validate_required_text_fields(self, payload):
        fields = (
            ("sample_id", "样品编号"),
            ("additive_name", "添加剂名称"),
            ("unit", "单位"),
            ("method_id", "方法编号"),
        )
        for field, label in fields:
            self._validate_text(
                payload[field],
                label,
                self.MAX_TEXT_LENGTH,
                required=True,
            )

    def _validate_optional_text_fields(self, payload):
        fields = (
            ("analyst", "检验人员", self.MAX_TEXT_LENGTH),
            ("instrument_id", "仪器编号", self.MAX_TEXT_LENGTH),
            ("batch_id", "批次编号", self.MAX_TEXT_LENGTH),
            ("notes", "备注", self.MAX_NOTE_LENGTH),
        )
        for field, label, limit in fields:
            if field in payload:
                self._validate_text(
                    payload[field],
                    label,
                    limit,
                    required=False,
                )

    def _validate_text(self, value, label, limit, required):
        if not isinstance(value, str):
            raise ValueError(label + "必须是字符串")
        if required and not value.strip():
            raise ValueError(label + "不能为空")
        if not required and value != "" and not value.strip():
            raise ValueError(label + "不能仅含空白字符")
        if len(value) > limit:
            raise ValueError(label + "长度不能超过" + str(limit))
        if "\x00" in value:
            raise ValueError(label + "不能包含空字符")

    def _validate_threshold(self, payload):
        value = payload["rsd_threshold_percent"]
        self._require_number(value, "相对标准差阈值")
        number = self._as_float(value)
        if number <= 0.0:
            raise ValueError("相对标准差阈值必须大于0")
        if number > 1000.0:
            raise ValueError("相对标准差阈值不能大于1000%")

    def _validate_robust_threshold(self, payload):
        if "robust_score_threshold" not in payload:
            return
        value = payload["robust_score_threshold"]
        self._require_number(value, "稳健偏离分数阈值")
        number = self._as_float(value)
        if number < 2.0:
            raise ValueError("稳健偏离分数阈值不能小于2")
        if number > 10.0:
            raise ValueError("稳健偏离分数阈值不能大于10")

    def _validate_value_bounds(self, payload):
        lower_exists = "value_min" in payload
        upper_exists = "value_max" in payload
        if lower_exists:
            self._require_number(payload["value_min"], "测定值下限")
        if upper_exists:
            self._require_number(payload["value_max"], "测定值上限")
        if lower_exists and upper_exists:
            lower = self._as_float(payload["value_min"])
            upper = self._as_float(payload["value_max"])
            if lower >= upper:
                raise ValueError("测定值下限必须小于上限")

    def _validate_decimal_places(self, payload):
        if "decimal_places" not in payload:
            return
        value = payload["decimal_places"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("小数位数必须是整数")
        if value < 0 or value > 10:
            raise ValueError("小数位数必须在0至10之间")

    def _validate_measurement_container(self, payload):
        records = payload["measurements"]
        if not isinstance(records, list):
            raise ValueError("重复测定记录必须是数组")
        if len(records) == 0:
            raise ValueError("重复测定记录不能为空")
        if len(records) > self.MAX_MEASUREMENTS:
            raise ValueError("重复测定记录数量超过系统上限")

    def _validate_measurement_records(self, payload):
        allowed = set(self.MEASUREMENT_REQUIRED_FIELDS)
        allowed.update(self.MEASUREMENT_OPTIONAL_FIELDS)
        for index, record in enumerate(payload["measurements"]):
            position = index + 1
            if not isinstance(record, dict):
                raise ValueError(
                    "第" + str(position) + "条测定记录必须是对象"
                )
            missing = [
                field
                for field in self.MEASUREMENT_REQUIRED_FIELDS
                if field not in record
            ]
            if missing:
                raise ValueError(
                    "第"
                    + str(position)
                    + "条测定记录缺少字段："
                    + "、".join(missing)
                )
            unknown = sorted(set(record) - allowed)
            if unknown:
                raise ValueError(
                    "第"
                    + str(position)
                    + "条测定记录存在未知字段："
                    + "、".join(unknown)
                )
            self._validate_record_texts(record, position)

    def _validate_record_texts(self, record, position):
        prefix = "第" + str(position) + "条记录的"
        self._validate_text(
            record["measurement_id"],
            prefix + "测定编号",
            self.MAX_TEXT_LENGTH,
            required=True,
        )
        if "measured_at" in record:
            self._validate_text(
                record["measured_at"],
                prefix + "测定时间",
                self.MAX_TEXT_LENGTH,
                required=False,
            )
        if "status_note" in record:
            self._validate_text(
                record["status_note"],
                prefix + "状态说明",
                self.MAX_NOTE_LENGTH,
                required=False,
            )

    def _validate_measurement_identifiers(self, payload):
        identifiers = [
            record["measurement_id"].strip()
            for record in payload["measurements"]
        ]
        counts = Counter(identifiers)
        duplicates = sorted(
            identifier
            for identifier, count in counts.items()
            if count > 1
        )
        if duplicates:
            raise ValueError(
                "测定编号不能重复：" + "、".join(duplicates)
            )

    def _validate_replicate_orders(self, payload):
        orders = []
        for index, record in enumerate(payload["measurements"]):
            if "replicate_order" not in record:
                continue
            value = record["replicate_order"]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    "第"
                    + str(index + 1)
                    + "条记录的重复次序必须是整数"
                )
            if value <= 0:
                raise ValueError("重复次序必须是正整数")
            orders.append(value)
        if len(orders) != len(set(orders)):
            raise ValueError("重复次序不能重复")

    def _validate_measurement_values(self, payload):
        for index, record in enumerate(payload["measurements"]):
            label = "第" + str(index + 1) + "条记录的测定值"
            self._require_number(record["value"], label)

    def _validate_values_against_bounds(self, payload):
        lower = payload.get("value_min")
        upper = payload.get("value_max")
        lower_number = None if lower is None else self._as_float(lower)
        upper_number = None if upper is None else self._as_float(upper)
        for index, record in enumerate(payload["measurements"]):
            value = self._as_float(record["value"])
            if lower_number is not None and value < lower_number:
                raise ValueError(
                    "第"
                    + str(index + 1)
                    + "条测定值低于用户录入下限"
                )
            if upper_number is not None and value > upper_number:
                raise ValueError(
                    "第"
                    + str(index + 1)
                    + "条测定值高于用户录入上限"
                )

    def _validate_dilution_factors(self, payload):
        for index, record in enumerate(payload["measurements"]):
            if "dilution_factor" not in record:
                continue
            label = "第" + str(index + 1) + "条记录的稀释倍数"
            self._require_number(record["dilution_factor"], label)
            value = self._as_float(record["dilution_factor"])
            if value <= 0.0:
                raise ValueError(label + "必须大于0")
            if value > 1000000.0:
                raise ValueError(label + "超出合理录入范围")

    def _validate_measurement_timestamps(self, payload):
        for index, record in enumerate(payload["measurements"]):
            value = record.get("measured_at")
            if value is None or value == "":
                continue
            stripped = value.strip()
            if len(stripped) < 8:
                raise ValueError(
                    "第"
                    + str(index + 1)
                    + "条记录的测定时间格式信息不足"
                )

    def _require_number(self, value, label):
        if isinstance(value, bool):
            raise ValueError(label + "必须是有限数字")
        if not isinstance(value, (int, float, Decimal)):
            raise ValueError(label + "必须是有限数字")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError, InvalidOperation):
            raise ValueError(label + "必须是有限数字")
        if not math.isfinite(number):
            raise ValueError(label + "必须是有限数字")

    def _as_float(self, value):
        return float(value)

    def _ordered_records(self, records):
        copied = copy.deepcopy(records)
        indexed = list(enumerate(copied))
        indexed.sort(
            key=lambda pair: (
                pair[1].get("replicate_order", pair[0] + 1),
                pair[0],
            )
        )
        return [record for _, record in indexed]

    def _get_robust_threshold(self, payload):
        value = payload.get(
            "robust_score_threshold",
            self.DEFAULT_ROBUST_THRESHOLD,
        )
        return self._as_float(value)

    def _describe(self, values):
        count = len(values)
        if count == 0:
            return {
                "count": 0,
                "mean": None,
                "median": None,
                "minimum": None,
                "maximum": None,
                "range": None,
                "sample_standard_deviation": None,
                "rsd_percent": None,
                "sum": 0.0,
                "sum_squares": 0.0,
                "coefficient_available": False,
            }
        total = math.fsum(values)
        mean = total / count
        median = statistics.median(values)
        minimum = min(values)
        maximum = max(values)
        value_range = maximum - minimum
        sum_squares = math.fsum(value * value for value in values)
        sample_sd = self._sample_standard_deviation(values, mean)
        rsd = self._relative_standard_deviation(sample_sd, mean)
        return {
            "count": count,
            "mean": mean,
            "median": median,
            "minimum": minimum,
            "maximum": maximum,
            "range": value_range,
            "sample_standard_deviation": sample_sd,
            "rsd_percent": rsd,
            "sum": total,
            "sum_squares": sum_squares,
            "coefficient_available": rsd is not None,
        }

    def _sample_standard_deviation(self, values, mean):
        if len(values) < 2:
            return None
        squared = math.fsum(
            (value - mean) * (value - mean)
            for value in values
        )
        variance = squared / (len(values) - 1)
        if variance < 0.0 and abs(variance) <= self.EPSILON:
            variance = 0.0
        return math.sqrt(variance)

    def _relative_standard_deviation(self, sample_sd, mean):
        if sample_sd is None:
            return None
        if abs(mean) <= self.EPSILON:
            return None
        return abs(sample_sd / mean) * 100.0

    def _robust_analysis(self, values, threshold):
        count = len(values)
        median = statistics.median(values) if values else None
        if median is None:
            return {
                "available": False,
                "reason": "无有效测定值",
                "median": None,
                "mad": None,
                "scores": [],
                "suspicious_indexes": [],
            }
        deviations = [abs(value - median) for value in values]
        mad = statistics.median(deviations)
        if count < 4:
            return {
                "available": False,
                "reason": "测定次数少于4，未执行稳健异常识别",
                "median": median,
                "mad": mad,
                "scores": [None for _ in values],
                "suspicious_indexes": [],
            }
        if mad <= self.EPSILON:
            return self._zero_mad_analysis(values, median, threshold)
        scores = [
            self.MAD_SCALE * abs(value - median) / mad
            for value in values
        ]
        suspicious = [
            index
            for index, score in enumerate(scores)
            if score > threshold
        ]
        return {
            "available": True,
            "reason": "已按中位数绝对偏差计算稳健偏离分数",
            "median": median,
            "mad": mad,
            "scores": scores,
            "suspicious_indexes": suspicious,
        }

    def _zero_mad_analysis(self, values, median, threshold):
        different = [
            index
            for index, value in enumerate(values)
            if abs(value - median) > self.EPSILON
        ]
        scores = []
        for value in values:
            if abs(value - median) <= self.EPSILON:
                scores.append(0.0)
            else:
                scores.append(None)
        reason = (
            "中位数绝对偏差为0；不同于中位数的值标记为可疑，"
            "其稳健偏离分数记为不可有限计算"
        )
        return {
            "available": True,
            "reason": reason,
            "median": median,
            "mad": 0.0,
            "scores": scores,
            "suspicious_indexes": different,
            "threshold": threshold,
        }

    def _compare_rsd(self, stats, threshold):
        if stats["count"] < 2:
            return {
                "available": False,
                "within_threshold": None,
                "difference": None,
                "reason": "少于两次测定，不能评价重复性",
            }
        rsd = stats["rsd_percent"]
        if rsd is None:
            return {
                "available": False,
                "within_threshold": None,
                "difference": None,
                "reason": "均值为0或过于接近0，RSD无定义",
            }
        within = rsd <= threshold + self.EPSILON
        return {
            "available": True,
            "within_threshold": within,
            "difference": rsd - threshold,
            "reason": "RSD已与用户核验并录入的阈值比较",
        }

    def _determine_status(self, count, suspicious, comparison):
        if count < 2:
            return "资料不足，提交人工复核"
        if suspicious:
            return "存在可疑点，需人工复核"
        if not comparison["available"]:
            return "无法判定，提交人工复核"
        if comparison["within_threshold"]:
            return "重复测定一致"
        return "重复测定不一致，需人工复核"

    def _build_rows(
        self,
        records,
        values,
        overall,
        robust,
        threshold,
        places,
    ):
        rows = []
        suspicious = set(robust["suspicious_indexes"])
        for index, record in enumerate(records):
            value = values[index]
            deviation = value - overall["mean"]
            absolute_deviation = abs(deviation)
            score = robust["scores"][index]
            flag = index in suspicious
            row = {
                "测定序号": record.get("replicate_order", index + 1),
                "测定编号": record["measurement_id"],
                "测定值": self._round(value, places),
                "单位": "与输入单位一致",
                "与均值差": self._round(deviation, places),
                "绝对偏差": self._round(absolute_deviation, places),
                "稳健偏离分数": self._score_display(score, flag, places),
                "可疑点": "是" if flag else "否",
                "处置要求": self._disposition_text(flag),
                "阈值来源": "用户依据已核验方法文件录入",
                "重复性阈值(%)": self._round(threshold, places),
            }
            if "measured_at" in record:
                row["测定时间"] = record["measured_at"]
            if "dilution_factor" in record:
                row["稀释倍数"] = self._round(
                    self._as_float(record["dilution_factor"]),
                    places,
                )
            if "status_note" in record:
                row["原记录说明"] = record["status_note"]
            rows.append(row)
        return rows

    def _score_display(self, score, suspicious, places):
        if score is None and suspicious:
            return "MAD为0，分数不可有限计算"
        if score is None:
            return "样本量不足，未计算"
        return self._round(score, places)

    def _disposition_text(self, suspicious):
        if suspicious:
            return "仅标记；须记录保留、重测或排除理由"
        return "保留原始测定，不自动剔除"

    def _build_series(self, records, values, places):
        return [
            {
                "label": record["measurement_id"],
                "value": self._round(value, places),
            }
            for record, value in zip(records, values)
        ]

    def _build_metrics(
        self,
        overall,
        retained,
        robust,
        threshold,
        robust_threshold,
        status,
        places,
    ):
        suspicious_count = len(robust["suspicious_indexes"])
        metrics = {
            "有效测定次数": overall["count"],
            "平均值": self._optional_round(overall["mean"], places),
            "中位数": self._optional_round(overall["median"], places),
            "最小值": self._optional_round(overall["minimum"], places),
            "最大值": self._optional_round(overall["maximum"], places),
            "极差": self._optional_round(overall["range"], places),
            "样本标准差": self._metric_value(
                overall["sample_standard_deviation"],
                places,
                "测定次数不足",
            ),
            "相对标准差(%)": self._metric_value(
                overall["rsd_percent"],
                places,
                "均值为0或测定次数不足",
            ),
            "用户重复性阈值(%)": self._round(threshold, places),
            "稳健识别阈值": self._round(robust_threshold, places),
            "中位数绝对偏差": self._optional_round(
                robust["mad"],
                places,
            ),
            "可疑点数量": suspicious_count,
            "剔除可疑点后测定次数": retained["count"],
            "剔除可疑点后平均值": self._optional_round(
                retained["mean"],
                places,
            ),
            "剔除可疑点后样本标准差": self._metric_value(
                retained["sample_standard_deviation"],
                places,
                "剩余测定次数不足",
            ),
            "剔除可疑点后相对标准差(%)": self._metric_value(
                retained["rsd_percent"],
                places,
                "均值为0或剩余测定次数不足",
            ),
            "一致性状态": status,
            "异常点处理": "仅标记，未自动删除",
        }
        return metrics

    def _metric_value(self, value, places, unavailable):
        if value is None:
            return unavailable
        return self._round(value, places)

    def _optional_round(self, value, places):
        if value is None:
            return None
        return self._round(value, places)

    def _round(self, value, places):
        rounded = round(float(value), places)
        if rounded == 0.0:
            return 0.0
        return rounded

    def _build_summary(
        self,
        payload,
        overall,
        retained,
        robust,
        threshold,
        status,
        places,
    ):
        parts = [
            "样品"
            + payload["sample_id"]
            + "的"
            + payload["additive_name"]
            + "重复测定评价结果为："
            + status
            + "。"
        ]
        parts.append(
            "采用均值、中位数、极差、样本标准差和相对标准差描述离散程度。"
        )
        if overall["rsd_percent"] is None:
            parts.append(
                "当前相对标准差无法定义，因此不能据此声明重复测定一致。"
            )
        else:
            parts.append(
                "包含全部原始测定的RSD为"
                + self._format_number(overall["rsd_percent"], places)
                + "%；用户录入阈值为"
                + self._format_number(threshold, places)
                + "% 。"
            )
        if robust["available"]:
            parts.append(
                "样本量不少于4，已使用中位数绝对偏差构造稳健偏离分数。"
            )
        else:
            parts.append(robust["reason"] + "。")
        suspicious_count = len(robust["suspicious_indexes"])
        if suspicious_count:
            parts.append(
                "共标记"
                + str(suspicious_count)
                + "个可疑点；系统未删除任何原始记录。"
            )
            if retained["rsd_percent"] is not None:
                parts.append(
                    "仅作敏感性说明，不包含可疑点时RSD为"
                    + self._format_number(retained["rsd_percent"], places)
                    + "% 。"
                )
            parts.append(
                "复核人员必须记录保留、重测或排除的理由后再作业务处置。"
            )
        parts.append(
            "统计异常不等同于实验错误，结果不能替代实验室质量控制程序。"
        )
        return "".join(parts)

    def _format_number(self, value, places):
        return format(self._round(value, places), "." + str(places) + "f")

    def _pairwise_analysis(self, records, values, places):
        rows = []
        if len(values) < 2:
            return rows
        for left in range(len(values)):
            for right in range(left + 1, len(values)):
                difference = values[right] - values[left]
                absolute = abs(difference)
                average = (values[left] + values[right]) / 2.0
                relative = None
                if abs(average) > self.EPSILON:
                    relative = absolute / abs(average) * 100.0
                rows.append(
                    {
                        "测定一": records[left]["measurement_id"],
                        "测定二": records[right]["measurement_id"],
                        "差值": self._round(difference, places),
                        "绝对差": self._round(absolute, places),
                        "成对平均值": self._round(average, places),
                        "相对差(%)": self._metric_value(
                            relative,
                            places,
                            "成对平均值为0",
                        ),
                    }
                )
        return rows

    def _leave_one_out_analysis(
        self,
        records,
        values,
        threshold,
        places,
    ):
        rows = []
        if len(values) < 3:
            return rows
        full = self._describe(values)
        for index, record in enumerate(records):
            remaining = [
                value
                for position, value in enumerate(values)
                if position != index
            ]
            stats = self._describe(remaining)
            comparison = self._compare_rsd(stats, threshold)
            change = None
            if (
                full["rsd_percent"] is not None
                and stats["rsd_percent"] is not None
            ):
                change = stats["rsd_percent"] - full["rsd_percent"]
            rows.append(
                {
                    "假设不包含测定": record["measurement_id"],
                    "剩余次数": stats["count"],
                    "剩余平均值": self._optional_round(
                        stats["mean"],
                        places,
                    ),
                    "剩余RSD(%)": self._metric_value(
                        stats["rsd_percent"],
                        places,
                        "无法计算",
                    ),
                    "RSD变化百分点": self._metric_value(
                        change,
                        places,
                        "无法计算",
                    ),
                    "剩余结果是否符合阈值": self._comparison_text(
                        comparison
                    ),
                    "用途": "敏感性分析，不代表自动排除",
                }
            )
        return rows

    def _comparison_text(self, comparison):
        if not comparison["available"]:
            return "无法判定"
        if comparison["within_threshold"]:
            return "是"
        return "否"

    def _distribution_analysis(self, values, places):
        ordered = sorted(values)
        count = len(ordered)
        lower_half, upper_half = self._split_halves(ordered)
        first_quartile = self._median_or_none(lower_half)
        third_quartile = self._median_or_none(upper_half)
        interquartile = None
        if first_quartile is not None and third_quartile is not None:
            interquartile = third_quartile - first_quartile
        return {
            "排序值": [self._round(value, places) for value in ordered],
            "数量": count,
            "第一四分位数": self._optional_round(
                first_quartile,
                places,
            ),
            "第三四分位数": self._optional_round(
                third_quartile,
                places,
            ),
            "四分位距": self._optional_round(interquartile, places),
            "说明": "四分位统计仅辅助观察分布，不用于自动删除测定值",
        }

    def _split_halves(self, ordered):
        count = len(ordered)
        midpoint = count // 2
        if count < 2:
            return [], []
        if count % 2 == 0:
            return ordered[:midpoint], ordered[midpoint:]
        return ordered[:midpoint], ordered[midpoint + 1:]

    def _median_or_none(self, values):
        if not values:
            return None
        return statistics.median(values)

    def _build_review_items(self, records, robust, status):
        items = []
        suspicious = robust["suspicious_indexes"]
        if status == "资料不足，提交人工复核":
            items.append(
                {
                    "级别": "必须复核",
                    "事项": "有效测定少于两次",
                    "要求": "补充测定或由授权人员记录无法补测的理由",
                }
            )
        if suspicious:
            identifiers = [
                records[index]["measurement_id"]
                for index in suspicious
            ]
            items.append(
                {
                    "级别": "必须复核",
                    "事项": "存在稳健统计可疑点",
                    "涉及测定": "、".join(identifiers),
                    "要求": "核查原始谱图、配制、仪器和计算记录",
                }
            )
            items.append(
                {
                    "级别": "必须记录",
                    "事项": "可疑点处置决定",
                    "要求": "记录保留、重测或排除的决定及理由",
                }
            )
        if not robust["available"]:
            items.append(
                {
                    "级别": "提示",
                    "事项": "小样本异常识别能力有限",
                    "要求": "结合实验室质量控制记录进行专业判断",
                }
            )
        if not items:
            items.append(
                {
                    "级别": "常规",
                    "事项": "保存评价记录",
                    "要求": "连同原始数据和方法阈值依据一并归档",
                }
            )
        return items

    def _method_explanation(self):
        return (
            "对全部原始测定计算算术均值、中位数、极差、样本标准差"
            "及RSD。样本量不少于4时，计算0.6745乘以测定值与中位数"
            "之绝对差再除以MAD所得的稳健偏离分数。超过阈值的记录仅"
            "标记为可疑，并同时报告包含与不包含这些记录的描述统计。"
        )

    def _limitations(self):
        return (
            "小样本异常识别能力有限；MAD为0时不能得到有限的传统稳健"
            "偏离分数；均值为0时RSD无定义；统计异常不等于实验错误，"
            "本结果不能替代方法确认、仪器适用性和实验室质量控制程序。"
        )

    def _decision_basis(
        self,
        overall_comparison,
        retained_comparison,
        suspicious,
    ):
        return {
            "全部测定阈值比较": self._comparison_text(
                overall_comparison
            ),
            "不包含可疑点阈值比较": self._comparison_text(
                retained_comparison
            ),
            "可疑点数量": len(suspicious),
            "最终原则": "可疑点不自动删除，最终处置须由复核人员记录",
            "阈值声明": "RSD阈值来自用户已核验的方法文件录入",
        }

    def _safe_input_echo(self, payload):
        return {
            "样品编号": payload["sample_id"],
            "添加剂": payload["additive_name"],
            "单位": payload["unit"],
            "方法编号": payload["method_id"],
            "批次编号": payload.get("batch_id", "未提供"),
            "仪器编号": payload.get("instrument_id", "未提供"),
            "检验人员": payload.get("analyst", "未提供"),
            "记录数量": len(payload["measurements"]),
        }

    def _chart_title(self, payload):
        return (
            payload["sample_id"]
            + "-"
            + payload["additive_name"]
            + "重复测定值趋势"
        )
