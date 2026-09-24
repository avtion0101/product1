import copy
import json
import unittest

from modules.classification_match.logic import Engine


class ClassificationMatchEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_example_and_exact_rule_selection(self):
        payload = self.engine.example()
        original = copy.deepcopy(payload)
        result = self.engine.calculate(payload)
        self.assertEqual(payload, original)
        self.assertEqual(result["review_status"], "已自动匹配")
        self.assertEqual(
            result["selected_rule"]["规则标识"],
            "R-001",
        )
        self.assertEqual(result["selected_rule"]["限量值"], 0.5)
        self.assertEqual(result["metrics"]["规则总数"], 5)
        self.assertEqual(result["metrics"]["完全代码命中数"], 3)
        self.assertEqual(result["metrics"]["祖先代码命中数"], 1)
        self.assertEqual(result["metrics"]["通配代码命中数"], 1)
        self.assertEqual(result["series"][0]["label"], "R-001")
        self.assertEqual(result["series"][0]["value"], 331.0)
        self.assertGreaterEqual(len(result["rows"]), 5)
        self.assertEqual(
            result["matching_scope"],
            [{"代码": "01.02.01", "名称": "发酵乳", "已确认": "是"}],
        )
        json.dumps(result, ensure_ascii=False, allow_nan=False)

    def test_same_priority_tie_requires_manual_review(self):
        payload = self.engine.example()
        payload["rules"] = [copy.deepcopy(payload["rules"][0])]
        second = copy.deepcopy(payload["rules"][0])
        second["rule_id"] = "R-TIE"
        second["limit_value"] = 0.6
        second["source"] = "用户录入规则集D第1条"
        payload["rules"].append(second)
        result = self.engine.calculate(payload)
        self.assertEqual(result["review_status"], "待人工复核")
        self.assertIsNone(result["selected_rule"])
        self.assertEqual(result["metrics"]["自动候选数"], 2)
        self.assertEqual(result["rows"][0]["匹配得分"], 331)
        self.assertEqual(result["rows"][1]["匹配得分"], 331)
        self.assertIn("并列", result["summary"])

    def test_parent_rule_requires_explicit_covering_condition(self):
        payload = self.engine.example()
        parent = copy.deepcopy(payload["rules"][1])
        parent["conditions"] = []
        payload["rules"] = [parent]
        result = self.engine.calculate(payload)
        self.assertEqual(result["review_status"], "未匹配")
        self.assertEqual(result["metrics"]["自动候选数"], 0)
        self.assertEqual(result["rows"][0]["代码匹配类型"], "祖先")
        self.assertIn(
            "父级规则未被明确条件覆盖",
            result["rows"][0]["排除原因"],
        )

    def test_parent_rule_with_confirmed_condition_is_candidate(self):
        payload = self.engine.example()
        payload["rules"] = [copy.deepcopy(payload["rules"][1])]
        result = self.engine.calculate(payload)
        self.assertEqual(result["review_status"], "已自动匹配")
        self.assertEqual(
            result["selected_rule"]["代码匹配类型"],
            "祖先",
        )
        self.assertEqual(result["selected_rule"]["规则标识"], "R-002")

    def test_future_rule_is_not_effective_on_production_date(self):
        payload = self.engine.example()
        payload["rules"] = [copy.deepcopy(payload["rules"][4])]
        result = self.engine.calculate(payload)
        self.assertEqual(result["review_status"], "未匹配")
        self.assertEqual(result["rows"][0]["自动候选"], "否")
        self.assertIn("尚未生效", result["rows"][0]["排除原因"])
        self.assertEqual(result["series"][0]["value"], 0.0)

    def test_invalid_missing_required_rule_field(self):
        payload = self.engine.example()
        del payload["rules"][0]["source"]
        with self.assertRaisesRegex(ValueError, "缺少字段.*source"):
            self.engine.validate(payload)

    def test_invalid_limit_and_date_boundaries(self):
        payload = self.engine.example()
        payload["rules"][0]["limit_value"] = -0.1
        with self.assertRaisesRegex(ValueError, "不得为负数"):
            self.engine.calculate(payload)
        payload = self.engine.example()
        payload["production_date"] = "2026-02-30"
        with self.assertRaisesRegex(ValueError, "不是有效日期"):
            self.engine.validate(payload)

    def test_unknown_verification_causes_review(self):
        payload = self.engine.example()
        payload["rules"] = [copy.deepcopy(payload["rules"][0])]
        payload["verifications"]["含水果配料"] = None
        result = self.engine.calculate(payload)
        self.assertEqual(result["review_status"], "待人工复核")
        self.assertIsNone(result["selected_rule"])
        self.assertEqual(result["rows"][0]["未知条件数"], 1)
        self.assertIn("未知", result["unmet_conditions"][0])

    def test_unconfirmed_candidates_are_all_considered(self):
        payload = self.engine.example()
        for candidate in payload["food_candidates"]:
            candidate["confirmed"] = False
        payload["rules"] = [copy.deepcopy(payload["rules"][0])]
        result = self.engine.calculate(payload)
        self.assertEqual(result["review_status"], "已自动匹配")
        self.assertEqual(
            result["selected_rule"]["匹配候选代码"],
            "01.02.01",
        )

    def test_multiple_confirmed_candidates_are_invalid(self):
        payload = self.engine.example()
        payload["food_candidates"][1]["confirmed"] = True
        with self.assertRaisesRegex(ValueError, "最多只能确认一个"):
            self.engine.validate(payload)

    def test_input_and_output_are_json_safe(self):
        payload = self.engine.example()
        result = self.engine.calculate(payload)
        encoded = json.dumps(
            result,
            ensure_ascii=False,
            allow_nan=False,
        )
        self.assertIn("食品分类规则匹配候选矩阵", encoded)
        self.assertGreater(len(result["series"]), 0)
        self.assertEqual(len(result["rows"]), len(payload["rules"]))


if __name__ == "__main__":
    unittest.main()
