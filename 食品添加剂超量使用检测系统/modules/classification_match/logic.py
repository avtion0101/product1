import copy
import datetime
import math
import re
import unicodedata


class Engine:
    REQUIRED_RULE_FIELDS = (
        "food_code",
        "additive_name",
        "limit_type",
        "limit_value",
        "unit",
        "standard_version",
        "effective_date",
        "source",
        "conditions",
    )
    LIMIT_TYPES = {
        "最大使用量",
        "残留量",
        "按生产需要适量使用",
        "禁止使用",
    }
    CONDITION_FIELDS = {
        "product_name",
        "candidate_code",
        "production_date",
        "ingredient",
        "ingredient_count",
        "verification",
    }
    OPERATORS = {
        "contains",
        "not_contains",
        "equals",
        "not_equals",
        "starts_with",
        "in",
        "not_in",
        "gte",
        "lte",
        "between",
        "confirmed",
    }
    CODE_PATTERN = re.compile(
        r"^[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*(?:[.\-]\*)?$"
    )
    UNIT_PATTERN = re.compile(r"^[^\s]{1,20}$")

    def __init__(self):
        self._date_floor = datetime.date(1900, 1, 1)

    def example(self):
        return {
            "sample_name": "草莓味发酵乳",
            "food_candidates": [
                {
                    "code": "01.02.01",
                    "name": "发酵乳",
                    "confirmed": True,
                },
                {
                    "code": "01.02",
                    "name": "乳制品",
                    "confirmed": False,
                },
            ],
            "additive_name": "山梨酸钾",
            "production_date": "2026-06-15",
            "ingredients": [
                "生牛乳",
                "草莓果酱",
                "白砂糖",
                "山梨酸钾",
            ],
            "verifications": {
                "含水果配料": True,
                "经发酵工艺": True,
                "仅用于表面处理": False,
            },
            "rules": [
                {
                    "rule_id": "R-001",
                    "food_code": "01.02.01",
                    "additive_name": "山梨酸钾",
                    "limit_type": "最大使用量",
                    "limit_value": 0.5,
                    "unit": "g/kg",
                    "standard_version": "企业核验规则2026-A",
                    "effective_date": "2026-01-01",
                    "source": "用户录入规则集A第1条",
                    "conditions": [
                        {
                            "field": "verification",
                            "operator": "confirmed",
                            "value": "含水果配料",
                        }
                    ],
                },
                {
                    "rule_id": "R-002",
                    "food_code": "01.02",
                    "additive_name": "山梨酸钾",
                    "limit_type": "最大使用量",
                    "limit_value": 0.3,
                    "unit": "g/kg",
                    "standard_version": "企业核验规则2025-B",
                    "effective_date": "2025-01-01",
                    "source": "用户录入规则集A第2条",
                    "conditions": [
                        {
                            "field": "verification",
                            "operator": "confirmed",
                            "value": "经发酵工艺",
                        }
                    ],
                },
                {
                    "rule_id": "R-003",
                    "food_code": "01.02.*",
                    "additive_name": "山梨酸钾",
                    "limit_type": "最大使用量",
                    "limit_value": 0.2,
                    "unit": "g/kg",
                    "standard_version": "企业核验规则2024-C",
                    "effective_date": "2024-01-01",
                    "source": "用户录入规则集B第8条",
                    "conditions": [],
                },
                {
                    "rule_id": "R-004",
                    "food_code": "01.02.01",
                    "additive_name": "苯甲酸钠",
                    "limit_type": "最大使用量",
                    "limit_value": 0.4,
                    "unit": "g/kg",
                    "standard_version": "企业核验规则2026-A",
                    "effective_date": "2026-01-01",
                    "source": "用户录入规则集A第4条",
                    "conditions": [],
                },
                {
                    "rule_id": "R-005",
                    "food_code": "01.02.01",
                    "additive_name": "山梨酸钾",
                    "limit_type": "禁止使用",
                    "limit_value": 0,
                    "unit": "g/kg",
                    "standard_version": "企业核验规则2027-D",
                    "effective_date": "2027-01-01",
                    "source": "用户录入规则集C第3条",
                    "conditions": [],
                },
            ],
        }

    def validate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("输入必须是JSON对象")
        required = (
            "sample_name",
            "food_candidates",
            "additive_name",
            "production_date",
            "ingredients",
            "verifications",
            "rules",
        )
        self._require_keys(payload, required, "输入")
        self._reject_unknown_keys(payload, set(required), "输入")
        self._validate_text(payload["sample_name"], "样品名称", 120)
        self._validate_text(payload["additive_name"], "添加剂名称", 100)
        production_date = self._parse_date(
            payload["production_date"],
            "生产日期",
        )
        if production_date < self._date_floor:
            raise ValueError("生产日期不得早于1900-01-01")
        self._validate_candidates(payload["food_candidates"])
        self._validate_ingredients(payload["ingredients"])
        self._validate_verifications(payload["verifications"])
        self._validate_rules(payload["rules"])
        self._validate_cross_constraints(payload)
        return None

    def _require_keys(self, value, keys, path):
        missing = [key for key in keys if key not in value]
        if missing:
            raise ValueError(
                f"{path}缺少字段：{'、'.join(missing)}"
            )

    def _reject_unknown_keys(self, value, allowed, path):
        unknown = sorted(set(value) - set(allowed))
        if unknown:
            raise ValueError(
                f"{path}包含未知字段：{'、'.join(unknown)}"
            )

    def _validate_text(self, value, path, maximum):
        if not isinstance(value, str):
            raise ValueError(f"{path}必须是字符串")
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{path}不得为空")
        if len(stripped) > maximum:
            raise ValueError(f"{path}长度不得超过{maximum}")
        if "\x00" in value:
            raise ValueError(f"{path}不得包含空字符")

    def _validate_candidates(self, candidates):
        if not isinstance(candidates, list):
            raise ValueError("食品分类候选必须是数组")
        if not candidates:
            raise ValueError("食品分类候选不得为空")
        if len(candidates) > 50:
            raise ValueError("食品分类候选不得超过50条")
        seen = set()
        for index, candidate in enumerate(candidates):
            path = f"食品分类候选[{index}]"
            if not isinstance(candidate, dict):
                raise ValueError(f"{path}必须是对象")
            required = ("code", "name", "confirmed")
            self._require_keys(candidate, required, path)
            self._reject_unknown_keys(candidate, set(required), path)
            self._validate_code(candidate["code"], f"{path}.code", False)
            self._validate_text(candidate["name"], f"{path}.name", 120)
            if type(candidate["confirmed"]) is not bool:
                raise ValueError(f"{path}.confirmed必须是布尔值")
            code = self._normalize_code(candidate["code"])
            if code in seen:
                raise ValueError("食品分类候选代码不得重复")
            seen.add(code)

    def _validate_ingredients(self, ingredients):
        if not isinstance(ingredients, list):
            raise ValueError("配料必须是数组")
        if len(ingredients) > 200:
            raise ValueError("配料不得超过200项")
        seen = set()
        for index, ingredient in enumerate(ingredients):
            self._validate_text(ingredient, f"配料[{index}]", 100)
            normalized = self._normalize_text(ingredient)
            if normalized in seen:
                raise ValueError("规范化后的配料名称不得重复")
            seen.add(normalized)

    def _validate_verifications(self, verifications):
        if not isinstance(verifications, dict):
            raise ValueError("用户核验信息必须是对象")
        if len(verifications) > 100:
            raise ValueError("用户核验信息不得超过100项")
        seen = set()
        for key, value in verifications.items():
            self._validate_text(key, "核验项名称", 100)
            if value is not None and type(value) is not bool:
                raise ValueError("核验项值必须为布尔值或null")
            normalized = self._normalize_text(key)
            if normalized in seen:
                raise ValueError("规范化后的核验项名称不得重复")
            seen.add(normalized)

    def _validate_rules(self, rules):
        if not isinstance(rules, list):
            raise ValueError("规则集合必须是数组")
        if not rules:
            raise ValueError("规则集合不得为空")
        if len(rules) > 5000:
            raise ValueError("规则集合不得超过5000条")
        identifiers = set()
        fingerprints = set()
        for index, rule in enumerate(rules):
            path = f"规则[{index}]"
            self._validate_rule(rule, path)
            identifier = rule.get("rule_id")
            if identifier is not None:
                if identifier in identifiers:
                    raise ValueError("规则标识不得重复")
                identifiers.add(identifier)
            fingerprint = self._rule_fingerprint(rule)
            if fingerprint in fingerprints:
                raise ValueError("规则集合包含完全重复的规则")
            fingerprints.add(fingerprint)

    def _validate_rule(self, rule, path):
        if not isinstance(rule, dict):
            raise ValueError(f"{path}必须是对象")
        self._require_keys(rule, self.REQUIRED_RULE_FIELDS, path)
        allowed = set(self.REQUIRED_RULE_FIELDS) | {"rule_id"}
        self._reject_unknown_keys(rule, allowed, path)
        if "rule_id" in rule:
            self._validate_text(rule["rule_id"], f"{path}.rule_id", 80)
        self._validate_code(rule["food_code"], f"{path}.food_code", True)
        self._validate_text(
            rule["additive_name"],
            f"{path}.additive_name",
            100,
        )
        self._validate_limit_type(rule["limit_type"], path)
        self._validate_limit_value(
            rule["limit_value"],
            rule["limit_type"],
            path,
        )
        self._validate_text(rule["unit"], f"{path}.unit", 20)
        if not self.UNIT_PATTERN.fullmatch(rule["unit"].strip()):
            raise ValueError(f"{path}.unit格式无效")
        self._validate_text(
            rule["standard_version"],
            f"{path}.standard_version",
            100,
        )
        self._parse_date(
            rule["effective_date"],
            f"{path}.effective_date",
        )
        self._validate_text(rule["source"], f"{path}.source", 300)
        self._validate_conditions(rule["conditions"], path)

    def _validate_limit_type(self, value, path):
        if not isinstance(value, str):
            raise ValueError(f"{path}.limit_type必须是字符串")
        if value not in self.LIMIT_TYPES:
            allowed = "、".join(sorted(self.LIMIT_TYPES))
            raise ValueError(f"{path}.limit_type必须为：{allowed}")

    def _validate_limit_value(self, value, limit_type, path):
        if isinstance(value, bool):
            raise ValueError(f"{path}.limit_value必须是数字")
        if not isinstance(value, (int, float)):
            raise ValueError(f"{path}.limit_value必须是数字")
        if not math.isfinite(float(value)):
            raise ValueError(f"{path}.limit_value必须是有限数字")
        if value < 0:
            raise ValueError(f"{path}.limit_value不得为负数")
        if value > 1000000000:
            raise ValueError(f"{path}.limit_value超出合理范围")
        if limit_type == "禁止使用" and value != 0:
            raise ValueError("禁止使用规则的限量数值必须为0")
        if limit_type == "按生产需要适量使用" and value != 0:
            raise ValueError("适量使用规则的限量数值必须为0")
        quantitative = {"最大使用量", "残留量"}
        if limit_type in quantitative and value <= 0:
            raise ValueError("定量限量规则的数值必须大于0")

    def _validate_conditions(self, conditions, path):
        if not isinstance(conditions, list):
            raise ValueError(f"{path}.conditions必须是数组")
        if len(conditions) > 50:
            raise ValueError(f"{path}.conditions不得超过50项")
        signatures = set()
        for index, condition in enumerate(conditions):
            condition_path = f"{path}.conditions[{index}]"
            self._validate_condition(condition, condition_path)
            signature = self._condition_signature(condition)
            if signature in signatures:
                raise ValueError(f"{path}.conditions包含重复条件")
            signatures.add(signature)

    def _validate_condition(self, condition, path):
        if not isinstance(condition, dict):
            raise ValueError(f"{path}必须是对象")
        required = ("field", "operator", "value")
        self._require_keys(condition, required, path)
        self._reject_unknown_keys(condition, set(required), path)
        field = condition["field"]
        operator = condition["operator"]
        if field not in self.CONDITION_FIELDS:
            raise ValueError(f"{path}.field不受支持")
        if operator not in self.OPERATORS:
            raise ValueError(f"{path}.operator不受支持")
        self._validate_operator_for_field(field, operator, path)
        self._validate_condition_value(
            field,
            operator,
            condition["value"],
            path,
        )

    def _validate_operator_for_field(self, field, operator, path):
        allowed = {
            "product_name": {
                "contains",
                "not_contains",
                "equals",
                "not_equals",
                "starts_with",
                "in",
                "not_in",
            },
            "candidate_code": {
                "equals",
                "not_equals",
                "starts_with",
                "in",
                "not_in",
            },
            "production_date": {
                "equals",
                "gte",
                "lte",
                "between",
            },
            "ingredient": {
                "contains",
                "not_contains",
                "equals",
                "not_equals",
                "in",
                "not_in",
            },
            "ingredient_count": {
                "equals",
                "gte",
                "lte",
                "between",
            },
            "verification": {
                "confirmed",
                "equals",
                "not_equals",
            },
        }
        if operator not in allowed[field]:
            raise ValueError(f"{path}的字段与运算符不兼容")

    def _validate_condition_value(self, field, operator, value, path):
        if operator == "between":
            if not isinstance(value, list) or len(value) != 2:
                raise ValueError(f"{path}.value必须是两个元素的数组")
            if field == "production_date":
                start = self._parse_date(value[0], f"{path}.value[0]")
                end = self._parse_date(value[1], f"{path}.value[1]")
                if start > end:
                    raise ValueError(f"{path}.value日期范围顺序错误")
            else:
                self._validate_count(value[0], f"{path}.value[0]")
                self._validate_count(value[1], f"{path}.value[1]")
                if value[0] > value[1]:
                    raise ValueError(f"{path}.value数值范围顺序错误")
            return
        if operator in {"in", "not_in"}:
            if not isinstance(value, list) or not value:
                raise ValueError(f"{path}.value必须是非空数组")
            if len(value) > 100:
                raise ValueError(f"{path}.value不得超过100项")
            normalized = set()
            for index, item in enumerate(value):
                self._validate_text(
                    item,
                    f"{path}.value[{index}]",
                    120,
                )
                marker = self._normalize_text(item)
                if marker in normalized:
                    raise ValueError(f"{path}.value包含重复项")
                normalized.add(marker)
            return
        if field == "ingredient_count":
            self._validate_count(value, f"{path}.value")
            return
        if field == "production_date":
            self._parse_date(value, f"{path}.value")
            return
        self._validate_text(value, f"{path}.value", 120)

    def _validate_count(self, value, path):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{path}必须是整数")
        if value < 0 or value > 200:
            raise ValueError(f"{path}必须在0至200之间")

    def _validate_code(self, value, path, wildcard_allowed):
        self._validate_text(value, path, 80)
        code = value.strip()
        if not self.CODE_PATTERN.fullmatch(code):
            raise ValueError(f"{path}不是有效分类代码")
        if "*" in code and not wildcard_allowed:
            raise ValueError(f"{path}不得包含通配符")
        if "*" in code and not code.endswith((".*", "-*")):
            raise ValueError(f"{path}通配符只能位于末级")
        segments = self._split_code(code)
        if not segments:
            raise ValueError(f"{path}缺少有效层级")
        if len(segments) > 20:
            raise ValueError(f"{path}层级不得超过20级")

    def _validate_cross_constraints(self, payload):
        additive = self._normalize_text(payload["additive_name"])
        if not additive:
            raise ValueError("规范化后的添加剂名称不得为空")
        confirmed = [
            item
            for item in payload["food_candidates"]
            if item["confirmed"]
        ]
        if len(confirmed) > 1:
            raise ValueError("最多只能确认一个食品分类候选")
        for index, rule in enumerate(payload["rules"]):
            effective = self._parse_date(
                rule["effective_date"],
                f"规则[{index}].effective_date",
            )
            if effective < self._date_floor:
                raise ValueError("规则生效日期不得早于1900-01-01")

    def _parse_date(self, value, path):
        if not isinstance(value, str):
            raise ValueError(f"{path}必须是YYYY-MM-DD字符串")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError(f"{path}必须使用YYYY-MM-DD格式")
        try:
            return datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{path}不是有效日期") from exc

    def _normalize_text(self, value):
        text = unicodedata.normalize("NFKC", value)
        text = text.strip().casefold()
        text = re.sub(r"[\s_\-—–·]+", "", text)
        text = text.replace("（", "(")
        text = text.replace("）", ")")
        return text

    def _normalize_code(self, value):
        code = unicodedata.normalize("NFKC", value)
        code = code.strip().upper().replace("-", ".")
        return re.sub(r"\.+", ".", code)

    def _split_code(self, value):
        code = self._normalize_code(value)
        return [
            part
            for part in code.split(".")
            if part and part != "*"
        ]

    def _condition_signature(self, condition):
        value = condition["value"]
        if isinstance(value, list):
            comparable = tuple(str(item) for item in value)
        else:
            comparable = str(value)
        return (
            condition["field"],
            condition["operator"],
            comparable,
        )

    def _rule_fingerprint(self, rule):
        conditions = tuple(
            self._condition_signature(item)
            for item in rule["conditions"]
        )
        return (
            self._normalize_code(rule["food_code"]),
            self._normalize_text(rule["additive_name"]),
            rule["limit_type"],
            float(rule["limit_value"]),
            rule["unit"].strip(),
            rule["standard_version"].strip(),
            rule["effective_date"],
            rule["source"].strip(),
            conditions,
        )

    def calculate(self, payload):
        self.validate(payload)
        data = copy.deepcopy(payload)
        production_date = self._parse_date(
            data["production_date"],
            "生产日期",
        )
        additive = self._normalize_text(data["additive_name"])
        displayed_candidates = self._ordered_food_candidates(
            data["food_candidates"]
        )
        matching_candidates = self._matching_food_candidates(
            displayed_candidates
        )
        matrix = []
        for rule_index, rule in enumerate(data["rules"]):
            row = self._evaluate_rule(
                rule,
                rule_index,
                matching_candidates,
                additive,
                production_date,
                data,
            )
            matrix.append(row)
        ranked = sorted(matrix, key=self._sort_key)
        eligible = [
            row
            for row in ranked
            if row["自动候选"] == "是"
        ]
        decision = self._make_decision(eligible, ranked)
        result = {
            "summary": self._build_summary(decision, data),
            "metrics": self._build_metrics(
                data,
                ranked,
                eligible,
                decision,
            ),
            "rows": self._public_rows(ranked),
            "series": self._build_series(ranked),
            "chart_title": "食品分类规则匹配候选矩阵",
            "review_status": decision["status"],
            "selected_rule": decision["selected_rule"],
            "unmet_conditions": decision["unmet_conditions"],
            "rule_snapshot": self._rule_snapshot(ranked),
            "candidate_order": self._candidate_view(displayed_candidates),
            "matching_scope": self._candidate_view(matching_candidates),
            "method": {
                "名称规范化": "NFKC、去空白与连接符、大小写折叠",
                "候选范围": "存在已确认代码时仅以该代码执行规则匹配",
                "代码优先级": "完全代码、祖先代码、末级通配范围",
                "排序": "代码具体度、满足条件数、生效日期降序",
                "消歧": "最高排序键并列或条件未知时转人工复核",
            },
        }
        return result

    def _ordered_food_candidates(self, candidates):
        copied = [copy.deepcopy(item) for item in candidates]
        return sorted(
            copied,
            key=lambda item: (
                0 if item["confirmed"] else 1,
                -len(self._split_code(item["code"])),
                self._normalize_code(item["code"]),
            ),
        )

    def _matching_food_candidates(self, candidates):
        confirmed = [
            item
            for item in candidates
            if item["confirmed"]
        ]
        if confirmed:
            return confirmed
        return candidates

    def _candidate_view(self, candidates):
        return [
            {
                "代码": item["code"],
                "名称": item["name"],
                "已确认": "是" if item["confirmed"] else "否",
            }
            for item in candidates
        ]

    def _evaluate_rule(
        self,
        rule,
        rule_index,
        candidates,
        additive,
        production_date,
        payload,
    ):
        rule_id = rule.get("rule_id", f"规则-{rule_index + 1}")
        additive_match = (
            self._normalize_text(rule["additive_name"]) == additive
        )
        effective_date = self._parse_date(
            rule["effective_date"],
            "规则生效日期",
        )
        date_active = effective_date <= production_date
        code_match = self._best_code_match(
            rule["food_code"],
            candidates,
        )
        conditions = self._evaluate_conditions(
            rule["conditions"],
            code_match["candidate"],
            payload,
        )
        false_conditions = [
            item
            for item in conditions
            if item["state"] == "不满足"
        ]
        unknown_conditions = [
            item
            for item in conditions
            if item["state"] == "未知"
        ]
        true_conditions = [
            item
            for item in conditions
            if item["state"] == "满足"
        ]
        parent_rule = code_match["kind"] == "祖先"
        parent_covered = not parent_rule or (
            bool(rule["conditions"])
            and not false_conditions
            and not unknown_conditions
        )
        base_eligible = all(
            (
                additive_match,
                date_active,
                code_match["rank"] > 0,
                not false_conditions,
                parent_covered,
            )
        )
        exact_unknown = (
            code_match["kind"] in {"完全", "通配"}
            and bool(unknown_conditions)
        )
        eligible = base_eligible or (
            exact_unknown
            and additive_match
            and date_active
            and not false_conditions
        )
        reasons = self._exclusion_reasons(
            additive_match,
            date_active,
            code_match,
            false_conditions,
            unknown_conditions,
            parent_covered,
        )
        specificity = code_match["rank"] * 100
        specificity += code_match["depth"] * 10
        score = specificity + len(true_conditions)
        if not eligible:
            score = 0
        return {
            "规则标识": rule_id,
            "规则序号": rule_index,
            "食品分类代码": rule["food_code"],
            "匹配候选代码": code_match["candidate_code"],
            "代码匹配类型": code_match["kind"],
            "代码具体度": specificity,
            "添加剂名称": rule["additive_name"],
            "添加剂名称匹配": "是" if additive_match else "否",
            "限量类型": rule["limit_type"],
            "限量值": rule["limit_value"],
            "单位": rule["unit"],
            "标准版本": rule["standard_version"],
            "生效日期": rule["effective_date"],
            "来源": rule["source"],
            "日期有效": "是" if date_active else "否",
            "满足条件数": len(true_conditions),
            "条件总数": len(conditions),
            "未知条件数": len(unknown_conditions),
            "条件结果": conditions,
            "未满足条件": [
                item["description"]
                for item in false_conditions
            ],
            "待确认条件": [
                item["description"]
                for item in unknown_conditions
            ],
            "排除原因": reasons,
            "自动候选": "是" if eligible else "否",
            "需人工复核": "是" if unknown_conditions else "否",
            "匹配得分": score,
            "effective_ordinal": effective_date.toordinal(),
            "rule": copy.deepcopy(rule),
        }

    def _best_code_match(self, rule_code, candidates):
        matches = []
        for candidate in candidates:
            match = self._code_match(rule_code, candidate["code"])
            match["candidate"] = candidate
            match["candidate_code"] = candidate["code"]
            matches.append(match)
        if not matches:
            return {
                "rank": 0,
                "depth": 0,
                "kind": "不匹配",
                "candidate": None,
                "candidate_code": "",
            }
        return max(
            matches,
            key=lambda item: (
                item["rank"],
                item["depth"],
                1 if item["candidate"]["confirmed"] else 0,
            ),
        )

    def _code_match(self, rule_code, candidate_code):
        rule_normalized = self._normalize_code(rule_code)
        rule_parts = self._split_code(rule_code)
        candidate_parts = self._split_code(candidate_code)
        if "*" not in rule_normalized:
            if rule_parts == candidate_parts:
                return {
                    "rank": 3,
                    "depth": len(rule_parts),
                    "kind": "完全",
                }
            parent = (
                len(rule_parts) < len(candidate_parts)
                and candidate_parts[:len(rule_parts)] == rule_parts
            )
            if parent:
                return {
                    "rank": 2,
                    "depth": len(rule_parts),
                    "kind": "祖先",
                }
            return {
                "rank": 0,
                "depth": 0,
                "kind": "不匹配",
            }
        prefix = (
            len(rule_parts) <= len(candidate_parts)
            and candidate_parts[:len(rule_parts)] == rule_parts
        )
        if prefix:
            return {
                "rank": 1,
                "depth": len(rule_parts),
                "kind": "通配",
            }
        return {
            "rank": 0,
            "depth": 0,
            "kind": "不匹配",
        }

    def _evaluate_conditions(self, conditions, candidate, payload):
        results = []
        for condition in conditions:
            state, actual = self._evaluate_condition(
                condition,
                candidate,
                payload,
            )
            results.append(
                {
                    "field": condition["field"],
                    "operator": condition["operator"],
                    "expected": copy.deepcopy(condition["value"]),
                    "actual": actual,
                    "state": state,
                    "description": self._describe_condition(
                        condition,
                        state,
                    ),
                }
            )
        return results

    def _evaluate_condition(self, condition, candidate, payload):
        field = condition["field"]
        operator = condition["operator"]
        expected = condition["value"]
        if field == "verification":
            return self._evaluate_verification(
                operator,
                expected,
                payload,
            )
        if field == "ingredient":
            return self._evaluate_ingredient(
                operator,
                expected,
                payload,
            )
        if field == "ingredient_count":
            actual = len(payload["ingredients"])
            state = self._compare_scalar(actual, operator, expected)
            return state, actual
        if field == "production_date":
            actual_date = self._parse_date(
                payload["production_date"],
                "生产日期",
            )
            state = self._compare_date(actual_date, operator, expected)
            return state, payload["production_date"]
        if field == "candidate_code":
            if candidate is None:
                return "未知", "无代码匹配候选"
            actual = candidate["code"]
            state = self._compare_text(
                actual,
                operator,
                expected,
                True,
            )
            return state, actual
        actual = payload["sample_name"]
        state = self._compare_text(
            actual,
            operator,
            expected,
            False,
        )
        return state, actual

    def _evaluate_verification(self, operator, expected, payload):
        target = self._normalize_text(expected)
        found_key = None
        for key in payload["verifications"]:
            if self._normalize_text(key) == target:
                found_key = key
                break
        if found_key is None:
            return "未知", "未录入"
        actual = payload["verifications"][found_key]
        if actual is None:
            return "未知", "未确认"
        if operator == "confirmed":
            state = "满足" if actual else "不满足"
            return state, actual
        expected_boolean = self._text_to_boolean(expected)
        if expected_boolean is None:
            expected_boolean = True
        matched = actual == expected_boolean
        if operator == "not_equals":
            matched = not matched
        return ("满足" if matched else "不满足"), actual

    def _text_to_boolean(self, value):
        normalized = self._normalize_text(value)
        if normalized in {"是", "true", "已确认", "1"}:
            return True
        if normalized in {"否", "false", "未确认", "0"}:
            return False
        return None

    def _evaluate_ingredient(self, operator, expected, payload):
        ingredients = payload["ingredients"]
        normalized = [
            self._normalize_text(item)
            for item in ingredients
        ]
        if operator in {"in", "not_in"}:
            expected_values = [
                self._normalize_text(item)
                for item in expected
            ]
            matched = any(
                item in expected_values
                for item in normalized
            )
            if operator == "not_in":
                matched = not matched
            return ("满足" if matched else "不满足"), ingredients
        target = self._normalize_text(expected)
        if operator == "contains":
            matched = any(target in item for item in normalized)
        elif operator == "not_contains":
            matched = not any(target in item for item in normalized)
        elif operator == "equals":
            matched = target in normalized
        else:
            matched = target not in normalized
        return ("满足" if matched else "不满足"), ingredients

    def _compare_scalar(self, actual, operator, expected):
        if operator == "equals":
            matched = actual == expected
        elif operator == "gte":
            matched = actual >= expected
        elif operator == "lte":
            matched = actual <= expected
        else:
            matched = expected[0] <= actual <= expected[1]
        return "满足" if matched else "不满足"

    def _compare_date(self, actual, operator, expected):
        if operator == "between":
            start = self._parse_date(expected[0], "条件开始日期")
            end = self._parse_date(expected[1], "条件结束日期")
            matched = start <= actual <= end
        else:
            target = self._parse_date(expected, "条件日期")
            if operator == "equals":
                matched = actual == target
            elif operator == "gte":
                matched = actual >= target
            else:
                matched = actual <= target
        return "满足" if matched else "不满足"

    def _compare_text(self, actual, operator, expected, code_mode):
        if code_mode:
            normalizer = self._normalize_code
        else:
            normalizer = self._normalize_text
        actual_value = normalizer(actual)
        if operator in {"in", "not_in"}:
            expected_values = [
                normalizer(item)
                for item in expected
            ]
            matched = actual_value in expected_values
            if operator == "not_in":
                matched = not matched
            return "满足" if matched else "不满足"
        expected_value = normalizer(expected)
        if operator == "contains":
            matched = expected_value in actual_value
        elif operator == "not_contains":
            matched = expected_value not in actual_value
        elif operator == "equals":
            matched = actual_value == expected_value
        elif operator == "not_equals":
            matched = actual_value != expected_value
        else:
            matched = actual_value.startswith(expected_value)
        return "满足" if matched else "不满足"

    def _describe_condition(self, condition, state):
        field_names = {
            "product_name": "样品名称",
            "candidate_code": "候选分类代码",
            "production_date": "生产日期",
            "ingredient": "配料",
            "ingredient_count": "配料数量",
            "verification": "用户核验",
        }
        operator_names = {
            "contains": "包含",
            "not_contains": "不包含",
            "equals": "等于",
            "not_equals": "不等于",
            "starts_with": "始于",
            "in": "属于集合",
            "not_in": "不属于集合",
            "gte": "不小于",
            "lte": "不大于",
            "between": "位于范围",
            "confirmed": "已明确确认",
        }
        value = condition["value"]
        if isinstance(value, list):
            rendered = "、".join(str(item) for item in value)
        else:
            rendered = str(value)
        field_name = field_names[condition["field"]]
        operator_name = operator_names[condition["operator"]]
        return f"{field_name}{operator_name}{rendered}：{state}"

    def _exclusion_reasons(
        self,
        additive_match,
        date_active,
        code_match,
        false_conditions,
        unknown_conditions,
        parent_covered,
    ):
        reasons = []
        if not additive_match:
            reasons.append("添加剂规范化名称不一致")
        if not date_active:
            reasons.append("规则在生产日期尚未生效")
        if code_match["rank"] == 0:
            reasons.append("食品分类代码不匹配")
        if false_conditions:
            reasons.append("存在不满足的适用条件")
        if unknown_conditions:
            reasons.append("存在无法确认的适用条件")
        if code_match["kind"] == "祖先" and not parent_covered:
            reasons.append("父级规则未被明确条件覆盖")
        return reasons

    def _sort_key(self, row):
        return (
            0 if row["自动候选"] == "是" else 1,
            -row["代码具体度"],
            -row["满足条件数"],
            -row["effective_ordinal"],
            row["规则标识"],
        )

    def _decision_key(self, row):
        return (
            row["代码具体度"],
            row["满足条件数"],
            row["effective_ordinal"],
        )

    def _make_decision(self, eligible, ranked):
        if not eligible:
            return {
                "status": "未匹配",
                "selected_rule": None,
                "unmet_conditions": self._collect_unresolved(ranked),
                "reason": "没有同时满足名称、日期、代码和条件的规则",
            }
        top = eligible[0]
        top_key = self._decision_key(top)
        tied = [
            row
            for row in eligible
            if self._decision_key(row) == top_key
        ]
        if len(tied) > 1:
            return {
                "status": "待人工复核",
                "selected_rule": None,
                "unmet_conditions": self._collect_unresolved(tied),
                "reason": "最高排序键存在并列规则，不能选择单一限量",
            }
        if top["未知条件数"] > 0:
            return {
                "status": "待人工复核",
                "selected_rule": None,
                "unmet_conditions": self._collect_unresolved([top]),
                "reason": "最高优先级规则含无法确认的适用条件",
            }
        return {
            "status": "已自动匹配",
            "selected_rule": self._selected_rule_view(top),
            "unmet_conditions": [],
            "reason": "最高优先级规则唯一且所有条件均已明确",
        }

    def _collect_unresolved(self, rows):
        values = []
        for row in rows:
            values.extend(row["未满足条件"])
            values.extend(row["待确认条件"])
            values.extend(row["排除原因"])
        return list(dict.fromkeys(values))

    def _selected_rule_view(self, row):
        return {
            "规则标识": row["规则标识"],
            "食品分类代码": row["食品分类代码"],
            "匹配候选代码": row["匹配候选代码"],
            "代码匹配类型": row["代码匹配类型"],
            "限量类型": row["限量类型"],
            "限量值": row["限量值"],
            "单位": row["单位"],
            "标准版本": row["标准版本"],
            "生效日期": row["生效日期"],
            "来源": row["来源"],
            "匹配得分": row["匹配得分"],
        }

    def _public_rows(self, ranked):
        rows = []
        for position, row in enumerate(ranked, 1):
            rows.append(
                {
                    "排序": position,
                    "规则标识": row["规则标识"],
                    "规则分类代码": row["食品分类代码"],
                    "匹配候选代码": row["匹配候选代码"],
                    "代码匹配类型": row["代码匹配类型"],
                    "添加剂名称匹配": row["添加剂名称匹配"],
                    "限量": self._format_limit(row),
                    "标准版本": row["标准版本"],
                    "生效日期": row["生效日期"],
                    "满足条件": (
                        f"{row['满足条件数']}/{row['条件总数']}"
                    ),
                    "未知条件数": row["未知条件数"],
                    "匹配得分": row["匹配得分"],
                    "自动候选": row["自动候选"],
                    "排除原因": self._join_or_none(
                        row["排除原因"]
                    ),
                }
            )
        return rows

    def _format_limit(self, row):
        if row["限量类型"] == "禁止使用":
            return "禁止使用"
        if row["限量类型"] == "按生产需要适量使用":
            return "按生产需要适量使用"
        return f"{row['限量值']} {row['单位']}"

    def _join_or_none(self, values):
        if values:
            return "；".join(values)
        return "无"

    def _build_series(self, ranked):
        series = [
            {
                "label": row["规则标识"],
                "value": float(row["匹配得分"]),
            }
            for row in ranked
        ]
        if not series:
            return [{"label": "无规则", "value": 0.0}]
        return series

    def _build_metrics(self, payload, ranked, eligible, decision):
        exact_count = sum(
            row["代码匹配类型"] == "完全"
            for row in ranked
        )
        ancestor_count = sum(
            row["代码匹配类型"] == "祖先"
            for row in ranked
        )
        wildcard_count = sum(
            row["代码匹配类型"] == "通配"
            for row in ranked
        )
        name_count = sum(
            row["添加剂名称匹配"] == "是"
            for row in ranked
        )
        active_count = sum(
            row["日期有效"] == "是"
            for row in ranked
        )
        return {
            "规则总数": len(ranked),
            "食品分类候选数": len(payload["food_candidates"]),
            "添加剂名称命中数": name_count,
            "生产日期有效规则数": active_count,
            "完全代码命中数": exact_count,
            "祖先代码命中数": ancestor_count,
            "通配代码命中数": wildcard_count,
            "自动候选数": len(eligible),
            "复核状态": decision["status"],
        }

    def _build_summary(self, decision, payload):
        method = (
            "先限定已确认食品分类候选并规范化添加剂名称，"
            "再按完全代码、祖先代码和通配范围匹配，随后按"
            "代码具体度、满足条件数及生效日期排序。"
        )
        if decision["status"] == "已自动匹配":
            selected = decision["selected_rule"]
            conclusion = (
                f"样品“{payload['sample_name']}”唯一命中规则"
                f"{selected['规则标识']}，限量结论为"
                f"{self._selected_limit_text(selected)}。"
            )
        elif decision["status"] == "待人工复核":
            conclusion = (
                "最高优先级候选无法唯一消歧，不选择单一限量，"
                "应依据候选矩阵完成人工复核。"
            )
        else:
            conclusion = (
                "未发现可自动采用的规则，不推断未知食品类别"
                "或法定限量。"
            )
        return conclusion + method + decision["reason"] + "。"

    def _selected_limit_text(self, selected):
        if selected["限量类型"] == "禁止使用":
            return "禁止使用"
        if selected["限量类型"] == "按生产需要适量使用":
            return "按生产需要适量使用"
        return (
            f"{selected['限量类型']}"
            f"{selected['限量值']} {selected['单位']}"
        )

    def _rule_snapshot(self, ranked):
        snapshots = []
        for row in ranked:
            rule = row["rule"]
            snapshots.append(
                {
                    "规则标识": row["规则标识"],
                    "食品分类代码": rule["food_code"],
                    "添加剂名称": rule["additive_name"],
                    "限量类型": rule["limit_type"],
                    "限量值": rule["limit_value"],
                    "单位": rule["unit"],
                    "标准版本": rule["standard_version"],
                    "生效日期": rule["effective_date"],
                    "来源": rule["source"],
                    "适用条件": copy.deepcopy(rule["conditions"]),
                    "条件判定": copy.deepcopy(row["条件结果"]),
                }
            )
        return snapshots
