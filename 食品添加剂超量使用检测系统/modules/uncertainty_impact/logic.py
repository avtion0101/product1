import copy
import math
from decimal import Decimal, InvalidOperation
from statistics import mean, median


class Engine:
    REQUIRED_RECORD_FIELDS = (
        "sample_id",
        "additive",
        "result",
        "limit",
        "unit",
    )
    UNCERTAINTY_TYPES = {
        "扩展不确定度",
        "标准不确定度",
        "未知",
    }
    UNCERTAINTY_FORMS = {
        "绝对",
        "相对",
        "未知",
    }
    STRONG_RISK = "较强超量风险"
    NOT_TRIGGERED = "未触发边界"
    OVERLAP = "边界重叠"
    INSUFFICIENT = "不确定度不足"

    def example(self):
        return {
            "records": [
                {
                    "sample_id": "SP-001",
                    "additive": "苯甲酸",
                    "result": 1.25,
                    "limit": 1.0,
                    "unit": "g/kg",
                    "uncertainty": 0.10,
                    "uncertainty_type": "扩展不确定度",
                    "uncertainty_form": "绝对",
                    "coverage_factor": 2.0,
                    "coverage_factor_source": "实验室评定报告 U-2026-01",
                },
                {
                    "sample_id": "SP-002",
                    "additive": "山梨酸",
                    "result": 0.92,
                    "limit": 1.0,
                    "unit": "g/kg",
                    "uncertainty": 8.0,
                    "uncertainty_type": "扩展不确定度",
                    "uncertainty_form": "相对",
                    "coverage_factor": 2.0,
                    "coverage_factor_source": "方法确认报告 M-17",
                },
                {
                    "sample_id": "SP-003",
                    "additive": "脱氢乙酸",
                    "result": 0.51,
                    "limit": 0.50,
                    "unit": "g/kg",
                    "uncertainty": 0.03,
                    "uncertainty_type": "标准不确定度",
                    "uncertainty_form": "绝对",
                    "coverage_factor": 2.0,
                    "coverage_factor_source": "校准证书 CAL-301",
                },
                {
                    "sample_id": "SP-004",
                    "additive": "糖精钠",
                    "result": 0.14,
                    "limit": 0.15,
                    "unit": "g/kg",
                    "uncertainty": 5.0,
                    "uncertainty_type": "标准不确定度",
                    "uncertainty_form": "相对",
                    "coverage_factor": 2.0,
                    "coverage_factor_source": "实验室年度评定 2026",
                },
                {
                    "sample_id": "SP-005",
                    "additive": "亚硝酸盐",
                    "result": 27.0,
                    "limit": 30.0,
                    "unit": "mg/kg",
                    "uncertainty": None,
                    "uncertainty_type": "未知",
                    "uncertainty_form": "未知",
                    "coverage_factor": None,
                    "coverage_factor_source": "",
                },
            ],
            "relative_uncertainty_unit": "%",
            "digits": 4,
        }

    def validate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("输入必须是JSON对象")
        allowed = {
            "records",
            "relative_uncertainty_unit",
            "digits",
        }
        self._reject_unknown_fields(payload, allowed, "顶层")
        if "records" not in payload:
            raise ValueError("缺少records字段")
        records = payload["records"]
        if not isinstance(records, list):
            raise ValueError("records必须是数组")
        if not records:
            raise ValueError("records不能为空")
        if len(records) > 10000:
            raise ValueError("单次记录数不得超过10000")
        relative_unit = payload.get(
            "relative_uncertainty_unit",
            "%",
        )
        if relative_unit not in ("%", "比例"):
            raise ValueError(
                "relative_uncertainty_unit只能是%或比例"
            )
        digits = payload.get("digits", 4)
        if isinstance(digits, bool) or not isinstance(digits, int):
            raise ValueError("digits必须是整数")
        if digits < 0 or digits > 8:
            raise ValueError("digits必须在0至8之间")
        seen_ids = set()
        for index, record in enumerate(records):
            self._validate_record(
                record,
                index,
                relative_unit,
                seen_ids,
            )
        return None

    def _reject_unknown_fields(self, data, allowed, location):
        unknown = sorted(set(data) - set(allowed))
        if unknown:
            joined = "、".join(unknown)
            raise ValueError(
                location + "存在未知字段：" + joined
            )

    def _validate_record(
        self,
        record,
        index,
        relative_unit,
        seen_ids,
    ):
        prefix = "第" + str(index + 1) + "条记录"
        if not isinstance(record, dict):
            raise ValueError(prefix + "必须是对象")
        allowed = {
            "sample_id",
            "additive",
            "result",
            "limit",
            "unit",
            "uncertainty",
            "uncertainty_type",
            "uncertainty_form",
            "coverage_factor",
            "coverage_factor_source",
            "lower_bound",
            "upper_bound",
            "interval_source",
        }
        self._reject_unknown_fields(record, allowed, prefix)
        for field in self.REQUIRED_RECORD_FIELDS:
            if field not in record:
                raise ValueError(prefix + "缺少" + field)
        sample_id = self._require_text(
            record["sample_id"],
            prefix + "的sample_id",
            100,
        )
        if sample_id in seen_ids:
            raise ValueError("sample_id不得重复：" + sample_id)
        seen_ids.add(sample_id)
        self._require_text(
            record["additive"],
            prefix + "的additive",
            100,
        )
        self._require_text(
            record["unit"],
            prefix + "的unit",
            30,
        )
        result = self._require_number(
            record["result"],
            prefix + "的result",
        )
        limit = self._require_number(
            record["limit"],
            prefix + "的limit",
        )
        if result < 0:
            raise ValueError(prefix + "的检测结果不得为负")
        if limit <= 0:
            raise ValueError(prefix + "的限量必须大于0")
        uncertainty = record.get("uncertainty")
        uncertainty_type = record.get(
            "uncertainty_type",
            "未知",
        )
        uncertainty_form = record.get(
            "uncertainty_form",
            "未知",
        )
        coverage_factor = record.get("coverage_factor")
        source = record.get("coverage_factor_source", "")
        lower = record.get("lower_bound")
        upper = record.get("upper_bound")
        interval_source = record.get("interval_source", "")
        self._validate_enum_or_missing(
            uncertainty_type,
            self.UNCERTAINTY_TYPES,
            prefix + "的不确定度类型",
        )
        self._validate_enum_or_missing(
            uncertainty_form,
            self.UNCERTAINTY_FORMS,
            prefix + "的不确定度形式",
        )
        self._validate_optional_text(
            source,
            prefix + "的包含因子来源",
            300,
        )
        self._validate_optional_text(
            interval_source,
            prefix + "的区间来源",
            300,
        )
        has_direct_interval = (
            lower is not None or upper is not None
        )
        if has_direct_interval:
            self._validate_direct_interval(
                prefix,
                result,
                lower,
                upper,
                interval_source,
                uncertainty,
            )
        if uncertainty is not None:
            uncertainty = self._require_number(
                uncertainty,
                prefix + "的uncertainty",
            )
            if uncertainty < 0:
                raise ValueError(prefix + "的不确定度不得为负")
        if coverage_factor is not None:
            coverage_factor = self._require_number(
                coverage_factor,
                prefix + "的coverage_factor",
            )
            if coverage_factor <= 0:
                raise ValueError(prefix + "的包含因子必须为正")
        self._validate_uncertainty_combination(
            prefix,
            uncertainty,
            uncertainty_type,
            uncertainty_form,
            coverage_factor,
            source,
            relative_unit,
            has_direct_interval,
        )

    def _validate_direct_interval(
        self,
        prefix,
        result,
        lower,
        upper,
        interval_source,
        uncertainty,
    ):
        if lower is None or upper is None:
            raise ValueError(prefix + "的人工区间必须同时给出上下界")
        lower_value = self._require_number(
            lower,
            prefix + "的lower_bound",
        )
        upper_value = self._require_number(
            upper,
            prefix + "的upper_bound",
        )
        if lower_value < 0:
            raise ValueError(prefix + "的区间下界不得为负")
        if upper_value < lower_value:
            raise ValueError(prefix + "的区间上界不得小于下界")
        if result < lower_value or result > upper_value:
            raise ValueError(prefix + "的中心结果必须位于人工区间内")
        if not isinstance(interval_source, str):
            raise ValueError(prefix + "的区间来源必须是字符串")
        if not interval_source.strip():
            raise ValueError(prefix + "的人工区间必须记录来源")
        if uncertainty is not None:
            raise ValueError(
                prefix + "不得同时提供人工区间和对称不确定度"
            )

    def _validate_uncertainty_combination(
        self,
        prefix,
        uncertainty,
        uncertainty_type,
        uncertainty_form,
        coverage_factor,
        source,
        relative_unit,
        has_direct_interval,
    ):
        if has_direct_interval:
            return
        known_type = uncertainty_type in (
            "扩展不确定度",
            "标准不确定度",
        )
        known_form = uncertainty_form in (
            "绝对",
            "相对",
        )
        if uncertainty is None:
            if known_type or known_form:
                raise ValueError(
                    prefix + "声明了不确定度类型或形式但未提供数值"
                )
            return
        if not known_type or not known_form:
            return
        if uncertainty_form == "相对":
            if relative_unit == "%" and uncertainty > 100:
                raise ValueError(prefix + "的相对不确定度百分比不得超过100")
            if relative_unit == "比例" and uncertainty > 1:
                raise ValueError(prefix + "的相对不确定度比例不得超过1")
        if uncertainty_type == "标准不确定度":
            if coverage_factor is None:
                raise ValueError(
                    prefix + "的标准不确定度缺少包含因子"
                )
            if not isinstance(source, str) or not source.strip():
                raise ValueError(
                    prefix + "的包含因子必须记录来源"
                )
        if uncertainty_type == "扩展不确定度":
            if coverage_factor is not None:
                if not isinstance(source, str) or not source.strip():
                    raise ValueError(
                        prefix + "记录包含因子时必须同时记录来源"
                    )

    def _validate_enum_or_missing(self, value, allowed, name):
        if value is None:
            return
        if not isinstance(value, str):
            raise ValueError(name + "必须是字符串")
        if value not in allowed:
            raise ValueError(name + "取值不受支持")

    def _validate_optional_text(self, value, name, maximum):
        if value is None:
            return
        if not isinstance(value, str):
            raise ValueError(name + "必须是字符串")
        if len(value) > maximum:
            raise ValueError(name + "长度超过限制")

    def _require_text(self, value, name, maximum):
        if not isinstance(value, str):
            raise ValueError(name + "必须是字符串")
        text = value.strip()
        if not text:
            raise ValueError(name + "不能为空")
        if len(text) > maximum:
            raise ValueError(name + "长度超过限制")
        return text

    def _require_number(self, value, name):
        if isinstance(value, bool):
            raise ValueError(name + "必须是有限数字")
        if not isinstance(value, (int, float, Decimal)):
            raise ValueError(name + "必须是有限数字")
        try:
            number = float(value)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(name + "必须是有限数字")
        if not math.isfinite(number):
            raise ValueError(name + "必须是有限数字")
        return number

    def calculate(self, payload):
        self.validate(payload)
        original = copy.deepcopy(payload)
        digits = payload.get("digits", 4)
        relative_unit = payload.get(
            "relative_uncertainty_unit",
            "%",
        )
        rows = []
        for record in payload["records"]:
            rows.append(
                self._calculate_record(
                    record,
                    relative_unit,
                    digits,
                )
            )
        if payload != original:
            raise RuntimeError("计算过程意外改变了输入")
        counts = self._count_statuses(rows)
        series = self._build_series(counts)
        metrics = self._build_metrics(rows, counts, digits)
        summary = self._build_summary(rows, counts)
        return {
            "summary": summary,
            "metrics": metrics,
            "rows": rows,
            "series": series,
            "chart_title": "测量不确定度边界影响分类",
            "method": {
                "interval_model": "对称区间近似",
                "comparison_rule": (
                    "下界高于限量为较强超量风险；"
                    "上界不高于限量为未触发边界；"
                    "其余为边界重叠"
                ),
                "relative_conversion": (
                    "绝对不确定度=检测结果×相对不确定度"
                ),
                "standard_conversion": (
                    "扩展不确定度=标准不确定度×包含因子"
                ),
                "limitation": (
                    "结果不替代实验室不确定度评定；"
                    "非对称分布应提供有来源的人工区间"
                ),
            },
        }

    def _calculate_record(
        self,
        record,
        relative_unit,
        digits,
    ):
        result = float(record["result"])
        limit = float(record["limit"])
        common = {
            "样品编号": record["sample_id"].strip(),
            "添加剂": record["additive"].strip(),
            "检测结果": self._round(result, digits),
            "限量": self._round(limit, digits),
            "单位": record["unit"].strip(),
            "中心值限量比": self._round(result / limit, digits),
        }
        if record.get("lower_bound") is not None:
            detail = self._from_direct_interval(
                record,
                result,
                limit,
                digits,
            )
        else:
            detail = self._from_uncertainty(
                record,
                result,
                limit,
                relative_unit,
                digits,
            )
        common.update(detail)
        return common

    def _from_direct_interval(
        self,
        record,
        result,
        limit,
        digits,
    ):
        lower = float(record["lower_bound"])
        upper = float(record["upper_bound"])
        status = self._classify(lower, upper, limit)
        margin = self._signed_margin(lower, upper, limit, status)
        return {
            "不确定度类型": "人工非对称区间",
            "不确定度形式": "直接区间",
            "录入不确定度": "不适用",
            "标准不确定度绝对值": "不适用",
            "扩展不确定度绝对值": "不适用",
            "包含因子": "不适用",
            "包含因子来源": "不适用",
            "区间来源": record["interval_source"].strip(),
            "区间下界": self._round(lower, digits),
            "区间上界": self._round(upper, digits),
            "下界限量比": self._round(lower / limit, digits),
            "上界限量比": self._round(upper / limit, digits),
            "区间宽度": self._round(upper - lower, digits),
            "交叠关系": status,
            "判定裕量": self._round(margin, digits),
            "复核建议": self._recommend(status, True),
            "换算说明": "采用有来源的人工非对称区间，未作对称换算",
        }

    def _from_uncertainty(
        self,
        record,
        result,
        limit,
        relative_unit,
        digits,
    ):
        uncertainty = record.get("uncertainty")
        uncertainty_type = record.get(
            "uncertainty_type",
            "未知",
        )
        uncertainty_form = record.get(
            "uncertainty_form",
            "未知",
        )
        if not self._is_complete_uncertainty(
            uncertainty,
            uncertainty_type,
            uncertainty_form,
        ):
            return self._insufficient_detail(
                record,
                result,
                limit,
                digits,
            )
        entered = float(uncertainty)
        absolute_entered = self._to_absolute(
            entered,
            uncertainty_form,
            relative_unit,
            result,
        )
        factor = self._effective_factor(record)
        if uncertainty_type == "标准不确定度":
            standard_absolute = absolute_entered
            expanded_absolute = absolute_entered * factor
            conversion = self._standard_conversion_text(
                uncertainty_form,
                relative_unit,
                entered,
                result,
                absolute_entered,
                factor,
                expanded_absolute,
                digits,
            )
        else:
            expanded_absolute = absolute_entered
            if factor is None:
                standard_absolute = None
            else:
                standard_absolute = absolute_entered / factor
            conversion = self._expanded_conversion_text(
                uncertainty_form,
                relative_unit,
                entered,
                result,
                expanded_absolute,
                factor,
                digits,
            )
        lower = max(0.0, result - expanded_absolute)
        upper = result + expanded_absolute
        status = self._classify(lower, upper, limit)
        margin = self._signed_margin(lower, upper, limit, status)
        return {
            "不确定度类型": uncertainty_type,
            "不确定度形式": uncertainty_form,
            "录入不确定度": self._round(entered, digits),
            "标准不确定度绝对值": self._optional_round(
                standard_absolute,
                digits,
            ),
            "扩展不确定度绝对值": self._round(
                expanded_absolute,
                digits,
            ),
            "包含因子": self._display_factor(factor),
            "包含因子来源": self._display_source(record),
            "区间来源": "对称不确定度换算",
            "区间下界": self._round(lower, digits),
            "区间上界": self._round(upper, digits),
            "下界限量比": self._round(lower / limit, digits),
            "上界限量比": self._round(upper / limit, digits),
            "区间宽度": self._round(upper - lower, digits),
            "交叠关系": status,
            "判定裕量": self._round(margin, digits),
            "复核建议": self._recommend(status, False),
            "换算说明": conversion,
        }

    def _is_complete_uncertainty(
        self,
        uncertainty,
        uncertainty_type,
        uncertainty_form,
    ):
        if uncertainty is None:
            return False
        if uncertainty_type not in (
            "扩展不确定度",
            "标准不确定度",
        ):
            return False
        if uncertainty_form not in ("绝对", "相对"):
            return False
        return True

    def _insufficient_detail(
        self,
        record,
        result,
        limit,
        digits,
    ):
        reasons = []
        if record.get("uncertainty") is None:
            reasons.append("未提供不确定度")
        uncertainty_type = record.get(
            "uncertainty_type",
            "未知",
        )
        uncertainty_form = record.get(
            "uncertainty_form",
            "未知",
        )
        if uncertainty_type not in (
            "扩展不确定度",
            "标准不确定度",
        ):
            reasons.append("不确定度类型不明")
        if uncertainty_form not in ("绝对", "相对"):
            reasons.append("不确定度形式不明")
        reason_text = "；".join(reasons)
        return {
            "不确定度类型": uncertainty_type,
            "不确定度形式": uncertainty_form,
            "录入不确定度": self._display_uncertainty(record),
            "标准不确定度绝对值": "无法计算",
            "扩展不确定度绝对值": "无法计算",
            "包含因子": self._display_factor(
                record.get("coverage_factor")
            ),
            "包含因子来源": self._display_source(record),
            "区间来源": "信息不足",
            "区间下界": "无法计算",
            "区间上界": "无法计算",
            "下界限量比": "无法计算",
            "上界限量比": "无法计算",
            "区间宽度": "无法计算",
            "交叠关系": self.INSUFFICIENT,
            "判定裕量": self._round(result - limit, digits),
            "复核建议": "待人工复核：" + reason_text,
            "换算说明": "未形成确定性边界判断",
        }

    def _to_absolute(
        self,
        entered,
        uncertainty_form,
        relative_unit,
        result,
    ):
        if uncertainty_form == "绝对":
            return entered
        if relative_unit == "%":
            ratio = entered / 100.0
        else:
            ratio = entered
        return result * ratio

    def _effective_factor(self, record):
        value = record.get("coverage_factor")
        if value is None:
            return None
        return float(value)

    def _standard_conversion_text(
        self,
        uncertainty_form,
        relative_unit,
        entered,
        result,
        absolute_entered,
        factor,
        expanded_absolute,
        digits,
    ):
        parts = []
        if uncertainty_form == "相对":
            parts.append(
                "相对标准不确定度"
                + self._format_number(entered, digits)
                + relative_unit
                + "按检测结果"
                + self._format_number(result, digits)
                + "换算为绝对标准不确定度"
                + self._format_number(absolute_entered, digits)
            )
        else:
            parts.append(
                "录入值作为绝对标准不确定度"
                + self._format_number(absolute_entered, digits)
            )
        parts.append(
            "乘以已核验包含因子"
            + self._format_number(factor, digits)
            + "得到扩展不确定度"
            + self._format_number(expanded_absolute, digits)
        )
        return "；".join(parts)

    def _expanded_conversion_text(
        self,
        uncertainty_form,
        relative_unit,
        entered,
        result,
        expanded_absolute,
        factor,
        digits,
    ):
        if uncertainty_form == "相对":
            text = (
                "相对扩展不确定度"
                + self._format_number(entered, digits)
                + relative_unit
                + "按检测结果"
                + self._format_number(result, digits)
                + "换算为绝对扩展不确定度"
                + self._format_number(expanded_absolute, digits)
            )
        else:
            text = (
                "录入值作为绝对扩展不确定度"
                + self._format_number(expanded_absolute, digits)
            )
        if factor is not None:
            text += (
                "；记录的包含因子为"
                + self._format_number(factor, digits)
            )
        else:
            text += "；未记录包含因子，不反推标准不确定度"
        return text

    def _classify(self, lower, upper, limit):
        tolerance = self._comparison_tolerance(
            lower,
            upper,
            limit,
        )
        if lower > limit + tolerance:
            return self.STRONG_RISK
        if upper <= limit + tolerance:
            return self.NOT_TRIGGERED
        return self.OVERLAP

    def _comparison_tolerance(self, *values):
        scale = max([1.0] + [abs(value) for value in values])
        return scale * 1e-12

    def _signed_margin(self, lower, upper, limit, status):
        if status == self.STRONG_RISK:
            return lower - limit
        if status == self.NOT_TRIGGERED:
            return limit - upper
        left = limit - lower
        right = upper - limit
        return -min(left, right)

    def _recommend(self, status, direct_interval):
        if status == self.STRONG_RISK:
            return "启动超量风险处置，并复核方法和不确定度资料"
        if status == self.NOT_TRIGGERED:
            return "未触发边界，保留不确定度换算和来源记录"
        if direct_interval:
            return "临界关注；按人工区间复核限量交叠及分布依据"
        return "临界关注并待人工复核，不得仅按中心值定性"

    def _display_uncertainty(self, record):
        value = record.get("uncertainty")
        if value is None:
            return "未提供"
        return float(value)

    def _display_factor(self, factor):
        if factor is None:
            return "未提供"
        return float(factor)

    def _display_source(self, record):
        source = record.get("coverage_factor_source", "")
        if not isinstance(source, str):
            return "未提供"
        text = source.strip()
        if not text:
            return "未提供"
        return text

    def _optional_round(self, value, digits):
        if value is None:
            return "无法反推"
        return self._round(value, digits)

    def _round(self, value, digits):
        rounded = round(float(value), digits)
        if rounded == 0:
            return 0.0
        return rounded

    def _format_number(self, value, digits):
        rounded = self._round(value, digits)
        return str(rounded)

    def _count_statuses(self, rows):
        counts = {
            self.STRONG_RISK: 0,
            self.OVERLAP: 0,
            self.NOT_TRIGGERED: 0,
            self.INSUFFICIENT: 0,
        }
        for row in rows:
            status = row["交叠关系"]
            counts[status] += 1
        return counts

    def _build_series(self, counts):
        order = (
            self.STRONG_RISK,
            self.OVERLAP,
            self.NOT_TRIGGERED,
            self.INSUFFICIENT,
        )
        return [
            {
                "label": status,
                "value": counts[status],
            }
            for status in order
        ]

    def _build_metrics(self, rows, counts, digits):
        ratios = [
            float(row["中心值限量比"])
            for row in rows
        ]
        available = [
            row
            for row in rows
            if isinstance(row["区间下界"], (int, float))
        ]
        overlap_or_risk = (
            counts[self.STRONG_RISK] + counts[self.OVERLAP]
        )
        review_count = overlap_or_risk + counts[self.INSUFFICIENT]
        metrics = {
            "记录总数": len(rows),
            "较强超量风险数": counts[self.STRONG_RISK],
            "边界重叠数": counts[self.OVERLAP],
            "未触发边界数": counts[self.NOT_TRIGGERED],
            "不确定度不足数": counts[self.INSUFFICIENT],
            "需复核记录数": review_count,
            "可计算区间率": self._round(
                len(available) / len(rows) * 100.0,
                digits,
            ),
            "平均中心值限量比": self._round(
                mean(ratios),
                digits,
            ),
            "中心值限量比中位数": self._round(
                median(ratios),
                digits,
            ),
            "最高中心值限量比": self._round(
                max(ratios),
                digits,
            ),
        }
        if available:
            widths = [
                float(row["区间宽度"])
                for row in available
            ]
            metrics["平均区间宽度"] = self._round(
                mean(widths),
                digits,
            )
        else:
            metrics["平均区间宽度"] = "无法计算"
        return metrics

    def _build_summary(self, rows, counts):
        total = len(rows)
        parts = [
            "采用对称扩展不确定度区间或有来源的人工区间，"
            "逐条比较区间端点与限量。",
            "共分析"
            + str(total)
            + "条记录：较强超量风险"
            + str(counts[self.STRONG_RISK])
            + "条，边界重叠"
            + str(counts[self.OVERLAP])
            + "条，未触发边界"
            + str(counts[self.NOT_TRIGGERED])
            + "条，不确定度不足"
            + str(counts[self.INSUFFICIENT])
            + "条。",
        ]
        if counts[self.OVERLAP]:
            parts.append(
                "区间跨越限量的记录已标记临界关注，"
                "不能仅按中心值给出确定结论。"
            )
        if counts[self.INSUFFICIENT]:
            parts.append(
                "信息不足的记录未生成确定性边界判断，"
                "需补充不确定度资料后人工复核。"
            )
        if counts[self.STRONG_RISK]:
            parts.append(
                "下界仍高于限量的记录具有较强超量风险，"
                "建议启动处置并复核检测链条。"
            )
        return "".join(parts)

    def decimal_ratio(self, numerator, denominator):
        try:
            left = Decimal(str(numerator))
            right = Decimal(str(denominator))
        except InvalidOperation:
            raise ValueError("比值参数无法转换为十进制数")
        if right == 0:
            raise ValueError("比值分母不得为零")
        value = left / right
        if not value.is_finite():
            raise ValueError("比值结果必须有限")
        return float(value)

    def explain_record(self, payload, sample_id):
        self.validate(payload)
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError("sample_id不能为空")
        result = self.calculate(payload)
        for row in result["rows"]:
            if row["样品编号"] == sample_id.strip():
                return {
                    "样品编号": row["样品编号"],
                    "结论": row["交叠关系"],
                    "依据": row["换算说明"],
                    "建议": row["复核建议"],
                }
        raise ValueError("未找到指定样品编号")

    def filter_review_rows(self, payload):
        result = self.calculate(payload)
        review_statuses = {
            self.STRONG_RISK,
            self.OVERLAP,
            self.INSUFFICIENT,
        }
        return [
            copy.deepcopy(row)
            for row in result["rows"]
            if row["交叠关系"] in review_statuses
        ]
