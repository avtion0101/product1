import copy
import hashlib
import json
import unittest

from modules.report_trace.logic import Engine


class ReportTraceEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_example_calculation_and_expected_values(self):
        payload = self.engine.example()
        original = copy.deepcopy(payload)
        result = self.engine.calculate(payload)
        self.assertEqual(payload, original)
        self.assertEqual(result["metrics"]["记录总数"], 5)
        self.assertEqual(result["metrics"]["超量记录数"], 2)
        self.assertEqual(result["metrics"]["报告版本"], 1)
        self.assertEqual(result["metrics"]["报告状态"], "待复核")
        self.assertEqual(result["integrity"]["status"], "完整")
        self.assertEqual(len(result["rows"]), 5)
        self.assertEqual(result["rows"][0]["统一检测值"], "1200")
        self.assertEqual(result["rows"][0]["判定"], "超量")
        self.assertEqual(result["rows"][1]["判定"], "合格")
        self.assertEqual(result["rows"][3]["统一检测值"], "420")
        self.assertEqual(result["series"][0]["value"], 3)
        self.assertEqual(result["series"][1]["value"], 2)
        node = result["current_version"]
        digest_input = {
            "version": node["version"],
            "previous_digest": node["previous_digest"],
            "content": node["content"],
        }
        serialized = json.dumps(
            digest_input,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        expected_digest = hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()
        self.assertEqual(node["digest"], expected_digest)
        self.assertEqual(
            result["json_export"]["追溯摘要"]["sha256"],
            expected_digest,
        )

    def test_boundary_equal_limit_is_qualified(self):
        payload = self.engine.example()
        payload["batch_package"]["raw_inputs"] = [
            {
                "sample_id": "BOUNDARY-1",
                "food_category": "酱腌菜",
                "additive": "苯甲酸",
                "measured_value": 1.0,
                "measured_unit": "g/kg",
            }
        ]
        result = self.engine.calculate(payload)
        self.assertEqual(result["rows"][0]["统一检测值"], "1000")
        self.assertEqual(result["rows"][0]["占限量比例"], "100%")
        self.assertEqual(result["rows"][0]["判定"], "合格")
        self.assertEqual(result["metrics"]["超量记录数"], 0)

    def test_second_version_links_previous_digest(self):
        first_payload = self.engine.example()
        first_result = self.engine.calculate(first_payload)
        second_payload = self.engine.example()
        second_payload["previous_versions"] = [
            first_result["current_version"]
        ]
        second_payload["status_action"] = "通过"
        second_payload["review_opinion"] = "复核计算及规则快照无误。"
        second_payload["timestamp"] = "2026-09-23T10:00:00+08:00"
        second_result = self.engine.calculate(second_payload)
        current = second_result["current_version"]
        self.assertEqual(current["version"], 2)
        self.assertEqual(
            current["previous_digest"],
            first_result["current_version"]["digest"],
        )
        self.assertEqual(current["content"]["status"], "已核验")
        self.assertEqual(second_result["edges"], [[0, 1]])
        self.assertTrue(second_result["integrity"]["verified_allowed"])

    def test_tampered_chain_is_marked_abnormal(self):
        first_result = self.engine.calculate(self.engine.example())
        tampered = copy.deepcopy(first_result["current_version"])
        tampered["content"]["review_opinion"] = "内容已被篡改"
        payload = self.engine.example()
        payload["previous_versions"] = [tampered]
        payload["status_action"] = "通过"
        payload["timestamp"] = "2026-09-23T10:00:00+08:00"
        result = self.engine.calculate(payload)
        self.assertEqual(result["integrity"]["status"], "完整性异常")
        self.assertFalse(result["integrity"]["verified_allowed"])
        self.assertIsNone(result["current_version"])
        self.assertEqual(result["metrics"]["允许显示已核验"], "否")
        self.assertEqual(result["series"][1]["value"], 1)
        self.assertIn("摘要校验失败", result["summary"])

    def test_invalid_inputs_raise_value_error(self):
        cases = []
        empty_operator = self.engine.example()
        empty_operator["operator"] = ""
        cases.append(empty_operator)
        bad_factor = self.engine.example()
        bad_factor["batch_package"]["unit_conversions"][0]["factor"] = 10.0
        cases.append(bad_factor)
        missing_rule = self.engine.example()
        missing_rule["rule_snapshot"]["rules"] = missing_rule[
            "rule_snapshot"
        ]["rules"][:-1]
        cases.append(missing_rule)
        nan_value = self.engine.example()
        nan_value["batch_package"]["raw_inputs"][0]["measured_value"] = (
            float("nan")
        )
        cases.append(nan_value)
        no_timezone = self.engine.example()
        no_timezone["timestamp"] = "2026-09-23T09:18:09"
        cases.append(no_timezone)
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    self.engine.calculate(payload)


if __name__ == "__main__":
    unittest.main()
