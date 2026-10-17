from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path

import cv2
import mss
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from diagnostics import write_diagnostics
from solver import CellKind, SolveResult, solve_board
from vision import COLS, ROWS, Recognition, recognize_board

APP_DIR = Path(__file__).resolve().parent
EXPECTED_BOARD_SIDE = 522  # confirmed from the user's fixed-size Windows game UI
if sys.platform == "win32":
    SETTINGS_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "KBaoHelper"
else:
    SETTINGS_DIR = APP_DIR
SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_PATH = SETTINGS_DIR / "settings.json"


def enable_windows_dpi_awareness():
    """Keep Qt geometry, MSS screenshots and physical coordinates aligned."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class RegionSelector(QWidget):
    def __init__(self, on_selected):
        super().__init__()
        self.on_selected = on_selected
        self.start: QPoint | None = None
        self.current: QPoint | None = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        screen = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(screen)
        self.show()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.start = event.position().toPoint()
            self.current = self.start
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.start is not None:
            self.current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton or self.start is None:
            return
        self.current = event.position().toPoint()
        rect = QRect(self.start, self.current).normalized()
        if rect.width() < 300 or rect.height() < 300:
            QMessageBox.warning(self, "区域太小", "请框住完整的 18×18 棋盘。")
            return
        global_rect = QRect(self.mapToGlobal(rect.topLeft()), rect.size())
        self.close()
        self.on_selected(global_rect)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 70))
        if self.start is not None and self.current is not None:
            rect = QRect(self.start, self.current).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setPen(QPen(QColor(0, 220, 255), 2))
            painter.drawRect(rect)


class BoardOverlay(QWidget):
    """Click-through overlay that marks certain cells on the real game board."""

    def __init__(self):
        super().__init__()
        self.result: SolveResult | None = None
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        if sys.platform == "win32":
            try:
                hwnd = int(self.winId())
                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_LAYERED = 0x00080000
                WS_EX_NOACTIVATE = 0x08000000
                user32 = ctypes.windll.user32
                style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                user32.SetWindowLongW(
                    hwnd,
                    GWL_EXSTYLE,
                    style | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE,
                )
            except Exception:
                pass

    def show_result(self, rect: QRect, result: SolveResult):
        self.result = result
        self.setGeometry(rect)
        self.show()
        self.raise_()
        self.update()

    def clear_result(self):
        self.result = None
        self.hide()

    def paintEvent(self, event):
        if self.result is None:
            return
        painter = QPainter(self)
        cw = self.width() / COLS
        ch = self.height() / ROWS
        for r in range(ROWS):
            for c in range(COLS):
                pos = (r, c)
                if pos not in self.result.safe and pos not in self.result.bombs:
                    continue
                x0 = round(c * cw)
                y0 = round(r * ch)
                x1 = round((c + 1) * cw)
                y1 = round((r + 1) * ch)
                rect = QRect(x0 + 2, y0 + 2, max(1, x1 - x0 - 4), max(1, y1 - y0 - 4))

                if pos in self.result.bombs:
                    painter.setPen(QPen(QColor(255, 45, 45, 235), 3))
                    painter.drawRect(rect)
                    painter.drawLine(rect.topLeft(), rect.bottomRight())
                    painter.drawLine(rect.topRight(), rect.bottomLeft())
                elif pos in self.result.kbaos:
                    painter.setPen(QPen(QColor(40, 190, 255, 235), 3))
                    painter.drawRect(rect)
                else:
                    painter.setPen(QPen(QColor(40, 230, 90, 235), 3))
                    painter.drawRect(rect)


class MiniBoard(QWidget):
    def __init__(self):
        super().__init__()
        self.result: SolveResult | None = None
        self.setMinimumSize(252, 252)

    def set_result(self, result: SolveResult | None):
        self.result = result
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        side = min(self.width(), self.height())
        cw = side / COLS
        ch = side / ROWS
        painter.fillRect(self.rect(), QColor(34, 34, 34))
        painter.setPen(QPen(QColor(75, 75, 75), 1))
        for r in range(ROWS):
            for c in range(COLS):
                x = int(c * cw)
                y = int(r * ch)
                rect = QRect(x, y, max(1, int(cw)), max(1, int(ch)))
                if self.result is not None:
                    pos = (r, c)
                    if pos in self.result.bombs:
                        painter.fillRect(rect.adjusted(1, 1, -1, -1), QColor(220, 70, 70))
                    elif pos in self.result.kbaos:
                        painter.fillRect(rect.adjusted(1, 1, -1, -1), QColor(70, 190, 255))
                    elif pos in self.result.safe:
                        painter.fillRect(rect.adjusted(1, 1, -1, -1), QColor(70, 190, 100))
                painter.drawRect(rect)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("K宝扫雷助手")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setFixedWidth(310)

        self.board_rect: QRect | None = None
        self.last_recognition: Recognition | None = None
        self.last_result: SolveResult | None = None
        self.auto_running = False
        self.overlay = BoardOverlay()

        self.status = QLabel("先框选一次完整棋盘。")
        self.status.setWordWrap(True)
        self.board_preview = MiniBoard()
        self.legend = QLabel("绿色=安全左键｜蓝色=确定K宝｜红叉=炸弹右键")
        self.legend.setWordWrap(True)

        self.calibrate_btn = QPushButton("框选棋盘")
        self.refresh_btn = QPushButton("刷新分析")
        self.auto_btn = QPushButton("自动执行确定格")
        self.data_btn = QPushButton("打开诊断目录")
        self.calibrate_btn.clicked.connect(self.start_calibration)
        self.refresh_btn.clicked.connect(self.refresh_analysis)
        self.auto_btn.clicked.connect(self.toggle_auto_execute)
        self.data_btn.clicked.connect(self.open_diagnostics_dir)

        layout = QVBoxLayout()
        layout.addWidget(self.status)
        layout.addWidget(self.legend)
        layout.addWidget(self.board_preview)
        layout.addWidget(self.calibrate_btn)
        layout.addWidget(self.refresh_btn)
        layout.addWidget(self.auto_btn)
        layout.addWidget(self.data_btn)
        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)

        self.load_settings()

    def load_settings(self):
        if not SETTINGS_PATH.exists():
            return
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            r = data.get("board_rect")
            if r and len(r) == 4:
                self.board_rect = QRect(*map(int, r))
                self.status.setText("已读取棋盘区域。点击“刷新分析”。")
        except Exception:
            pass

    def save_settings(self):
        if self.board_rect is None:
            return
        data = {
            "board_rect": [
                self.board_rect.x(),
                self.board_rect.y(),
                self.board_rect.width(),
                self.board_rect.height(),
            ]
        }
        SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def open_diagnostics_dir(self):
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(SETTINGS_DIR))
            elif sys.platform == "darwin":
                os.system(f'open "{SETTINGS_DIR}"')
            else:
                os.system(f'xdg-open "{SETTINGS_DIR}"')
        except Exception as exc:
            self.status.setText(f"无法打开诊断目录：{exc}")

    def start_calibration(self):
        self.overlay.clear_result()
        self.status.setText("大致框住 18×18 棋盘即可，我会按固定 522px 尺寸自动吸附；Esc 取消。")
        self.hide()
        QApplication.processEvents()
        time.sleep(0.15)

        def done(rect: QRect):
            raw_side = min(rect.width(), rect.height())
            if abs(raw_side - EXPECTED_BOARD_SIDE) <= 80:
                side = EXPECTED_BOARD_SIDE
                cell = side // COLS
            else:
                cell = max(1, round(raw_side / COLS))
                side = cell * COLS
            center = rect.center()
            x = center.x() - side // 2
            y = center.y() - side // 2
            self.board_rect = QRect(x, y, side, side)
            self.save_settings()
            self.show()
            self.raise_()
            self.status.setText(
                f"棋盘已保存：{side}×{side}（每格约 {cell}px）。点击“刷新分析”。"
            )

        self.selector = RegionSelector(done)

    def _capture_board(self) -> np.ndarray:
        if self.board_rect is None:
            raise RuntimeError("请先框选棋盘")
        r = self.board_rect
        with mss.mss() as sct:
            raw = np.array(
                sct.grab({"left": r.x(), "top": r.y(), "width": r.width(), "height": r.height()})
            )
        return cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)

    def _cell_center(self, pos: tuple[int, int]) -> tuple[int, int]:
        if self.board_rect is None:
            raise RuntimeError("请先框选棋盘")
        r, c = pos
        rect = self.board_rect
        x = round(rect.x() + (c + 0.5) * rect.width() / COLS)
        y = round(rect.y() + (r + 0.5) * rect.height() / ROWS)
        return x, y

    def _click_cell(self, pos: tuple[int, int], *, right: bool) -> None:
        if sys.platform != "win32":
            raise RuntimeError("自动点击只支持 Windows")

        # `mouse_event` is deprecated and some modern game/browser shells ignore it.
        # Use SendInput instead, which is the supported Win32 input injection API.
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class INPUTUNION(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", ctypes.c_ulong), ("u", INPUTUNION)]

        user32 = ctypes.windll.user32
        x, y = self._cell_center(pos)
        if not user32.SetCursorPos(x, y):
            raise RuntimeError(f"鼠标移动失败：({x}, {y})")

        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        MOUSEEVENTF_RIGHTDOWN = 0x0008
        MOUSEEVENTF_RIGHTUP = 0x0010
        down_flag, up_flag = (
            (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP)
            if right
            else (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP)
        )

        down = INPUT(type=0, mi=MOUSEINPUT(0, 0, 0, down_flag, 0, 0))
        sent = user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
        if sent != 1:
            err = ctypes.windll.kernel32.GetLastError()
            raise RuntimeError(
                f"鼠标按下未被 Windows 接受（SendInput={sent}, error={err}）。"
                "如果游戏/浏览器以管理员身份运行，请也用管理员身份启动助手。"
            )

        time.sleep(0.06)

        up = INPUT(type=0, mi=MOUSEINPUT(0, 0, 0, up_flag, 0, 0))
        sent = user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))
        if sent != 1:
            err = ctypes.windll.kernel32.GetLastError()
            raise RuntimeError(
                f"鼠标抬起未被 Windows 接受（SendInput={sent}, error={err}）。"
                "如果游戏/浏览器以管理员身份运行，请也用管理员身份启动助手。"
            )

        time.sleep(0.20)
        QApplication.processEvents()

    def _execute_result(self, result: SolveResult) -> int:
        actions = len(result.bombs) + len(result.safe)
        if actions == 0:
            return 0
        if sys.platform != "win32":
            raise RuntimeError("自动点击只支持 Windows")

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        user32 = ctypes.windll.user32
        old_pos = POINT()
        user32.GetCursorPos(ctypes.byref(old_pos))

        # Explicitly activate the game/browser window under the board before the
        # batch. Some shells ignore injected button events while not foreground.
        if self.board_rect is not None:
            probe = POINT(self.board_rect.center().x(), self.board_rect.center().y())
            user32.WindowFromPoint.argtypes = [POINT]
            user32.WindowFromPoint.restype = ctypes.c_void_p
            hwnd = user32.WindowFromPoint(probe)
            if hwnd:
                GA_ROOT = 2
                user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                user32.GetAncestor.restype = ctypes.c_void_p
                root_hwnd = user32.GetAncestor(hwnd, GA_ROOT) or hwnd
                user32.SetForegroundWindow(root_hwnd)
                time.sleep(0.15)

        self.overlay.clear_result()
        QApplication.processEvents()
        try:
            # Mark certain bombs first, then left-click every cell proven non-bomb.
            # The helper window stays visible and the user keeps it outside the board.
            for pos in sorted(result.bombs):
                if not self.auto_running:
                    break
                self._click_cell(pos, right=True)
            if self.auto_running:
                for pos in sorted(result.safe):
                    if not self.auto_running:
                        break
                    self._click_cell(pos, right=False)
        finally:
            user32.SetCursorPos(old_pos.x, old_pos.y)
            QApplication.processEvents()
        return actions

    def toggle_auto_execute(self):
        if self.auto_running:
            self.auto_running = False
            self.auto_btn.setText("自动执行确定格")
            self.status.setText("已请求停止自动执行。")
            return
        if self.board_rect is None:
            self.status.setText("请先框选棋盘。")
            return
        if sys.platform != "win32":
            self.status.setText("自动点击只支持 Windows。")
            return

        self.auto_running = True
        self.auto_btn.setText("停止自动执行")
        rounds = 0
        try:
            while self.auto_running:
                self._refresh_analysis(show_overlay=False)
                QApplication.processEvents()
                result = self.last_result
                if result is None:
                    self.status.setText(self.status.text() + " 自动已停止。")
                    break
                actions = len(result.bombs) + len(result.safe)
                if actions == 0:
                    self.status.setText(self.status.text() + " 自动停止：没有100%确定格。")
                    break

                rounds += 1
                self.status.setText(
                    f"自动第 {rounds} 轮：右键 {len(result.bombs)} 个炸弹，"
                    f"左键 {len(result.safe)} 个安全格。"
                )
                QApplication.processEvents()
                self._execute_result(result)
                # Let all click animations and board counters settle before the
                # next screenshot / solve pass, while keeping the Stop button responsive.
                deadline = time.monotonic() + 3.0
                while self.auto_running and time.monotonic() < deadline:
                    QApplication.processEvents()
                    time.sleep(0.05)

                if rounds >= 100:
                    self.status.setText("自动执行达到100轮保护上限，已停止。")
                    break
        finally:
            self.auto_running = False
            self.auto_btn.setText("自动执行确定格")

    def refresh_analysis(self):
        self._refresh_analysis(show_overlay=True)

    def _refresh_analysis(self, *, show_overlay: bool):
        img: np.ndarray | None = None
        rec: Recognition | None = None
        result: SolveResult | None = None
        try:
            # The helper window is kept outside the board by the user, so it never
            # needs to hide during analysis. Only clear the board overlay itself.
            self.overlay.clear_result()
            QApplication.processEvents()
            time.sleep(0.05)
            img = self._capture_board()
            rec = recognize_board(img)

            if rec.unknown_cells:
                write_diagnostics(SETTINGS_DIR, img, rec, None)
                self.last_recognition = None
                self.last_result = None
                self.board_preview.set_result(None)
                self.status.setText(
                    f"识别到 {len(rec.unknown_cells)} 个低置信度格子，未显示标记。"
                    "请确认框选；必要时点“打开诊断目录”把 last_board.png 和 last_recognition.txt 发给我。"
                )
                return

            revealed_kbaos = sum(
                cell.kind == CellKind.REVEALED_KBAO for row in rec.board for cell in row
            )
            flagged_bombs = sum(
                cell.kind == CellKind.FLAG_BOMB for row in rec.board for cell in row
            )
            remaining_kbaos = 38 - revealed_kbaos
            remaining_bombs = 26 - flagged_bombs
            if remaining_kbaos < 0 or remaining_bombs < 0:
                raise ValueError("识别到的K宝/炸弹标记数量超过本局总数")

            result = solve_board(rec.board, total_bombs=26, total_kbaos=38)
            write_diagnostics(SETTINGS_DIR, img, rec, result)
            self.last_recognition = rec
            self.last_result = result
            self.board_preview.set_result(result)
            if show_overlay and self.board_rect is not None:
                self.overlay.show_result(self.board_rect, result)
            else:
                self.overlay.clear_result()

            count_actions = len(result.safe) + len(result.bombs)
            suffix = (
                " 已标在真实棋盘上。"
                if count_actions and show_overlay
                else (" 已找到确定步骤。" if count_actions else " 当前没有 100% 确定步骤。")
            )
            self.status.setText(
                f"识别 {rec.confidence:.1%}｜剩余K宝 {remaining_kbaos}｜剩余炸弹 {remaining_bombs}｜"
                f"安全 {len(result.safe)}｜炸弹 {len(result.bombs)}｜确定K宝 {len(result.kbaos)}。"
                + suffix
            )
        except Exception as exc:
            self.last_recognition = None
            self.last_result = None
            self.board_preview.set_result(None)
            self.overlay.clear_result()
            if img is not None and rec is not None:
                try:
                    write_diagnostics(SETTINGS_DIR, img, rec, result)
                except Exception:
                    pass
            self.status.setText(
                f"分析失败：{exc}。如需排查，点“打开诊断目录”查看最近的诊断文件。"
            )


def main():
    enable_windows_dpi_awareness()
    app = QApplication(sys.argv)
    app.setApplicationName("K宝扫雷助手")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
