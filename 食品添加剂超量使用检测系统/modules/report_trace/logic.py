import copy
import datetime
import hashlib
import json
import math
import re


class Engine:
    ACTION_CREATE = "新建"
    ACTION_SUBMIT = "提交"
    ACTION_APPROVE = "通过"
    ACTION_RETURN = "退回"
    ACTION_REVISE = "修订"

    ALLOWED_ACTIONS = (
        ACTION_CREATE,
        ACTION_SUBMIT,
        ACTION_APPROVE,
        ACTION_RETURN,
        ACTION_REVISE,
    )

    ACTION_STATUS = {
        ACTION_CREATE: "草稿",
        ACTION_SUBMIT: "待复核",
        ACTION_APPROVE: "已核验",
        ACTION_RETURN: "已退回",
        ACTION_REVISE: "待复核",
    }

    TERMINAL_STATUSES = (
        "已核验",
        "已退回",
    )

    ALLOWED_UNITS = (
        "mg/kg",
        "g/kg",
        "ug/kg",
    )

    UNIT_TO_MG = {
        "mg/kg": 1.0,
        "g/kg": 1000.0,
        "ug/kg": 0.001,
    }

    REQUIRED_PACKAGE_FIELDS = (
        "batch_id",
        "raw_inputs",
        "unit_conversions",
        "calculation_steps",
        "warnings",
    )

    REQUIRED_RAW_FIELDS = (
        "sample_id",
        "food_category",
        "additive",
        "measured_value",
        "measured_unit",
    )

    REQUIRED_CONVERSION_FIELDS = (
        "from_unit",
        "to_unit",
        "factor",
    )

    REQUIRED_SNAPSHOT_FIELDS = (
        "source",
        "version",
        "effective_date",
        "rules",
    )

    REQUIRED_RULE_FIELDS = (
        "rule_id",
        "food_category",
        "additive",
        "max_value",
        "unit",
    )

    REQUIRED_NODE_FIELDS = (
        "version",
        "previous_digest",
        "content",
        "digest",
    )

    REQUIRED_CONTENT_FIELDS = (
        "batch_package",
        "rule_snapshot",
        "operator",
        "review_opinion",
        "status_action",
        "status",
        "algorithm_version",
        "timestamp",
        "calculation_details",
        "warning_statement",
        "limitations",
    )

    DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")

    LIMITATION_TEXT = (
        "SHA-256摘要可发现内容变化，但不能证明录入事实真实，"
        "也不等同于数字签名或可信时间戳服务。"
    )

    WARNING_TEXT = (
        "初筛结果用于风险提示，结论应结合适用规则、"
        "检测方法和人工复核意见解释。"
    )

    def __init__(self):
        self._json_separators = (
            ",",
            ":",
        )

    def example(self):
        raw_inputs = [
            {
                "sample_id": "S-001",
                "food_category": "酱腌菜",
                "additive": "苯甲酸",
                "measured_value": 1.20,
                "measured_unit": "g/kg",
            },
            {
                "sample_id": "S-002",
                "food_category": "酱腌菜",
                "additive": "山梨酸",
                "measured_value": 650.0,
                "measured_unit": "mg/kg",
            },
            {
                "sample_id": "S-003",
                "food_category": "碳酸饮料",
                "additive": "苯甲酸",
                "measured_value": 180.0,
                "measured_unit": "mg/kg",
            },
            {
                "sample_id": "S-004",
                "food_category": "蜜饯",
                "additive": "二氧化硫",
                "measured_value": 420000.0,
                "measured_unit": "ug/kg",
            },
            {
                "sample_id": "S-005",
                "food_category": "果酱",
                "additive": "山梨酸",
                "measured_value": 0.75,
                "measured_unit": "g/kg",
            },
        ]
        unit_conversions = [
            {
                "from_unit": "g/kg",
                "to_unit": "mg/kg",
                "factor": 1000.0,
            },
            {
                "from_unit": "ug/kg",
                "to_unit": "mg/kg",
                "factor": 0.001,
            },
        ]
        calculation_steps = [
            "按样品、食品类别和添加剂匹配规则",
            "依据显式单位换算记录统一计量单位",
            "计算检测值与最大允许量的比值",
            "比值大于1时标记为超量",
            "汇总报告内容并写入哈希链",
        ]
        warnings = [
            "检测值等于限量时按未超量处理",
            "未匹配规则的数据不得生成核验结论",
        ]
        rules = [
            {
                "rule_id": "R-BZ-001",
                "food_category": "酱腌菜",
                "additive": "苯甲酸",
                "max_value": 1000.0,
                "unit": "mg/kg",
            },
            {
                "rule_id": "R-SA-001",
                "food_category": "酱腌菜",
                "additive": "山梨酸",
                "max_value": 1000.0,
                "unit": "mg/kg",
            },
            {
                "rule_id": "R-BZ-002",
                "food_category": "碳酸饮料",
                "additive": "苯甲酸",
                "max_value": 200.0,
                "unit": "mg/kg",
            },
            {
                "rule_id": "R-SO2-001",
                "food_category": "蜜饯",
                "additive": "二氧化硫",
                "max_value": 350.0,
                "unit": "mg/kg",
            },
            {
                "rule_id": "R-SA-002",
                "food_category": "果酱",
                "additive": "山梨酸",
                "max_value": 1000.0,
                "unit": "mg/kg",
            },
        ]
        return {
            "batch_package": {
                "batch_id": "BATCH-20260923-001",
                "raw_inputs": raw_inputs,
                "unit_conversions": unit_conversions,
                "calculation_steps": calculation_steps,
                "warnings": warnings,
            },
            "rule_snapshot": {
                "source": "食品添加剂使用规则示例库",
                "version": "2026.09",
                "effective_date": "2026-09-01",
                "rules": rules,
            },
            "operator": "初筛员甲",
            "review_opinion": "原始记录齐全，提交复核。",
            "status_action": "提交",
            "algorithm_version": "report-trace-1.0.0",
            "timestamp": "2026-09-23T09:18:09+08:00",
            "previous_versions": [],
        }

    def validate(self, payload):
        self._require_dict(
            payload,
            "输入",
        )
        required = (
            "batch_package",
            "rule_snapshot",
            "operator",
            "review_opinion",
            "status_action",
            "algorithm_version",
            "timestamp",
            "previous_versions",
        )
        self._require_exact_fields(
            payload,
            required,
            "输入",
        )
        self._validate_package(
            payload["batch_package"],
        )
        self._validate_snapshot(
            payload["rule_snapshot"],
        )
        self._require_text(
            payload["operator"],
            "操作者",
            1,
            80,
        )
        self._require_text(
            payload["review_opinion"],
            "复核意见",
            1,
            500,
        )
        action = payload["status_action"]
        self._require_text(
            action,
            "状态动作",
            1,
            20,
        )
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError("状态动作不在允许范围内")
        self._require_text(
            payload["algorithm_version"],
            "算法版本",
            1,
            80,
        )
        self._parse_timestamp(
            payload["timestamp"],
            "时间戳",
        )
        versions = payload["previous_versions"]
        self._require_list(
            versions,
            "历史版本",
        )
        if len(versions) > 10000:
            raise ValueError("历史版本数量不能超过10000")
        for index, node in enumerate(versions):
            self._validate_node_structure(
                node,
                index,
            )
        self._validate_action_transition(
            action,
            versions,
        )
        self._validate_rule_coverage(
            payload["batch_package"],
            payload["rule_snapshot"],
        )
        return None

    def calculate(self, payload):
        self.validate(payload)
        working = copy.deepcopy(payload)
        chain_result = self._audit_chain(
            working["previous_versions"],
        )
        if not chain_result["valid"]:
            return self._build_integrity_failure(
                working,
                chain_result,
            )
        details = self._calculate_details(
            working["batch_package"],
            working["rule_snapshot"],
        )
        version = len(working["previous_versions"]) + 1
        previous_digest = ""
        if working["previous_versions"]:
            previous_digest = working[
                "previous_versions"
            ][-1]["digest"]
        status = self.ACTION_STATUS[
            working["status_action"]
        ]
        content = self._build_content(
            working,
            status,
            details,
        )
        node = self._build_node(
            version,
            previous_digest,
            content,
        )
        full_chain = copy.deepcopy(
            working["previous_versions"]
        )
        full_chain.append(node)
        final_audit = self._audit_chain(
            full_chain,
        )
        if not final_audit["valid"]:
            return self._build_integrity_failure(
                working,
                final_audit,
            )
        rows = self._build_rows(
            details,
        )
        series = self._build_series(
            details,
        )
        metrics = self._build_metrics(
            details,
            version,
            node["digest"],
            status,
        )
        edges = self._build_edges(
            full_chain,
        )
        export_data = self._build_export(
            node,
            full_chain,
            final_audit,
        )
        summary = self._build_summary(
            details,
            version,
            status,
        )
        return {
            "summary": summary,
            "metrics": metrics,
            "rows": rows,
            "series": series,
            "chart_title": "初筛报告版本追溯网络",
            "edges": edges,
            "version_nodes": self._build_version_nodes(
                full_chain,
            ),
            "current_version": node,
            "version_chain": full_chain,
            "integrity": final_audit,
            "json_export": export_data,
        }

    def _validate_package(self, package):
        self._require_dict(
            package,
            "批次计算包",
        )
        self._require_exact_fields(
            package,
            self.REQUIRED_PACKAGE_FIELDS,
            "批次计算包",
        )
        self._require_text(
            package["batch_id"],
            "批次号",
            1,
            100,
        )
        raw_inputs = package["raw_inputs"]
        self._require_list(
            raw_inputs,
            "原始输入",
        )
        if not raw_inputs:
            raise ValueError("原始输入不能为空")
        if len(raw_inputs) > 10000:
            raise ValueError("原始输入不能超过10000条")
        sample_keys = set()
        for index, record in enumerate(raw_inputs):
            self._validate_raw_record(
                record,
                index,
            )
            key = (
                record["sample_id"],
                record["food_category"],
                record["additive"],
            )
            if key in sample_keys:
                raise ValueError("原始输入存在重复样品检测项")
            sample_keys.add(key)
        conversions = package["unit_conversions"]
        self._require_list(
            conversions,
            "单位换算",
        )
        conversion_keys = set()
        for index, conversion in enumerate(conversions):
            self._validate_conversion(
                conversion,
                index,
            )
            key = (
                conversion["from_unit"],
                conversion["to_unit"],
            )
            if key in conversion_keys:
                raise ValueError("单位换算存在重复方向")
            conversion_keys.add(key)
        steps = package["calculation_steps"]
        self._validate_text_list(
            steps,
            "计算步骤",
            1,
            100,
            300,
        )
        warnings = package["warnings"]
        self._validate_text_list(
            warnings,
            "预警声明",
            1,
            100,
            500,
        )

    def _validate_raw_record(self, record, index):
        name = "原始输入第%d条" % (index + 1)
        self._require_dict(
            record,
            name,
        )
        self._require_exact_fields(
            record,
            self.REQUIRED_RAW_FIELDS,
            name,
        )
        self._require_text(
            record["sample_id"],
            name + "样品编号",
            1,
            100,
        )
        self._require_text(
            record["food_category"],
            name + "食品类别",
            1,
            100,
        )
        self._require_text(
            record["additive"],
            name + "添加剂",
            1,
            100,
        )
        self._require_number(
            record["measured_value"],
            name + "检测值",
            0.0,
            1000000000.0,
        )
        unit = record["measured_unit"]
        self._require_unit(
            unit,
            name + "检测单位",
        )

    def _validate_conversion(self, conversion, index):
        name = "单位换算第%d条" % (index + 1)
        self._require_dict(
            conversion,
            name,
        )
        self._require_exact_fields(
            conversion,
            self.REQUIRED_CONVERSION_FIELDS,
            name,
        )
        from_unit = conversion["from_unit"]
        to_unit = conversion["to_unit"]
        self._require_unit(
            from_unit,
            name + "原单位",
        )
        self._require_unit(
            to_unit,
            name + "目标单位",
        )
        if from_unit == to_unit:
            raise ValueError(name + "原单位与目标单位不能相同")
        factor = conversion["factor"]
        self._require_number(
            factor,
            name + "换算系数",
            0.000000001,
            1000000000.0,
        )
        expected = (
            self.UNIT_TO_MG[from_unit]
            / self.UNIT_TO_MG[to_unit]
        )
        if not math.isclose(
            factor,
            expected,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError(name + "换算系数与单位定义不一致")

    def _validate_snapshot(self, snapshot):
        self._require_dict(
            snapshot,
            "规则快照",
        )
        self._require_exact_fields(
            snapshot,
            self.REQUIRED_SNAPSHOT_FIELDS,
            "规则快照",
        )
        self._require_text(
            snapshot["source"],
            "规则来源",
            1,
            300,
        )
        self._require_text(
            snapshot["version"],
            "规则版本",
            1,
            100,
        )
        self._parse_date(
            snapshot["effective_date"],
            "规则生效日期",
        )
        rules = snapshot["rules"]
        self._require_list(
            rules,
            "规则列表",
        )
        if not rules:
            raise ValueError("规则列表不能为空")
        if len(rules) > 10000:
            raise ValueError("规则数量不能超过10000")
        rule_ids = set()
        rule_keys = set()
        for index, rule in enumerate(rules):
            self._validate_rule(
                rule,
                index,
            )
            rule_id = rule["rule_id"]
            key = (
                rule["food_category"],
                rule["additive"],
            )
            if rule_id in rule_ids:
                raise ValueError("规则编号不能重复")
            if key in rule_keys:
                raise ValueError("同一类别和添加剂只能有一条规则")
            rule_ids.add(rule_id)
            rule_keys.add(key)

    def _validate_rule(self, rule, index):
        name = "规则第%d条" % (index + 1)
        self._require_dict(
            rule,
            name,
        )
        self._require_exact_fields(
            rule,
            self.REQUIRED_RULE_FIELDS,
            name,
        )
        self._require_text(
            rule["rule_id"],
            name + "规则编号",
            1,
            100,
        )
        self._require_text(
            rule["food_category"],
            name + "食品类别",
            1,
            100,
        )
        self._require_text(
            rule["additive"],
            name + "添加剂",
            1,
            100,
        )
        self._require_number(
            rule["max_value"],
            name + "最大允许量",
            0.000000001,
            1000000000.0,
        )
        self._require_unit(
            rule["unit"],
            name + "规则单位",
        )

    def _validate_node_structure(self, node, index):
        name = "历史版本第%d个节点" % (index + 1)
        self._require_dict(
            node,
            name,
        )
        self._require_exact_fields(
            node,
            self.REQUIRED_NODE_FIELDS,
            name,
        )
        version = node["version"]
        self._require_integer(
            version,
            name + "版本号",
            1,
            1000000,
        )
        previous_digest = node["previous_digest"]
        if not isinstance(previous_digest, str):
            raise ValueError(name + "前序摘要必须是字符串")
        if previous_digest:
            self._require_digest(
                previous_digest,
                name + "前序摘要",
            )
        self._validate_content_structure(
            node["content"],
            name + "内容",
        )
        self._require_digest(
            node["digest"],
            name + "摘要",
        )

    def _validate_content_structure(self, content, name):
        self._require_dict(
            content,
            name,
        )
        self._require_exact_fields(
            content,
            self.REQUIRED_CONTENT_FIELDS,
            name,
        )
        self._validate_package(
            content["batch_package"],
        )
        self._validate_snapshot(
            content["rule_snapshot"],
        )
        self._require_text(
            content["operator"],
            name + "操作者",
            1,
            80,
        )
        self._require_text(
            content["review_opinion"],
            name + "复核意见",
            1,
            500,
        )
        action = content["status_action"]
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(name + "状态动作无效")
        status = content["status"]
        expected_status = self.ACTION_STATUS[action]
        if status != expected_status:
            raise ValueError(name + "状态与动作不一致")
        self._require_text(
            content["algorithm_version"],
            name + "算法版本",
            1,
            80,
        )
        self._parse_timestamp(
            content["timestamp"],
            name + "时间戳",
        )
        details = content["calculation_details"]
        self._require_list(
            details,
            name + "计算明细",
        )
        if not details:
            raise ValueError(name + "计算明细不能为空")
        for detail_index, detail in enumerate(details):
            self._validate_detail(
                detail,
                detail_index,
                name,
            )
        self._validate_text_list(
            content["warning_statement"],
            name + "预警声明",
            1,
            100,
            500,
        )
        if content["limitations"] != self.LIMITATION_TEXT:
            raise ValueError(name + "局限性声明不完整")

    def _validate_detail(self, detail, index, prefix):
        name = prefix + "计算明细第%d条" % (index + 1)
        expected_fields = (
            "sample_id",
            "food_category",
            "additive",
            "original_value",
            "original_unit",
            "conversion_factor",
            "normalized_value",
            "rule_id",
            "limit_value",
            "limit_unit",
            "ratio",
            "result",
            "calculation_expression",
        )
        self._require_dict(
            detail,
            name,
        )
        self._require_exact_fields(
            detail,
            expected_fields,
            name,
        )
        for field in (
            "sample_id",
            "food_category",
            "additive",
            "rule_id",
            "calculation_expression",
        ):
            self._require_text(
                detail[field],
                name + field,
                1,
                500,
            )
        self._require_unit(
            detail["original_unit"],
            name + "原始单位",
        )
        self._require_unit(
            detail["limit_unit"],
            name + "限量单位",
        )
        for field in (
            "original_value",
            "conversion_factor",
            "normalized_value",
            "limit_value",
            "ratio",
        ):
            self._require_number(
                detail[field],
                name + field,
                0.0,
                1000000000000.0,
            )
        if detail["conversion_factor"] <= 0.0:
            raise ValueError(name + "换算系数必须大于0")
        if detail["limit_value"] <= 0.0:
            raise ValueError(name + "限量必须大于0")
        if detail["result"] not in ("合格", "超量"):
            raise ValueError(name + "判定结果无效")

    def _validate_rule_coverage(self, package, snapshot):
        rule_map = {}
        for rule in snapshot["rules"]:
            key = (
                rule["food_category"],
                rule["additive"],
            )
            rule_map[key] = rule
        conversion_map = self._conversion_map(
            package["unit_conversions"],
        )
        for record in package["raw_inputs"]:
            key = (
                record["food_category"],
                record["additive"],
            )
            if key not in rule_map:
                raise ValueError(
                    "样品%s未匹配到适用规则"
                    % record["sample_id"]
                )
            rule = rule_map[key]
            from_unit = record["measured_unit"]
            to_unit = rule["unit"]
            if from_unit != to_unit:
                conversion_key = (
                    from_unit,
                    to_unit,
                )
                if conversion_key not in conversion_map:
                    raise ValueError(
                        "样品%s缺少%s到%s的单位换算"
                        % (
                            record["sample_id"],
                            from_unit,
                            to_unit,
                        )
                    )

    def _validate_action_transition(self, action, versions):
        if not versions:
            if action not in (
                self.ACTION_CREATE,
                self.ACTION_SUBMIT,
            ):
                raise ValueError("首个版本只能执行新建或提交动作")
            return
        previous_status = versions[-1]["content"]["status"]
        if action == self.ACTION_CREATE:
            raise ValueError("已有版本时不能再次执行新建动作")
        if action in (
            self.ACTION_APPROVE,
            self.ACTION_RETURN,
        ):
            if previous_status != "待复核":
                raise ValueError("仅待复核版本可执行通过或退回")
        if action == self.ACTION_REVISE:
            if previous_status not in self.TERMINAL_STATUSES:
                raise ValueError("仅通过或退回后的报告可生成修订版本")
        if action == self.ACTION_SUBMIT:
            if previous_status != "草稿":
                raise ValueError("仅草稿版本可直接提交")

    def _audit_chain(self, versions):
        rows = []
        previous_digest = ""
        expected_version = 1
        valid = True
        first_error = ""
        previous_time = None
        previous_batch = None
        for index, node in enumerate(versions):
            errors = []
            if node["version"] != expected_version:
                errors.append("版本序号不连续")
            if node["previous_digest"] != previous_digest:
                errors.append("前序摘要引用不一致")
            recalculated = self._digest_node_fields(
                node["version"],
                node["previous_digest"],
                node["content"],
            )
            if node["digest"] != recalculated:
                errors.append("内容摘要校验失败")
            node_time = self._parse_timestamp(
                node["content"]["timestamp"],
                "历史时间戳",
            )
            if previous_time is not None:
                if node_time <= previous_time:
                    errors.append("版本时间戳未严格递增")
            batch_id = node[
                "content"
            ]["batch_package"]["batch_id"]
            if previous_batch is not None:
                if batch_id != previous_batch:
                    errors.append("版本链批次号发生变化")
            node_valid = not errors
            if not node_valid:
                valid = False
                if not first_error:
                    first_error = (
                        "第%d个节点：%s"
                        % (
                            index + 1,
                            "、".join(errors),
                        )
                    )
            rows.append(
                {
                    "版本号": node["version"],
                    "摘要": node["digest"],
                    "前序摘要": node["previous_digest"] or "创世节点",
                    "校验结果": "正常" if node_valid else "异常",
                    "异常原因": "、".join(errors) or "无",
                }
            )
            previous_digest = node["digest"]
            expected_version += 1
            previous_time = node_time
            previous_batch = batch_id
        return {
            "valid": valid,
            "status": "完整" if valid else "完整性异常",
            "verified_allowed": valid,
            "checked_nodes": len(versions),
            "first_error": first_error,
            "audit_rows": rows,
        }

    def _calculate_details(self, package, snapshot):
        rule_map = {}
        for rule in snapshot["rules"]:
            key = (
                rule["food_category"],
                rule["additive"],
            )
            rule_map[key] = rule
        conversion_map = self._conversion_map(
            package["unit_conversions"],
        )
        details = []
        for record in package["raw_inputs"]:
            key = (
                record["food_category"],
                record["additive"],
            )
            rule = rule_map[key]
            from_unit = record["measured_unit"]
            to_unit = rule["unit"]
            factor = 1.0
            if from_unit != to_unit:
                factor = conversion_map[
                    (
                        from_unit,
                        to_unit,
                    )
                ]
            normalized = record["measured_value"] * factor
            ratio = normalized / rule["max_value"]
            result = "超量" if ratio > 1.0 else "合格"
            expression = (
                "%s %s × %s = %s %s；%s ÷ %s = %s"
                % (
                    self._short_number(record["measured_value"]),
                    from_unit,
                    self._short_number(factor),
                    self._short_number(normalized),
                    to_unit,
                    self._short_number(normalized),
                    self._short_number(rule["max_value"]),
                    self._short_number(ratio),
                )
            )
            details.append(
                {
                    "sample_id": record["sample_id"],
                    "food_category": record["food_category"],
                    "additive": record["additive"],
                    "original_value": record["measured_value"],
                    "original_unit": from_unit,
                    "conversion_factor": factor,
                    "normalized_value": normalized,
                    "rule_id": rule["rule_id"],
                    "limit_value": rule["max_value"],
                    "limit_unit": to_unit,
                    "ratio": ratio,
                    "result": result,
                    "calculation_expression": expression,
                }
            )
        return details

    def _build_content(self, payload, status, details):
        warnings = copy.deepcopy(
            payload["batch_package"]["warnings"]
        )
        if self.WARNING_TEXT not in warnings:
            warnings.append(self.WARNING_TEXT)
        return {
            "batch_package": copy.deepcopy(
                payload["batch_package"]
            ),
            "rule_snapshot": copy.deepcopy(
                payload["rule_snapshot"]
            ),
            "operator": payload["operator"],
            "review_opinion": payload["review_opinion"],
            "status_action": payload["status_action"],
            "status": status,
            "algorithm_version": payload["algorithm_version"],
            "timestamp": payload["timestamp"],
            "calculation_details": details,
            "warning_statement": warnings,
            "limitations": self.LIMITATION_TEXT,
        }

    def _build_node(self, version, previous_digest, content):
        digest = self._digest_node_fields(
            version,
            previous_digest,
            content,
        )
        return {
            "version": version,
            "previous_digest": previous_digest,
            "content": content,
            "digest": digest,
        }

    def _digest_node_fields(self, version, previous_digest, content):
        digest_payload = {
            "version": version,
            "previous_digest": previous_digest,
            "content": content,
        }
        serialized = json.dumps(
            digest_payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=self._json_separators,
        )
        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def _build_rows(self, details):
        rows = []
        for detail in details:
            rows.append(
                {
                    "样品编号": detail["sample_id"],
                    "食品类别": detail["food_category"],
                    "添加剂": detail["additive"],
                    "原始检测值": self._short_number(
                        detail["original_value"]
                    ),
                    "原始单位": detail["original_unit"],
                    "换算系数": self._short_number(
                        detail["conversion_factor"]
                    ),
                    "统一检测值": self._short_number(
                        detail["normalized_value"]
                    ),
                    "限量值": self._short_number(
                        detail["limit_value"]
                    ),
                    "限量单位": detail["limit_unit"],
                    "占限量比例": self._short_number(
                        detail["ratio"] * 100.0
                    ) + "%",
                    "规则编号": detail["rule_id"],
                    "判定": detail["result"],
                    "计算过程": detail["calculation_expression"],
                }
            )
        return rows

    def _build_series(self, details):
        qualified = 0
        excessive = 0
        for detail in details:
            if detail["result"] == "超量":
                excessive += 1
            else:
                qualified += 1
        return [
            {
                "label": "合格记录",
                "value": qualified,
            },
            {
                "label": "超量记录",
                "value": excessive,
            },
        ]

    def _build_metrics(self, details, version, digest, status):
        excessive = sum(
            1
            for detail in details
            if detail["result"] == "超量"
        )
        maximum_ratio = max(
            detail["ratio"]
            for detail in details
        )
        return {
            "报告版本": version,
            "记录总数": len(details),
            "超量记录数": excessive,
            "最高限量比": self._short_number(maximum_ratio),
            "报告状态": status,
            "完整性状态": "完整",
            "摘要前缀": digest[:16],
        }

    def _build_edges(self, chain):
        edges = []
        for index in range(len(chain) - 1):
            edges.append(
                [
                    index,
                    index + 1,
                ]
            )
        return edges

    def _build_version_nodes(self, chain):
        nodes = []
        for node in chain:
            nodes.append(
                {
                    "版本号": node["version"],
                    "状态": node["content"]["status"],
                    "动作": node["content"]["status_action"],
                    "操作者": node["content"]["operator"],
                    "时间戳": node["content"]["timestamp"],
                    "摘要前缀": node["digest"][:16],
                }
            )
        return nodes

    def _build_export(self, node, chain, audit):
        content = node["content"]
        return {
            "报告版本": node["version"],
            "原始输入": copy.deepcopy(
                content["batch_package"]["raw_inputs"]
            ),
            "单位换算": copy.deepcopy(
                content["batch_package"]["unit_conversions"]
            ),
            "规则来源": {
                "source": content["rule_snapshot"]["source"],
                "version": content["rule_snapshot"]["version"],
                "effective_date": content[
                    "rule_snapshot"
                ]["effective_date"],
                "rules": copy.deepcopy(
                    content["rule_snapshot"]["rules"]
                ),
            },
            "计算步骤": copy.deepcopy(
                content["batch_package"]["calculation_steps"]
            ),
            "计算中间值": copy.deepcopy(
                content["calculation_details"]
            ),
            "预警声明": copy.deepcopy(
                content["warning_statement"]
            ),
            "复核意见": content["review_opinion"],
            "操作者": content["operator"],
            "状态动作": content["status_action"],
            "报告状态": content["status"],
            "算法版本": content["algorithm_version"],
            "时间戳": content["timestamp"],
            "追溯摘要": {
                "sha256": node["digest"],
                "previous_sha256": (
                    node["previous_digest"] or "创世节点"
                ),
                "chain_length": len(chain),
                "integrity_status": audit["status"],
            },
            "局限性": content["limitations"],
        }

    def _build_summary(self, details, version, status):
        excessive = sum(
            1
            for detail in details
            if detail["result"] == "超量"
        )
        return (
            "第%d版报告已按固定字段顺序序列化并计算SHA-256摘要，"
            "版本链校验完整；共核对%d条检测记录，其中%d条超量，"
            "当前状态为%s。判定方法为单位统一后计算检测值与限量值比值，"
            "比值大于1判为超量。"
            % (
                version,
                len(details),
                excessive,
                status,
            )
        )

    def _build_integrity_failure(self, payload, audit):
        rows = audit["audit_rows"]
        if not rows:
            rows = [
                {
                    "版本号": "无",
                    "摘要": "无",
                    "前序摘要": "无",
                    "校验结果": "异常",
                    "异常原因": audit["first_error"] or "链校验失败",
                }
            ]
        normal_count = sum(
            1
            for row in rows
            if row["校验结果"] == "正常"
        )
        abnormal_count = len(rows) - normal_count
        return {
            "summary": (
                "历史报告链存在完整性异常，已禁止追加新版本，"
                "且不得将报告显示为已核验版本。异常原因：%s。"
                % (audit["first_error"] or "未知链错误")
            ),
            "metrics": {
                "已检查节点数": audit["checked_nodes"],
                "正常节点数": normal_count,
                "异常节点数": abnormal_count,
                "完整性状态": "完整性异常",
                "允许显示已核验": "否",
            },
            "rows": rows,
            "series": [
                {
                    "label": "正常节点",
                    "value": normal_count,
                },
                {
                    "label": "异常节点",
                    "value": abnormal_count,
                },
            ],
            "chart_title": "初筛报告版本链完整性检查",
            "edges": self._build_edges(
                payload["previous_versions"]
            ),
            "version_nodes": self._build_version_nodes(
                payload["previous_versions"]
            ),
            "current_version": None,
            "version_chain": copy.deepcopy(
                payload["previous_versions"]
            ),
            "integrity": audit,
            "json_export": {
                "原始输入": copy.deepcopy(
                    payload["batch_package"]["raw_inputs"]
                ),
                "单位换算": copy.deepcopy(
                    payload["batch_package"]["unit_conversions"]
                ),
                "规则来源": copy.deepcopy(
                    payload["rule_snapshot"]
                ),
                "计算步骤": copy.deepcopy(
                    payload["batch_package"]["calculation_steps"]
                ),
                "预警声明": copy.deepcopy(
                    payload["batch_package"]["warnings"]
                ),
                "复核意见": payload["review_opinion"],
                "追溯摘要": {
                    "integrity_status": "完整性异常",
                    "verified_allowed": False,
                    "first_error": audit["first_error"],
                },
                "局限性": self.LIMITATION_TEXT,
            },
        }

    def _conversion_map(self, conversions):
        result = {}
        for conversion in conversions:
            key = (
                conversion["from_unit"],
                conversion["to_unit"],
            )
            result[key] = conversion["factor"]
        return result

    def _require_dict(self, value, name):
        if not isinstance(value, dict):
            raise ValueError(name + "必须是对象")

    def _require_list(self, value, name):
        if not isinstance(value, list):
            raise ValueError(name + "必须是数组")

    def _require_exact_fields(self, value, fields, name):
        expected = set(fields)
        actual = set(value.keys())
        missing = expected - actual
        extra = actual - expected
        if missing:
            raise ValueError(
                name + "缺少字段：" + "、".join(sorted(missing))
            )
        if extra:
            raise ValueError(
                name + "包含未知字段：" + "、".join(sorted(extra))
            )

    def _require_text(self, value, name, minimum, maximum):
        if not isinstance(value, str):
            raise ValueError(name + "必须是字符串")
        if value != value.strip():
            raise ValueError(name + "首尾不能包含空白字符")
        length = len(value)
        if length < minimum:
            raise ValueError(name + "不能为空")
        if length > maximum:
            raise ValueError(name + "长度超出限制")
        if "\x00" in value:
            raise ValueError(name + "不能包含空字符")

    def _require_number(self, value, name, minimum, maximum):
        if isinstance(value, bool):
            raise ValueError(name + "必须是数字")
        if not isinstance(value, (int, float)):
            raise ValueError(name + "必须是数字")
        if not math.isfinite(value):
            raise ValueError(name + "必须是有限数字")
        if value < minimum:
            raise ValueError(name + "低于允许范围")
        if value > maximum:
            raise ValueError(name + "高于允许范围")

    def _require_integer(self, value, name, minimum, maximum):
        if isinstance(value, bool):
            raise ValueError(name + "必须是整数")
        if not isinstance(value, int):
            raise ValueError(name + "必须是整数")
        if value < minimum or value > maximum:
            raise ValueError(name + "超出允许范围")

    def _require_unit(self, value, name):
        self._require_text(
            value,
            name,
            1,
            20,
        )
        if value not in self.ALLOWED_UNITS:
            raise ValueError(name + "不是受支持的单位")

    def _require_digest(self, value, name):
        if not isinstance(value, str):
            raise ValueError(name + "必须是字符串")
        if not self.DIGEST_PATTERN.fullmatch(value):
            raise ValueError(name + "必须是64位小写十六进制SHA-256")

    def _validate_text_list(
        self,
        value,
        name,
        minimum_items,
        maximum_items,
        maximum_length,
    ):
        self._require_list(
            value,
            name,
        )
        if len(value) < minimum_items:
            raise ValueError(name + "不能为空")
        if len(value) > maximum_items:
            raise ValueError(name + "条目过多")
        seen = set()
        for index, item in enumerate(value):
            item_name = name + "第%d项" % (index + 1)
            self._require_text(
                item,
                item_name,
                1,
                maximum_length,
            )
            if item in seen:
                raise ValueError(name + "不能包含重复项")
            seen.add(item)

    def _parse_date(self, value, name):
        self._require_text(
            value,
            name,
            10,
            10,
        )
        try:
            parsed = datetime.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(name + "必须是YYYY-MM-DD格式") from exc
        return parsed

    def _parse_timestamp(self, value, name):
        self._require_text(
            value,
            name,
            20,
            40,
        )
        try:
            parsed = datetime.datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(name + "必须是ISO 8601格式") from exc
        if parsed.tzinfo is None:
            raise ValueError(name + "必须包含时区偏移")
        offset = parsed.utcoffset()
        if offset is None:
            raise ValueError(name + "必须包含有效时区偏移")
        return parsed

    def _short_number(self, value):
        if not math.isfinite(float(value)):
            raise ValueError("输出数字必须有限")
        text = format(float(value), ".12g")
        if text == "-0":
            return "0"
        return text
