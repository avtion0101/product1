"""Interactive OpenCV-rendered risk space for the food safety workbench.

The blocks are data markers, not a reconstruction of a physical laboratory.
"""
import math

import cv2
import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QImage, QPainter, QColor, QFont
from PyQt6.QtWidgets import QWidget


def _polygon(canvas, points, fill, edge=(100, 128, 158)):
    shape = np.asarray(points, dtype=np.int32)
    cv2.fillPoly(canvas, [shape], fill, lineType=cv2.LINE_AA)
    cv2.polylines(canvas, [shape], True, edge, 1, cv2.LINE_AA)


class RiskScene(QWidget):
    selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.yaw = math.radians(-28)
        self.drag_x = None
        self.hitboxes = []
        self.setMinimumHeight(330)
        self.setMouseTracking(True)

    def set_rows(self, rows):
        self.rows = list(rows)[:12]
        self.update()

    def mousePressEvent(self, event):
        self.drag_x = event.position().x()

    def mouseMoveEvent(self, event):
        if self.drag_x is None:
            return
        x = event.position().x()
        self.yaw += (x - self.drag_x) * 0.006
        self.drag_x = x
        self.update()

    def mouseReleaseEvent(self, event):
        if self.drag_x is not None and abs(event.position().x() - self.drag_x) < 5:
            x, y = event.position().x(), event.position().y()
            for left, top, right, bottom, index in self.hitboxes:
                if left <= x <= right and top <= y <= bottom:
                    self.selected.emit(index)
                    break
        self.drag_x = None

    def paintEvent(self, event):
        w, h = max(self.width(), 1), max(self.height(), 1)
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        canvas[:] = (22, 17, 12)
        for y in range(h):
            shade = int(17 + 16 * y / max(h, 1))
            canvas[y, :, :] = (shade + 11, shade + 4, shade)

        scale = min(w / 11.5, h / 7.2)
        cx, cy = w * 0.51, h * 0.57
        cosine, sine = math.cos(self.yaw), math.sin(self.yaw)

        def project(x, depth, z=0):
            rotated_x = x * cosine - depth * sine
            rotated_d = x * sine + depth * cosine
            perspective = 1 / (1 + max(-2.0, rotated_d) * 0.065)
            return (
                int(cx + rotated_x * scale * perspective),
                int(cy + rotated_d * scale * 0.43 * perspective - z * scale * perspective),
            )

        grid_color = (48, 48, 42)
        for i in range(-6, 7):
            cv2.line(canvas, project(i, -3), project(i, 4), grid_color, 1, cv2.LINE_AA)
        for d in range(-3, 5):
            cv2.line(canvas, project(-6, d), project(6, d), grid_color, 1, cv2.LINE_AA)

        entries = self.rows or [
            {"food_name": "演示样品", "risk_label": "待计算", "ratio": 0},
            {"food_name": "示例批次", "risk_label": "待计算", "ratio": 0},
            {"food_name": "规则待核", "risk_label": "待人工复核", "ratio": 0},
        ]
        self.hitboxes = []
        for index, row in enumerate(entries):
            col, line = index % 4, index // 4
            x, d = (col - 1.5) * 2.05, (line - 1) * 1.8
            risk = str(row.get("risk_label", ""))
            try:
                ratio = max(0, min(float(row.get("ratio") or 0), 3))
            except (TypeError, ValueError):
                ratio = 0
            height = 0.42 + ratio * 0.42
            if "未超量" in risk or "已通过" in risk:
                front, top, side = (139, 179, 36), (175, 216, 54), (92, 130, 28)
            elif "超量" in risk or "禁止" in risk:
                front, top, side = (71, 78, 218), (100, 117, 250), (48, 56, 164)
            elif "复核" in risk or "临界" in risk:
                front, top, side = (46, 147, 232), (89, 183, 249), (35, 105, 174)
            else:
                front, top, side = (127, 107, 63), (157, 132, 75), (91, 75, 45)
            half = 0.63
            bottom = [
                project(x-half, d-half), project(x+half, d-half),
                project(x+half, d+half), project(x-half, d+half),
            ]
            upper = [
                project(x-half, d-half, height), project(x+half, d-half, height),
                project(x+half, d+half, height), project(x-half, d+half, height),
            ]
            shadow = [project(x-half-.15, d+half+.08), project(x+half+.15, d+half+.08),
                      project(x+half+.35, d+half+.42), project(x-half, d+half+.42)]
            _polygon(canvas, shadow, (29, 27, 24), (37, 37, 34))
            _polygon(canvas, [bottom[0], bottom[3], upper[3], upper[0]], side)
            _polygon(canvas, [bottom[1], bottom[2], upper[2], upper[1]], side)
            _polygon(canvas, [bottom[3], bottom[2], upper[2], upper[3]], front)
            _polygon(canvas, upper, top)
            xs = [p[0] for p in bottom + upper]
            ys = [p[1] for p in bottom + upper]
            self.hitboxes.append((min(xs), min(ys), max(xs), max(ys), index))
            center = project(x, d, height)
            cv2.circle(canvas, center, 4, (255, 255, 255), -1, cv2.LINE_AA)

        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        image = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        painter = QPainter(self)
        painter.drawImage(0, 0, image)
        painter.setPen(QColor("#dbeafe"))
        painter.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.DemiBold))
        painter.drawText(22, 31, "批次风险空间")
        painter.setPen(QColor("#8298ae"))
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.drawText(22, 52, "拖拽旋转 · 点击柱体查看记录 · 高度仅表示相对比值")
        painter.drawText(22, h - 16, "演示数据可视化，不代表实物结构或图像测定浓度")
        painter.end()
