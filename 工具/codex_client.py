import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from contracts import write_json

HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_codex():
    path = shutil.which("codex.exe") or shutil.which("codex")
    if path:
        return path
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.extend((Path(local) / "OpenAI/Codex/bin").glob("*/codex.exe"))
    candidates.extend([
        Path.home() / ".local/bin/codex",
        Path.home() / ".local/bin/codex.exe",
        Path("/opt/homebrew/bin/codex"),
        Path("/usr/local/bin/codex"),
    ])
    candidates = [p for p in candidates if p.exists()]
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    raise RuntimeError("找不到Codex CLI，请先安装Codex并运行 codex login")


def login_status():
    p = subprocess.run([find_codex(), "login", "status"], capture_output=True,
                       encoding="utf-8", errors="replace", timeout=30, creationflags=HIDDEN)
    text = (p.stdout + p.stderr).strip()
    if p.returncode or "ChatGPT" not in text:
        raise RuntimeError("未确认ChatGPT登录，请运行 codex login；不会自动改用付费API")
    return text


def provider_config(settings):
    provider = settings.get("provider", "codex").strip().lower()
    providers = settings.get("providers", {})
    if provider == "codex" and not providers:
        return provider, {"model": settings.get("model", "")}
    if provider not in providers:
        raise ValueError(f"未知模型提供商：{provider}")
    config = dict(providers[provider])
    if provider == "codex" and not config.get("model"):
        config["model"] = settings.get("model", "")
    return provider, config


def credential_status(settings):
    provider, config = provider_config(settings)
    if provider == "codex":
        try:
            return True, login_status()
        except RuntimeError as exc:
            return False, str(exc)
    env_name = config.get("api_key_env", "")
    return bool(env_name and os.environ.get(env_name)), env_name


class CodexClient:
    provider = "codex"

    def __init__(self, settings, directory, log=print, cancel=None):
        self.settings, self.directory, self.log = settings, Path(directory), log
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cancel = cancel or threading.Event()
        self.counter = len(list(self.directory.glob("*.prompt.txt")))

    def request(self, stage, prompt, schema):
        if self.cancel.is_set():
            raise InterruptedError("已停止")
        self.counter += 1
        stem = f"{self.counter:03}_{stage}"
        schema_path = self.directory / (stem + ".schema.json")
        output = self.directory / (stem + ".result.json")
        errors = self.directory / (stem + ".stderr.log")
        write_json(schema_path, schema)
        (self.directory / (stem + ".prompt.txt")).write_text(prompt, encoding="utf-8")
        _, config = provider_config(self.settings)
        command = [find_codex(), "exec", "--json", "--ephemeral", "--skip-git-repo-check",
                   "--sandbox", "read-only", "--color", "never", "--output-schema", str(schema_path),
                   "--output-last-message", str(output), "-C", str(self.directory), "-c",
                   'model_reasoning_effort="' + self.settings["reasoning_effort"] + '"']
        if config.get("model"):
            command += ["--model", config["model"]]
        command.append("-")
        env = os.environ.copy()
        for key in ("CODEX_API_KEY", "OPENAI_API_KEY"):
            env.pop(key, None)
        started, heartbeat = time.monotonic(), time.monotonic()
        q = queue.Queue()
        self.log(f"Codex开始 {stage}")
        with errors.open("w", encoding="utf-8") as err:
            p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                                 encoding="utf-8", errors="replace", env=env, creationflags=HIDDEN)

            def read():
                for line in p.stdout:
                    q.put(line)
                q.put(None)

            threading.Thread(target=read, daemon=True).start()
            try:
                p.stdin.write("仅根据文本返回JSON。不要调用工具、访问文件或启动其他代理。\n" + prompt)
                p.stdin.close()
                while True:
                    if self.cancel.is_set():
                        raise InterruptedError("已停止，完成阶段保留")
                    if time.monotonic() - started > self.settings["call_timeout_seconds"]:
                        raise TimeoutError(f"{stage}超时")
                    try:
                        line = q.get(timeout=0.5)
                    except queue.Empty:
                        line = ""
                    if line is None:
                        break
                    if time.monotonic() - heartbeat > 20:
                        self.log(f"{stage}已运行{round(time.monotonic() - started)}秒")
                        heartbeat = time.monotonic()
                p.wait(timeout=15)
            finally:
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        p.wait()
        if p.returncode or not output.exists():
            raise RuntimeError(f"Codex {stage}失败；日志：{errors}\n" + errors.read_text(encoding="utf-8")[-1200:])
        return json.loads(output.read_text(encoding="utf-8"))


def _message_text(message):
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
        return "".join(parts)
    return str(content)


def _json_text(text):
    text = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    return fenced.group(1) if fenced else text


class CompatibleAPIClient:
    def __init__(self, settings, directory, log=print, cancel=None):
        self.settings, self.directory, self.log = settings, Path(directory), log
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cancel = cancel or threading.Event()
        self.provider, self.config = provider_config(settings)
        self.counter = len(list(self.directory.glob("*.prompt.txt")))

    def request(self, stage, prompt, schema):
        if self.cancel.is_set():
            raise InterruptedError("已停止")
        env_name = self.config.get("api_key_env", "")
        api_key = os.environ.get(env_name, "")
        if not api_key:
            raise RuntimeError(f"未设置 {env_name}。请在启动前设置环境变量，或在生成器窗口临时输入API Key。")
        model = self.config.get("model", "").strip()
        base_url = self.config.get("base_url", "").strip().rstrip("/")
        if not model or not base_url.startswith("https://"):
            raise ValueError(f"{self.provider} 的model或HTTPS base_url未配置")
        endpoint = base_url if base_url.endswith("/chat/completions") else base_url + "/chat/completions"
        self.counter += 1
        stem = f"{self.counter:03}_{stage}"
        request_path = self.directory / (stem + ".request.json")
        result_path = self.directory / (stem + ".result.json")
        error_path = self.directory / (stem + ".stderr.log")
        (self.directory / (stem + ".prompt.txt")).write_text(prompt, encoding="utf-8")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "只返回符合给定JSON Schema的JSON，不使用Markdown围栏。"},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "generated_result", "strict": True, "schema": schema},
            },
        }
        if self.config.get("supports_reasoning_effort") and self.settings.get("reasoning_effort"):
            payload["reasoning_effort"] = self.settings["reasoning_effort"]
        write_json(request_path, {**payload, "messages": [{"role": "system", "content": payload["messages"][0]["content"]},
                                                        {"role": "user", "content": "见同名prompt.txt"}]})
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
                     "User-Agent": "software-project-generator/1.3"},
            method="POST",
        )
        self.log(f"{self.provider} API开始 {stage}（模型：{model}）")
        try:
            try:
                with urllib.request.urlopen(request, timeout=self.settings["call_timeout_seconds"]) as response:
                    raw = response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                error_path.write_text(f"HTTP {exc.code}\n{body[-6000:]}", encoding="utf-8")
                raise RuntimeError(f"{self.provider} API {stage}失败：HTTP {exc.code}，详见 {error_path}") from exc
            except urllib.error.URLError as exc:
                error_path.write_text(str(exc), encoding="utf-8")
                raise RuntimeError(f"{self.provider} API {stage}网络失败：{exc.reason}") from exc
            data = json.loads(raw)
            content = _message_text(data["choices"][0]["message"])
            result = json.loads(_json_text(content))
            write_json(result_path, result)
            return result
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            error_path.write_text(f"响应解析失败：{exc}", encoding="utf-8")
            raise RuntimeError(f"{self.provider} API没有返回可解析的结构化JSON，详见 {error_path}") from exc


def create_client(settings, directory, log=print, cancel=None):
    provider, _ = provider_config(settings)
    if provider == "codex":
        return CodexClient(settings, directory, log, cancel)
    return CompatibleAPIClient(settings, directory, log, cancel)
