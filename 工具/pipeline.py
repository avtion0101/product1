import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from PIL import Image
from contracts import ENGINE, PLAN, read_json, validate_engine, validate_name, validate_plan, write_json
from codex_client import create_client, provider_config
from documents import (distill, build_code, build_manual, application_form, word_convert,
                       validate_documents, render_pdf, contact_sheets)
from learn import learn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CONTRACT = """
每个模块的logic.py必须定义可无参数实例化的Engine类，只能依赖Python标准库。
Engine.example()返回非空JSON可序列化dict，至少包含5条有领域意义的样例记录。
Engine.validate(payload)成功时返回None，非法输入抛ValueError，检查字段、类型、空值、范围及业务约束。
Engine.calculate(payload)先验证，不能改变输入，必须返回JSON可序列化dict：
{
 "summary":"中文结论和方法说明",
 "metrics":{"中文指标名": 数字或短字符串},
 "rows":[{"中文列名":数字或短字符串}],
 "series":[{"label":"中文标签","value":有限数字}],
 "chart_title":"中文图表名称"
}
网络图可增加edges:[[0,1],[1,2]]；其他字段也可追加。
标准返回字段必须始终存在，series不能空，rows要有真实明细。
仅进行本地确定性业务计算，不访问文件、网络或外部进程，不使用随机数伪造结果。
实现真正的领域算法、数据一致性检查、异常边界处理、可解释中间结果。
有效代码至少MIN_LINES行（不含空行和单行注释），通过有价值的功能达到，而非长注释或重复表达式凑行。
代码每行建议不超过90个半角字符。中文提示和输出，但类/函数名用英文。
不要用TODO、pass、NotImplementedError占位。不得生成安装程序或依赖额外库。
tests是完整unittest文件，使用from modules.MODULE_ID.logic import Engine。
至少3个test_方法，包含明确期望值计算、边界输入、非法输入；不得只assertTrue(True)。
只输出source和tests两个字符串。不要输出markdown围栏。
"""


def child(command, cwd, log_path, timeout=180, cancel=None):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    secret_names = {"OPENAI_API_KEY", "CODEX_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY", "CUSTOM_API_KEY"}
    if os.environ.get("GENERATOR_API_KEY_ENV"):
        secret_names.add(os.environ["GENERATOR_API_KEY_ENV"])
    for key in secret_names:
        env.pop(key, None)
    with Path(log_path).open("w", encoding="utf-8") as f:
        p = subprocess.Popen(command, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                             env=env, creationflags=HIDDEN)
        start = time.monotonic()
        try:
            while p.poll() is None:
                if cancel and cancel.is_set():
                    raise InterruptedError("已停止")
                if time.monotonic() - start > timeout:
                    raise TimeoutError(f"运行检查超时：{Path(log_path).name}")
                time.sleep(.25)
        finally:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill(); p.wait()
    text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    if p.returncode:
        raise RuntimeError(text[-6500:])
    return text


def seed_project(project, plan):
    project.mkdir(parents=True, exist_ok=True)
    write_json(project / "project.json", plan)
    shutil.copy2(HERE / "templates/runtime.py", project / "runtime.py")
    (project / "main.py").write_text("from runtime import main\n\nif __name__ == '__main__':\n    main()\n", encoding="utf-8")
    (project / "requirements.txt").write_text("PyQt6>=6.7,<7\n", encoding="utf-8")
    windows_launcher = (
        '@echo off\nchcp 65001 >nul\ncd /d "%~dp0"\n'
        'if not exist ".venv\\Scripts\\python.exe" (\n'
        '  python -m venv .venv\n  if errorlevel 1 goto failed\n)\n'
        '".venv\\Scripts\\python.exe" -c "import PyQt6" 2>nul\n'
        'if errorlevel 1 (\n  ".venv\\Scripts\\python.exe" -m pip install -r requirements.txt\n'
        '  if errorlevel 1 goto failed\n)\n'
        '".venv\\Scripts\\python.exe" main.py\nif errorlevel 1 goto failed\nexit /b 0\n'
        ':failed\necho 启动失败，请确认已安装Python 3.11以上并加入PATH。\npause\nexit /b 1\n'
    )
    (project / "启动软件.cmd").write_bytes(windows_launcher.replace("\n", "\r\n").encode("utf-8"))
    (project / "启动软件.command").write_text(
        '#!/bin/zsh\nset -e\nROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\ncd "$ROOT"\n'
        'PYTHON_BIN="${PYTHON_BIN:-python3}"\n'
        'if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then echo "请先安装Python 3.11以上"; read; exit 1; fi\n'
        'if [[ ! -x ".venv/bin/python" ]]; then "$PYTHON_BIN" -m venv .venv; fi\n'
        'if ! .venv/bin/python -c "import PyQt6" 2>/dev/null; then '
        '.venv/bin/python -m pip install -r requirements.txt; fi\n'
        'exec .venv/bin/python main.py\n', encoding="utf-8")
    (project / "modules").mkdir(exist_ok=True)
    (project / "modules/__init__.py").write_text("", encoding="utf-8")
    (project / "README.md").write_text(
        f"# {plan['name']} V1.0\n\nWindows双击启动软件.cmd；macOS首次运行执行 "
        "`chmod +x 启动软件.command`，以后可双击启动。首次启动会创建venv并安装PyQt6。\n\n"
        "演示管理员：admin / Admin123!。注册账号默认为操作员。\n\n"
        "输入为可编辑JSON，包含实际字段和样例；执行计算后保存结果。"
        "提交后由管理员通过/退回。可导出JSON并从历史记录恢复。\n\n"
        "本地算法和演示样例不连接真实外部设备。SQLite位于data/app.sqlite。\n",
        encoding="utf-8")


def install_module(project, spec, bundle):
    directory = project / "modules" / spec["id"]
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "__init__.py").write_text("", encoding="utf-8")
    (directory / "logic.py").write_text(bundle["source"], encoding="utf-8")
    (directory / "test_logic.py").write_text(bundle["tests"], encoding="utf-8")
    (directory / "view.py").write_text(
        "from runtime import BasePage\nfrom .logic import Engine\n\n"
        "class Page(BasePage):\n"
        "    def __init__(self, store, spec):\n"
        "        super().__init__(store, spec, Engine())\n", encoding="utf-8")


def verify_module(project, spec, logs, cancel):
    target = f"modules.{spec['id']}.test_logic"
    child([sys.executable, "-m", "unittest", target, "-v"], project,
          logs / (spec["id"] + "_tests.log"), 120, cancel)
    check = (
        "import copy,json;from modules." + spec["id"] + ".logic import Engine;"
        "from runtime import check_result;"
        "e=Engine();p=e.example();original=copy.deepcopy(p);e.validate(p);r=e.calculate(p);"
        "assert p==original,'calculate改变了输入';check_result(r);"
        "assert r['rows'] and r['series'],'返回数据为空';"
        "assert r==e.calculate(copy.deepcopy(original)),'同一输入的结果不确定';"
        "print(json.dumps(r,ensure_ascii=False))")
    child([sys.executable, "-c", check], project, logs / (spec["id"] + "_sample.log"), 120, cancel)


def verify_captures(folder, modules):
    entries = read_json(folder / "manifest.json")
    if len(entries) < 2 + 3 * len(modules):
        raise ValueError("截图流程不完整")
    hashes = set()
    for entry in entries:
        path = (folder / entry["file"]).resolve()
        if path.parent != folder.resolve():
            raise ValueError("截图路径越界")
        with Image.open(path) as image:
            if image.width < 700 or image.height < 400:
                raise ValueError(f"截图太小：{path.name}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError(f"重复截图：{path.name}")
        hashes.add(digest)
    for m in modules:
        if sum(e.get("module") == m["id"] for e in entries) < 3:
            raise ValueError(f"{m['title']}缺少输入、计算或复核截图")
    return len(entries)


def source_count(project):
    return sum(sum(bool(line.strip()) for line in p.read_text(encoding="utf-8").splitlines())
               for p in project.rglob("*.py") if not p.name.startswith("test_"))


def package(delivery, target):
    temporary = target.with_suffix(".tmp.zip")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(delivery.rglob("*")):
            if path.is_file() and not any(x in path.parts for x in (".venv", "__pycache__", ".git")):
                arcname = str(Path(delivery.name) / path.relative_to(delivery)).replace("\\", "/")
                z.write(path, arcname)
                if path.suffix == ".command":
                    z.getinfo(arcname).external_attr = (0o100755 << 16)
    temporary.replace(target)


class Pipeline:
    def __init__(self, log=print, progress=None, cancel=None, settings=None):
        self.settings = settings or read_json(HERE / "settings.json")
        self.log = log
        self.progress = progress or (lambda value: None)
        self.cancel = cancel or threading.Event()
        self.run_dir = None

    def status(self, text, progress):
        if self.cancel.is_set():
            raise InterruptedError("已停止")
        self.log(text)
        self.progress(progress)

    def run(self, name, resume=None, fixture=None):
        name = validate_name(name)
        start = time.monotonic()
        if resume:
            run = Path(resume).resolve()
            if not run.is_relative_to((ROOT / "生成结果").resolve()):
                raise ValueError("仅能续跑本工具生成结果内的任务")
            state = read_json(run / "state.json")
            if state["name"] != name:
                raise ValueError("续跑名称不匹配")
        else:
            run = ROOT / "生成结果" / (datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + name + "_" + uuid.uuid4().hex[:4])
            run.mkdir(parents=True)
            state = {"name": name, "status": "运行中", "elapsed_seconds": 0, "completed_modules": []}
        self.run_dir = run
        write_json(run / "settings_snapshot.json", self.settings)
        logs, cache = run / "日志", run / "缓存"
        logs.mkdir(exist_ok=True); cache.mkdir(exist_ok=True)
        state["status"] = "运行中"
        write_json(run / "state.json", state)
        delivery = run / "交付包"
        delivery.mkdir(exist_ok=True)
        for prior in run.glob("*_待验收.zip"):
            prior.rename(prior.with_name(prior.stem + "_" + uuid.uuid4().hex[:8] + ".previous.zip"))
        project = delivery / name
        provider, provider_settings = provider_config(self.settings)
        state["provider"] = provider
        if provider_settings.get("api_key_env"):
            os.environ["GENERATOR_API_KEY_ENV"] = provider_settings["api_key_env"]
        client = create_client(self.settings, logs / "模型调用", self.log, self.cancel)
        try:
            self.status("1/7 检查环境并提取案例规范", 2)
            if not fixture:
                from environment import ensure_environment
                ensure_environment(ROOT, self.log, self.settings)
            source_root = Path(self.settings.get("source_root", ""))
            if source_root.exists() and (source_root / "案例").exists():
                learn(source_root, ROOT / "知识库")
            elif not (ROOT / "知识库/案例提炼.md").exists():
                raise FileNotFoundError("原案例目录不可用，且生成器内没有已提炼知识库")
            else:
                self.log("原案例目录不可用，使用生成器内置的案例知识与模板副本。")
            knowledge = (ROOT / "知识库/案例提炼.md").read_text(encoding="utf-8")
            self.status("2/7 生成业务方案", 7)
            plan_path = cache / "plan.json"
            if fixture:
                plan = read_json(Path(fixture) / "plan.json")
                write_json(plan_path, plan)
            elif plan_path.exists():
                plan = read_json(plan_path)
            else:
                prompt = (f"为软件《{name}》设计{self.settings['module_count']}个有实际算法的独立业务模块。"
                          "只实现本地可验证的Python标准库算法，不声称调用外部AI或真实设备。"
                          "不要只有增删改查。可选真实排序、统计、路径、规则、几何、排程、质量评估。"
                          "purpose 8至50字，domain 2至50字，main_features 500至1300字，"
                          "technical_features 10至100字。中文菜单，不要中英括号混排。"
                          "主界面提供输入、计算、提交复核、管理员通过/退回、JSON导出和历史记录。"
                          "每个模块必须描述具体算法和至少两条业务规则。visualization按返回数据选bars/line/matrix/network。"
                          "\n案例知识：\n" + knowledge)
                errors = ""
                for attempt in range(self.settings["max_attempts"]):
                    plan = client.request("业务方案", prompt + "\n上次校验问题：" + errors, PLAN)
                    try:
                        validate_plan(plan, name, self.settings["module_count"])
                        write_json(plan_path, plan)
                        break
                    except ValueError as exc:
                        errors = str(exc)
                else:
                    raise ValueError("方案未通过校验：" + errors)
            validate_plan(plan, name, self.settings["module_count"])
            seed_project(project, plan)
            self.status("3/7 逐模块生成并运行测试", 12)
            for i, spec in enumerate(plan["modules"]):
                self.status(f"模块 {i+1}/{len(plan['modules'])}：{spec['title']}", 12 + int(48*i/len(plan["modules"])))
                module_cache = cache / (spec["id"] + ".json")
                error, previous = "", ""
                for attempt in range(self.settings["max_attempts"]):
                    if fixture:
                        bundle = read_json(Path(fixture) / (spec["id"] + ".json"))
                    elif module_cache.exists() and attempt == 0:
                        bundle = read_json(module_cache)
                    else:
                        prompt = (CONTRACT.replace("MIN_LINES", str(self.settings["min_module_lines"])).replace("MODULE_ID", spec["id"])
                                  + "\n软件：" + name + "\n模块需求：" + json.dumps(spec, ensure_ascii=False)
                                  + "\n上次实际检查错误：" + error + "\n需修复的上次代码：" + previous)
                        bundle = client.request(spec["id"], prompt, ENGINE)
                    try:
                        validate_engine(bundle, self.settings["min_module_lines"])
                        install_module(project, spec, bundle)
                        verify_module(project, spec, logs, self.cancel)
                        write_json(module_cache, bundle)
                        if spec["id"] not in state["completed_modules"]:
                            state["completed_modules"].append(spec["id"])
                        write_json(run / "state.json", state)
                        break
                    except (ValueError, SyntaxError, RuntimeError, TimeoutError) as exc:
                        error = str(exc)
                        previous = json.dumps(bundle, ensure_ascii=False)
                        write_json(cache / (spec["id"] + f"_failed_{attempt}.json"), bundle)
                        self.log("模块检查未通过：" + error[-600:])
                        if fixture:
                            raise
                else:
                    raise RuntimeError(f"{spec['title']}在限定重试次数内未通过。\n{error}")
            self.status("4/7 完整运行与真实界面截图", 63)
            child([sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py", "-v"],
                  project, logs / "全部模块测试.log", 180, self.cancel)
            captures = run / "截图"
            child([sys.executable, "main.py", "--capture", str(captures)], project,
                  logs / "界面截图.log", 240, self.cancel)
            capture_count = verify_captures(captures, plan["modules"])
            self.status("5/7 套用原模板生成资料", 75)
            templates = distill(self.settings["source_root"], self.settings, ROOT / "知识库/模板")
            manual, code = delivery / "操作手册.docx", delivery / "代码.docx"
            build_manual(templates["manual_template"]["path"], project, captures, manual)
            build_code(templates["code_template"]["path"], project, code,
                       self.settings["code_pages"], self.settings["code_lines_per_page"])
            self.status("6/7 转换PDF并检查页面", 83)
            word_convert(manual, manual.with_suffix(".pdf"))
            word_convert(code, code.with_suffix(".pdf"))
            checks = validate_documents(manual.with_suffix(".pdf"), code.with_suffix(".pdf"), self.settings["code_pages"])
            if checks["errors"]:
                raise ValueError("\n".join(checks["errors"]))
            application_form(plan, self.settings, source_count(project), checks["manual_pages"],
                             checks["code_pages"], delivery / "申请表信息.txt")
            qa = run / "质量检查"
            for doc in (manual, code):
                images = render_pdf(doc.with_suffix(".pdf"), qa / doc.stem)
                contact_sheets(images, qa / doc.stem)
            self.status("7/7 输出验收清单、成本统计与压缩包", 96)
            report = {"status": "自动检查通过，待人工验收", "name": name, "modules": len(plan["modules"]),
                      "screenshots": capture_count, "source_nonblank_lines": source_count(project),
                      **checks, "manual_review": ["专业算法适用性", "所有页面可读性", "界面效果", "开发硬件配置", "委托方最终验收"],
                      "fixture": bool(fixture)}
            write_json(run / "验收报告.json", report)
            (run / "验收说明.md").write_text(
                "# 自动检查结果\n\n自动结构与运行检查通过，尚需人工验收。\n\n"
                f"项目：{name}\n\n模块：{len(plan['modules'])}；截图：{capture_count}；"
                f"手册：{checks['manual_pages']}页；代码：{checks['code_pages']}页。\n\n"
                "质量检查目录包含全部PDF页面渲染图和总览。请检查截图裁切、文字溢出、业务算法以及申请表硬件字段。\n"
                "只有委托方确认后才算交付通过。本工具不承诺自动通过外部验收。\n", encoding="utf-8")
            package(delivery, run / (name + "_V1.0_待验收.zip"))
            state["status"] = "自动检查通过，待人工验收"
            self.status(f"已生成：{run}", 100)
            return run
        except BaseException as exc:
            state["status"] = "已停止" if isinstance(exc, InterruptedError) else "失败，可续跑"
            state["error"] = str(exc)
            self.log(str(exc))
            raise
        finally:
            state["elapsed_seconds"] += round(time.monotonic() - start, 1)
            usage = client.usage
            totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
            unknown = 0
            for entry in usage:
                if entry["usage"] is None:
                    unknown += 1
                else:
                    for key in totals:
                        totals[key] += entry["usage"].get(key, 0)
            report = {"seconds": state["elapsed_seconds"], "minutes": round(state["elapsed_seconds"]/60, 1),
                      "calls": len(usage), "token_totals": totals, "calls_without_usage": unknown,
                      "token_count_complete": unknown == 0, "payment_assumption_yuan": self.settings["price_per_project"],
                      "gross_yuan_per_hour": round(self.settings["price_per_project"]*3600/max(state["elapsed_seconds"],1), 2),
                      "provider": client.provider, "billing": client.billing,
                      "notes": "输入token含缓存部分，不重复加总。时间含模型等待、测试和资料生成，不含人工验收及沟通。失败任务的时薪不代表收入。"}
            write_json(run / "耗时与Token.json", report)
            write_json(run / "state.json", state)
