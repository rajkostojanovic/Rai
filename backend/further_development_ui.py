import math

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QScrollArea,
    QSlider,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


STAGE_DRAG_MIME = "application/x-rai-stage-index"
PHOTO_TIMELINE_TRANSITION_OPTIONS = (
    ("Cut", "cut"),
    ("Mix", "interpolate"),
    ("Fade", "fade"),
    ("Wipe ->", "wipe_horizontal"),
    ("Wipe v", "wipe_vertical"),
    ("Scan", "scanline_reconstruct"),
)


class ImageSetPreviewButton(QToolButton):
    stageSelected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stage_index = 0
        self._drag_start_pos = None
        self.setCheckable(True)
        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(92, 92))
        self.setMinimumSize(116, 126)
        self.setCursor(Qt.OpenHandCursor)
        self.setStyleSheet(
            """
            QToolButton {
                background: #fffdf8;
                border: 1px solid #d8d0c3;
                border-radius: 12px;
                padding: 6px;
                text-align: center;
            }
            QToolButton:checked {
                border: 2px solid #1f6f78;
                background: #eef6f6;
            }
            QToolButton:hover {
                background: #f7f2ea;
            }
            """
        )
        self.clicked.connect(self._emit_selection)

    def set_stage(self, stage_index: int, label: str, pixmap: QPixmap, tooltip: str = ""):
        self._stage_index = max(0, int(stage_index))
        self.setText(str(label))
        self.setIcon(QIcon(pixmap))
        self.setToolTip(str(tooltip or label))

    def stage_index(self):
        return self._stage_index

    def _emit_selection(self):
        self.stageSelected.emit(self._stage_index)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(STAGE_DRAG_MIME, str(self._stage_index).encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.icon().pixmap(self.iconSize()))
        drag.exec(Qt.CopyAction)
        self._drag_start_pos = None


class TimelineSlotButton(QPushButton):
    stageDropped = Signal(int, int)
    slotClicked = Signal(int)
    slotCleared = Signal(int)

    def __init__(self, slot_index: int, parent=None):
        super().__init__(parent)
        self._slot_index = int(slot_index)
        self._slot_number = self._slot_index + 1
        self._stage_item = None
        self.setAcceptDrops(True)
        self.setFixedSize(106, 126)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def set_stage_item(self, slot_number: int, stage_item):
        self._slot_number = max(1, int(slot_number))
        self._stage_item = stage_item if isinstance(stage_item, dict) else None
        if self._stage_item is None:
            self.setToolTip("Drag a picture here, click to assign the selected picture, right-click to clear.")
        else:
            self.setToolTip(str(self._stage_item.get("tooltip", self._stage_item.get("label", ""))))
        self.update()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(STAGE_DRAG_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(STAGE_DRAG_MIME):
            event.ignore()
            return
        try:
            stage_index = int(bytes(event.mimeData().data(STAGE_DRAG_MIME)).decode("utf-8"))
        except Exception:
            event.ignore()
            return
        self.stageDropped.emit(self._slot_index, stage_index)
        event.acceptProposedAction()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.slotCleared.emit(self._slot_index)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self.slotClicked.emit(self._slot_index)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        _ = event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        preview_rect = self.rect().adjusted(14, 8, -14, -42)
        point_center_x = self.rect().center().x()
        point_center_y = self.rect().bottom() - 18
        assigned = self._stage_item is not None

        border_color = QColor("#1f6f78") if self.underMouse() else QColor("#d2c8b8")
        fill_color = QColor("#fffdf8") if assigned else QColor("#faf5eb")
        p.setPen(QPen(border_color, 1.5, Qt.SolidLine if assigned else Qt.DashLine))
        p.setBrush(fill_color)
        p.drawRoundedRect(preview_rect, 12, 12)

        if assigned:
            pixmap = QPixmap.fromImage(self._stage_item["preview"])
            scaled = pixmap.scaled(
                int(max(1, preview_rect.width() - 10)),
                int(max(1, preview_rect.height() - 26)),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            pix_x = int(preview_rect.center().x() - (scaled.width() * 0.5))
            pix_y = int(preview_rect.top() + 6)
            p.drawPixmap(pix_x, pix_y, scaled)
            text = str(self._stage_item.get("label", "Stage"))
            p.setPen(QColor("#26404a"))
        else:
            text = "Drop"
            p.setPen(QColor("#8a8173"))

        text_rect = preview_rect.adjusted(6, int(preview_rect.height() - 22), -6, -4)
        p.drawText(text_rect, Qt.AlignCenter | Qt.TextWordWrap, text)

        p.setPen(QColor("#6a7077"))
        beat_rect = self.rect().adjusted(4, self.height() - 36, -4, -18)
        p.drawText(beat_rect, Qt.AlignCenter, f"Beat {self._slot_number}")

        p.setPen(QPen(QColor("#1f6f78") if assigned else QColor("#b8ab94"), 2))
        p.setBrush(QColor("#1f6f78") if assigned else QColor("#fffdf8"))
        p.drawEllipse(point_center_x - 6, point_center_y - 6, 12, 12)


class PhotoTimelineLaneWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(156)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        line_y = self.height() - 24
        start_x = 32
        end_x = max(start_x + 80, self.width() - 32)
        p.setPen(QPen(QColor("#cfbea5"), 3))
        p.drawLine(start_x, line_y, end_x, line_y)


class LoopCircleWidget(QWidget):
    pointMenuRequested = Signal(int, QPoint)
    pointCleared = Signal(int)
    pointCreateRequested = Signal(float, QPoint)
    transitionMenuRequested = Signal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._slot_count = 4
        self._stage_count = 0
        self._timeline_points = []
        self._hover_point_index = -1
        self._hover_transition_index = -1
        self._hover_ring = False
        self.setMinimumHeight(320)
        self.setMouseTracking(True)
        self.setStyleSheet("background: #f9f7f4; border: 1px solid #d8d0c3; border-radius: 12px;")

    def set_loop(self, slot_count: int, timeline_points, stage_count: int):
        self._slot_count = max(1, int(slot_count))
        self._stage_count = max(0, int(stage_count))
        values = []
        for item in list(timeline_points) if isinstance(timeline_points, (list, tuple)) else []:
            if not isinstance(item, dict):
                continue
            try:
                position = float(item.get("position", 0.0)) % float(self._slot_count)
            except Exception:
                position = 0.0
            try:
                state = max(0, int(item.get("state", 0)))
            except Exception:
                state = 0
            state = min(state, self._stage_count) if self._stage_count > 0 else 0
            if state <= 0:
                continue
            transition = item.get("transition", {})
            values.append(
                {
                    "position": position,
                    "state": state,
                    "transition": transition if isinstance(transition, dict) else {},
                }
            )
        self._timeline_points = sorted(values, key=lambda item: float(item["position"]))
        self.update()

    def _content_rect(self):
        return self.rect().adjusted(18, 18, -18, -18)

    def _center(self):
        return QPointF(self._content_rect().center())

    def _ring_radius(self):
        rect = self._content_rect()
        return max(48.0, min(rect.width(), rect.height()) * 0.36)

    def _transition_outer_scale(self):
        return 0.96

    def _transition_inner_scale(self):
        return 0.58

    def _angle_for_position(self, position: float):
        return (-math.pi / 2.0) + ((2.0 * math.pi * float(position)) / float(max(1, self._slot_count)))

    def _point_for_position(self, position: float, radius_scale: float = 1.0):
        center = self._center()
        radius = self._ring_radius() * float(radius_scale)
        angle = self._angle_for_position(position)
        return QPointF(
            center.x() + (math.cos(angle) * radius),
            center.y() + (math.sin(angle) * radius),
        )

    def _beat_tick_positions(self):
        return [self._point_for_position(slot_index, 1.0) for slot_index in range(self._slot_count)]

    def _timeline_point_positions(self):
        return [self._point_for_position(item["position"], 1.0) for item in self._timeline_points]

    def _arc_points(self, start_position: float, span: float, radius_scale: float):
        step_count = max(12, int(math.ceil(max(0.1, float(span)) * 18.0)))
        points = []
        for step_index in range(step_count + 1):
            progress = float(step_index) / float(step_count)
            position = (float(start_position) + (float(span) * progress)) % float(max(1, self._slot_count))
            points.append(self._point_for_position(position, radius_scale))
        return points

    def _point_at(self, pos):
        target = QPointF(pos)
        for index, point in enumerate(self._timeline_point_positions()):
            if math.hypot(target.x() - point.x(), target.y() - point.y()) <= 22.0:
                return index
        return -1

    def _transition_fill_color(self, effect: str, hovered: bool = False):
        palette = {
            "cut": "#efe3cf",
            "interpolate": "#d8ece8",
            "fade": "#efdee6",
            "wipe_horizontal": "#dfe7f5",
            "wipe_vertical": "#deedf7",
            "scanline_reconstruct": "#f4e7cc",
        }
        color = QColor(palette.get(str(effect or "cut").strip().lower(), "#ebe3d6"))
        color.setAlpha(245 if hovered else 210)
        return color

    def _transition_regions(self):
        regions = []
        if len(self._timeline_points) < 2:
            return regions
        total = float(max(1, self._slot_count))
        for index, point in enumerate(self._timeline_points):
            next_point = self._timeline_points[(index + 1) % len(self._timeline_points)]
            span = (float(next_point["position"]) - float(point["position"])) % total
            if span <= 1e-6:
                span = total
            outer_points = self._arc_points(point["position"], span, self._transition_outer_scale())
            inner_points = list(reversed(self._arc_points(point["position"], span, self._transition_inner_scale())))
            path = QPainterPath()
            path.moveTo(outer_points[0])
            for value in outer_points[1:]:
                path.lineTo(value)
            for value in inner_points:
                path.lineTo(value)
            path.closeSubpath()
            regions.append(
                {
                    "index": index,
                    "path": path,
                    "effect": str(point.get("transition", {}).get("effect", "cut")),
                }
            )
        return regions

    def _transition_at(self, pos):
        target = QPointF(pos)
        for region in self._transition_regions():
            if region["path"].contains(target):
                return int(region["index"])
        return -1

    def _ring_hit(self, pos):
        target = QPointF(pos)
        center = self._center()
        distance = math.hypot(target.x() - center.x(), target.y() - center.y())
        outer_radius = self._ring_radius() + 18.0
        inner_radius = (self._ring_radius() * self._transition_inner_scale()) - 12.0
        return inner_radius <= distance <= outer_radius

    def _timeline_position_at(self, pos):
        target = QPointF(pos)
        center = self._center()
        angle = math.atan2(target.y() - center.y(), target.x() - center.x())
        position = ((angle + (math.pi / 2.0)) / (2.0 * math.pi)) * float(max(1, self._slot_count))
        while position < 0.0:
            position += float(max(1, self._slot_count))
        while position >= float(max(1, self._slot_count)):
            position -= float(max(1, self._slot_count))
        return position

    def _update_hover_state(self, pos=None):
        point_index = -1
        transition_index = -1
        ring_hit = False
        if pos is not None:
            point_index = self._point_at(pos)
            if point_index < 0:
                transition_index = self._transition_at(pos)
                if transition_index < 0:
                    ring_hit = self._ring_hit(pos)
        changed = (
            point_index != self._hover_point_index
            or transition_index != self._hover_transition_index
            or ring_hit != self._hover_ring
        )
        self._hover_point_index = point_index
        self._hover_transition_index = transition_index
        self._hover_ring = ring_hit
        self.setCursor(Qt.PointingHandCursor if point_index >= 0 or transition_index >= 0 or ring_hit else Qt.ArrowCursor)
        if changed:
            self.update()

    def mousePressEvent(self, event):
        self._update_hover_state(event.position())
        marker_index = self._point_at(event.position())
        if marker_index >= 0:
            if event.button() == Qt.RightButton:
                self.pointCleared.emit(marker_index)
                event.accept()
                return
            if event.button() == Qt.LeftButton:
                self.pointMenuRequested.emit(marker_index, event.position().toPoint())
                event.accept()
                return

        transition_index = self._transition_at(event.position())
        if transition_index >= 0 and event.button() == Qt.LeftButton:
            self.transitionMenuRequested.emit(transition_index, event.position().toPoint())
            event.accept()
            return

        if event.button() == Qt.LeftButton and self._ring_hit(event.position()):
            self.pointCreateRequested.emit(self._timeline_position_at(event.position()), event.position().toPoint())
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._update_hover_state(event.position())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._update_hover_state(None)
        super().leaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        center = self._center()
        radius = self._ring_radius()
        tick_positions = self._beat_tick_positions()
        inner_radius = radius * self._transition_inner_scale()
        transition_regions = self._transition_regions()

        outer_rect = QRectF(center.x() - radius, center.y() - radius, radius * 2.0, radius * 2.0)
        inner_rect = QRectF(center.x() - inner_radius, center.y() - inner_radius, inner_radius * 2.0, inner_radius * 2.0)

        p.setPen(QPen(QColor("#d8d0c3"), 1.6))
        p.setBrush(QColor("#fbf6ed"))
        p.drawEllipse(outer_rect)

        if self._hover_ring:
            ring_pen = QPen(QColor("#1f6f78"), 2.2)
        else:
            ring_pen = QPen(QColor("#e1d7c8"), 1.4)
        p.setPen(ring_pen)
        p.setBrush(QColor("#f9f7f4"))
        p.drawEllipse(inner_rect)

        for beat_index, point in enumerate(tick_positions):
            inner_point = self._point_for_position(beat_index, self._transition_inner_scale())
            p.setPen(QPen(QColor("#e5dac9"), 1))
            p.drawLine(inner_point, point)
            p.setPen(QPen(QColor("#d7cbb7"), 1))
            p.setBrush(QColor("#f2ebdf"))
            p.drawEllipse(QRectF(point.x() - 5.5, point.y() - 5.5, 11.0, 11.0))
            label_point = self._point_for_position(beat_index, 1.18)
            beat_rect = QRectF(label_point.x() - 18.0, label_point.y() - 10.0, 36.0, 20.0)
            p.setPen(QColor("#6b716f"))
            p.drawText(beat_rect, Qt.AlignCenter, str(beat_index + 1))

        for region in transition_regions:
            hovered = int(region["index"]) == self._hover_transition_index
            effect = region["effect"]
            p.setPen(QPen(QColor("#c9b99f") if not hovered else QColor("#1f6f78"), 1.8 if hovered else 1.3))
            p.setBrush(self._transition_fill_color(effect, hovered=hovered))
            p.drawPath(region["path"])

        for index, point in enumerate(self._timeline_points):
            marker = self._point_for_position(point["position"], 1.0)
            hovered = index == self._hover_point_index
            node_rect = QRectF(marker.x() - 20.0, marker.y() - 20.0, 40.0, 40.0)
            if hovered:
                halo_rect = QRectF(marker.x() - 24.0, marker.y() - 24.0, 48.0, 48.0)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(31, 111, 120, 48))
                p.drawEllipse(halo_rect)
            p.setPen(QPen(QColor("#145760") if hovered else QColor("#1f6f78"), 2.4 if hovered else 2))
            p.setBrush(QColor("#1f6f78"))
            p.drawEllipse(node_rect)
            p.setPen(QColor("#ffffff"))
            p.drawText(node_rect, Qt.AlignCenter, str(point["state"]))


def _build_change_state_editor(
    panel,
    *,
    parent: QWidget,
    key: str,
    title: str,
    selection_label: str,
    note_text: str,
    include_import_button: bool = False,
    show_selection: bool = True,
    show_stage_info: bool = True,
    show_appearance: bool = True,
    show_loop_note: bool = True,
):
    subtab = QWidget(parent)
    layout = QVBoxLayout(subtab)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(12)

    editor = {
        "key": key,
        "subtab": subtab,
    }

    selection_box, selection_layout = panel._make_section_box(title)
    combo = QComboBox(subtab)
    combo.setToolTip(str(selection_label))
    combo.currentIndexChanged.connect(lambda _=0, editor_key=key: panel._on_change_editor_selection_changed(editor_key))
    selection_layout.addWidget(combo)
    editor["combo"] = combo

    if include_import_button:
        import_button = QPushButton("Import Background...")
        import_button.clicked.connect(panel.backgroundImportRequested.emit)
        selection_layout.addWidget(import_button)
        editor["import_button"] = import_button

    stage_info = panel._make_status_label(note_text)
    selection_layout.addWidget(stage_info)
    editor["stage_info"] = stage_info
    if show_selection or show_stage_info or include_import_button:
        layout.addWidget(selection_box)
    else:
        selection_box.hide()

    transform_box, transform_layout = panel._make_section_box("Transform")
    transform_grid = QGridLayout()
    transform_grid.setSpacing(8)

    translate_button = QPushButton("T")
    translate_button.setCheckable(True)
    translate_button.setFixedHeight(44)
    translate_button.clicked.connect(lambda _=False, editor_key=key: panel._activate_change_transform_mode(editor_key, "translate"))
    transform_grid.addWidget(translate_button, 0, 0)

    rotate_button = QPushButton("R")
    rotate_button.setCheckable(True)
    rotate_button.setFixedHeight(44)
    rotate_button.clicked.connect(lambda _=False, editor_key=key: panel._activate_change_transform_mode(editor_key, "rotate"))
    transform_grid.addWidget(rotate_button, 0, 1)

    scale_button = QPushButton("S")
    scale_button.setCheckable(True)
    scale_button.setFixedHeight(44)
    scale_button.clicked.connect(lambda _=False, editor_key=key: panel._activate_change_transform_mode(editor_key, "scale"))
    transform_grid.addWidget(scale_button, 1, 0)

    reflect_button = QPushButton("M")
    reflect_button.setCheckable(True)
    reflect_button.setFixedHeight(44)
    reflect_button.clicked.connect(lambda _=False, editor_key=key: panel._activate_change_transform_mode(editor_key, "reflect"))
    transform_grid.addWidget(reflect_button, 1, 1)

    transform_layout.addLayout(transform_grid)
    action_grid = QGridLayout()
    action_grid.setHorizontalSpacing(8)
    action_grid.setVerticalSpacing(8)

    apply_button = QPushButton("Apply State")
    reset_button = QPushButton("Reset Preview")
    reset_states_button = QPushButton("Clear States")
    apply_button.setMinimumHeight(40)
    reset_button.setMinimumHeight(40)
    reset_states_button.setMinimumHeight(40)
    state_counter = QLabel("0 states")
    state_counter.setAlignment(Qt.AlignCenter)
    action_grid.addWidget(apply_button, 0, 0)
    action_grid.addWidget(reset_button, 1, 0)
    action_grid.addWidget(reset_states_button, 2, 0)
    action_grid.addWidget(state_counter, 3, 0)
    transform_layout.addLayout(action_grid)
    layout.addWidget(transform_box)
    editor["transform_buttons"] = {
        "translate": translate_button,
        "rotate": rotate_button,
        "scale": scale_button,
        "reflect": reflect_button,
    }
    editor["transform_hint"] = None
    editor["preview_toggle"] = None

    preview_box, preview_layout = panel._make_section_box("Appearance")
    color_row = QHBoxLayout()
    color_button = QPushButton("#000000")
    color_button.setToolTip("Color")
    color_button.clicked.connect(lambda _=False, editor_key=key: panel._choose_change_editor_color(editor_key))
    color_row.addWidget(color_button)
    color_row.addStretch(1)
    preview_layout.addLayout(color_row)
    if show_appearance:
        layout.addWidget(preview_box)
    else:
        preview_box.hide()
    editor["color_button"] = color_button
    editor["visibility_combo"] = None

    if key == "object":
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacity"))
        opacity_slider = QSlider(Qt.Horizontal, subtab)
        opacity_slider.setRange(0, 100)
        opacity_slider.setValue(100)
        opacity_slider.setToolTip("Object opacity for this state")
        opacity_value = QLabel("100%")
        opacity_value.setMinimumWidth(42)
        opacity_slider.valueChanged.connect(lambda value: opacity_value.setText(f"{value}%"))
        opacity_slider.valueChanged.connect(panel.changeOpacityChanged.emit)
        opacity_row.addWidget(opacity_slider, 1)
        opacity_row.addWidget(opacity_value)
        layout.addLayout(opacity_row)
        editor["opacity_slider"] = opacity_slider
        editor["opacity_value"] = opacity_value

    loop_box, loop_layout = panel._make_section_box("Loop")
    loop_count = QComboBox(subtab)
    loop_count.setToolTip("Beat Count")
    loop_count.addItem("4", 4)
    loop_count.setCurrentIndex(0)
    loop_count.hide()
    if show_loop_note:
        loop_layout.addWidget(panel._make_note_label("The stage loop is fixed to 4 beats. Assign states directly on the circle."))

    loop_circle = LoopCircleWidget(subtab)
    loop_circle.pointMenuRequested.connect(
        lambda point_index, pos, editor_key=key: panel._open_change_timeline_point_picker(editor_key, point_index, pos)
    )
    loop_circle.pointCleared.connect(lambda point_index, editor_key=key: panel._remove_change_timeline_point(editor_key, point_index))
    loop_circle.pointCreateRequested.connect(
        lambda position, pos, editor_key=key: panel._create_change_timeline_point(editor_key, position, pos)
    )
    loop_circle.transitionMenuRequested.connect(
        lambda point_index, pos, editor_key=key: panel._open_change_timeline_transition_picker(editor_key, point_index, pos)
    )
    loop_layout.addWidget(loop_circle)
    layout.addWidget(loop_box)
    layout.addStretch(1)
    editor["loop_count"] = loop_count
    editor["loop_circle"] = loop_circle

    if key == "object":
        apply_button.clicked.connect(panel.applyStageRequested.emit)
        reset_button.clicked.connect(panel.resetStagePreviewRequested.emit)
        reset_states_button.clicked.connect(panel.resetStagesRequested.emit)
    else:
        apply_button.clicked.connect(panel.backgroundApplyStageRequested.emit)
        reset_button.clicked.connect(panel.backgroundResetStagePreviewRequested.emit)
        reset_states_button.clicked.connect(panel.backgroundResetStagesRequested.emit)

    editor["apply_button"] = apply_button
    editor["reset_button"] = reset_button
    editor["reset_stages_button"] = reset_states_button
    editor["state_counter"] = state_counter
    panel._change_editors[key] = editor
    return subtab


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child_layout = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child_layout is not None:
            _clear_layout(child_layout)


def build_further_development_object_tab(panel, _color_wheel_cls):
    panel.object_tab, _content, layout = panel._build_scroll_tab()

    panel.object_subtabs = QTabWidget(panel.object_tab)
    panel.object_subtabs.currentChanged.connect(panel._emit_tool_for_current_tab)
    layout.addWidget(panel.object_subtabs)

    panel.draw_subtab = QWidget(panel.object_subtabs)
    panel.draw_subtab.hide()

    panel.object_tool = QComboBox(panel.object_tab)
    panel.object_tool.addItem("Select", "select")
    panel.object_tool.currentIndexChanged.connect(panel._emit_object_tool_changed)
    panel.object_tool.hide()

    panel.brush_style = QComboBox(panel.object_tab)
    panel.brush_style.addItem("Circle", "circle")
    panel.brush_style.currentIndexChanged.connect(panel._emit_brush_style_changed)
    panel.brush_style.hide()

    panel.size = QSlider(Qt.Horizontal, panel.object_tab)
    panel.size.setRange(1, 200)
    panel.size.setValue(20)
    panel.size.valueChanged.connect(panel.brushSizeChanged)
    panel.size.hide()

    panel.opacity = QSlider(Qt.Horizontal, panel.object_tab)
    panel.opacity.setRange(0, 100)
    panel.opacity.setValue(100)
    panel.opacity.valueChanged.connect(panel.brushOpacityChanged)
    panel.opacity.hide()

    panel.spray = QSlider(Qt.Horizontal, panel.object_tab)
    panel.spray.setRange(0, 100)
    panel.spray.setValue(0)
    panel.spray.valueChanged.connect(panel.brushSprayChanged)
    panel.spray.hide()

    panel.polygon_sides = QComboBox(panel.object_tab)
    panel.polygon_sides.addItem("3", 3)
    panel.polygon_sides.currentIndexChanged.connect(panel._emit_polygon_sides_changed)
    panel.polygon_sides.hide()

    panel.shape_fill_mode = QComboBox(panel.object_tab)
    panel.shape_fill_mode.addItem("Empty", False)
    panel.shape_fill_mode.currentIndexChanged.connect(panel._emit_shape_fill_changed)
    panel.shape_fill_mode.hide()

    panel.brightness = QSlider(Qt.Horizontal, panel.object_tab)
    panel.brightness.setRange(0, 200)
    panel.brightness.setValue(100)
    panel.brightness.valueChanged.connect(panel.brushBrightnessChanged)
    panel.brightness.hide()

    panel.object_wheel = None
    panel.object_value_slider = None
    panel.object_color_preview = None
    panel.save_preset_button = None
    panel.load_preset_button = None

    panel.image_subtab = QWidget(panel.object_subtabs)
    image_layout = QVBoxLayout(panel.image_subtab)
    image_layout.setContentsMargins(10, 10, 10, 10)
    image_layout.setSpacing(12)

    import_box, import_layout = panel._make_section_box("Image")

    panel.import_image_button = QPushButton("Import Single Image...")
    panel.import_image_button.clicked.connect(panel.importImageRequested.emit)
    import_layout.addWidget(panel.import_image_button)

    panel.import_image_set_button = QPushButton("Import Background...")
    panel.import_image_set_button.clicked.connect(panel.importBackgroundRequested.emit)
    import_layout.addWidget(panel.import_image_set_button)

    image_layout.addWidget(import_box)
    image_layout.addStretch(1)
    panel.object_subtabs.addTab(panel.image_subtab, "Image")

    panel.object_subtabs.setCurrentWidget(panel.image_subtab)
    layout.addStretch(1)
    panel.tabs.addTab(panel.object_tab, "Object")


def build_further_development_module_tab(panel):
    panel.further_development_tab = None

    panel.text_input = QLineEdit(panel)
    panel.text_input.setPlaceholderText("Type text here")
    panel.text_input.setText("Text")
    panel.text_input.textChanged.connect(panel._emit_text_value_changed)
    panel.text_input.hide()

    panel.text_size = QSlider(Qt.Horizontal, panel)
    panel.text_size.setRange(8, 240)
    panel.text_size.setValue(48)
    panel.text_size.valueChanged.connect(panel._emit_text_size_changed)
    panel.text_size.hide()

    panel.text_subtab = None


def _legacy_build_further_development_change_tab(
    panel,
    *,
    default_switch_time_seconds,
    default_timing_translation,
    default_timing_pause,
    image_set_timing_mode_options,
):
    panel.change_tab, _content, layout = panel._build_scroll_tab()
    layout.addWidget(panel._make_note_label("Use the tabs below to edit regular objects or backgrounds. Start in Backgrounds to configure your background set."))

    selection_box, selection_layout = panel._make_section_box("Select Object or Background")
    selection_layout.addWidget(QLabel("Object / Background"))
    panel.object_combo = QComboBox()
    panel.object_combo.currentIndexChanged.connect(panel._emit_object_selection_changed)
    selection_layout.addWidget(panel.object_combo)

    panel.change_stage_info = panel._make_status_label("No object or background selected")
    selection_layout.addWidget(panel.change_stage_info)
    layout.addWidget(selection_box)

    panel.change_subtabs = QTabWidget(panel.change_tab)
    panel.change_subtabs.setTabPosition(QTabWidget.North)
    layout.addWidget(panel.change_subtabs)

    panel.change_object_subtab = None
    panel.transform_mode = None
    panel.transform_mode_hint = None
    panel.change_color_button = None
    panel.change_visibility_mode = None
    panel.change_visibility_note = None
    panel.apply_stage_button = None
    panel.reset_stage_button = None

    panel.change_photo_subtab = QWidget(panel.change_subtabs)
    photo_layout = QVBoxLayout(panel.change_photo_subtab)
    photo_layout.setContentsMargins(10, 10, 10, 10)
    photo_layout.setSpacing(12)

    # Transform controls section
    transform_box, transform_layout = panel._make_section_box("Transform Tools")
    transform_layout.addWidget(panel._make_note_label("Click a button below, then interact with the object on the main canvas to apply the transformation."))
    
    transform_grid = QGridLayout()
    transform_grid.setSpacing(8)
    
    # Translation transform
    panel.transform_translate_button = QPushButton("T - Translation")
    panel.transform_translate_button.setFixedHeight(60)
    panel.transform_translate_button.setToolTip("Click, then drag the object center on the canvas to move it")
    transform_grid.addWidget(panel.transform_translate_button, 0, 0)
    
    # Rotation transform
    panel.transform_rotate_button = QPushButton("R - Rotation")
    panel.transform_rotate_button.setFixedHeight(60)
    panel.transform_rotate_button.setToolTip("Click, then drag on canvas to rotate [0-360Â°] around center")
    transform_grid.addWidget(panel.transform_rotate_button, 0, 1)
    
    # Scaling transform
    panel.transform_scale_button = QPushButton("S - Scaling")
    panel.transform_scale_button.setFixedHeight(60)
    panel.transform_scale_button.setToolTip("Click, then drag on canvas to scale [0.3 - 3.0] from center")
    transform_grid.addWidget(panel.transform_scale_button, 1, 0)
    
    # Reflection transform
    panel.transform_reflect_button = QPushButton("M - Reflection")
    panel.transform_reflect_button.setFixedHeight(60)
    panel.transform_reflect_button.setToolTip("Click, then pick two points on canvas to mirror across the line")
    transform_grid.addWidget(panel.transform_reflect_button, 1, 1)
    
    transform_layout.addLayout(transform_grid)
    photo_layout.addWidget(transform_box)

    # Apply state section
    state_box, state_layout = panel._make_section_box("Apply State")
    
    state_button_layout = QHBoxLayout()
    panel.apply_state_button = QPushButton("Apply State")
    panel.apply_state_button.setMinimumHeight(40)
    panel.apply_state_button.setToolTip("Save the current object state to the beat loop")
    state_button_layout.addWidget(panel.apply_state_button)
    
    panel.state_counter_label = QLabel("0 states")
    panel.state_counter_label.setAlignment(Qt.AlignCenter)
    panel.state_counter_label.setMinimumWidth(80)
    state_button_layout.addWidget(panel.state_counter_label)
    
    state_layout.addLayout(state_button_layout)
    photo_layout.addWidget(state_box)

    # Loop configuration section
    loop_config_box, loop_config_layout = panel._make_section_box("Beat Loop Configuration")
    
    loop_count_row = QHBoxLayout()
    loop_count_row.addWidget(QLabel("Loop Beat Positions"))
    panel.object_loop_count = QComboBox()
    for count in range(1, 33):
        panel.object_loop_count.addItem(str(count), count)
    panel.object_loop_count.setCurrentIndex(max(0, panel.object_loop_count.findData(8)))
    panel.object_loop_count.currentIndexChanged.connect(lambda: None)  # Will connect in main
    loop_count_row.addWidget(panel.object_loop_count)
    loop_count_row.addStretch(1)
    loop_config_layout.addLayout(loop_count_row)
    
    # Circular beat selector info
    panel.object_beat_circle_info = panel._make_note_label("Click a position on the circle below. A state dropdown will appear - select a state. The angle between positions controls the transition effect.")
    loop_config_layout.addWidget(panel.object_beat_circle_info)
    
    # Circular beat selector
    panel.object_beat_circle_canvas = QLabel("Beat Circle")
    panel.object_beat_circle_canvas.setAlignment(Qt.AlignCenter)
    panel.object_beat_circle_canvas.setMinimumHeight(320)
    panel.object_beat_circle_canvas.setStyleSheet("border: 1px solid #d8d0c3; border-radius: 8px; background: #f9f7f4;")
    loop_config_layout.addWidget(panel.object_beat_circle_canvas)
    
    photo_layout.addWidget(loop_config_box)
    photo_layout.addStretch(1)

    panel.change_subtabs.addTab(panel.change_photo_subtab, "Objects")
    
    # Connect transform buttons to emit signals
    panel.transform_translate_button.clicked.connect(lambda: panel.transformModeChanged.emit("translate"))
    panel.transform_rotate_button.clicked.connect(lambda: panel.transformModeChanged.emit("rotate"))
    panel.transform_scale_button.clicked.connect(lambda: panel.transformModeChanged.emit("scale"))
    panel.transform_reflect_button.clicked.connect(lambda: panel.transformModeChanged.emit("reflect"))
    panel.apply_state_button.clicked.connect(lambda: panel.applyStageRequested.emit())

    # Background subtab
    panel.change_background_subtab = QWidget(panel.change_subtabs)
    background_layout = QVBoxLayout(panel.change_background_subtab)
    background_layout.setContentsMargins(10, 10, 10, 10)
    background_layout.setSpacing(12)

    bg_info_box, bg_info_layout = panel._make_section_box("Background Set")
    bg_info_layout.addWidget(QLabel("Background Information"))
    panel.background_info_label = panel._make_status_label("No background selected")
    bg_info_layout.addWidget(panel.background_info_label)
    background_layout.addWidget(bg_info_box)

    bg_preview_box, bg_preview_layout = panel._make_section_box("Background Images")
    panel.background_preview_grid_host = QWidget(panel.change_background_subtab)
    panel.background_preview_grid = QGridLayout(panel.background_preview_grid_host)
    panel.background_preview_grid.setContentsMargins(0, 0, 0, 0)
    panel.background_preview_grid.setHorizontalSpacing(8)
    panel.background_preview_grid.setVerticalSpacing(8)
    bg_preview_layout.addWidget(panel.background_preview_grid_host)
    background_layout.addWidget(bg_preview_box)

    bg_timeline_box, bg_timeline_layout = panel._make_section_box("Background Transitions")
    bg_timeline_layout.addWidget(QLabel("Transition Timing"))
    panel.background_timing_slider = QSlider(Qt.Horizontal)
    panel.background_timing_slider.setRange(0, 1000)
    panel.background_timing_slider.setValue(500)
    panel.background_timing_slider.valueChanged.connect(lambda v: None)  # Will connect later in main
    bg_timeline_layout.addWidget(panel.background_timing_slider)
    panel.background_timing_label = panel._make_status_label("500 ms")
    bg_timeline_layout.addWidget(panel.background_timing_label)
    background_layout.addWidget(bg_timeline_box)

    background_layout.addStretch(1)
    panel.change_subtabs.addTab(panel.change_background_subtab, "Backgrounds")
    panel.change_subtabs.setCurrentWidget(panel.change_background_subtab)

    layout.addStretch(1)
    panel.tabs.addTab(panel.change_tab, "Change")


def build_further_development_change_tab(
    panel,
    *,
    default_switch_time_seconds,
    default_timing_translation,
    default_timing_pause,
    image_set_timing_mode_options,
):
    _ = (default_switch_time_seconds, default_timing_translation, default_timing_pause, image_set_timing_mode_options)
    panel.change_tab, _content, layout = panel._build_scroll_tab()

    panel._change_editors = {}
    panel.change_subtabs = QTabWidget(panel.change_tab)
    panel.change_subtabs.setTabPosition(QTabWidget.North)
    panel.change_subtabs.currentChanged.connect(panel._on_change_subtab_changed)
    layout.addWidget(panel.change_subtabs)

    panel.change_object_subtab = _build_change_state_editor(
        panel,
        parent=panel.change_subtabs,
        key="object",
        title="Object Loop",
        selection_label="Select Object",
        note_text="No object selected",
        show_selection=False,
        show_stage_info=False,
        show_appearance=False,
        show_loop_note=False,
    )
    panel.change_background_subtab = _build_change_state_editor(
        panel,
        parent=panel.change_subtabs,
        key="background",
        title="Background Loop",
        selection_label="Select Background",
        note_text="No background selected",
        show_selection=False,
        show_stage_info=False,
        show_appearance=False,
        show_loop_note=False,
    )

    slot_box = QWidget(panel.change_background_subtab)
    slot_layout = QVBoxLayout(slot_box)
    row = QHBoxLayout()
    panel.background_slot_buttons = []
    for name in ("A", "B"):
        button = QToolButton()
        button.setText("Background " + name + "\nChoose image…")
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setStyleSheet("QToolButton { min-height: 130px; min-width: 130px; }")
        row.addWidget(button)
        panel.background_slot_buttons.append(button)
    slot_layout.addLayout(row)
    panel.background_mix_label = QLabel("A 100% / B 0%")
    slot_layout.addWidget(panel.background_mix_label)
    panel.background_mix_slider = QSlider(Qt.Horizontal)
    panel.background_mix_slider.setRange(0, 100)
    panel.background_mix_slider.setToolTip("Manual background opacity crossfade: A to B")
    slot_layout.addWidget(panel.background_mix_slider)
    panel.change_background_subtab.layout().insertWidget(0, slot_box)

    panel.change_subtabs.addTab(panel.change_object_subtab, "Object")
    panel.change_subtabs.addTab(panel.change_background_subtab, "Background")
    panel.change_subtabs.setCurrentWidget(panel.change_object_subtab)

    object_editor = panel._change_editors["object"]
    background_editor = panel._change_editors["background"]

    panel.object_combo = object_editor["combo"]
    panel.change_stage_info = object_editor["stage_info"]
    panel.transform_translate_button = object_editor["transform_buttons"]["translate"]
    panel.transform_rotate_button = object_editor["transform_buttons"]["rotate"]
    panel.transform_scale_button = object_editor["transform_buttons"]["scale"]
    panel.transform_reflect_button = object_editor["transform_buttons"]["reflect"]
    panel.transform_mode_hint = object_editor["transform_hint"]
    panel.change_color_button = object_editor["color_button"]
    panel.change_visibility_mode = None
    panel.loop_slot_count = object_editor["loop_count"]
    panel.apply_stage_button = object_editor["apply_button"]
    panel.reset_stage_button = object_editor["reset_button"]
    panel.reset_state_stages_button = object_editor["reset_stages_button"]
    panel.state_counter_label = object_editor["state_counter"]

    panel.background_combo = background_editor["combo"]
    panel.background_stage_info = background_editor["stage_info"]
    panel.background_change_color_button = background_editor["color_button"]
    panel.background_change_visibility_mode = None
    panel.background_loop_slot_count = background_editor["loop_count"]
    panel.background_apply_stage_button = background_editor["apply_button"]
    panel.background_reset_stage_button = background_editor["reset_button"]
    panel.background_reset_state_stages_button = background_editor["reset_stages_button"]
    panel.background_state_counter_label = background_editor["state_counter"]

    apply_config_row = QHBoxLayout()
    apply_config_row.addStretch(1)
    panel.apply_change_configuration_button = QPushButton("Apply Configuration")
    panel.apply_change_configuration_button.setMinimumHeight(42)
    panel.apply_change_configuration_button.setToolTip("Apply the current loop configuration to the selected object or background.")
    panel.apply_change_configuration_button.clicked.connect(panel._apply_current_change_configuration)
    apply_config_row.addWidget(panel.apply_change_configuration_button)
    layout.addLayout(apply_config_row)

    layout.addStretch(1)
    panel.tabs.addTab(panel.change_tab, "Change")


def rebuild_stage_preview_grid(panel, preview_items, selected_stage_index: int, active_key: str = "", target_key: str = ""):
    _clear_layout(panel.image_set_preview_grid)
    buttons = []
    for index, item in enumerate(preview_items):
        pixmap = QPixmap.fromImage(item["preview"])
        button = ImageSetPreviewButton(panel.image_set_preview_grid_host)
        button.set_stage(int(item["stage_index"]), item["label"], pixmap, tooltip=item.get("tooltip", item["label"]))
        button.setChecked(int(item["stage_index"]) == int(selected_stage_index))
        if item.get("label") == active_key:
            button.setText(f'{item["label"]}\nLive')
        elif item.get("label") == target_key:
            button.setText(f'{item["label"]}\nNext')
        button.stageSelected.connect(panel._select_photo_stage_preview)
        panel.image_set_preview_grid.addWidget(button, index // 4, index % 4)
        buttons.append(button)
    panel._stage_preview_buttons = buttons


def rebuild_photo_timeline(panel, preview_lookup, compact_transition_specs):
    _clear_layout(panel.photo_timeline_row)
    panel._timeline_slot_buttons = []
    panel._timeline_transition_boxes = []

    beat_map = list(panel._selected_loop_timeline.get("beat_map", []))
    beat_transitions = list(panel._selected_loop_timeline.get("beat_transitions", []))
    slot_count = max(1, len(beat_map))

    for slot_index in range(slot_count):
        stage_index = int(beat_map[slot_index]) if 0 <= slot_index < len(beat_map) else 0
        stage_item = preview_lookup.get(stage_index)

        slot_button = TimelineSlotButton(slot_index, panel.photo_timeline_content)
        slot_button.set_stage_item(slot_index + 1, stage_item)
        slot_button.stageDropped.connect(panel._assign_photo_stage_to_slot)
        slot_button.slotClicked.connect(panel._assign_selected_photo_stage_to_slot)
        slot_button.slotCleared.connect(panel._clear_photo_timeline_slot)
        panel.photo_timeline_row.addWidget(slot_button)
        panel._timeline_slot_buttons.append(slot_button)

        transition_combo = QComboBox(panel.photo_timeline_content)
        transition_combo.setMinimumWidth(80)
        transition_combo.setMaximumWidth(92)
        for label, value in PHOTO_TIMELINE_TRANSITION_OPTIONS:
            transition_combo.addItem(label, value)
        current_effect = compact_transition_specs[slot_index] if 0 <= slot_index < len(compact_transition_specs) else "cut"
        found_index = transition_combo.findData(current_effect)
        transition_combo.setCurrentIndex(found_index if found_index >= 0 else 0)
        transition_combo.currentIndexChanged.connect(
            lambda _=0, slot=slot_index, combo=transition_combo: panel._set_photo_timeline_transition(slot, combo.currentData())
        )
        transition_shell = QWidget(panel.photo_timeline_content)
        transition_layout = QVBoxLayout(transition_shell)
        transition_layout.setContentsMargins(0, 0, 0, 0)
        transition_layout.setSpacing(4)
        transition_layout.addStretch(1)
        transition_layout.addWidget(transition_combo, alignment=Qt.AlignHCenter)
        if slot_index >= slot_count - 1:
            wrap_label = QLabel("-> 1", transition_shell)
            wrap_label.setAlignment(Qt.AlignCenter)
            wrap_label.setStyleSheet("color: #786f62; font-size: 11px;")
            transition_layout.addWidget(wrap_label)
        else:
            spacer = QLabel("", transition_shell)
            spacer.setFixedHeight(16)
            transition_layout.addWidget(spacer)
        transition_layout.addStretch(1)
        panel.photo_timeline_row.addWidget(transition_shell)
        panel._timeline_transition_boxes.append(transition_combo)

    panel.photo_timeline_row.addStretch(1)
