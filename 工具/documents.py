import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile, is_zipfile
from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from contracts import write_json
from learn import inspect_docx, sha256

HERE = Path(__file__).resolve().parent
HIDDEN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def word_convert(source, destination, fmt="pdf"):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    from environment import find_soffice
    soffice = find_soffice()
    if soffice:
        with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
            p = subprocess.run([soffice, "--headless", "--convert-to", fmt,
                                "--outdir", temp, str(source)],
                               capture_output=True, encoding="utf-8", errors="replace", timeout=180,
                               creationflags=HIDDEN)
            generated = Path(temp) / (source.stem + "." + fmt)
            if p.returncode == 0 and generated.exists():
                shutil.move(str(generated), destination)
                return
            libre_error = (p.stdout + p.stderr)[-1000:]
    else:
        libre_error = "未找到LibreOffice。"
    if os.name != "nt":
        raise RuntimeError("文档转换失败。macOS请安装LibreOffice：brew install --cask libreoffice\n" + libre_error)
    p = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(HERE / "word_convert.ps1"), "-Source", str(source),
                        "-Destination", str(destination), "-Format", fmt],
                       capture_output=True, encoding="utf-8", errors="replace", timeout=180,
                       creationflags=HIDDEN)
    if p.returncode or not destination.exists():
        raise RuntimeError("Word/LibreOffice转换失败，请确认至少一个转换器可用。\n" +
                           libre_error + "\n" + p.stderr[-1000:])


def prepare_template(source, cache):
    source, cache = Path(source), Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    suffix = sha256(source)[:12]
    target = cache / (source.stem + "_" + suffix + ".docx")
    if not target.exists():
        if is_zipfile(source):
            shutil.copy2(source, target)
        else:
            word_convert(source, target, "docx")
    return target


def distill(source_root, settings, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=True)
    templates = {}
    for key in ("manual_template", "code_template"):
        source = Path(source_root) / settings[key]
        if source.exists():
            path = prepare_template(source, out / "原模板副本")
            original_path = str(source)
            original_hash = sha256(source)
        else:
            prefix = "操作手册_" if key == "manual_template" else "代码_"
            candidates = sorted((out / "原模板副本").glob(prefix + "*.docx"))
            if not candidates:
                raise FileNotFoundError(f"原案例目录不可用，且没有内置{key}副本：{source}")
            path = candidates[-1]
            original_path = "内置模板副本（原案例目录不可用）"
            original_hash = sha256(path)
        info = inspect_docx(path)
        info["original_path"] = original_path
        info["original_sha256"] = original_hash
        templates[key] = {"path": str(path), "evidence": info}
    write_json(out / "模板样式.json", templates)
    lines = ["# 文档模板执行契约", "", "来源：用户提供的操作手册与代码模板，保留原文件和哈希。", "",
             "## 页面和样式证据", ""]
    for key, entry in templates.items():
        info = entry["evidence"]
        lines += [f"### {key}", "", f"原文件：{info['original_path']}",
                  f"SHA256：{info['original_sha256']}",
                  f"转换副本：{entry['path']}", "",
                  "页面：" + json.dumps(info.get("sections"), ensure_ascii=False), "",
                  "标题层级：" + json.dumps(info.get("headings", [])[:16], ensure_ascii=False), ""]
    lines += ["## 允许替换的内容", "",
        "- 保留模板的样式集合、A4纸张和主要页边距。",
        "- 软件名称、版本、所有旧正文与图像、旧表格、页眉页脚属于内容槽，全部替换。",
        "- 多个同尺寸示例分节合并为单节，避免旧模板空白页和遗留页码。",
        "- 手册沿用封面、概述、使用过程、模块操作的顺序，增加真实截图步骤页。",
        "- 代码文档按明确的交付要求覆盖字号和行距，使每页固定50行，无底色无空行。",
        "- 代码长行只在文档中按显示宽度折行，源码本身不改写，保留源码行映射。",
        "- 头部使用新软件名及V1.0，底部使用当前页码，清除旧名称。",
        "- 最终页数由转换后的PDF确认，不能仅依据Word元数据。",
        "- 图表与截图须完整；每页渲染图可在质量检查目录查看。"]
    (out / "artifact.md").write_text("\n".join(lines), encoding="utf-8")
    return templates


def set_font(style, name, size):
    style.font.name = name
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    style.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), name)


def clean_template(path, title):
    doc = Document(path)
    section = copy.deepcopy(doc.sections[0]._sectPr)
    body = doc._element.body
    for node in list(body):
        body.remove(node)
    body.append(section)
    # Slots containing the previous example's identity must never survive.
    for sec in doc.sections:
        for container in (sec.header, sec.footer, sec.first_page_header, sec.first_page_footer,
                          sec.even_page_header, sec.even_page_footer):
            for child in list(container._element):
                container._element.remove(child)
            container.add_paragraph("")
        sec.different_first_page_header_footer = False
        sec.header.paragraphs[0].text = title + " V1.0"
        p = sec.footer.paragraphs[0]
        p.alignment = 1
        field = OxmlElement("w:fldSimple"); field.set(qn("w:instr"), "PAGE"); p._p.append(field)
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
        if name not in doc.styles:
            created = doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
            created.base_style = doc.styles["Normal"]
            if name == "Title":
                set_font(created, "Microsoft YaHei", 22)
                created.font.bold = True
        doc.styles[name].font.color.rgb = RGBColor(0, 0, 0)
    return doc


def build_manual(template, project, captures, destination):
    plan = json.loads((project / "project.json").read_text(encoding="utf-8"))
    entries = json.loads((captures / "manifest.json").read_text(encoding="utf-8"))
    doc = clean_template(template, plan["name"])
    p = doc.add_paragraph(plan["name"], "Title"); p.alignment = 1
    p = doc.add_paragraph("操作手册"); p.alignment = 1
    p = doc.add_paragraph("V1.0"); p.alignment = 1
    doc.add_paragraph(plan["purpose"])
    doc.add_page_break()
    doc.add_heading("概述", level=1)
    doc.add_heading("编写目的", level=2)
    doc.add_paragraph("本手册说明软件的启动、账号注册、业务数据输入、计算分析、复核和结果导出操作，供操作员和管理员使用。")
    doc.add_paragraph(plan["main_features"])
    doc.add_page_break()
    doc.add_heading("使用前准备", level=1)
    doc.add_paragraph("Windows 10或11安装Python 3.11及以上版本后双击启动软件.cmd；macOS安装Python 3.11及以上版本后运行启动软件.command。首次启动会创建虚拟环境并安装项目依赖，后续启动复用同一环境。")
    doc.add_paragraph("内置演示账号为admin，密码为Admin123!。注册的新账号为操作员，最终通过或退回操作由管理员执行。样例仅用于演示和测试。")
    doc.add_paragraph("在业务表单中填写字段，在记录卡片中增删明细；数值和业务规则无效时会显示说明。业务数据和复核记录保存在data/app.sqlite。")
    doc.add_paragraph("操作顺序为载入样例、修改数据、执行计算、提交复核、复核通过或退回、导出结果。历史记录下拉框可恢复以前的计算。")
    for index, entry in enumerate(entries):
        doc.add_page_break()
        doc.add_heading(f"{index + 1} {entry['title']}", level=1)
        doc.add_paragraph(entry["description"])
        width = min(doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin, Mm(160))
        doc.add_picture(str(captures / entry["file"]), width=width)
        p = doc.add_paragraph(f"图{index + 1} {entry['title']}"); p.alignment = 1
        if entry.get("module"):
            spec = next(m for m in plan["modules"] if m["id"] == entry["module"])
            doc.add_heading("操作要点", level=2)
            doc.add_paragraph("；".join(spec["rules"]))
            doc.add_paragraph("输出内容：" + spec["output_description"])
    doc.add_page_break()
    doc.add_heading("异常处理与数据留存", level=1)
    doc.add_paragraph("输入无效时，请检查表单字段类型、数值范围和必填项；业务规则错误时，请根据提示调整。复核前必须完成计算，已通过记录不能直接改回草稿，需要重新计算建立新记录。")
    doc.add_paragraph("导出结果以JSON文件保存，包含概要、指标、明细及图表数据。关闭软件后可备份data目录。恢复时先关闭软件再恢复数据库文件，避免覆盖正在写入的数据。")
    doc.add_paragraph("本地算法不自动连接外部设备、云端模型或第三方业务系统。各模块适用边界见操作步骤；演示结果不代表真实业务测量或预测。")
    doc.save(destination)
    return len(entries) + 4


def display_chunks(line, limit=90):
    current, width = "", 0
    for char in line.expandtabs(4):
        cost = 2 if ord(char) > 255 else 1
        if width + cost > limit and current:
            if current.strip():
                yield current.rstrip()
            current, width = "", 0
        current += char
        width += cost
    if current.strip():
        yield current.rstrip()


def collect_code(project):
    items = []
    files = sorted((project / "modules").rglob("*.py")) + [project / "runtime.py", project / "main.py"]
    for path in files:
        if path.name.startswith("test") or path.name == "__init__.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            for part in display_chunks(line):
                items.append({"file": str(path.relative_to(project)), "line": n, "text": part})
    return items


def build_code(template, project, destination, pages=65, per_page=50):
    items = collect_code(project)
    # Reject shortage; never pad with duplicates or generated filler.
    count = pages * per_page
    if len(items) < count:
        raise ValueError(f"实际源码仅够{len(items)}个显示行，要求{count}行；须补足实际功能")
    chosen = items[:count//2] + items[-(count-count//2):] if len(items) > count else items
    plan = json.loads((project / "project.json").read_text(encoding="utf-8"))
    doc = clean_template(template, plan["name"])
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    section.top_margin = section.bottom_margin = Mm(20)
    section.left_margin = section.right_margin = Mm(22)
    style = doc.styles["Normal"]
    set_font(style, "Consolas", 8.5)
    style.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "SimSun")
    for i, item in enumerate(chosen):
        p = doc.add_paragraph(item["text"])
        fmt = p.paragraph_format
        fmt.space_before = fmt.space_after = Pt(0)
        fmt.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        fmt.line_spacing = Pt(13)
        fmt.keep_together = True
        fmt.keep_with_next = False
        fmt.widow_control = False
        fmt.first_line_indent = fmt.left_indent = fmt.right_indent = Pt(0)
        if i and i % per_page == 0:
            fmt.page_break_before = True
        for shd in list(p._p.xpath(".//w:shd")):
            shd.getparent().remove(shd)
    doc.save(destination)
    write_json(destination.parent / "代码行映射.json", chosen)
    return pages


def application_form(plan, settings, source_lines, manual_pages, code_pages, destination):
    values = [
        ("软件全称", plan["name"]), ("版本号", "V1.0"),
        ("开发的硬件环境", settings["development_hardware"]),
        ("运行的硬件环境", settings["runtime_hardware"]),
        ("开发该软件的操作系统", settings["runtime_os"]),
        ("软件开发环境 / 开发工具", settings["developer_tool"]),
        ("该软件的运行平台 / 操作系统", settings["runtime_os"]),
        ("软件运行支撑环境 / 支持软件", "Python 3.11及以上、PyQt6、SQLite"),
        ("编程语言", "Python"), ("源程序量", str(source_lines)),
        ("开发目的", plan["purpose"]), ("面向领域 / 行业", plan["domain"]),
        ("软件的主要功能", plan["main_features"]), ("技术特点", plan["technical_features"]),
        ("软件的技术特点选项", "应用软件"),
        ("页数", f"操作手册{manual_pages}页，代码文档{code_pages}页"), ("软件分类", "应用软件"),
    ]
    for key, value in values:
        low, high = (500, 1300) if key == "软件的主要功能" else (1, 100) if key == "技术特点" else (1, 50)
        if key == "软件全称":
            low, high = 1, 70
        if not low <= len(value) <= high:
            raise ValueError(f"申请表字段{key}有{len(value)}字，不符合{low}至{high}要求")
    destination.write_text("\n".join(f"{i}.★{k}：{v}" for i, (k, v) in enumerate(values, 1)), encoding="utf-8")


def poppler(name):
    runtime = Path(os.environ.get("GENERATOR_RUNTIME", str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies")))
    p = runtime / "native/poppler/Library/bin" / (name + ".exe")
    if p.exists():
        return str(p)
    found = shutil.which(name)
    if found:
        return found
    for candidate in (Path("/opt/homebrew/bin") / name, Path("/usr/local/bin") / name):
        if candidate.exists():
            return str(candidate)
    return None


def render_pdf(pdf, output, dpi=105):
    output.mkdir(parents=True, exist_ok=True)
    binary = poppler("pdftoppm")
    if not binary:
        raise RuntimeError("缺少Poppler，不能检查最终PDF")
    subprocess.run([binary, "-r", str(dpi), "-png", str(pdf), str(output / "page")],
                   check=True, capture_output=True, timeout=240, creationflags=HIDDEN)
    return sorted(output.glob("page-*.png"))


def contact_sheets(images, output):
    paths = []
    for start in range(0, len(images), 20):
        sheet = Image.new("RGB", (1100, 1500), "white")
        draw = ImageDraw.Draw(sheet)
        for k, path in enumerate(images[start:start+20]):
            with Image.open(path) as image:
                image.thumbnail((255, 270))
                x, y = (k % 4)*275, (k//4)*300
                sheet.paste(image, (x, y+20))
                draw.text((x+5, y+3), path.stem, fill="black")
        path = output / f"contact-{start//20+1}.jpg"
        sheet.save(path, quality=88); paths.append(str(path))
    return paths


def validate_documents(manual, code, expected_code_pages):
    manual_reader, code_reader = PdfReader(manual), PdfReader(code)
    errors = []
    if len(manual_reader.pages) < 30:
        errors.append("操作手册不足30页")
    if len(code_reader.pages) != expected_code_pages:
        errors.append(f"代码PDF为{len(code_reader.pages)}页，要求{expected_code_pages}页")
    mapping_path = Path(code).parent / "代码行映射.json"
    code_docx = Path(code).with_suffix(".docx")
    if not mapping_path.exists():
        errors.append("缺少代码行映射.json，无法证明每页50行来自真实源码")
    elif not code_docx.exists():
        errors.append("缺少代码.docx，无法核对PDF转换前的逐行结构")
    else:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
        required_lines = expected_code_pages * 50
        if len(mapping) != required_lines:
            errors.append(f"代码行映射为{len(mapping)}行，要求{required_lines}行")

        # DOCX正文是逐源码行写入的；页眉和页脚不属于paragraphs，因此这里可以
        # 无损证明转换前恰好有 expected_code_pages * 50 个正文行，而且内容未变。
        paragraphs = [p.text for p in Document(code_docx).paragraphs if p.text.strip()]
        if len(paragraphs) != required_lines:
            errors.append(f"代码DOCX正文为{len(paragraphs)}行，要求{required_lines}行")
        else:
            for index, (paragraph, item) in enumerate(zip(paragraphs, mapping), start=1):
                if paragraph != item.get("text", ""):
                    errors.append(f"代码DOCX第{index}行与源码行映射不一致")
                    break

        # PDF文本提取会因字体而改变空格或标点表示，不能用字符串逐字比对。
        # 固定行距、固定50行分页已在DOCX层验证；PDF层只检查转换没有额外折行。
        for i, page in enumerate(code_reader.pages):
            actual_lines = [line for line in (page.extract_text() or "").splitlines() if line.strip()]
            if not 50 <= len(actual_lines) <= 54:
                errors.append(
                    f"代码PDF第{i+1}页提取到{len(actual_lines)}行（含页眉页脚），疑似发生折行或丢行"
                )
    for label, reader in (("manual", manual_reader), ("code", code_reader)):
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if len(text.strip()) < 10:
                errors.append(f"{label}第{i+1}页内容过少")
    return {"manual_pages": len(manual_reader.pages), "code_pages": len(code_reader.pages), "errors": errors}
