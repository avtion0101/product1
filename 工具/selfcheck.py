"""Deterministic tests. No model calls or fabricated approval claims."""
import copy
import ast
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / ".packages"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from contracts import validate_name, validate_plan, read_json, write_json
from codex_client import CompatibleAPIClient, _json_text, _message_text, provider_config
from documents import build_code, display_chunks, distill, prepare_template
from pipeline import seed_project, install_module, verify_module, verify_captures, child, package

ROOT = HERE.parent
TEST_NAME = "仓储拣选与调度联调样例"
TITLES = ["订单优先排序", "库存缺口评估", "货位距离测算", "波次容量校验", "人员负载评估",
          "设备工时测算", "异常阈值分析", "批次质量评分", "配送成本核算", "交付风险汇总"]


def sample_plan():
    plan = {"name": TEST_NAME, "domain": "仓储业务", "purpose": "验证本地生成工具的完整界面与资料输出链路",
            "main_features": "本软件用于仓储业务流程的本地演示与工具联调，支持数据准备、计算结果查看、提交复核和结果归档。"
                + "".join(f"{title}模块提供参数输入与样例载入，输入校验后执行本地计算，显示明细与指标。操作员提交记录，管理员复核通过或退回，结果可以导出JSON并通过历史记录恢复。" for title in TITLES),
            "technical_features": "采用Python、PyQt6和SQLite，提供输入校验、事务存储、版本检查、权限复核及本地结果可视化。",
            "modules": []}
    for i, title in enumerate(TITLES):
        plan["modules"].append({"id": f"demo_{i}", "title": title,
            "purpose": f"{title}的界面、存储与资料流程联调",
            "algorithm": "对样例中的数量与系数执行逐项乘积和汇总，此算法仅用于联调，不代表标题所指完整业务算法",
            "rules": ["数量不得为负数，系数必须大于零", "结果保存为草稿，提交后由管理员复核"],
            "input_description": "records中填写名称和数量，factor填写大于零的系数",
            "output_description": "显示逐项乘积、总量、排序结果与条形图",
            "limitations": "此项目仅为生成器联调，不可作为真实业务软件交付",
            "visualization": "bars" if i % 2 == 0 else "line"})
    return plan


def sample_bundle(i):
    source = f'''
import math

class Engine:
    def example(self):
        return {{"factor": {i+1}, "records": [{{"name": "样本"+str(n), "quantity": n*2}} for n in range(1, 7)]}}

    def validate(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("输入须为对象")
        records = payload.get("records")
        factor = payload.get("factor")
        if not isinstance(factor, (int, float)) or isinstance(factor, bool) or not math.isfinite(factor) or factor <= 0:
            raise ValueError("系数须为正数")
        if not isinstance(records, list) or not records:
            raise ValueError("记录不能为空")
        for row in records:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str):
                raise ValueError("记录须有名称")
            quantity = row.get("quantity")
            if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not math.isfinite(quantity) or quantity < 0:
                raise ValueError("数量不能为负")

    def calculate(self, payload):
        self.validate(payload)
        rows = [{{"名称":r["name"], "计算值":round(r["quantity"]*payload["factor"], 2)}} for r in payload["records"]]
        total = sum(r["计算值"] for r in rows)
        return {{"summary": "已完成联调用乘积汇总计算", "metrics": {{"合计": total, "条数":len(rows)}},
                "rows": rows, "series":[{{"label":r["名称"],"value":r["计算值"]}} for r in rows],
                "chart_title": "联调样例计算结果"}}
'''
    tests = f'''
import unittest
from modules.demo_{i}.logic import Engine
class EngineTests(unittest.TestCase):
    def test_expected_value(self):
        e=Engine()
        self.assertEqual(e.calculate(e.example())["metrics"]["合计"], {42*(i+1)})
    def test_invalid(self):
        with self.assertRaises(ValueError):
            Engine().calculate({{"factor":0,"records":[]}})
    def test_zero(self):
        self.assertEqual(Engine().calculate({{"factor":1,"records":[{{"name":"零","quantity":0}}]}})["metrics"]["合计"], 0)
'''
    return {"source": source, "tests": tests}


class ContractTests(unittest.TestCase):
    def runtime_store(self, path):
        tree = ast.parse((HERE / "templates/runtime.py").read_text(encoding="utf-8"))
        selected = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                    and node.name in ("stamp", "Store", "check_result")]
        namespace = {"Path": Path, "json": json, "hashlib": hashlib, "hmac": hmac,
                     "secrets": secrets, "sqlite3": sqlite3, "datetime": datetime}
        exec(compile(ast.Module(body=selected, type_ignores=[]), "<runtime-core>", "exec"), namespace)
        return namespace["Store"](path)

    def test_permissions_and_transitions(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.runtime_store(Path(temp) / "state.db")
            try:
                store.register("worker", "Password123!")
                store.login("worker", "Password123!")
                rid = store.save_result("module", {}, {})
                store.transition(rid, "已提交", 1)
                with self.assertRaises(PermissionError):
                    store.transition(rid, "已通过", 2)
                store.login("admin", "Admin123!")
                store.transition(rid, "已通过", 2)
                with self.assertRaises(ValueError):
                    store.transition(rid, "草稿", 3)
            finally:
                store.close()

    def test_optimistic_concurrency(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.runtime_store(Path(temp) / "state.db")
            try:
                rid = store.save_result("module", {}, {})
                store.transition(rid, "已提交", 1)
                with self.assertRaises(ValueError):
                    store.transition(rid, "已通过", 1)
                self.assertEqual(store.get(rid)["state"], "已提交")
            finally:
                store.close()

    def test_registration_and_login(self):
        with tempfile.TemporaryDirectory() as temp:
            store = self.runtime_store(Path(temp) / "state.db")
            try:
                with self.assertRaises(ValueError):
                    store.register("a", "short")
                with self.assertRaises(ValueError):
                    store.login("admin", "wrong")
                with self.assertRaises(ValueError):
                    store.register("admin", "Password123!")
            finally:
                store.close()

    def test_names(self):
        for name in ["", "../test", "a:b", "CON", "nul.txt"]:
            with self.assertRaises(ValueError):
                validate_name(name)
        self.assertEqual(validate_name("仓储系统"), "仓储系统")

    def test_plan(self):
        p = sample_plan()
        validate_plan(p, TEST_NAME)
        p["modules"][1]["id"] = p["modules"][0]["id"]
        with self.assertRaises(ValueError):
            validate_plan(p, TEST_NAME)

    def test_code_wrapping(self):
        line = "一二三四五" * 30
        chunks = list(display_chunks(line, 90))
        self.assertEqual("".join(chunks), line)
        self.assertTrue(all(sum(2 if ord(c) > 255 else 1 for c in chunk) <= 90 for chunk in chunks))

    def test_code_shortage_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); (p / "modules").mkdir()
            (p / "runtime.py").write_text("x=1\n", encoding="utf-8")
            (p / "main.py").write_text("x=2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "实际源码"):
                build_code("unused", p, p / "code.docx")

    def test_provider_configuration_and_json_helpers(self):
        settings = read_json(HERE / "settings.json")
        for provider in ("codex", "gemini", "grok", "openai", "custom"):
            current = copy.deepcopy(settings); current["provider"] = provider
            selected, config = provider_config(current)
            self.assertEqual(selected, provider)
            self.assertIn("model", config)
        self.assertEqual(_json_text('```json\n{"ok": true}\n```'), '{"ok": true}')
        self.assertEqual(_message_text({"content": [{"type": "text", "text": "a"},
                                                     {"type": "text", "text": "b"}]}), "ab")

    def test_dual_platform_launchers_and_zip_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); project = root / "交付包" / TEST_NAME
            seed_project(project, sample_plan())
            command = (project / "启动软件.cmd").read_bytes()
            self.assertIn(b"\r\n", command)
            self.assertNotIn(b"\n", command.replace(b"\r\n", b""))
            mac_launcher = (project / "启动软件.command").read_text(encoding="utf-8")
            self.assertTrue(mac_launcher.startswith("#!/bin/zsh"))
            self.assertIn("sys.version_info < (3, 11)", mac_launcher)
            self.assertIn("--only-binary=:all:", mac_launcher)
            food_plan = sample_plan()
            food_plan["name"] = "食品添加剂超量使用检测系统"
            food_project = root / "食品添加剂超量使用检测系统"
            seed_project(food_project, food_plan)
            self.assertTrue((food_project / "food_ui.py").exists())
            self.assertTrue((food_project / "food_scene.py").exists())
            self.assertIn("opencv-python-headless>=4.12,<4.14", (food_project / "requirements.txt").read_text(encoding="utf-8"))
            self.assertIn("import PyQt6, cv2", (food_project / "启动软件.command").read_text(encoding="utf-8"))
            target = root / "result.zip"
            package(root / "交付包", target)
            from zipfile import ZipFile
            with ZipFile(target) as archive:
                info = next(i for i in archive.infolist() if i.filename.endswith("启动软件.command"))
                self.assertTrue((info.external_attr >> 16) & 0o111)

    def test_bundled_template_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "模板"
            shutil.copytree(ROOT / "知识库/模板/原模板副本", output / "原模板副本")
            settings = read_json(HERE / "settings.json")
            result = distill(Path(temp) / "不存在的案例目录", settings, output)
            self.assertTrue(Path(result["manual_template"]["path"]).exists())
            self.assertTrue(Path(result["code_template"]["path"]).exists())

    def test_compatible_api_client_without_network_or_key_leak(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self):
                return json.dumps({"choices": [{"message": {"content": '{"source":"x","tests":"y"}'}}],
                                   "usage": {"prompt_tokens": 12, "completion_tokens": 5,
                                             "prompt_tokens_details": {"cached_tokens": 3}}}).encode()

        with tempfile.TemporaryDirectory() as temp:
            settings = read_json(HERE / "settings.json")
            settings["provider"] = "custom"
            settings["providers"]["custom"].update(
                {"base_url": "https://example.invalid/v1", "model": "test-model"})
            os.environ["CUSTOM_API_KEY"] = "secret-for-offline-test"
            try:
                with mock.patch("urllib.request.urlopen", return_value=Response()):
                    client = CompatibleAPIClient(settings, temp)
                    result = client.request("离线", "prompt", {"type": "object"})
                self.assertEqual(result["source"], "x")
                all_logs = "".join(p.read_text(encoding="utf-8", errors="ignore")
                                   for p in Path(temp).glob("*") if p.is_file())
                self.assertNotIn("secret-for-offline-test", all_logs)
                self.assertEqual(client.usage[-1]["usage"]["cached_input_tokens"], 3)
            finally:
                os.environ.pop("CUSTOM_API_KEY", None)


def smoke(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    fixture = root / "fixture"; fixture.mkdir(exist_ok=True)
    plan = sample_plan(); validate_plan(plan, TEST_NAME)
    write_json(fixture / "plan.json", plan)
    for i in range(10):
        write_json(fixture / f"demo_{i}.json", sample_bundle(i))
    project = root / "联调项目"
    seed_project(project, plan)
    logs = root / "logs"; logs.mkdir(exist_ok=True)
    for i, spec in enumerate(plan["modules"]):
        install_module(project, spec, sample_bundle(i))
        verify_module(project, spec, logs, None)
    child([sys.executable, "main.py", "--capture", str(root / "截图")], project, logs / "截图.log", 180)
    verify_captures(root / "截图", plan["modules"])
    # Verify actual store permissions, optimistic concurrency and registration.
    code = """
from runtime import Store
from pathlib import Path
import tempfile
with tempfile.TemporaryDirectory() as d:
    s=Store(Path(d)/'test.sqlite')
    s.register('worker','Password123')
    s.login('worker','Password123')
    rid=s.save_result('m',{}, {'ok':True})
    s.transition(rid,'已提交',1)
    try:
        s.transition(rid,'已通过',2)
    except PermissionError:
        pass
    else:
        raise AssertionError('操作员不应有复核权限')
    s.login('admin','Admin123!')
    try:
        s.transition(rid,'已通过',1)
    except ValueError:
        pass
    else:
        raise AssertionError('过期版本不应写入')
    s.transition(rid,'已通过',2)
    assert s.get(rid)['state']=='已通过'
    s.close()
print('Store权限、状态与版本检查通过')
"""
    child([sys.executable, "-c", code], project, logs / "store.log", 120)
    return project, plan


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests))
    if not result.wasSuccessful():
        sys.exit(1)
    if "--smoke" in sys.argv:
        smoke(ROOT / "验证记录/完整联调")
        print("十模块联调及32张真实截图通过")
