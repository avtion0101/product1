import ast
import hashlib
from pathlib import Path
from zipfile import ZipFile
from docx import Document
from pypdf import PdfReader
from contracts import write_json


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def inspect_docx(p):
    try:
        d = Document(p)
    except Exception:
        return {"path": str(p), "sha256": sha256(p), "format": "legacy", "conversion_required": True}
    result = {"path": str(p), "sha256": sha256(p), "format": "docx",
              "sections": [{"width_mm": round(s.page_width.mm, 2), "height_mm": round(s.page_height.mm, 2),
                            "top_mm": round(s.top_margin.mm, 2), "bottom_mm": round(s.bottom_margin.mm, 2),
                            "left_mm": round(s.left_margin.mm, 2), "right_mm": round(s.right_margin.mm, 2)}
                           for s in d.sections],
              "headings": [{"style": p.style.name, "text": p.text} for p in d.paragraphs
                           if p.text and (p.style.name.startswith("Heading") or len(p.text) < 30)]}
    with ZipFile(p) as z:
        result["media_count"] = sum(e.startswith("word/media/") for e in z.namelist())
    return result


def learn(source_root, output):
    source_root, output = Path(source_root), Path(output)
    if not (source_root / "案例").is_dir():
        raise FileNotFoundError(f"缺少案例目录：{source_root}")
    examples = []
    for folder in sorted((source_root / "案例").iterdir()):
        if not folder.is_dir():
            continue
        files = [p for p in folder.rglob("*.py") if not any(x in p.parts for x in (".venv", "venv", "__pycache__"))]
        if not files:
            continue
        item = {"name": folder.name, "source_files": len(files), "nonblank_lines": 0,
                "characters": 0, "modules": [], "pdfs": [], "docx": [], "algorithms": []}
        for p in files:
            text = p.read_text(encoding="utf-8-sig", errors="replace")
            item["nonblank_lines"] += sum(bool(s.strip()) for s in text.splitlines())
            item["characters"] += len(text)
            if p.name != "__init__.py":
                item["modules"].append(str(p.relative_to(folder)))
            if any(k in p.stem for k in ("algorithm", "analysis", "logic", "width", "geometry", "quality", "repair")):
                try:
                    tree = ast.parse(text)
                    item["algorithms"].append({"file": str(p.relative_to(folder)),
                        "functions": [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))][:18]})
                except SyntaxError:
                    pass
        for p in folder.glob("*.pdf"):
            try:
                item["pdfs"].append({"file": p.name, "pages": len(PdfReader(p).pages)})
            except Exception:
                item["pdfs"].append({"file": p.name, "pages": None})
        item["docx"] = [inspect_docx(p) for p in folder.glob("*.docx")]
        examples.append(item)
    inv = {"source_root": str(source_root), "examples": examples,
           "templates": [inspect_docx(p) for p in (source_root / "模板").glob("*.docx")],
           "requirements": (source_root / "工作内容要求-这个可做参考不要求完全按照这个.txt").read_text(encoding="utf-8-sig")}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "案例分析.json", inv)
    text = ["# 案例提炼与生成约束", "", "这是从本地案例提炼的知识库和工作流，不是重新训练模型。", ""]
    for e in examples:
        text.append(f"- {e['name']}：{e['source_files']}个源码文件，{e['nonblank_lines']}行非空源码；"
                    + "，".join(f"{p['file']} {p['pages']}页" for p in e["pdfs"]))
    text += ["", "## 可复用规范", "",
      "- Python/PyQt6、SQLite事务、登录注册、权限、导航、独立业务模块。",
      "- 模块分别包含logic.py和view.py；真实领域计算，输入校验、状态流转、审计与数据一致性。",
      "- 统一V1.0，至少10个业务菜单；不使用系统配置凑数。",
      "- 手册以真实Qt截图为依据；代码文档从实际源码提取65页，每页50行。",
      "- 申请表目的不超过50字、主要功能500至1300字、技术特点不超过100字。",
      "- 源码量和页数按实际统计；旧示例的语言、硬件、页数不可照抄。",
      "- 不把随机演示当预测，不把模拟数据当实时设备，不把预留接口写成已实现。",
      "- 格式为旧Word二进制的.docx先转成副本；原文件不变。",
      "", "## 验收范围", "",
      "自动门槛覆盖运行、截图、字数和页数。领域正确性、审美和委托方验收仍需复核。"]
    (output / "案例提炼.md").write_text("\n".join(text), encoding="utf-8")
    return inv

