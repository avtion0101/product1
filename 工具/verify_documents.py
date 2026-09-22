import json
import shutil
from pathlib import Path
from zipfile import ZipFile
from contracts import read_json, write_json
from documents import (distill, build_code, build_manual, word_convert, application_form,
                       validate_documents, render_pdf, contact_sheets)
from selfcheck import sample_plan
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main():
    settings = read_json(HERE / "settings.json")
    source = Path(settings["source_root"])
    out = ROOT / "验证记录/资料联调"
    out.mkdir(parents=True, exist_ok=True)
    project = out / "源码排版测试"
    project.mkdir(exist_ok=True)
    sample = source / "案例/排水管网规划与污水处理厂选址优化系统"
    shutil.copytree(sample / "src", project / "modules", dirs_exist_ok=True)
    shutil.copy2(sample / "main.py", project / "main.py")
    (project / "runtime.py").write_text("", encoding="utf-8")
    plan = sample_plan()
    write_json(project / "project.json", plan)
    captures = out / "参考截图"
    captures.mkdir(exist_ok=True)
    manual = source / "案例/物流设备综合故障自锁与任务旁路接管软件/操作手册.docx"
    entries = []
    with ZipFile(manual) as z:
        media = [n for n in z.namelist() if n.startswith("word/media/") and n.lower().endswith((".png", ".jpg", ".jpeg"))][:32]
        for i, item in enumerate(media):
            filename = f"{i:02}" + Path(item).suffix
            (captures / filename).write_bytes(z.read(item))
            entries.append({"file": filename, "title": f"原案例参考截图 {i+1}",
                            "description": "此页仅测试排版。图像来自用户提供的物流软件案例，不是本次生成软件的运行证据。",
                            "module": ""})
    write_json(captures / "manifest.json", entries)
    templates = distill(source, settings, ROOT / "知识库/模板")
    build_manual(templates["manual_template"]["path"], project, captures, out / "操作手册.docx")
    build_code(templates["code_template"]["path"], project, out / "代码.docx", 65, 50)
    for name in ("操作手册", "代码"):
        word_convert(out / (name + ".docx"), out / (name + ".pdf"))
    result = validate_documents(out / "操作手册.pdf", out / "代码.pdf", 65)
    result["code_extracted_line_counts"] = [len([s for s in (p.extract_text() or "").splitlines() if s.strip()])
                                          for p in PdfReader(out / "代码.pdf").pages]
    source_lines = sum(sum(bool(s.strip()) for s in p.read_text(encoding="utf-8-sig").splitlines())
                       for p in project.rglob("*.py"))
    application_form(plan, settings, source_lines, result["manual_pages"], result["code_pages"], out / "测试申请表信息.txt")
    for name in ("操作手册", "代码"):
        images = render_pdf(out / (name + ".pdf"), out / "页面预览" / name)
        contact_sheets(images, out / "页面预览" / name)
    write_json(out / "检查结果.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

