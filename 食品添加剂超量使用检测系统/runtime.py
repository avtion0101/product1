"""Shared runtime copied into each generated deliverable."""
import argparse
import hashlib
import hmac
import importlib
import json
import math
import os
import secrets
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QFileDialog,
)

BASE = Path(__file__).resolve().parent
PLAN = json.loads((BASE / "project.json").read_text(encoding="utf-8"))
STYLE = """
QWidget {font-family:'Microsoft YaHei','PingFang SC','Noto Sans CJK SC',sans-serif; font-size:13px; color:#20354c;}
QMainWindow,QDialog {background:#f3f6fa;}
QListWidget {background:#132940;color:#dce7f3;border:0;padding:14px;min-width:180px;}
QListWidget::item {padding:13px;border-radius:6px;}
QListWidget::item:selected {background:#2366a3;color:white;}
QPushButton {background:#2366a3;color:white;border:0;padding:10px 16px;border-radius:5px;}
QPushButton:disabled {background:#aebdcb;}
QLineEdit,QTextEdit,QTableWidget,QComboBox {background:white;border:1px solid #cbd7e3;
padding:6px;border-radius:4px;}
QLabel#title {font-size:23px;font-weight:600;color:#132940;}
QLabel#sub {color:#597085;}
QLabel#status {background:#e4eef7;padding:10px;border-radius:5px;}
QHeaderView::section {background:#e4eef7;padding:7px;border:0;}
"""


def stamp():
    return datetime.now().isoformat(timespec="seconds")


class Store:
    TRANSITIONS = {"草稿": {"已提交"}, "已提交": {"已通过", "已退回"}, "已退回": {"已提交"}, "已通过": set()}

    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          username TEXT PRIMARY KEY, salt TEXT NOT NULL, digest TEXT NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('管理员','操作员')));
        CREATE TABLE IF NOT EXISTS results(
          id INTEGER PRIMARY KEY AUTOINCREMENT, module TEXT NOT NULL, payload TEXT NOT NULL,
          result TEXT NOT NULL, state TEXT NOT NULL, owner TEXT NOT NULL,
          version INTEGER NOT NULL DEFAULT 1, updated TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL,
          action TEXT NOT NULL, ref_id INTEGER, detail TEXT NOT NULL, created TEXT NOT NULL);
        """)
        if not self.db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            self.register("admin", "Admin123!", "管理员")
        self.actor = "admin"
        self.role = "管理员"

    @staticmethod
    def digest(password, salt):
        return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120000).hex()

    def register(self, username, password, role="操作员"):
        username = username.strip()
        if not 3 <= len(username) <= 40 or len(password) < 8:
            raise ValueError("账号须3至40字，密码至少8位")
        if role not in ("操作员", "管理员"):
            raise ValueError("角色无效")
        salt = secrets.token_hex(16)
        try:
            with self.db:
                self.db.execute("INSERT INTO users VALUES(?,?,?,?)", (username, salt, self.digest(password, salt), role))
        except sqlite3.IntegrityError as exc:
            raise ValueError("账号已经存在") from exc

    def login(self, username, password):
        row = self.db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if row is None or not hmac.compare_digest(row["digest"], self.digest(password, row["salt"])):
            raise ValueError("账号或密码错误")
        self.actor, self.role = row["username"], row["role"]
        self.record("登录", None, username)

    def record(self, action, rid, detail):
        with self.db:
            self.db.execute("INSERT INTO audit(actor,action,ref_id,detail,created) VALUES(?,?,?,?,?)",
                            (self.actor, action, rid, str(detail), stamp()))

    def save_result(self, module, payload, result):
        with self.db:
            cursor = self.db.execute(
                "INSERT INTO results(module,payload,result,state,owner,updated) VALUES(?,?,?,?,?,?)",
                (module, json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False),
                 "草稿", self.actor, stamp()))
            rid = cursor.lastrowid
            self.db.execute("INSERT INTO audit(actor,action,ref_id,detail,created) VALUES(?,?,?,?,?)",
                            (self.actor, "计算保存", rid, module, stamp()))
        return rid

    def get(self, rid):
        row = self.db.execute("SELECT * FROM results WHERE id=?", (rid,)).fetchone()
        if not row:
            raise ValueError("记录不存在")
        return dict(row)

    def transition(self, rid, new_state, expected_version):
        row = self.get(rid)
        if new_state not in self.TRANSITIONS[row["state"]]:
            raise ValueError(f"不允许从{row['state']}变为{new_state}")
        if new_state in ("已通过", "已退回") and self.role != "管理员":
            raise PermissionError("只有管理员可以复核")
        if self.role != "管理员" and row["owner"] != self.actor:
            raise PermissionError("不能提交其他用户记录")
        with self.db:
            cur = self.db.execute(
                "UPDATE results SET state=?,version=version+1,updated=? WHERE id=? AND version=?",
                (new_state, stamp(), rid, expected_version))
            if cur.rowcount != 1:
                raise ValueError("记录已被修改，请刷新后重试")
            self.db.execute("INSERT INTO audit(actor,action,ref_id,detail,created) VALUES(?,?,?,?,?)",
                            (self.actor, "状态变更", rid, new_state, stamp()))
        return self.get(rid)

    def list_results(self, module):
        rows = self.db.execute("SELECT id,state,owner,updated FROM results WHERE module=? ORDER BY id DESC LIMIT 100",
                               (module,)).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.db.close()


class Chart(QWidget):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.result = {}
        self.setMinimumHeight(230)

    def set_result(self, result):
        self.result = result
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        w, h = self.width(), self.height()
        p.setPen(QColor("#527088"))
        p.drawText(18, 24, str(self.result.get("chart_title", "业务计算结果")))
        values = self.result.get("series", [])
        if not values:
            p.drawText(20, 70, "载入样例并执行计算后显示结果")
            p.end()
            return
        numbers = [float(x["value"]) for x in values]
        scale = max((abs(x) for x in numbers), default=1) or 1
        n = len(values)
        if self.mode == "matrix":
            cols = max(1, math.ceil(math.sqrt(n)))
            side = min((w - 50) / cols, (h - 65) / math.ceil(n / cols))
            for i, item in enumerate(values):
                x, y = 25 + (i % cols) * side, 42 + (i // cols) * side
                color = QColor("#2c7dbc")
                color.setAlpha(int(60 + 190 * abs(numbers[i]) / scale))
                p.fillRect(int(x), int(y), int(side - 3), int(side - 3), color)
                p.setPen(QColor("#132940"))
                p.drawText(int(x + 5), int(y + side / 2), f"{numbers[i]:.2g}")
        elif self.mode == "network":
            points = [QPointF(w/2 + (w/2-65)*math.cos(i*2*math.pi/n),
                             h/2 + (h/2-52)*math.sin(i*2*math.pi/n)) for i in range(n)]
            p.setPen(QPen(QColor("#aac2d6"), 2))
            for edge in self.result.get("edges", []):
                a, b = int(edge[0]), int(edge[1])
                if 0 <= a < n and 0 <= b < n:
                    p.drawLine(points[a], points[b])
            for i, point in enumerate(points):
                p.setBrush(QColor("#2366a3"))
                p.drawEllipse(point, 9, 9)
                p.drawText(int(point.x()+12), int(point.y()+4), str(values[i]["label"])[:12])
        else:
            baseline = h - 42
            slot = (w - 75) / max(n, 1)
            points = []
            p.setPen(QPen(QColor("#d0deea"), 1))
            p.drawLine(35, baseline, w-20, baseline)
            for i, item in enumerate(values):
                x = 45 + i * slot
                height = abs(numbers[i]) / scale * (h - 100)
                y = baseline - height
                if self.mode == "bars":
                    p.fillRect(int(x), int(y), max(3, int(slot * .65)), int(height), QColor("#2c7dbc"))
                points.append(QPointF(x+slot*.3, y))
                p.setPen(QColor("#3e5a71"))
                p.drawText(int(x), baseline+20, str(item["label"])[:8])
                p.drawText(int(x), int(y-8), f"{numbers[i]:.3g}")
            if self.mode == "line" and len(points) > 1:
                p.setPen(QPen(QColor("#2c7dbc"), 3))
                p.drawPolyline(QPolygonF(points))
        p.end()


def check_result(result):
    if not isinstance(result, dict) or not isinstance(result.get("summary"), str):
        raise ValueError("算法结果缺少summary")
    if not isinstance(result.get("metrics"), dict) or not isinstance(result.get("rows"), list):
        raise ValueError("算法结果缺少metrics或rows")
    for point in result.get("series", []):
        if not isinstance(point, dict) or "label" not in point or not math.isfinite(float(point["value"])):
            raise ValueError("图表数据格式无效")
    json.dumps(result, ensure_ascii=False, allow_nan=False)


class BasePage(QWidget):
    def __init__(self, store, spec, engine):
        super().__init__()
        self.store, self.spec, self.engine = store, spec, engine
        self.rid = None
        self.result = None
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        title = QLabel(spec["title"]); title.setObjectName("title")
        sub = QLabel(spec["purpose"]); sub.setObjectName("sub"); sub.setWordWrap(True)
        root.addWidget(title); root.addWidget(sub)
        toolbar = QHBoxLayout()
        self.buttons = {}
        actions = [("载入样例", self.load_demo), ("执行计算", self.calculate),
                   ("提交复核", lambda: self.change_state("已提交")),
                   ("复核通过", lambda: self.change_state("已通过")),
                   ("退回修改", lambda: self.change_state("已退回")),
                   ("导出结果", self.export_result)]
        for name, callback in actions:
            b = QPushButton(name)
            b.clicked.connect(lambda checked=False, fn=callback: self.guarded(fn))
            toolbar.addWidget(b); self.buttons[name] = b
        root.addLayout(toolbar)
        self.status = QLabel("草稿 · 等待输入"); self.status.setObjectName("status")
        root.addWidget(self.status)
        body = QSplitter()
        left = QWidget(); fl = QVBoxLayout(left)
        desc = QLabel("输入数据 / JSON\n" + spec["input_description"])
        desc.setWordWrap(True)
        fl.addWidget(desc)
        self.editor = QTextEdit(); self.editor.setMinimumWidth(290)
        fl.addWidget(self.editor)
        rules = QLabel("业务规则\n" + "\n".join("• " + r for r in spec["rules"]))
        rules.setWordWrap(True); fl.addWidget(rules)
        right = QWidget(); rl = QVBoxLayout(right)
        self.summary = QLabel("计算说明将在这里显示"); self.summary.setWordWrap(True)
        self.chart = Chart(spec["visualization"])
        self.table = QTableWidget(); self.table.setMinimumHeight(145)
        rl.addWidget(self.summary); rl.addWidget(self.chart, 2); rl.addWidget(self.table, 1)
        body.addWidget(left); body.addWidget(right); body.setSizes([330, 760])
        root.addWidget(body, 1)
        self.history = QComboBox()
        self.history.activated.connect(self.restore)
        root.addWidget(self.history)
        self.refresh_history()

    def guarded(self, fn):
        try:
            fn()
        except Exception as exc:
            QMessageBox.warning(self, "操作未完成", str(exc))

    def load_demo(self):
        self.editor.setPlainText(json.dumps(self.engine.example(), ensure_ascii=False, indent=2))
        self.rid, self.result = None, None
        self.status.setText("草稿 · 样例数据已载入，可修改后计算")

    def calculate(self):
        payload = json.loads(self.editor.toPlainText())
        self.engine.validate(payload)
        result = self.engine.calculate(payload)
        check_result(result)
        self.rid = self.store.save_result(self.spec["id"], payload, result)
        self.show_result(result)
        self.status.setText(f"记录 #{self.rid} · 草稿 · 结果已保存")
        self.refresh_history()

    def show_result(self, result):
        self.result = result
        metrics = "    ".join(f"{k}：{v}" for k, v in list(result["metrics"].items())[:5])
        self.summary.setText(result["summary"] + "\n" + metrics)
        self.chart.set_result(result)
        rows = result["rows"]
        headers = list(rows[0]) if rows else []
        self.table.setColumnCount(len(headers)); self.table.setRowCount(len(rows))
        self.table.setHorizontalHeaderLabels(headers)
        for r, row in enumerate(rows):
            for c, key in enumerate(headers):
                self.table.setItem(r, c, QTableWidgetItem(str(row.get(key, ""))))
        self.table.resizeColumnsToContents()

    def change_state(self, state):
        if self.rid is None:
            raise ValueError("请先执行计算")
        row = self.store.get(self.rid)
        row = self.store.transition(self.rid, state, row["version"])
        self.status.setText(f"记录 #{self.rid} · {row['state']} · 版本{row['version']} · {self.store.actor}")
        self.refresh_history()

    def refresh_history(self):
        self.history.clear()
        self.history.addItem("历史记录（选择可恢复输入和结果）", None)
        for row in self.store.list_results(self.spec["id"]):
            self.history.addItem(f"#{row['id']} / {row['state']} / {row['owner']} / {row['updated']}", row["id"])

    def restore(self, index):
        rid = self.history.itemData(index)
        if rid is None:
            return
        row = self.store.get(rid); self.rid = rid
        self.editor.setPlainText(json.dumps(json.loads(row["payload"]), ensure_ascii=False, indent=2))
        self.show_result(json.loads(row["result"]))
        self.status.setText(f"记录 #{rid} · {row['state']} · 版本{row['version']}")

    def export_result(self, path=None):
        if self.result is None:
            raise ValueError("请先执行计算")
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "导出", self.spec["id"] + ".json", "JSON (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding="utf-8")
            self.store.record("导出", self.rid, Path(path).name)
        return path


class Login(QDialog):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.setWindowTitle(PLAN["name"] + " V1.0")
        self.resize(750, 430)
        lay = QVBoxLayout(self)
        title = QLabel(PLAN["name"]); title.setObjectName("title"); title.setWordWrap(True)
        lay.addWidget(title); lay.addWidget(QLabel("V1.0  ·  本地业务工作台"))
        form = QFormLayout()
        self.username, self.password = QLineEdit("admin"), QLineEdit("Admin123!")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("账号", self.username); form.addRow("密码", self.password); lay.addLayout(form)
        lay.addWidget(QLabel("演示账号 admin / Admin123!；注册新账号默认为操作员。"))
        self.message = QLabel(""); lay.addWidget(self.message)
        btn = QPushButton("登录工作台"); btn.clicked.connect(self.sign_in); lay.addWidget(btn)
        reg = QPushButton("注册操作员账号"); reg.clicked.connect(self.sign_up); lay.addWidget(reg)

    def sign_in(self):
        try:
            self.store.login(self.username.text(), self.password.text()); self.accept()
        except Exception as exc:
            self.message.setText(str(exc))

    def sign_up(self):
        try:
            self.store.register(self.username.text(), self.password.text())
            self.message.setText("注册成功，请登录")
        except Exception as exc:
            self.message.setText(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.setWindowTitle(PLAN["name"] + " V1.0")
        self.resize(1360, 860)
        self.store = store
        root = QWidget(); self.setCentralWidget(root)
        lay = QHBoxLayout(root); lay.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget(); self.nav.setMaximumWidth(240)
        self.stack = QStackedWidget(); self.pages = []
        for spec in PLAN["modules"]:
            module = importlib.import_module(f"modules.{spec['id']}.view")
            page = module.Page(store, spec)
            self.pages.append(page); self.stack.addWidget(page); self.nav.addItem(spec["title"])
        lay.addWidget(self.nav); lay.addWidget(self.stack, 1)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex); self.nav.setCurrentRow(0)
        self.statusBar().showMessage(f"{store.actor} · {store.role}   |   SQLite本地存储   |   V1.0")


def capture(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion"); app.setStyleSheet(STYLE)
    entries = []
    with tempfile.TemporaryDirectory(prefix="project-capture-") as temp:
        store = Store(Path(temp) / "demo.sqlite")
        login = Login(store); login.show(); app.processEvents()
        def save(window, key, title, description, module=""):
            app.processEvents()
            p = output / (key + ".png")
            if not window.grab().save(str(p)):
                raise RuntimeError("截图保存失败")
            entries.append({"file": p.name, "title": title, "description": description, "module": module})
        save(login, "00_login", "登录系统", "输入演示账号admin及密码Admin123!，单击登录工作台。")
        store.register("operator", "Operator123!")
        login.username.setText("operator"); login.password.setText("Operator123!")
        login.message.setText("注册成功，新账号为操作员；管理员负责最终复核。")
        save(login, "01_registration", "注册账号", "填写至少3字账号和8位密码后注册，新账号默认操作员权限。")
        store.login("admin", "Admin123!"); login.close()
        window = MainWindow(store); window.show(); app.processEvents()
        for i, page in enumerate(window.pages):
            spec = page.spec
            window.nav.setCurrentRow(i)
            page.load_demo()
            save(window, f"{i+2:02}_a", spec["title"] + " 输入准备",
                 spec["input_description"] + "。单击载入样例，在左侧JSON输入区调整参数。", spec["id"])
            page.calculate()
            save(window, f"{i+2:02}_b", spec["title"] + " 计算结果",
                 "单击执行计算。算法：" + spec["algorithm"] + "。结果：" + page.result["summary"], spec["id"])
            page.change_state("已提交"); page.change_state("已通过")
            export = output / (spec["id"] + "_result.json")
            page.export_result(export)
            save(window, f"{i+2:02}_c", spec["title"] + " 复核与导出",
                 "单击提交复核，再由管理员单击复核通过。结果和状态存入SQLite，导出结果写入JSON。"
                 + "适用边界：" + spec["limitations"], spec["id"])
        window.close(); store.close()
    (output / "manifest.json").write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture")
    args = parser.parse_args()
    if args.capture:
        capture(args.capture)
        return
    app = QApplication(sys.argv); app.setStyle("Fusion"); app.setStyleSheet(STYLE)
    store = Store(BASE / "data/app.sqlite")
    login = Login(store)
    if login.exec() != QDialog.DialogCode.Accepted:
        store.close(); return
    window = MainWindow(store); window.show()
    app.exec(); store.close()

if "食品添加剂" in PLAN["name"]:
    from food_ui import main, capture


if __name__ == "__main__":
    main()
