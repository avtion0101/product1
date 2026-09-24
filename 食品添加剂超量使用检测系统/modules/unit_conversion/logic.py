import copy
import json
import math
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_DOWN
from decimal import ROUND_HALF_EVEN
from decimal import ROUND_HALF_UP
from decimal import ROUND_UP
from fractions import Fraction


class UnitSpec:
    def __init__(
        self,
        symbol,
        dimension,
        factor,
        chinese_name,
        numerator_dimension,
        denominator_dimension,
    ):
        self.symbol = symbol
        self.dimension = dimension
        self.factor = Fraction(factor)
        self.chinese_name = chinese_name
        self.numerator_dimension = numerator_dimension
        self.denominator_dimension = denominator_dimension

    def as_dict(self):
        return {
            "symbol": self.symbol,
            "dimension": self.dimension,
            "factor": self.factor,
            "chinese_name": self.chinese_name,
            "numerator_dimension": self.numerator_dimension,
            "denominator_dimension": self.denominator_dimension,
        }


def _build_units():
    units = {}
    units["ug"] = UnitSpec(
        "ug",
        "mass",
        Fraction(1, 1000000),
        "微克",
        "mass",
        "one",
    )
    units["mg"] = UnitSpec(
        "mg",
        "mass",
        Fraction(1, 1000),
        "毫克",
        "mass",
        "one",
    )
    units["g"] = UnitSpec(
        "g",
        "mass",
        Fraction(1, 1),
        "克",
        "mass",
        "one",
    )
    units["kg"] = UnitSpec(
        "kg",
        "mass",
        Fraction(1000, 1),
        "千克",
        "mass",
        "one",
    )
    units["uL"] = UnitSpec(
        "uL",
        "volume",
        Fraction(1, 1000000),
        "微升",
        "volume",
        "one",
    )
    units["mL"] = UnitSpec(
        "mL",
        "volume",
        Fraction(1, 1000),
        "毫升",
        "volume",
        "one",
    )
    units["L"] = UnitSpec(
        "L",
        "volume",
        Fraction(1, 1),
        "升",
        "volume",
        "one",
    )
    units["mg/kg"] = UnitSpec(
        "mg/kg",
        "mass_fraction",
        Fraction(1, 1000000),
        "毫克每千克",
        "mass",
        "mass",
    )
    units["g/kg"] = UnitSpec(
        "g/kg",
        "mass_fraction",
        Fraction(1, 1000),
        "克每千克",
        "mass",
        "mass",
    )
    units["ug/kg"] = UnitSpec(
        "ug/kg",
        "mass_fraction",
        Fraction(1, 1000000000),
        "微克每千克",
        "mass",
        "mass",
    )
    units["mg/g"] = UnitSpec(
        "mg/g",
        "mass_fraction",
        Fraction(1, 1000),
        "毫克每克",
        "mass",
        "mass",
    )
    units["ug/g"] = UnitSpec(
        "ug/g",
        "mass_fraction",
        Fraction(1, 1000000),
        "微克每克",
        "mass",
        "mass",
    )
    units["%"] = UnitSpec(
        "%",
        "mass_fraction",
        Fraction(1, 100),
        "质量百分数",
        "mass",
        "mass",
    )
    units["ppm"] = UnitSpec(
        "ppm",
        "mass_fraction",
        Fraction(1, 1000000),
        "百万分之一",
        "mass",
        "mass",
    )
    units["ppb"] = UnitSpec(
        "ppb",
        "mass_fraction",
        Fraction(1, 1000000000),
        "十亿分之一",
        "mass",
        "mass",
    )
    units["ug/L"] = UnitSpec(
        "ug/L",
        "mass_concentration",
        Fraction(1, 1000000),
        "微克每升",
        "mass",
        "volume",
    )
    units["mg/L"] = UnitSpec(
        "mg/L",
        "mass_concentration",
        Fraction(1, 1000),
        "毫克每升",
        "mass",
        "volume",
    )
    units["g/L"] = UnitSpec(
        "g/L",
        "mass_concentration",
        Fraction(1, 1),
        "克每升",
        "mass",
        "volume",
    )
    units["ug/mL"] = UnitSpec(
        "ug/mL",
        "mass_concentration",
        Fraction(1, 1000),
        "微克每毫升",
        "mass",
        "volume",
    )
    units["mg/mL"] = UnitSpec(
        "mg/mL",
        "mass_concentration",
        Fraction(1, 1),
        "毫克每毫升",
        "mass",
        "volume",
    )
    units["g/mL"] = UnitSpec(
        "g/mL",
        "mass_concentration",
        Fraction(1000, 1),
        "克每毫升",
        "mass",
        "volume",
    )
    return units


def _build_aliases():
    return {
        "μg": "ug",
        "µg": "ug",
        "微克": "ug",
        "毫克": "mg",
        "克": "g",
        "千克": "kg",
        "公斤": "kg",
        "μL": "uL",
        "µL": "uL",
        "微升": "uL",
        "ml": "mL",
        "毫升": "mL",
        "l": "L",
        "升": "L",
        "公升": "L",
        "mg／kg": "mg/kg",
        "毫克/千克": "mg/kg",
        "毫克每千克": "mg/kg",
        "g／kg": "g/kg",
        "克/千克": "g/kg",
        "克每千克": "g/kg",
        "μg/kg": "ug/kg",
        "µg/kg": "ug/kg",
        "微克/千克": "ug/kg",
        "微克每千克": "ug/kg",
        "mg／g": "mg/g",
        "毫克/克": "mg/g",
        "毫克每克": "mg/g",
        "μg/g": "ug/g",
        "µg/g": "ug/g",
        "微克/克": "ug/g",
        "微克每克": "ug/g",
        "％": "%",
        "质量百分数": "%",
        "百万分之一": "ppm",
        "十亿分之一": "ppb",
        "μg/L": "ug/L",
        "µg/L": "ug/L",
        "ug/l": "ug/L",
        "微克/升": "ug/L",
        "微克每升": "ug/L",
        "mg/l": "mg/L",
        "毫克/升": "mg/L",
        "毫克每升": "mg/L",
        "g/l": "g/L",
        "克/升": "g/L",
        "克每升": "g/L",
        "μg/mL": "ug/mL",
        "µg/mL": "ug/mL",
        "微克/毫升": "ug/mL",
        "微克每毫升": "ug/mL",
        "mg/ml": "mg/mL",
        "毫克/毫升": "mg/mL",
        "毫克每毫升": "mg/mL",
        "g/ml": "g/mL",
        "克/毫升": "g/mL",
        "克每毫升": "g/mL",
    }


class Engine:
    UNITS = _build_units()
    ALIASES = _build_aliases()
    ROUNDINGS = {
        "HALF_UP": ROUND_HALF_UP,
        "HALF_EVEN": ROUND_HALF_EVEN,
        "DOWN": ROUND_DOWN,
        "UP": ROUND_UP,
    }
    DIMENSION_NAMES = {
        "mass": "质量",
        "volume": "体积",
        "mass_fraction": "质量分数",
        "mass_concentration": "质量浓度",
    }
    MAX_RECORDS = 500
    MAX_ABS_VALUE = Decimal("1E30")

    def __init__(self):
        self.units = dict(self.UNITS)
        self.aliases = dict(self.ALIASES)

    def example(self):
        return {
            "records": [
                {
                    "id": "样品-苯甲酸-01",
                    "value": "0.125",
                    "source_unit": "g/kg",
                    "target_unit": "mg/kg",
                    "significant_digits": 4,
                    "rounding": "HALF_UP",
                },
                {
                    "id": "饮料-山梨酸-02",
                    "value": "850",
                    "source_unit": "mg/L",
                    "target_unit": "g/L",
                    "significant_digits": 3,
                    "rounding": "HALF_EVEN",
                },
                {
                    "id": "酱料-脱氢乙酸-03",
                    "value": "420",
                    "source_unit": "mg/kg",
                    "target_unit": "mg/L",
                    "density_g_ml": "1.08",
                    "density_confirmed": True,
                    "significant_digits": 3,
                    "rounding": "HALF_UP",
                },
                {
                    "id": "浸提液-糖精钠-04",
                    "value": "2.50",
                    "source_unit": "mg/L",
                    "target_unit": "mg",
                    "volume_ml": "200",
                    "significant_digits": 3,
                    "rounding": "HALF_UP",
                },
                {
                    "id": "糕点-铝残留-05",
                    "value": "0.0300",
                    "source_unit": "%",
                    "target_unit": "mg",
                    "sample_mass_g": "250",
                    "significant_digits": 3,
                    "rounding": "HALF_UP",
                },
            ],
            "default_significant_digits": 4,
            "default_rounding": "HALF_UP",
        }

    def validate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("输入必须是对象")
        allowed = {
            "records",
            "default_significant_digits",
            "default_rounding",
        }
        self._reject_unknown_fields(payload, allowed, "输入")
        if "records" not in payload:
            raise ValueError("缺少records字段")
        records = payload["records"]
        if not isinstance(records, list):
            raise ValueError("records必须是数组")
        if not records:
            raise ValueError("records不能为空")
        if len(records) > self.MAX_RECORDS:
            raise ValueError("records最多允许500条")
        default_digits = payload.get("default_significant_digits", 6)
        self._validate_digits(default_digits, "default_significant_digits")
        default_rounding = payload.get("default_rounding", "HALF_UP")
        self._validate_rounding(default_rounding, "default_rounding")
        identifiers = set()
        for index, record in enumerate(records):
            self._validate_record(record, index, identifiers)
        return None

    def calculate(self, payload):
        self.validate(payload)
        snapshot = copy.deepcopy(payload)
        default_digits = payload.get("default_significant_digits", 6)
        default_rounding = payload.get("default_rounding", "HALF_UP")
        rows = []
        series = []
        converted_count = 0
        review_count = 0
        exact_count = 0
        for index, record in enumerate(payload["records"]):
            row = self._calculate_record(
                record,
                index,
                default_digits,
                default_rounding,
            )
            rows.append(row)
            if row["处理状态"] == "换算成功":
                converted_count += 1
                if row["是否直接同量纲"] == "是":
                    exact_count += 1
                series_value = self._series_number(row["舍入值"])
            else:
                review_count += 1
                series_value = 0.0
            series.append(
                {
                    "label": row["记录标识"],
                    "value": series_value,
                }
            )
        if payload != snapshot:
            raise RuntimeError("内部错误：计算改变了输入")
        result = {
            "summary": self._build_summary(
                len(rows),
                converted_count,
                review_count,
                exact_count,
            ),
            "metrics": {
                "记录总数": len(rows),
                "换算成功数": converted_count,
                "待人工复核数": review_count,
                "直接同量纲换算数": exact_count,
                "成功率": self._percentage(converted_count, len(rows)),
                "计算方法": "有理数因子与十进制有效数字舍入",
            },
            "rows": rows,
            "series": series,
            "chart_title": "检测单位换算结果",
            "unit_basis": self._unit_basis(),
        }
        json.dumps(result, ensure_ascii=False, allow_nan=False)
        return result

    def _validate_record(self, record, index, identifiers):
        location = "records[{}]".format(index)
        if not isinstance(record, dict):
            raise ValueError("{}必须是对象".format(location))
        allowed = {
            "id",
            "value",
            "source_unit",
            "target_unit",
            "sample_mass_g",
            "volume_ml",
            "density_g_ml",
            "density_confirmed",
            "significant_digits",
            "rounding",
            "note",
        }
        self._reject_unknown_fields(record, allowed, location)
        required = ("id", "value", "source_unit", "target_unit")
        for field in required:
            if field not in record:
                raise ValueError("{}缺少{}字段".format(location, field))
        identifier = self._validate_text(record["id"], location + ".id", 80)
        if identifier in identifiers:
            raise ValueError("记录标识重复：{}".format(identifier))
        identifiers.add(identifier)
        value = self._to_decimal(record["value"], location + ".value")
        if value < 0:
            raise ValueError("{}.value不得为负数".format(location))
        if abs(value) > self.MAX_ABS_VALUE:
            raise ValueError("{}.value绝对值过大".format(location))
        self._validate_unit_text(record["source_unit"], location + ".source_unit")
        self._validate_unit_text(record["target_unit"], location + ".target_unit")
        self._validate_context_number(record, "sample_mass_g", location)
        self._validate_context_number(record, "volume_ml", location)
        self._validate_context_number(record, "density_g_ml", location)
        self._validate_confirmation(record, location)
        self._validate_record_format(record, location)
        self._validate_note(record, location)
        self._validate_context_consistency(record, location)

    def _reject_unknown_fields(self, value, allowed, location):
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(
                "{}含未知字段：{}".format(location, "、".join(unknown))
            )

    def _validate_text(self, value, location, maximum):
        if not isinstance(value, str):
            raise ValueError("{}必须是字符串".format(location))
        text = value.strip()
        if not text:
            raise ValueError("{}不能为空".format(location))
        if len(text) > maximum:
            raise ValueError("{}长度不得超过{}".format(location, maximum))
        return text

    def _validate_unit_text(self, value, location):
        text = self._validate_text(value, location, 40)
        if any(character in text for character in "\r\n\t"):
            raise ValueError("{}含非法控制字符".format(location))

    def _validate_context_number(self, record, field, location):
        if field not in record:
            return
        value = self._to_decimal(record[field], location + "." + field)
        if value <= 0:
            raise ValueError("{}.{}必须大于0".format(location, field))
        if value > self.MAX_ABS_VALUE:
            raise ValueError("{}.{}数值过大".format(location, field))

    def _validate_confirmation(self, record, location):
        if "density_confirmed" not in record:
            return
        value = record["density_confirmed"]
        if not isinstance(value, bool):
            raise ValueError(
                "{}.density_confirmed必须是布尔值".format(location)
            )
        if value and "density_g_ml" not in record:
            raise ValueError(
                "{}确认密度时必须提供density_g_ml".format(location)
            )

    def _validate_record_format(self, record, location):
        if "significant_digits" in record:
            self._validate_digits(
                record["significant_digits"],
                location + ".significant_digits",
            )
        if "rounding" in record:
            self._validate_rounding(
                record["rounding"],
                location + ".rounding",
            )

    def _validate_digits(self, value, location):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("{}必须是整数".format(location))
        if value < 1 or value > 15:
            raise ValueError("{}必须在1至15之间".format(location))

    def _validate_rounding(self, value, location):
        if not isinstance(value, str):
            raise ValueError("{}必须是字符串".format(location))
        if value not in self.ROUNDINGS:
            raise ValueError(
                "{}必须为HALF_UP、HALF_EVEN、DOWN或UP".format(location)
            )

    def _validate_note(self, record, location):
        if "note" not in record:
            return
        self._validate_text(record["note"], location + ".note", 200)

    def _validate_context_consistency(self, record, location):
        fields = ("sample_mass_g", "volume_ml", "density_g_ml")
        if not all(field in record for field in fields):
            return
        mass = self._to_fraction(record["sample_mass_g"])
        volume = self._to_fraction(record["volume_ml"])
        density = self._to_fraction(record["density_g_ml"])
        derived = mass / volume
        relative = abs(derived - density) / density
        if relative > Fraction(1, 100):
            raise ValueError(
                "{}的样品质量、体积与密度偏差超过1%".format(location)
            )

    def _to_decimal(self, value, location):
        if isinstance(value, bool):
            raise ValueError("{}不得为布尔值".format(location))
        if not isinstance(value, (int, float, str, Decimal)):
            raise ValueError("{}必须是数字或数字字符串".format(location))
        if isinstance(value, str) and not value.strip():
            raise ValueError("{}不能为空".format(location))
        try:
            decimal_value = Decimal(str(value).strip())
        except (InvalidOperation, ValueError):
            raise ValueError("{}不是有效数字".format(location))
        if not decimal_value.is_finite():
            raise ValueError("{}必须是有限数字".format(location))
        return decimal_value

    def _to_fraction(self, value):
        decimal_value = Decimal(str(value).strip())
        return Fraction(decimal_value)

    def _normalize_unit(self, value):
        text = value.strip()
        if text in self.units:
            return text
        return self.aliases.get(text)

    def _calculate_record(
        self,
        record,
        index,
        default_digits,
        default_rounding,
    ):
        identifier = record["id"].strip()
        source_text = record["source_unit"].strip()
        target_text = record["target_unit"].strip()
        source_unit = self._normalize_unit(source_text)
        target_unit = self._normalize_unit(target_text)
        digits = record.get("significant_digits", default_digits)
        rounding = record.get("rounding", default_rounding)
        base = self._base_row(
            identifier,
            record["value"],
            source_text,
            target_text,
            digits,
            rounding,
        )
        if source_unit is None or target_unit is None:
            return self._unknown_unit_row(base, source_unit, target_unit)
        source = self.units[source_unit]
        target = self.units[target_unit]
        value = self._to_fraction(record["value"])
        outcome = self._dispatch_conversion(
            value,
            source,
            target,
            record,
        )
        if not outcome["success"]:
            return self._review_row(base, source, target, outcome)
        exact_value = outcome["value"]
        rounded = self._round_fraction(exact_value, digits, rounding)
        base.update(
            {
                "标准原单位": source.symbol,
                "标准目标单位": target.symbol,
                "原量纲": self.DIMENSION_NAMES[source.dimension],
                "目标量纲": self.DIMENSION_NAMES[target.dimension],
                "量纲校验": "通过",
                "处理状态": "换算成功",
                "精确换算式": outcome["expression"],
                "精确结果": self._fraction_text(exact_value),
                "舍入值": self._decimal_text(rounded),
                "换算因子": outcome["factor"],
                "上下文依据": outcome["context"],
                "异常原因": "无",
                "是否直接同量纲": (
                    "是" if outcome["direct"] else "否"
                ),
            }
        )
        return base

    def _base_row(
        self,
        identifier,
        value,
        source_unit,
        target_unit,
        digits,
        rounding,
    ):
        return {
            "记录标识": identifier,
            "原值": self._decimal_text(Decimal(str(value).strip())),
            "原单位": source_unit,
            "目标单位": target_unit,
            "有效数字": digits,
            "舍入规则": rounding,
        }

    def _unknown_unit_row(self, base, source_unit, target_unit):
        missing = []
        if source_unit is None:
            missing.append("原单位不在白名单")
        if target_unit is None:
            missing.append("目标单位不在白名单")
        base.update(
            {
                "标准原单位": source_unit or "未识别",
                "标准目标单位": target_unit or "未识别",
                "原量纲": "未知",
                "目标量纲": "未知",
                "量纲校验": "不通过",
                "处理状态": "待人工复核",
                "精确换算式": "禁止换算",
                "精确结果": "不可计算",
                "舍入值": "不可计算",
                "换算因子": "不可计算",
                "上下文依据": "无",
                "异常原因": "；".join(missing),
                "是否直接同量纲": "否",
            }
        )
        return base

    def _review_row(self, base, source, target, outcome):
        base.update(
            {
                "标准原单位": source.symbol,
                "标准目标单位": target.symbol,
                "原量纲": self.DIMENSION_NAMES[source.dimension],
                "目标量纲": self.DIMENSION_NAMES[target.dimension],
                "量纲校验": "不通过",
                "处理状态": "待人工复核",
                "精确换算式": "禁止换算",
                "精确结果": "不可计算",
                "舍入值": "不可计算",
                "换算因子": "不可计算",
                "上下文依据": outcome["context"],
                "异常原因": outcome["reason"],
                "是否直接同量纲": "否",
            }
        )
        return base

    def _dispatch_conversion(self, value, source, target, record):
        if source.dimension == target.dimension:
            return self._convert_same_dimension(value, source, target)
        pair = (source.dimension, target.dimension)
        if pair == ("mass", "mass_concentration"):
            return self._mass_to_concentration(value, source, target, record)
        if pair == ("mass_concentration", "mass"):
            return self._concentration_to_mass(value, source, target, record)
        if pair == ("mass", "mass_fraction"):
            return self._mass_to_fraction(value, source, target, record)
        if pair == ("mass_fraction", "mass"):
            return self._fraction_to_mass(value, source, target, record)
        if pair == ("mass_fraction", "mass_concentration"):
            return self._fraction_to_concentration(
                value,
                source,
                target,
                record,
            )
        if pair == ("mass_concentration", "mass_fraction"):
            return self._concentration_to_fraction(
                value,
                source,
                target,
                record,
            )
        if pair == ("mass", "volume"):
            return self._mass_to_volume(value, source, target, record)
        if pair == ("volume", "mass"):
            return self._volume_to_mass(value, source, target, record)
        return self._failure(
            "量纲不兼容，且没有登记可解释的上下文换算路径",
            "未使用上下文",
        )

    def _convert_same_dimension(self, value, source, target):
        factor = source.factor / target.factor
        result = value * factor
        expression = "{} {} × ({}/{}) = {} {}".format(
            self._fraction_text(value),
            source.symbol,
            source.factor,
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        return self._success(
            result,
            factor,
            expression,
            "同量纲白名单因子",
            True,
        )

    def _mass_to_concentration(self, value, source, target, record):
        if "volume_ml" not in record:
            return self._failure(
                "质量换算为质量浓度必须提供定容体积",
                "缺少volume_ml",
            )
        volume_ml = self._to_fraction(record["volume_ml"])
        mass_g = value * source.factor
        volume_l = volume_ml / 1000
        base_concentration = mass_g / volume_l
        result = base_concentration / target.factor
        expression = "({}×{} g)/({}/1000 L)/{} = {} {}".format(
            self._fraction_text(value),
            source.factor,
            self._fraction_text(volume_ml),
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        factor = result / value if value else Fraction(0, 1)
        context = "定容体积{} mL".format(self._fraction_text(volume_ml))
        return self._success(result, factor, expression, context, False)

    def _concentration_to_mass(self, value, source, target, record):
        if "volume_ml" not in record:
            return self._failure(
                "质量浓度换算为质量必须提供定容体积",
                "缺少volume_ml",
            )
        volume_ml = self._to_fraction(record["volume_ml"])
        volume_l = volume_ml / 1000
        mass_g = value * source.factor * volume_l
        result = mass_g / target.factor
        expression = "{}×{} g/L×({}/1000 L)/{} = {} {}".format(
            self._fraction_text(value),
            source.factor,
            self._fraction_text(volume_ml),
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        factor = result / value if value else Fraction(0, 1)
        context = "定容体积{} mL".format(self._fraction_text(volume_ml))
        return self._success(result, factor, expression, context, False)

    def _mass_to_fraction(self, value, source, target, record):
        if "sample_mass_g" not in record:
            return self._failure(
                "质量换算为质量分数必须提供样品质量",
                "缺少sample_mass_g",
            )
        sample_mass = self._to_fraction(record["sample_mass_g"])
        analyte_mass = value * source.factor
        ratio = analyte_mass / sample_mass
        result = ratio / target.factor
        expression = "({}×{} g)/({} g)/{} = {} {}".format(
            self._fraction_text(value),
            source.factor,
            self._fraction_text(sample_mass),
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        factor = result / value if value else Fraction(0, 1)
        context = "样品质量{} g".format(self._fraction_text(sample_mass))
        return self._success(result, factor, expression, context, False)

    def _fraction_to_mass(self, value, source, target, record):
        if "sample_mass_g" not in record:
            return self._failure(
                "质量分数换算为质量必须提供样品质量",
                "缺少sample_mass_g",
            )
        sample_mass = self._to_fraction(record["sample_mass_g"])
        ratio = value * source.factor
        analyte_mass = ratio * sample_mass
        result = analyte_mass / target.factor
        expression = "{}×{}×{} g/{} = {} {}".format(
            self._fraction_text(value),
            source.factor,
            self._fraction_text(sample_mass),
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        factor = result / value if value else Fraction(0, 1)
        context = "样品质量{} g".format(self._fraction_text(sample_mass))
        return self._success(result, factor, expression, context, False)

    def _fraction_to_concentration(
        self,
        value,
        source,
        target,
        record,
    ):
        density_result = self._obtain_density(record)
        if not density_result["success"]:
            return density_result
        density = density_result["density"]
        ratio = value * source.factor
        base_concentration = ratio * density * 1000
        result = base_concentration / target.factor
        expression = "{}×{}×{} g/mL×1000/{} = {} {}".format(
            self._fraction_text(value),
            source.factor,
            self._fraction_text(density),
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        factor = result / value if value else Fraction(0, 1)
        return self._success(
            result,
            factor,
            expression,
            density_result["context"],
            False,
        )

    def _concentration_to_fraction(
        self,
        value,
        source,
        target,
        record,
    ):
        density_result = self._obtain_density(record)
        if not density_result["success"]:
            return density_result
        density = density_result["density"]
        base_concentration = value * source.factor
        ratio = base_concentration / (density * 1000)
        result = ratio / target.factor
        expression = "{}×{} g/L/({}×1000 g/L)/{} = {} {}".format(
            self._fraction_text(value),
            source.factor,
            self._fraction_text(density),
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        factor = result / value if value else Fraction(0, 1)
        return self._success(
            result,
            factor,
            expression,
            density_result["context"],
            False,
        )

    def _mass_to_volume(self, value, source, target, record):
        density_result = self._confirmed_density_only(record)
        if not density_result["success"]:
            return density_result
        density = density_result["density"]
        mass_g = value * source.factor
        volume_ml = mass_g / density
        volume_l = volume_ml / 1000
        result = volume_l / target.factor
        expression = "{}×{} g/{} g/mL/1000/{} = {} {}".format(
            self._fraction_text(value),
            source.factor,
            self._fraction_text(density),
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        factor = result / value if value else Fraction(0, 1)
        return self._success(
            result,
            factor,
            expression,
            density_result["context"],
            False,
        )

    def _volume_to_mass(self, value, source, target, record):
        density_result = self._confirmed_density_only(record)
        if not density_result["success"]:
            return density_result
        density = density_result["density"]
        volume_l = value * source.factor
        volume_ml = volume_l * 1000
        mass_g = volume_ml * density
        result = mass_g / target.factor
        expression = "{}×{} L×1000×{} g/mL/{} = {} {}".format(
            self._fraction_text(value),
            source.factor,
            self._fraction_text(density),
            target.factor,
            self._fraction_text(result),
            target.symbol,
        )
        factor = result / value if value else Fraction(0, 1)
        return self._success(
            result,
            factor,
            expression,
            density_result["context"],
            False,
        )

    def _obtain_density(self, record):
        if "density_g_ml" in record:
            if record.get("density_confirmed") is not True:
                return self._failure(
                    "使用实测密度前必须明确确认",
                    "density_confirmed不是true",
                )
            density = self._to_fraction(record["density_g_ml"])
            context = "经确认密度{} g/mL".format(
                self._fraction_text(density)
            )
            return {
                "success": True,
                "density": density,
                "context": context,
            }
        if "sample_mass_g" in record and "volume_ml" in record:
            mass = self._to_fraction(record["sample_mass_g"])
            volume = self._to_fraction(record["volume_ml"])
            density = mass / volume
            context = "由样品质量{} g和体积{} mL计算密度".format(
                self._fraction_text(mass),
                self._fraction_text(volume),
            )
            return {
                "success": True,
                "density": density,
                "context": context,
            }
        return self._failure(
            "质量分数与质量浓度互换必须提供经确认密度，"
            "或同时提供样品质量和体积；未假设密度为1",
            "上下文参数不完整，未执行跨量纲换算",
        )

    def _confirmed_density_only(self, record):
        if "density_g_ml" not in record:
            return self._failure(
                "质量与体积互换必须提供密度；未假设密度为1",
                "缺少density_g_ml",
            )
        if record.get("density_confirmed") is not True:
            return self._failure(
                "质量与体积互换必须确认密度；未假设密度为1",
                "density_confirmed不是true",
            )
        density = self._to_fraction(record["density_g_ml"])
        context = "经确认密度{} g/mL".format(
            self._fraction_text(density)
        )
        return {
            "success": True,
            "density": density,
            "context": context,
        }

    def _success(
        self,
        value,
        factor,
        expression,
        context,
        direct,
    ):
        return {
            "success": True,
            "value": value,
            "factor": self._fraction_text(factor),
            "expression": expression,
            "context": context,
            "direct": direct,
        }

    def _failure(self, reason, context):
        return {
            "success": False,
            "reason": reason,
            "context": context,
        }

    def _round_fraction(self, value, digits, rounding_name):
        decimal_value = self._fraction_to_decimal(value)
        if decimal_value == 0:
            return Decimal(0)
        adjusted = decimal_value.copy_abs().adjusted()
        exponent = Decimal("1e{}".format(adjusted - digits + 1))
        return decimal_value.quantize(
            exponent,
            rounding=self.ROUNDINGS[rounding_name],
        )

    def _fraction_to_decimal(self, value):
        numerator = Decimal(value.numerator)
        denominator = Decimal(value.denominator)
        return numerator / denominator

    def _fraction_text(self, value):
        if value.denominator == 1:
            return str(value.numerator)
        decimal_value = self._fraction_to_decimal(value)
        text = format(decimal_value, ".28f").rstrip("0").rstrip(".")
        return text + "（精确分数{}/{}）".format(
            value.numerator,
            value.denominator,
        )

    def _decimal_text(self, value):
        if value == 0:
            return "0"
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text

    def _series_number(self, value):
        decimal_value = Decimal(value)
        if not decimal_value.is_finite():
            raise ValueError("图表值必须为有限数字")
        number = float(decimal_value)
        if not math.isfinite(number):
            raise ValueError("图表值超出有限浮点范围")
        return number

    def _percentage(self, numerator, denominator):
        if denominator == 0:
            return "0%"
        value = Decimal(numerator) * Decimal(100) / Decimal(denominator)
        rounded = value.quantize(
            Decimal("0.1"),
            rounding=ROUND_HALF_UP,
        )
        return self._decimal_text(rounded) + "%"

    def _build_summary(self, total, converted, review, exact):
        if review == 0:
            conclusion = "全部记录均已完成单位统一"
        elif converted == 0:
            conclusion = "全部记录因单位或上下文问题转待人工复核"
        else:
            conclusion = "部分记录完成单位统一，其余转待人工复核"
        method = (
            "采用白名单量纲表和Fraction有理数因子计算，"
            "跨质量分数、质量浓度、质量与体积时仅使用已提供且"
            "满足约束的样品质量、定容体积或经确认密度；"
            "最后按指定有效数字执行Decimal舍入。"
        )
        counts = "共{}条，成功{}条，复核{}条，同量纲{}条。".format(
            total,
            converted,
            review,
            exact,
        )
        return conclusion + "。" + counts + method

    def _unit_basis(self):
        rows = []
        for symbol in sorted(self.units):
            unit = self.units[symbol]
            rows.append(
                {
                    "单位": symbol,
                    "中文名称": unit.chinese_name,
                    "量纲": self.DIMENSION_NAMES[unit.dimension],
                    "基准因子": str(unit.factor),
                    "分子量纲": unit.numerator_dimension,
                    "分母量纲": unit.denominator_dimension,
                }
            )
        return rows
