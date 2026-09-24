import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from codex_client import credential_status, find_codex, login_status, provider_config

HERE = Path(__file__).resolve().parent


def word_registered():
    if os.name != "nt":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"Word.Application\CLSID"):
            return True
    except (ImportError, OSError):
        return False


def find_soffice():
    candidates = [shutil.which("soffice"), shutil.which("libreoffice")]
    if sys.platform == "darwin":
        candidates += ["/Applications/LibreOffice.app/Contents/MacOS/soffice"]
    elif os.name == "nt":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")):
            if base:
                candidates.append(str(Path(base) / "LibreOffice/program/soffice.exe"))
    return next((str(Path(p)) for p in candidates if p and Path(p).exists()), None)


def find_pdftoppm():
    path = shutil.which("pdftoppm")
    if path:
        return path
    runtime = Path(os.environ.get(
        "GENERATOR_RUNTIME",
        str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies"),
    ))
    candidates = [runtime / "native/poppler/Library/bin/pdftoppm.exe",
                  Path("/opt/homebrew/bin/pdftoppm"), Path("/usr/local/bin/pdftoppm")]
    return next((str(p) for p in candidates if p.exists()), None)


def inspect_environment(root, settings=None):
    settings = settings or {"provider": "codex"}
    free_mb = round(shutil.disk_usage(root).free / 1024**2)
    provider, config = provider_config(settings)
    try:
        codex = find_codex()
    except RuntimeError:
        codex = None
    credential_ready, credential_detail = credential_status(settings)
    office = word_registered()
    soffice = find_soffice()
    converter = "libreoffice" if soffice else ("microsoft_word" if office else None)
    return {
        "platform": platform.system(),
        "free_disk_mb": free_mb,
        "required_free_mb": 700,
        "document_converter": converter,
        "word_registered": office,
        "libreoffice": soffice,
        "pdf_renderer": find_pdftoppm(),
        "provider": provider,
        "model": config.get("model", ""),
        "credential_ready": credential_ready,
        "credential": "ChatGPT login" if provider == "codex" and credential_ready else credential_detail,
        "codex": codex,
        "qt_available": importlib.util.find_spec("PyQt6") is not None,
        "python": sys.executable,
    }


def ensure_environment(root, log, settings):
    info = inspect_environment(root, settings)
    if info["free_disk_mb"] < info["required_free_mb"]:
        raise RuntimeError(
            f"生成器所在磁盘只剩{info['free_disk_mb']}MB，至少需要700MB空闲空间（建议2GB）。"
            "\n请释放空间，或把整个生成器文件夹复制到有空间且可写的目录后再启动。")
    if not info["document_converter"]:
        if sys.platform == "darwin":
            raise RuntimeError("macOS缺少LibreOffice，无法稳定转换和核验PDF。请先安装：brew install --cask libreoffice")
        raise RuntimeError("缺少Microsoft Word或LibreOffice，无法按模板生成并核验PDF。")
    if not info["pdf_renderer"]:
        if sys.platform == "darwin":
            raise RuntimeError("macOS缺少Poppler。请先安装：brew install poppler")
        raise RuntimeError("缺少Poppler的pdftoppm，不能逐页渲染检查PDF。")
    provider, config = provider_config(settings)
    if provider == "codex":
        log(login_status())
    else:
        env_name = config.get("api_key_env", "")
        if not env_name or not os.environ.get(env_name):
            raise RuntimeError(f"未设置 {env_name}。API Key只从环境变量或本次窗口读取，不写入文件。")
        log(f"{provider} API凭据已就绪（环境变量：{env_name}；不会写入日志）。")
    if not info["qt_available"]:
        log("首次安装PyQt6到工具/.packages，此步骤需要联网。")
        command = [sys.executable, "-m", "pip", "install", "--no-cache-dir",
                   "--target", str(HERE / ".packages"), "PyQt6>=6.7,<7"]
        p = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace",
                           timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        (HERE / "依赖安装.log").write_text(p.stdout + p.stderr, encoding="utf-8")
        if p.returncode:
            raise RuntimeError("Qt依赖安装失败，详见工具/依赖安装.log。可按使用说明使用镜像源重试。")
        importlib.invalidate_caches()
    return info
