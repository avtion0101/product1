import ast
import json
import re
from pathlib import Path

VERSION = "V1.0"
S = {"type": "string"}


def obj(p):
    return {"type": "object", "properties": p, "required": list(p), "additionalProperties": False}


def array(item):
    return {"type": "array", "items": item}


MODULE = obj({"id": S, "title": S, "purpose": S, "algorithm": S, "rules": array(S),
              "input_description": S, "output_description": S, "limitations": S,
              "visualization": {"type": "string", "enum": ["bars", "line", "matrix", "network"]}})
PLAN = obj({"name": S, "domain": S, "purpose": S, "main_features": S,
            "technical_features": S, "modules": array(MODULE)})
ENGINE = obj({"source": S, "tests": S})


def validate_name(name):
    name = name.strip()
    if not name or len(name) > 70 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith("."):
        raise ValueError("名称须为1至70个字符，且不含Windows文件名非法字符")
    if name.upper().split(".")[0] in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("请更换软件名称")
    return name


def validate_plan(plan, name, count=10):
    errors = []
    if plan.get("name") != name:
        errors.append("名称必须与输入一致")
    for field, low, high in [("purpose", 8, 50), ("main_features", 500, 1300),
                             ("technical_features", 10, 100), ("domain", 2, 50)]:
        if not low <= len(plan.get(field, "")) <= high:
            errors.append(f"{field}字数必须在{low}到{high}之间")
    modules = plan.get("modules", [])
    if len(modules) != count:
        errors.append(f"必须有{count}个业务模块")
    ids, titles = set(), set()
    for m in modules:
        mid = m.get("id", "")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,35}", mid) or mid in ids:
            errors.append(f"模块id无效或重复: {mid}")
        ids.add(mid)
        if not m.get("title") or m["title"] in titles:
            errors.append("中文菜单重复或为空")
        titles.add(m.get("title"))
        if len(m.get("rules", [])) < 2 or len(m.get("algorithm", "")) < 15:
            errors.append(f"{mid}需要具体算法与至少两条业务规则")
        if any(s in m.get("title", "") for s in ["系统配置", "个人设置", "账号管理"]):
            errors.append("不能使用系统设置菜单凑业务模块")
    if errors:
        raise ValueError("\n".join(errors))


def validate_engine(bundle, min_lines):
    tree = ast.parse(bundle["source"])
    tests = ast.parse(bundle["tests"])
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Engine"]
    methods = {n.name for n in classes[0].body if isinstance(n, ast.FunctionDef)} if classes else set()
    if not {"example", "validate", "calculate"}.issubset(methods):
        raise ValueError("Engine须实现example、validate、calculate")
    lines = [s for s in bundle["source"].splitlines() if s.strip() and not s.lstrip().startswith("#")]
    if len(lines) < min_lines:
        raise ValueError(f"有效代码仅{len(lines)}行，要求{min_lines}行，请补充实际领域逻辑及边界处理")
    if sum(isinstance(n, ast.FunctionDef) and n.name.startswith("test_") for n in ast.walk(tests)) < 3:
        raise ValueError("至少提供正常、边界、非法输入三类测试")
    return len(lines)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)

