"""Food additive screening workbench generated with the software project."""
import argparse
import copy
import json
import math
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSplitter, QStackedWidget, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from runtime import BASE, PLAN, Login, Store, check_result
from food_scene import RiskScene


THEME = """
QWidget {background:#0c121e;color:#e9f0f9;font-family:'Microsoft YaHei','PingFang SC','Noto Sans CJK SC';font-size:12px;}
QMainWindow,QDialog {background:#0c121e;}
QLabel {background:transparent;}
QFrame#sidebar {background:#131b29;border-right:1px solid #253348;}
QFrame#panel {background:#151e2c;border:1px solid #26394e;border-radius:11px;}
QFrame#metricCard {background:#172335;border:1px solid #2a4057;border-radius:10px;}
QFrame#recordCard {background:#1b293a;border:1px solid #34506a;border-radius:8px;}
QLabel#recordBadge {background:#236fab;color:white;border-radius:16px;font-weight:700;}
QLabel#brand {font-size:19px;font-weight:700;color:#f3f8ff;}
QLabel#headline {font-size:23px;font-weight:700;color:#f2f7ff;}
QLabel#sectionTitle {font-size:15px;font-weight:700;color:#d8eafe;}
QLabel#muted {color:#8da3b9;}
QLabel#metricValue {font-size:26px;font-weight:700;color:#54d9f3;}
QLabel#warning {background:#302621;color:#ffd3a0;border:1px solid #795139;padding:9px;border-radius:6px;}
QLabel#status {background:#172d41;color:#a8e7f6;padding:8px;border-radius:6px;}
QListWidget {background:transparent;border:0;outline:0;}
QListWidget::item {padding:11px 13px;margin:3px 7px;border-radius:8px;color:#a9b9cb;}
QListWidget::item:selected {background:#1760b2;color:#ffffff;font-weight:700;}
QListWidget::item:hover {background:#1d3148;}
QLineEdit,QTextEdit,QComboBox,QTreeWidget,QTableWidget {background:#0f1724;color:#ecf4ff;border:1px solid #34475d;border-radius:6px;padding:6px;selection-background-color:#145f9c;}
QLineEdit:focus,QTextEdit:focus,QComboBox:focus,QTreeWidget:focus {border:1px solid #3bc8e4;}
QPushButton {background:#227ed2;color:white;border:1px solid #3497e6;padding:9px 16px;border-radius:6px;font-weight:600;}
QPushButton:hover {background:#3196ec;}
QPushButton:disabled {background:#34465a;color:#8595a7;border-color:#34465a;}
QPushButton#quiet {background:#1b2a3b;border-color:#344b62;color:#d6e9f7;}
QPushButton#danger {background:#633235;border-color:#a05153;}
QHeaderView::section {background:#1b2b3e;color:#a8d9ef;border:0;border-bottom:1px solid #35506c;padding:9px;font-weight:700;}
QTableWidget {gridline-color:#25374b;alternate-background-color:#172334;}
QTreeWidget {alternate-background-color:#172334;}
QTabWidget::pane {border:1px solid #344b62;background:#151e2c;}
QTabBar::tab {background:#1b2a3b;color:#a9b9cb;padding:8px 14px;margin-right:3px;}
QTabBar::tab:selected {background:#247ac8;color:white;font-weight:700;}
QStatusBar {background:#131c29;color:#8da8bd;}
QScrollBar:vertical {background:#101924;width:11px;}
QScrollBar::handle:vertical {background:#3b526a;border-radius:5px;}
"""


def label(text, kind=""):
    widget = QLabel(str(text))
    if kind:
        widget.setObjectName(kind)
    widget.setWordWrap(True)
    return widget


def panel(layout=None):
    frame = QFrame()
    frame.setObjectName("panel")
    frame.setLayout(layout or QVBoxLayout())
    frame.layout().setContentsMargins(17, 15, 17, 15)
    frame.layout().setSpacing(11)
    return frame


def section(title, subtitle=""):
    box = QVBoxLayout()
    box.setSpacing(2)
    box.addWidget(label(title, "headline"))
    if subtitle:
        box.addWidget(label(subtitle, "muted"))
    return box


def setup_table(table, headers):
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)


def cell(text, color=None):
    item = QTableWidgetItem(str(text if text is not None else "—"))
    if color:
        item.setForeground(QColor(color))
    return item


def risk_color(name):
    value = str(name)
    if "待人工" in value or "临界" in value:
        return "#ffc47d"
    if "超量" in value and "未超量" not in value:
        return "#ff7c80"
    if "未超量" in value or "已通过" in value:
        return "#6ddac5"
    return "#a7bbcf"


class FoodStore(Store):
    def __init__(self, path):
        super().__init__(path)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS cases(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          batch_no TEXT NOT NULL, sample_no TEXT NOT NULL,
          food_name TEXT NOT NULL, food_category TEXT NOT NULL,
          additive_name TEXT NOT NULL, detected_value TEXT NOT NULL,
          unit TEXT NOT NULL, limit_value TEXT NOT NULL,
          comparison_basis TEXT NOT NULL, rule_id TEXT NOT NULL,
          rule_source TEXT NOT NULL, result_id INTEGER,
          risk_label TEXT NOT NULL DEFAULT '待计算',
          ratio TEXT NOT NULL DEFAULT '—',
          status TEXT NOT NULL DEFAULT '草稿',
          created TEXT NOT NULL,
          FOREIGN KEY(result_id) REFERENCES results(id)
        );
        """)

    def add_case(self, data):
        required = ("batch_no", "sample_no", "food_name", "food_category",
                    "additive_name", "detected_value", "unit", "limit_value",
                    "comparison_basis", "rule_id", "rule_source")
        for field in required:
            if not str(data.get(field, "")).strip():
                raise ValueError("请填写完整字段：" + field)
        for field in ("detected_value", "limit_value"):
            value = float(data[field])
            if not math.isfinite(value) or value < 0 or (field == "limit_value" and value == 0):
                raise ValueError(field + "必须为有效的非负数，限量须大于0")
        if data["comparison_basis"] not in ("成品残留量", "最大使用量", "未确认"):
            raise ValueError("比较口径无效")
        with self.db:
            cursor = self.db.execute(
                """INSERT INTO cases(batch_no,sample_no,food_name,food_category,
                   additive_name,detected_value,unit,limit_value,comparison_basis,
                   rule_id,rule_source,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                tuple(str(data[field]).strip() for field in required) + (datetime.now().isoformat(timespec="seconds"),),
            )
            case_id = cursor.lastrowid
        self.record("建立检测任务", case_id, data["sample_no"])
        return case_id

    def cases(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM cases ORDER BY id DESC").fetchall()]

    def case(self, case_id):
        row = self.db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if row is None:
            raise ValueError("检测任务不存在")
        return dict(row)

    def save_assessment(self, case_id, payload, result):
        rid = self.save_result("excess_ratio", payload, result)
        row = result["rows"][0]
        with self.db:
            self.db.execute(
                "UPDATE cases SET result_id=?,risk_label=?,ratio=?,status='草稿' WHERE id=?",
                (rid, row["初筛标签"], row["超量比值"], case_id),
            )
        self.record("完成初筛", case_id, row["初筛标签"])
        return rid

    def review_case(self, case_id, target, opinion):
        row = self.case(case_id)
        if row["result_id"] is None:
            raise ValueError("请先完成初筛")
        result = self.get(row["result_id"])
        self.transition(row["result_id"], target, result["version"])
        with self.db:
            self.db.execute("UPDATE cases SET status=? WHERE id=?", (target, case_id))
        self.record("复核意见", case_id, opinion or "未填写")

    def events(self, limit=9):
        return [dict(row) for row in self.db.execute(
            "SELECT created,actor,action,detail FROM audit ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


class MetricCard(QFrame):
    def __init__(self, title, value="0", detail=""):
        super().__init__()
        self.setObjectName("metricCard")
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 12, 16, 12)
        box.addWidget(label(title, "muted"))
        self.number = label(value, "metricValue")
        box.addWidget(self.number)
        box.addWidget(label(detail, "muted"))

    def set_value(self, value):
        self.number.setText(str(value))


class Dashboard(QWidget):
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window
        root = QVBoxLayout(self)
        root.setContentsMargins(23, 18, 23, 18)
        root.setSpacing(14)
        root.addLayout(section("检测任务总览", "从批次、样品到初筛复核的统一工作台 · 所有数值均来自本地记录"))
        cards = QHBoxLayout()
        self.total = MetricCard("样品总数", "0", "已登记的检测记录")
        self.flagged = MetricCard("疑似超量", "0", "需优先核对")
        self.pending = MetricCard("待人工复核", "0", "规则或口径待确认")
        self.approved = MetricCard("已复核", "0", "已通过的初筛记录")
        for card in (self.total, self.flagged, self.pending, self.approved):
            cards.addWidget(card)
        root.addLayout(cards)
        center = QHBoxLayout()
        scene_box = panel()
        scene_box.layout().addWidget(label("批次风险空间 / 3D SCREENING MAP", "sectionTitle"))
        self.scene = RiskScene()
        self.scene.selected.connect(self.open_case)
        scene_box.layout().addWidget(self.scene, 1)
        center.addWidget(scene_box, 3)
        queue_box = panel()
        queue_box.layout().addWidget(label("重点任务", "sectionTitle"))
        queue_box.layout().addWidget(label("点击记录进入判读详情", "muted"))
        self.queue = QTableWidget()
        setup_table(self.queue, ["样品", "添加剂", "状态"])
        self.queue.cellDoubleClicked.connect(lambda row, col: self.open_case(row))
        queue_box.layout().addWidget(self.queue, 1)
        center.addWidget(queue_box, 2)
        root.addLayout(center, 1)
        event_box = panel()
        event_box.layout().addWidget(label("操作与复核事件", "sectionTitle"))
        self.events_list = QListWidget()
        self.events_list.setMaximumHeight(140)
        event_box.layout().addWidget(self.events_list)
        root.addWidget(event_box)

    def open_case(self, index):
        rows = self.app_window.store.cases()
        if 0 <= index < len(rows):
            self.app_window.select_case(rows[index]["id"], "检测结果")

    def refresh(self):
        rows = self.app_window.store.cases()
        self.total.set_value(len(rows))
        self.flagged.set_value(sum("超量" in r["risk_label"] and "未超量" not in r["risk_label"] for r in rows))
        self.pending.set_value(sum("复核" in r["risk_label"] for r in rows))
        self.approved.set_value(sum(r["status"] == "已通过" for r in rows))
        self.scene.set_rows(rows)
        self.queue.setRowCount(min(6, len(rows)))
        for index, row in enumerate(rows[:6]):
            for column, text in enumerate((row["sample_no"], row["additive_name"], row["risk_label"])):
                self.queue.setItem(index, column, cell(text, risk_color(row["risk_label"]) if column == 2 else None))
        self.events_list.clear()
        for event in self.app_window.store.events():
            self.events_list.addItem(
                f"{event['created'][11:19]}   {event['actor']}   {event['action']}   {event['detail']}"
            )


DEMO_CASES = [
    ("LOT-260923-A", "S-001", "酱油", "调味品", "苯甲酸", "1.20", "g/kg", "1.0", "成品残留量", "DEMO-R001"),
    ("LOT-260923-A", "S-002", "果汁饮料", "饮料", "山梨酸", "0.36", "g/kg", "0.5", "成品残留量", "DEMO-R002"),
    ("LOT-260923-B", "S-003", "糕点", "焙烤食品", "脱氢乙酸", "0.28", "g/kg", "0.3", "最大使用量", "DEMO-R003"),
    ("LOT-260923-B", "S-004", "调味酱", "调味品", "苯甲酸", "0.82", "g/kg", "1.0", "成品残留量", "DEMO-R004"),
    ("LOT-260923-C", "S-005", "复合饮料", "饮料", "山梨酸", "0.57", "g/kg", "0.5", "成品残留量", "DEMO-R005"),
]


class SamplesPage(QWidget):
    FIELDS = (
        ("batch_no", "检测批次号"), ("sample_no", "样品编号"),
        ("food_name", "食品名称"), ("food_category", "食品分类"),
        ("additive_name", "添加剂名称"), ("detected_value", "成品检测值"),
        ("limit_value", "用户核验的规则值"), ("rule_id", "规则标识"),
        ("rule_source", "规则来源／版本"),
    )

    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window
        root = QVBoxLayout(self)
        root.setContentsMargins(23, 18, 23, 18)
        root.setSpacing(14)
        root.addLayout(section("样品与检测任务", "先登记样品，再录入已有实验室检测结果；不从照片推断添加剂含量"))
        root.addWidget(label("演示样例中的规则值是虚构数据，仅用于软件操作展示，不得用于真实判定。", "warning"))
        split = QSplitter()
        form_box = panel()
        form_box.setMinimumWidth(330)
        form_box.layout().addWidget(label("新建检测任务", "sectionTitle"))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.fields = {}
        for key, title in self.FIELDS:
            edit = QLineEdit()
            edit.setPlaceholderText(title)
            form.addRow(title, edit)
            self.fields[key] = edit
        self.unit = QComboBox()
        self.unit.addItems(["g/kg", "mg/kg"])
        form.addRow("检测／规则单位", self.unit)
        self.basis = QComboBox()
        self.basis.addItems(["成品残留量", "最大使用量", "未确认"])
        form.addRow("比较口径", self.basis)
        form_box.layout().addLayout(form)
        buttons = QHBoxLayout()
        save = QPushButton("保存任务")
        save.clicked.connect(self.save_case)
        demo = QPushButton("载入演示批次")
        demo.setObjectName("quiet")
        demo.clicked.connect(self.load_demo)
        buttons.addWidget(save)
        buttons.addWidget(demo)
        form_box.layout().addLayout(buttons)
        form_box.layout().addWidget(label("规则匹配和比较口径必须由专业人员核验；缺失时进入人工复核。", "muted"))
        form_box.layout().addStretch()
        split.addWidget(form_box)
        table_box = panel()
        table_box.layout().addWidget(label("检测任务列表", "sectionTitle"))
        self.table = QTableWidget()
        setup_table(self.table, ["编号", "批次", "食品", "添加剂", "检测值", "初筛状态"])
        self.table.cellDoubleClicked.connect(self.open_result)
        table_box.layout().addWidget(self.table)
        split.addWidget(table_box)
        split.setSizes([380, 790])
        root.addWidget(split, 1)

    def form_data(self):
        data = {key: edit.text().strip() for key, edit in self.fields.items()}
        data["unit"] = self.unit.currentText()
        data["comparison_basis"] = self.basis.currentText()
        return data

    def save_case(self):
        try:
            case_id = self.app_window.store.add_case(self.form_data())
            self.app_window.refresh_all()
            self.app_window.select_case(case_id, "检测结果")
        except Exception as exc:
            QMessageBox.warning(self, "录入未完成", str(exc))

    def load_demo(self):
        if self.app_window.store.cases():
            QMessageBox.information(self, "演示数据", "已有检测任务；为避免重复载入，本次未新增样例。")
            return
        for values in DEMO_CASES:
            data = dict(zip(
                ("batch_no", "sample_no", "food_name", "food_category", "additive_name",
                 "detected_value", "unit", "limit_value", "comparison_basis", "rule_id"),
                values,
            ))
            data["rule_source"] = "DEMO-SPEC-2026 / 虚构演示规则"
            self.app_window.store.add_case(data)
        self.app_window.refresh_all()

    def open_result(self, row, column):
        rows = self.app_window.store.cases()
        if 0 <= row < len(rows):
            self.app_window.select_case(rows[row]["id"], "检测结果")

    def refresh(self):
        rows = self.app_window.store.cases()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = (row["sample_no"], row["batch_no"], row["food_name"],
                      row["additive_name"], row["detected_value"] + " " + row["unit"], row["risk_label"])
            for j, value in enumerate(values):
                self.table.setItem(i, j, cell(value, risk_color(value) if j == 5 else None))


def assessment_payload(case):
    from modules.excess_ratio.logic import Engine
    engine = Engine()
    payload = copy.deepcopy(engine.example())
    payload["as_of_date"] = date.today().isoformat()
    record = copy.deepcopy(payload["records"][0])
    record.update({
        "record_id": case["sample_no"],
        "food_name": case["food_name"],
        "additive_name": case["additive_name"],
        "detected_value": case["detected_value"],
        "unit": case["unit"],
        "sample_batch": case["batch_no"],
        "laboratory": "用户录入／待核验",
    })
    rule = record["matched_rules"][0]
    rule.update({
        "rule_id": case["rule_id"],
        "limit_type": engine.LIMIT_NUMERIC,
        "limit_value": case["limit_value"],
        "unit": case["unit"],
        "effective_date": "2025-01-01",
        "expiry_date": None,
    })
    if case["comparison_basis"] == "未确认":
        rule.pop("comparison_basis", None)
    else:
        rule["comparison_basis"] = case["comparison_basis"]
    record["matched_rules"] = [rule]
    payload["records"] = [record]
    return engine, payload


class ResultsPage(QWidget):
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window
        self.selected_id = None
        root = QVBoxLayout(self)
        root.setContentsMargins(23, 18, 23, 18)
        root.setSpacing(14)
        root.addLayout(section("检测结果与初筛判读", "每条样品先核对检测值、单位、比较口径及规则来源，再运行数值初筛"))
        split = QSplitter()
        left = panel()
        left.layout().addWidget(label("待处理样品", "sectionTitle"))
        self.table = QTableWidget()
        setup_table(self.table, ["样品", "食品", "检测值", "比值", "初筛标签"])
        self.table.cellClicked.connect(self.pick)
        left.layout().addWidget(self.table)
        split.addWidget(left)
        right = panel()
        right.layout().addWidget(label("判读依据", "sectionTitle"))
        self.details = label("选择左侧样品，查看检测值、规则和来源。", "muted")
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right.layout().addWidget(self.details)
        self.verdict = label("尚未计算", "metricValue")
        right.layout().addWidget(self.verdict)
        self.explain = label("结果仅用于内部初筛；不能代替人工审查。", "muted")
        right.layout().addWidget(self.explain)
        buttons = QHBoxLayout()
        run = QPushButton("执行初筛")
        run.clicked.connect(self.assess)
        review = QPushButton("提交复核")
        review.setObjectName("quiet")
        review.clicked.connect(self.submit)
        buttons.addWidget(run)
        buttons.addWidget(review)
        right.layout().addLayout(buttons)
        right.layout().addStretch()
        split.addWidget(right)
        split.setSizes([760, 420])
        root.addWidget(split, 1)

    def pick(self, row, column):
        rows = self.app_window.store.cases()
        if 0 <= row < len(rows):
            self.select_case(rows[row]["id"])

    def select_case(self, case_id):
        self.selected_id = case_id
        self.refresh_detail()

    def refresh_detail(self):
        if self.selected_id is None:
            return
        row = self.app_window.store.case(self.selected_id)
        self.details.setText(
            f"批次：{row['batch_no']}     样品：{row['sample_no']}\n"
            f"食品：{row['food_name']}（{row['food_category']}）\n"
            f"检测项目：{row['additive_name']}\n"
            f"成品检测值：{row['detected_value']} {row['unit']}\n"
            f"规则数值：{row['limit_value']} {row['unit']}\n"
            f"比较口径：{row['comparison_basis']}\n"
            f"规则标识：{row['rule_id']}\n"
            f"来源／版本：{row['rule_source']}"
        )
        self.verdict.setText(row["risk_label"])
        self.verdict.setStyleSheet("color:" + risk_color(row["risk_label"]))
        if row["result_id"]:
            result = json.loads(self.app_window.store.get(row["result_id"])["result"])
            self.explain.setText(result["rows"][0]["预警依据"] + "\n\n" + result["summary"])
        else:
            self.explain.setText("未运行初筛。请先核对规则来源与比较口径。")

    def assess(self):
        if self.selected_id is None:
            QMessageBox.warning(self, "请选择样品", "请先从左侧选择一条检测任务。")
            return
        try:
            row = self.app_window.store.case(self.selected_id)
            engine, payload = assessment_payload(row)
            engine.validate(payload)
            result = engine.calculate(payload)
            check_result(result)
            self.app_window.store.save_assessment(self.selected_id, payload, result)
            self.app_window.refresh_all()
            self.refresh_detail()
        except Exception as exc:
            QMessageBox.warning(self, "初筛未完成", str(exc))

    def submit(self):
        if self.selected_id is None:
            return
        try:
            self.app_window.store.review_case(self.selected_id, "已提交", "提交人工复核")
            self.app_window.refresh_all()
            self.refresh_detail()
        except Exception as exc:
            QMessageBox.warning(self, "提交未完成", str(exc))

    def refresh(self):
        rows = self.app_window.store.cases()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = (row["sample_no"], row["food_name"],
                      row["detected_value"] + " " + row["unit"], row["ratio"], row["risk_label"])
            for j, value in enumerate(values):
                self.table.setItem(i, j, cell(value, risk_color(value) if j == 4 else None))
        self.refresh_detail()


class RulesPage(QWidget):
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window
        root = QVBoxLayout(self)
        root.setContentsMargins(23, 18, 23, 18)
        root.setSpacing(14)
        root.addLayout(section("规则与依据", "规则必须有来源、版本和比较口径；本页展示当前任务所引用的规则快照"))
        root.addWidget(label("当前演示数据不是 GB 2760 的正式限量库。真实使用前须由专业人员核验食品分类、适用条件及标准版本。", "warning"))
        box = panel()
        box.layout().addWidget(label("任务规则快照", "sectionTitle"))
        self.table = QTableWidget()
        setup_table(self.table, ["规则标识", "食品分类", "添加剂", "规则值", "比较口径", "来源／版本"])
        box.layout().addWidget(self.table)
        root.addWidget(box, 1)
        foot = panel()
        foot.layout().addWidget(label("判读顺序", "sectionTitle"))
        foot.layout().addWidget(label(
            "① 核对食品分类与添加剂是否适用  →  ② 核对标准版本和来源  →  "
            "③ 核对最大使用量或成品残留量口径  →  ④ 核对检测单位和测量不确定度  →  ⑤ 执行初筛",
            "muted",
        ))
        root.addWidget(foot)

    def refresh(self):
        rows = self.app_window.store.cases()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            values = (row["rule_id"], row["food_category"], row["additive_name"],
                      row["limit_value"] + " " + row["unit"], row["comparison_basis"], row["rule_source"])
            for j, value in enumerate(values):
                self.table.setItem(i, j, cell(value, "#ffc47d" if j == 4 and value != "成品残留量" else None))


class RiskPage(QWidget):
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window
        self.selected_id = None
        root = QVBoxLayout(self)
        root.setContentsMargins(23, 18, 23, 18)
        root.setSpacing(14)
        root.addLayout(section("风险空间与异常追踪", "交互式 3D 视图与真实样品记录联动；拖动旋转、点击柱体查看判读依据"))
        split = QSplitter()
        scene_box = panel()
        self.scene = RiskScene()
        self.scene.setMinimumHeight(520)
        self.scene.selected.connect(self.pick)
        scene_box.layout().addWidget(self.scene)
        split.addWidget(scene_box)
        detail_box = panel()
        detail_box.setMinimumWidth(270)
        detail_box.layout().addWidget(label("选中任务", "sectionTitle"))
        self.detail = label("点击左侧柱体查看样品与规则。", "muted")
        detail_box.layout().addWidget(self.detail)
        go = QPushButton("打开判读详情")
        go.clicked.connect(self.open_result)
        detail_box.layout().addWidget(go)
        detail_box.layout().addStretch()
        split.addWidget(detail_box)
        split.setSizes([900, 280])
        root.addWidget(split, 1)
        root.addWidget(label("本视图只显示已录入样品的相对数值，不代表食品内部结构，也不用于从照片推断含量。", "muted"))

    def pick(self, index):
        rows = self.app_window.store.cases()
        if 0 <= index < len(rows):
            row = rows[index]
            self.selected_id = row["id"]
            self.detail.setText(
                f"样品 {row['sample_no']}  ·  {row['food_name']}\n"
                f"检测项目：{row['additive_name']}\n"
                f"成品检测值：{row['detected_value']} {row['unit']}\n"
                f"规则：{row['rule_id']}／{row['comparison_basis']}\n"
                f"初筛：{row['risk_label']}\n比值：{row['ratio']}"
            )

    def open_result(self):
        if self.selected_id is not None:
            self.app_window.select_case(self.selected_id, "检测结果")

    def refresh(self):
        rows = self.app_window.store.cases()
        self.scene.set_rows(rows)
        if rows:
            selected = next((i for i, row in enumerate(rows) if row["id"] == self.selected_id), 0)
            self.pick(selected)
        else:
            self.selected_id = None
            self.detail.setText("暂无检测任务。请先在‘样品与批次’登记记录。")


class ReviewPage(QWidget):
    def __init__(self, app_window):
        super().__init__()
        self.app_window = app_window
        self.selected_id = None
        root = QVBoxLayout(self)
        root.setContentsMargins(23, 18, 23, 18)
        root.setSpacing(14)
        root.addLayout(section("复核与报告", "初筛结果须由授权人员核对；通过或退回都记录操作者与时间"))
        split = QSplitter()
        list_box = panel()
        list_box.layout().addWidget(label("复核队列", "sectionTitle"))
        self.table = QTableWidget()
        setup_table(self.table, ["样品", "添加剂", "初筛", "流程状态"])
        self.table.cellClicked.connect(self.pick)
        list_box.layout().addWidget(self.table)
        split.addWidget(list_box)
        detail_box = panel()
        detail_box.setMinimumWidth(320)
        detail_box.layout().addWidget(label("复核操作", "sectionTitle"))
        self.detail = label("选择左侧记录。", "muted")
        detail_box.layout().addWidget(self.detail)
        detail_box.layout().addWidget(label("复核意见", "sectionTitle"))
        self.opinion = QTextEdit()
        self.opinion.setPlaceholderText("记录规则适用性、检测资料核对情况或退回原因")
        self.opinion.setMaximumHeight(110)
        detail_box.layout().addWidget(self.opinion)
        actions = QHBoxLayout()
        approve = QPushButton("复核通过")
        approve.clicked.connect(lambda: self.review("已通过"))
        reject = QPushButton("退回修改")
        reject.setObjectName("danger")
        reject.clicked.connect(lambda: self.review("已退回"))
        actions.addWidget(approve)
        actions.addWidget(reject)
        detail_box.layout().addLayout(actions)
        report = QPushButton("导出 PDF 初筛报告")
        report.setObjectName("quiet")
        report.clicked.connect(self.export_pdf)
        detail_box.layout().addWidget(report)
        detail_box.layout().addStretch()
        split.addWidget(detail_box)
        split.setSizes([800, 380])
        root.addWidget(split, 1)

    def pick(self, index, column):
        rows = self.app_window.store.cases()
        if 0 <= index < len(rows):
            self.select_case(rows[index]["id"])

    def select_case(self, case_id):
        self.selected_id = case_id
        row = self.app_window.store.case(case_id)
        self.detail.setText(
            f"样品：{row['sample_no']}  ·  {row['food_name']}\n"
            f"添加剂：{row['additive_name']}\n"
            f"初筛标签：{row['risk_label']}\n"
            f"规则标识：{row['rule_id']}\n"
            f"规则来源：{row['rule_source']}\n"
            f"当前状态：{row['status']}"
        )

    def review(self, target):
        if self.selected_id is None:
            QMessageBox.warning(self, "未选样品", "请先选择一条检测任务。")
            return
        try:
            self.app_window.store.review_case(self.selected_id, target, self.opinion.toPlainText().strip())
            self.app_window.refresh_all()
            self.select_case(self.selected_id)
        except Exception as exc:
            QMessageBox.warning(self, "复核未完成", str(exc))

    def export_pdf(self):
        if self.selected_id is None:
            QMessageBox.warning(self, "未选样品", "请先选择一条检测任务。")
            return
        row = self.app_window.store.case(self.selected_id)
        if row["result_id"] is None:
            QMessageBox.warning(self, "尚无结果", "请先完成初筛。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存初筛报告", row["sample_no"] + "_初筛报告.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            from html import escape
            from PyQt6.QtGui import QPdfWriter, QTextDocument
            from PyQt6.QtGui import QPageSize
            result = json.loads(self.app_window.store.get(row["result_id"])["result"])
            evidence = result["rows"][0]["预警依据"]
            html = (
                "<html><body style='font-family:Microsoft YaHei,PingFang SC;font-size:11pt'>"
                "<h1>食品添加剂使用风险初筛报告</h1>"
                "<p>本报告仅供内部初筛及人工复核，不作法定合规或产品放行结论。</p>"
                "<table border='1' cellspacing='0' cellpadding='8' width='100%'>"
                + "".join(
                    f"<tr><td>{escape(title)}</td><td>{escape(str(row[key]))}</td></tr>"
                    for title, key in (
                        ("批次", "batch_no"), ("样品", "sample_no"), ("食品", "food_name"),
                        ("食品分类", "food_category"), ("添加剂", "additive_name"),
                        ("检测值", "detected_value"), ("单位", "unit"),
                        ("规则值", "limit_value"), ("规则口径", "comparison_basis"),
                        ("规则来源", "rule_source"), ("初筛标签", "risk_label"),
                        ("复核状态", "status"),
                    )
                )
                + "</table><h2>判读依据</h2><p>" + escape(evidence) + "</p>"
                + "<p>生成时间：" + escape(datetime.now().isoformat(timespec="seconds")) + "</p></body></html>"
            )
            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            document = QTextDocument()
            document.setHtml(html)
            document.print_(writer)
            self.app_window.store.record("导出初筛报告", self.selected_id, Path(path).name)
            QMessageBox.information(self, "导出完成", "初筛报告已保存。")
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

    def refresh(self):
        rows = self.app_window.store.cases()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, value in enumerate((
                row["sample_no"], row["additive_name"], row["risk_label"], row["status"]
            )):
                self.table.setItem(i, j, cell(value, risk_color(value) if j >= 2 else None))
        if self.selected_id is not None:
            self.select_case(self.selected_id)


FIELD_LABELS = {
    "as_of_date": "判读日期", "rounding_places": "显示精度", "records": "检测记录",
    "record_id": "记录编号", "sample_batch": "批次", "food_name": "食品名称",
    "food_category": "食品分类", "additive_name": "添加剂名称",
    "detected_value": "检测值", "limit_value": "规则数值", "unit": "单位",
    "matched_rules": "匹配规则", "rule_id": "规则编号",
    "comparison_basis": "比较口径", "effective_date": "生效日期",
    "expiry_date": "失效日期", "detection_limit": "检出限",
    "laboratory": "检测机构", "limit_type": "限量类型",
    "sample_name": "样品名称", "food_candidates": "候选食品分类",
    "production_date": "生产日期", "ingredients": "配料",
    "verifications": "分类核验", "rules": "适用规则",
    "code": "分类代码", "name": "名称", "confirmed": "已确认",
    "batch_no": "检测批次", "sample_no": "样品编号",
    "measurements": "重复测定记录", "notes": "备注",
}


class EnginePage(QWidget):
    """Business forms and record cards instead of a raw data tree."""
    def __init__(self, store, spec):
        super().__init__()
        self.store, self.spec = store, spec
        module = __import__("modules." + spec["id"] + ".logic", fromlist=["Engine"])
        self.engine = module.Engine()
        self.template = None
        self.scalar_items = []
        self.result = None
        self.rid = None
        root = QVBoxLayout(self)
        root.setContentsMargins(23, 18, 23, 18)
        root.setSpacing(12)
        root.addLayout(section(spec["title"], spec["purpose"]))
        actions = QHBoxLayout()
        for text, callback, quiet in (
            ("载入演示数据", self.load_demo, True),
            ("运行专项分析", self.calculate, False),
            ("提交复核", lambda: self.change_state("已提交"), True),
            ("复核通过", lambda: self.change_state("已通过"), True),
            ("导出计算明细", self.export_result, True),
        ):
            button = QPushButton(text)
            if quiet:
                button.setObjectName("quiet")
            button.clicked.connect(lambda checked=False, fn=callback: self.guarded(fn))
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)
        self.status = label("专项分析 · 等待运行", "status")
        root.addWidget(self.status)
        split = QSplitter()
        inputs = panel()
        inputs.layout().addWidget(label("业务资料录入", "sectionTitle"))
        inputs.layout().addWidget(label("切换资料标签，在卡片中填写和核对记录。", "muted"))
        self.tabs = QTabWidget()
        inputs.layout().addWidget(self.tabs)
        split.addWidget(inputs)
        results = panel()
        results.layout().addWidget(label("分析结论与明细", "sectionTitle"))
        self.summary = label("运行后显示可复核的计算结论。", "muted")
        results.layout().addWidget(self.summary)
        self.metrics = label("指标将在这里显示", "status")
        results.layout().addWidget(self.metrics)
        self.table = QTableWidget()
        setup_table(self.table, [])
        results.layout().addWidget(self.table, 1)
        self.rules = label("业务规则：\n" + "\n".join("• " + rule for rule in spec["rules"]), "muted")
        results.layout().addWidget(self.rules)
        split.addWidget(results)
        split.setSizes([480, 760])
        root.addWidget(split, 1)
        self.load_demo()

    def guarded(self, fn):
        try:
            fn()
        except Exception as exc:
            QMessageBox.warning(self, "操作未完成", str(exc))

    def _name(self, key):
        return FIELD_LABELS.get(str(key), str(key).replace("_", " "))

    def _field(self, form, key, value, path):
        if isinstance(value, bool):
            editor = QComboBox()
            editor.addItem("是", True)
            editor.addItem("否", False)
            editor.setCurrentIndex(0 if value else 1)
        else:
            editor = QLineEdit("" if value is None else str(value))
            editor.setMinimumWidth(150)
        form.addRow(self._name(key) + "：", editor)
        self.scalar_items.append((editor, path, value))

    def _node(self, layout, value, path):
        if isinstance(value, list):
            if not value:
                layout.addWidget(label("暂无记录", "muted"))
            for index, row in enumerate(value):
                caption = (str(row.get("name") or row.get("food_name") or row.get("rule_id") or "")
                           if isinstance(row, dict) else "")
                card = QFrame()
                card.setObjectName("recordCard")
                box = QVBoxLayout(card)
                heading = QHBoxLayout()
                badge = label(f"{index + 1:02d}", "recordBadge")
                badge.setFixedSize(32, 32)
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                heading.addWidget(badge)
                heading.addWidget(label(caption or "记录", "sectionTitle"), 1)
                box.addLayout(heading)
                self._node(box, row, path + (index,))
                layout.addWidget(card)
        elif isinstance(value, dict):
            form = QFormLayout()
            form.setSpacing(8)
            for key, child in value.items():
                if not isinstance(child, (dict, list)):
                    self._field(form, key, child, path + (key,))
            layout.addLayout(form)
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    layout.addWidget(label(self._name(key), "sectionTitle"))
                    self._node(layout, child, path + (key,))
        else:
            form = QFormLayout()
            self._field(form, path[-1], value, path)
            layout.addLayout(form)

    def _tab(self, name, value, path):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        canvas = QWidget()
        box = QVBoxLayout(canvas)
        box.setContentsMargins(13, 13, 13, 13)
        box.setSpacing(11)
        self._node(box, value, path)
        box.addStretch()
        scroll.setWidget(canvas)
        self.tabs.addTab(scroll, name)

    def load_demo(self):
        self.template = copy.deepcopy(self.engine.example())
        self.scalar_items = []
        self.tabs.clear()
        basic = {key: value for key, value in self.template.items()
                 if not isinstance(value, (dict, list))}
        if basic:
            self._tab("基本信息", basic, ())
        for key, value in self.template.items():
            if isinstance(value, (dict, list)):
                self._tab(self._name(key), value, (key,))
        self.result = None
        self.rid = None
        self.status.setText("演示资料已载入 · 可在表单卡片中修改")
        self.summary.setText("输入来自模块样例，执行后显示结果和计算依据。")
        self.metrics.setText("指标将在这里显示")
        self.table.setRowCount(0)

    def collect_payload(self):
        payload = copy.deepcopy(self.template)
        for item, path, original in self.scalar_items:
            value = item.currentData() if isinstance(item, QComboBox) else item.text().strip()
            if original is None:
                parsed = None if value in ("", "—", "None") else value
            elif isinstance(original, bool):
                parsed = bool(value)
            elif isinstance(original, int):
                parsed = int(value)
            elif isinstance(original, float):
                parsed = float(value)
            else:
                parsed = value
            target = payload
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = parsed
        return payload

    def calculate(self):
        payload = self.collect_payload()
        self.engine.validate(payload)
        result = self.engine.calculate(payload)
        check_result(result)
        self.rid = self.store.save_result(self.spec["id"], payload, result)
        self.show_result(result)
        self.status.setText(f"专项分析 #{self.rid} · 草稿 · 结果已保存")

    def show_result(self, result):
        self.result = result
        self.summary.setText(result["summary"])
        self.metrics.setText("   ·   ".join(f"{key}：{value}" for key, value in list(result["metrics"].items())[:4]))
        rows = result["rows"]
        headers = list(rows[0]) if rows else []
        setup_table(self.table, headers)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(headers):
                self.table.setItem(i, j, cell(row.get(key)))
        self.table.resizeColumnsToContents()

    def change_state(self, state):
        if self.rid is None:
            raise ValueError("请先运行专项分析")
        current = self.store.get(self.rid)
        new = self.store.transition(self.rid, state, current["version"])
        self.status.setText(f"专项分析 #{self.rid} · {new['state']} · 版本 {new['version']}")

    def export_result(self, path=None):
        if self.result is None:
            raise ValueError("请先运行专项分析")
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "保存计算明细", self.spec["id"] + "_details.json", "JSON 数据 (*.json)"
            )
        if path:
            Path(path).write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding="utf-8")
            self.store.record("导出计算明细", self.rid, Path(path).name)
        return path


class FoodWindow(QMainWindow):
    BUSINESS_PAGES = (
        ("检测总览", Dashboard),
        ("样品与批次", SamplesPage),
        ("检测结果", ResultsPage),
        ("规则与依据", RulesPage),
        ("风险空间", RiskPage),
        ("复核与报告", ReviewPage),
    )

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.setWindowTitle(PLAN["name"] + " · 业务工作台")
        self.resize(1500, 940)
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(243)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(13, 19, 13, 12)
        side.addWidget(label("◇  食安智检", "brand"))
        side.addWidget(label("FOOD ADDITIVE SCREENING", "muted"))
        side.addSpacing(18)
        side.addWidget(label("业务工作台", "sectionTitle"))
        self.nav = QListWidget()
        self.nav.setSpacing(2)
        self.titles = [name for name, _ in self.BUSINESS_PAGES]
        self.titles += [spec["title"] for spec in PLAN["modules"]]
        for index, title in enumerate(self.titles):
            self.nav.addItem(QListWidgetItem(f"{index + 1:02d}  {title}"))
        side.addWidget(self.nav, 1)
        side.addWidget(label("演示工作站  ·  本地数据", "muted"))
        side.addWidget(label(f"当前账号：{store.actor}  /  {store.role}", "muted"))
        shell.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("panel")
        header.setStyleSheet("QFrame#panel{border-radius:0;border-top:0;border-right:0;border-left:0;}")
        head = QHBoxLayout(header)
        head.setContentsMargins(22, 11, 22, 11)
        left = QVBoxLayout()
        left.addWidget(label(PLAN["name"], "sectionTitle"))
        left.addWidget(label("批次登记  /  规则核验  /  初筛判读  /  人工复核", "muted"))
        head.addLayout(left)
        head.addStretch()
        head.addWidget(label("●  本地演示 · 非实时仪器数据", "status"))
        content_layout.addWidget(header)
        self.stack = QStackedWidget()
        self.business_pages = [cls(self) for _, cls in self.BUSINESS_PAGES]
        self.engine_pages = [EnginePage(store, spec) for spec in PLAN["modules"]]
        for page in self.business_pages + self.engine_pages:
            self.stack.addWidget(page)
        content_layout.addWidget(self.stack, 1)
        shell.addWidget(content, 1)
        self.nav.currentRowChanged.connect(self.change_page)
        self.nav.setCurrentRow(0)
        self.statusBar().showMessage(
            "就绪  ·  先登记样品和已有实验室检测结果；演示数值不可用于真实法定判定"
        )
        self.refresh_all()

    def change_page(self, index):
        if index < 0:
            return
        self.stack.setCurrentIndex(index)
        self.statusBar().showMessage(
            f"{self.titles[index]}  ·  操作者 {self.store.actor}  ·  数据保存在本地 SQLite"
        )

    def page(self, title):
        return self.business_pages[self.titles.index(title)]

    def select_case(self, case_id, title="检测结果"):
        self.nav.setCurrentRow(self.titles.index(title))
        target = self.page(title)
        if hasattr(target, "select_case"):
            target.select_case(case_id)

    def refresh_all(self):
        for page in self.business_pages:
            page.refresh()


def _set_font(app):
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )
    for path in candidates:
        if path.exists():
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id >= 0:
                names = QFontDatabase.applicationFontFamilies(font_id)
                if names:
                    app.setFont(QFont(names[0], 10))
                    break


def capture(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    _set_font(app)
    app.setStyle("Fusion")
    app.setStyleSheet(THEME)
    manifest = []
    with tempfile.TemporaryDirectory(prefix="food-workbench-") as temp:
        store = FoodStore(Path(temp) / "demo.sqlite")
        login = Login(store)
        login.show()
        app.processEvents()

        def snap(window, name, title, description, module=""):
            app.processEvents()
            path = output / (name + ".png")
            if not window.grab().save(str(path)):
                raise RuntimeError("截图保存失败：" + name)
            manifest.append({
                "file": path.name, "title": title,
                "description": description, "module": module,
            })

        snap(login, "00_login", "登录工作台", "登录后进入检测任务总览。")
        store.login("admin", "Admin123!")
        login.close()
        window = FoodWindow(store)
        window.show()
        window.page("样品与批次").load_demo()
        from modules.excess_ratio.logic import Engine
        for case in store.cases():
            engine, payload = assessment_payload(case)
            result = engine.calculate(payload)
            store.save_assessment(case["id"], payload, result)
        first = store.cases()[0]
        store.review_case(first["id"], "已提交", "演示初筛记录提交复核")
        store.review_case(first["id"], "已通过", "演示资料核对完成")
        window.refresh_all()

        for index, title in enumerate((
            "检测总览", "样品与批次", "检测结果",
            "规则与依据", "风险空间", "复核与报告",
        ), start=1):
            window.nav.setCurrentRow(window.titles.index(title))
            if title in ("检测结果", "复核与报告"):
                window.select_case(first["id"], title)
            snap(window, f"{index:02}_workflow", title,
                 "端到端业务页面：样品登记、规则核验、初筛和复核都围绕同一批次记录。")

        for index, page in enumerate(window.engine_pages, start=1):
            window.nav.setCurrentRow(5 + index)
            page.load_demo()
            snap(window, f"{index+6:02}_a", page.spec["title"] + " 输入字段",
                 "可编辑字段树提供带名称的结构化录入，不要求用户编写JSON。", page.spec["id"])
            page.calculate()
            snap(window, f"{index+6:02}_b", page.spec["title"] + " 分析结果",
                 "计算结果包含摘要、指标、明细与业务规则。", page.spec["id"])
            page.change_state("已提交")
            page.change_state("已通过")
            page.export_result(output / (page.spec["id"] + "_result.json"))
            snap(window, f"{index+6:02}_c", page.spec["title"] + " 复核留痕",
                 "提交复核与审核动作保存至本地数据记录。", page.spec["id"])
        window.close()
        store.close()
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture")
    args = parser.parse_args()
    if args.capture:
        capture(args.capture)
        return
    app = QApplication(sys.argv)
    _set_font(app)
    app.setStyle("Fusion")
    app.setStyleSheet(THEME)
    store = FoodStore(BASE / "data/app.sqlite")
    login = Login(store)
    if login.exec() != QDialog.DialogCode.Accepted:
        store.close()
        return
    window = FoodWindow(store)
    window.show()
    app.exec()
    store.close()
