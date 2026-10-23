from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QContextMenuEvent,
    QDesktopServices,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QIcon,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QTextOption,
    QWheelEvent,
)
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QSystemTrayIcon,
    QWidget,
)


APP_NAME = "StarryPocket"
APP_ID = "StarryPocketDesktopPet"
SERVER_NAME = "StarryPocketDesktopPet-3D2A78D9"

if getattr(sys, "frozen", False):
    APP_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    INSTALL_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
    INSTALL_DIR = APP_DIR

ASSET_DIR = APP_DIR / "assets"
ICON_PATH = ASSET_DIR / "icon.png"
MESSAGES_PATH = INSTALL_DIR / "messages.json"


POSES = [
    {
        "key": "aurora",
        "label": "Aurora",
        "file": "nova_aurora.png",
        "accent": "#65c8ff",
        "face": (0.33, 0.19, 0.34, 0.25),
    },
    {
        "key": "ember",
        "label": "Ember",
        "file": "nova_ember.png",
        "accent": "#ff9b7c",
        "face": (0.33, 0.19, 0.34, 0.25),
    },
    {
        "key": "mint",
        "label": "Mint",
        "file": "nova_mint.png",
        "accent": "#73d9bb",
        "face": (0.33, 0.19, 0.34, 0.25),
    },
]


DEFAULT_MESSAGES = {
    "greetings": [
        "A little starlight for your desktop.",
        "I saved you a quiet corner of the sky.",
        "Need a tiny break? Nova is here.",
        "Work at your pace. I will keep you company.",
    ],
    "tap": [
        "Boo! Made you smile.",
        "My antenna says it is time for water.",
        "You are doing better than you think.",
        "Tiny stretch? I will do one too.",
        "The stars approved this little break.",
        "I found a pocketful of good luck for you.",
    ],
    "idle": [
        "Still here. Still sparkling.",
        "The desktop feels cozy today.",
        "Remember to look away from the screen once in a while.",
        "No rush. Small steps count.",
        "I am guarding your cursor.",
    ],
    "morning": [
        "Morning, stargazer.",
        "A new day has entered the chat.",
        "Breakfast first, adventures second.",
    ],
    "afternoon": [
        "Afternoon check-in: hydrate!",
        "A short walk might unlock the next idea.",
        "You have permission to take a slower breath.",
    ],
    "evening": [
        "Evening shift, Nova reporting.",
        "You made it through today. That counts.",
        "Wrap up gently. Tomorrow can wait.",
    ],
    "night": [
        "The moon says it is bedtime.",
        "I can keep watch. You should rest.",
        "One last sip of water before sleep?",
    ],
    "outfits": {
        "aurora": [
            "Aurora mode: all systems sparkling.",
            "Blue skies, incoming.",
            "A fresh scarf for a fresh start.",
        ],
        "ember": [
            "Ember mode: extra warm.",
            "A little sunset energy for you.",
            "Cozy and ready to help.",
        ],
        "mint": [
            "Mint mode: fresh thoughts ahead.",
            "One cool breeze, delivered.",
            "A tiny reset button for the day.",
        ],
    },
}


@dataclass
class Sparkle:
    x: float
    y: float
    vx: float
    vy: float
    born: float
    lifetime: float
    size: float
    color: QColor
    shape: str = "heart"


def load_json(path: Path, default: dict) -> dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            return loaded
    except (OSError, ValueError, TypeError):
        pass
    return default


def settings_file() -> Path:
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / ".config"
    target = root / "StarryPocket"
    target.mkdir(parents=True, exist_ok=True)
    return target / "settings.json"


class SettingsStore:
    def __init__(self) -> None:
        self.path = settings_file()
        self.first_run = not self.path.exists()
        self.values = {
            "pose": "aurora",
            "scale": 1.0,
            "x": None,
            "y": None,
            "always_on_top": True,
        }
        self.values.update(load_json(self.path, {}))

    def get(self, key: str, fallback=None):
        return self.values.get(key, fallback)

    def set(self, key: str, value) -> None:
        self.values[key] = value

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self.values, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass


class PetWindow(QWidget):
    def __init__(self, settings: SettingsStore) -> None:
        super().__init__()
        self.settings = settings
        self.messages = load_json(MESSAGES_PATH, DEFAULT_MESSAGES)
        self.preview_mode = "--preview" in sys.argv
        self.pose_index = max(
            0,
            next(
                (
                    i
                    for i, pose in enumerate(POSES)
                    if pose["key"] == settings.get("pose")
                ),
                0,
            ),
        )
        try:
            self.scale = min(1.4, max(0.75, float(settings.get("scale", 1.0))))
        except (TypeError, ValueError):
            self.scale = 1.0
        self.always_on_top = bool(settings.get("always_on_top", True))

        self._base_size = QSize(360, 520)
        self._pixmaps: dict[str, QPixmap] = {}
        self._scaled_cache: dict[tuple[str, int, int], QPixmap] = {}
        for pose in POSES:
            pixmap = QPixmap(str(ASSET_DIR / pose["file"]))
            if pixmap.isNull():
                raise FileNotFoundError(f"Missing image: {pose['file']}")
            self._pixmaps[pose["key"]] = pixmap

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.NoDropShadowWindowHint
        )
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setToolTip(
            "Drag me · Click to chat · Double-click to change outfit · Scroll to resize"
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(self._window_size())

        self.phase = random.random() * math.tau
        now = time.monotonic()
        self._started_at = now
        self._blink_until = 0.0
        self._next_blink = now + random.uniform(2.4, 4.8)
        self._speech = ""
        self._speech_started = 0.0
        self._speech_until = 0.0
        self._speech_alpha = 0.0
        self._particles: list[Sparkle] = []
        self._pressed_global: QPoint | None = None
        self._window_at_press = QPoint()
        self._dragging = False
        self._double_click_pending = False
        self._tap_timer = QTimer(self)
        self._tap_timer.setSingleShot(True)
        self._tap_timer.timeout.connect(self._tap)
        self._tray: QSystemTrayIcon | None = None
        self._quitting = False
        self._last_tick = time.monotonic()
        self._sprite_rect = QRectF()

        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(33)
        self._animation_timer.timeout.connect(self._animate)
        self._animation_timer.start()

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._idle_speak)
        self._schedule_idle()

        self._restore_position()
        if not self.preview_mode:
            self._arrange_tray()
        QTimer.singleShot(650, self._welcome)

    @property
    def pose(self) -> dict:
        return POSES[self.pose_index]

    def _window_size(self) -> QSize:
        return QSize(
            round(self._base_size.width() * self.scale),
            round(self._base_size.height() * self.scale),
        )

    def _restore_position(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.move(100, 100)
            return
        area = screen.availableGeometry()
        x = self.settings.get("x")
        y = self.settings.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            x = area.right() - self.width() - 54
            y = area.bottom() - self.height() - 38
        self.move(x, y)
        self._clamp_to_screen()

    def _clamp_to_screen(self) -> None:
        center = self.frameGeometry().center()
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        margin = max(24, round(42 * self.scale))
        min_x = area.left() - self.width() + margin
        max_x = area.right() - margin
        min_y = area.top() - self.height() + margin
        max_y = area.bottom() - margin
        self.move(
            min(max(self.x(), min_x), max_x),
            min(max(self.y(), min_y), max_y),
        )

    def _save_position(self) -> None:
        self.settings.set("x", self.x())
        self.settings.set("y", self.y())
        self.settings.set("scale", round(self.scale, 2))
        self.settings.set("pose", self.pose["key"])
        self.settings.set("always_on_top", self.always_on_top)
        self.settings.save()

    def _scale_pixmap(self, pose: dict, target: QSize) -> QPixmap:
        key = (pose["key"], max(1, target.width()), max(1, target.height()))
        if key not in self._scaled_cache:
            scaled = self._pixmaps[pose["key"]].scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if len(self._scaled_cache) > 12:
                self._scaled_cache.clear()
            self._scaled_cache[key] = scaled
        return self._scaled_cache[key]

    def _sprite_pixmap(self) -> QPixmap:
        source = self._pixmaps[self.pose["key"]]
        available_w = self.width() - round(24 * self.scale)
        available_h = self.height() - round(104 * self.scale)
        factor = min(
            available_w / source.width(),
            available_h / source.height(),
        )
        size = QSize(
            max(1, round(source.width() * factor)),
            max(1, round(source.height() * factor)),
        )
        return self._scale_pixmap(self.pose, size)

    def _set_speech(self, text: str, duration: float = 4.6) -> None:
        self._speech = text.strip()
        if not self._speech:
            self._speech_until = 0.0
            return
        now = time.monotonic()
        self._speech_started = now
        self._speech_until = now + duration
        self._speech_alpha = max(self._speech_alpha, 0.2)
        self.update()

    def _welcome(self) -> None:
        if self.preview_mode:
            return
        if self.settings.first_run:
            self._set_speech("A little starlight landed in your pocket. Drag me anywhere!", 7.0)
            self.settings.first_run = False
            self._save_position()
        else:
            self._set_speech(self._time_greeting(), 5.5)

    def _pick(self, bucket: str) -> str:
        values = self.messages.get(bucket, DEFAULT_MESSAGES.get(bucket, []))
        if not isinstance(values, list) or not values:
            values = DEFAULT_MESSAGES.get(bucket, ["I am right here."])
        return str(random.choice(values))

    def _time_greeting(self) -> str:
        hour = time.localtime().tm_hour
        if 5 <= hour < 11:
            return self._pick("morning")
        if 11 <= hour < 18:
            return self._pick("afternoon")
        if 18 <= hour < 23:
            return self._pick("evening")
        return self._pick("night")

    def _tap(self) -> None:
        self._set_speech(self._pick("tap"))
        self._spawn_sparkles(7)

    def _idle_speak(self) -> None:
        if self.isVisible() and not self._dragging and not self._speech:
            self._set_speech(self._pick("idle"), 4.2)
            self._spawn_sparkles(2)
        self._schedule_idle()

    def _schedule_idle(self) -> None:
        self._idle_timer.start(random.randint(48_000, 88_000))

    def _change_pose(self, index: int | None = None, announce: bool = True) -> None:
        if index is None:
            index = (self.pose_index + 1) % len(POSES)
        self.pose_index = index % len(POSES)
        self.settings.set("pose", self.pose["key"])
        self.settings.save()
        self._refresh_tray_menu()
        self.update()
        if announce:
            outfits = self.messages.get("outfits", {})
            choices = outfits.get(self.pose["key"], [])
            if isinstance(choices, list) and choices:
                self._set_speech(str(random.choice(choices)))
            else:
                self._set_speech(f"{self.pose['label']} mode activated.")
        self._spawn_sparkles(8)

    def _change_scale(self, value: float) -> None:
        old_bottom_center = QPoint(self.x() + self.width() // 2, self.y() + self.height())
        self.scale = min(1.4, max(0.75, value))
        self.setFixedSize(self._window_size())
        self.move(
            old_bottom_center.x() - self.width() // 2,
            old_bottom_center.y() - self.height(),
        )
        self._clamp_to_screen()
        self._save_position()
        self._refresh_tray_menu()
        self.update()

    def _set_always_on_top(self, enabled: bool) -> None:
        self.always_on_top = enabled
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()
        self.settings.set("always_on_top", enabled)
        self.settings.save()
        self._refresh_tray_menu()

    def _open_messages(self) -> None:
        if not MESSAGES_PATH.exists():
            try:
                MESSAGES_PATH.write_text(
                    json.dumps(DEFAULT_MESSAGES, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except OSError:
                pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(MESSAGES_PATH)))
        self._set_speech("Phrases live here. Restart me after editing.", 4.0)

    def _reset_corner(self) -> None:
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        screen = screen or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(
            area.right() - self.width() - 54,
            area.bottom() - self.height() - 38,
        )
        self._save_position()

    def _autostart_enabled(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
            ) as key:
                winreg.QueryValueEx(key, APP_ID)
            return True
        except OSError:
            return False

    def _set_autostart(self, enabled: bool) -> None:
        if sys.platform != "win32":
            self._set_speech("This feature is available on Windows only.")
            return
        try:
            import winreg

            command = self._launch_command()
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, APP_ID)
                    except FileNotFoundError:
                        pass
            self._set_speech(
                "I will join you at startup." if enabled else "Removed from startup."
            )
        except OSError:
            self._set_speech("Could not update startup settings.", 5.0)
        self._refresh_tray_menu()

    @staticmethod
    def _launch_command() -> str:
        if getattr(sys, "frozen", False):
            executable = Path(sys.executable).resolve()
            return f'"{executable}"'
        pythonw = INSTALL_DIR / ".venv" / "Scripts" / "pythonw.exe"
        executable = pythonw if pythonw.exists() else Path(sys.executable)
        script = INSTALL_DIR / "main.py"
        return f'"{executable}" "{script}"'

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setStyleSheet(
            """
            QMenu {
                background: #fffafc;
                color: #4d3a43;
                border: 1px solid #f0c7d6;
                border-radius: 9px;
                padding: 7px;
                font-family: "Segoe UI";
                font-size: 10.5pt;
            }
            QMenu::item {
                padding: 7px 28px 7px 28px;
                border-radius: 6px;
            }
            QMenu::item:selected { background: #ffe2ec; }
            QMenu::separator {
                height: 1px;
                background: #f3dbe4;
                margin: 5px 8px;
            }
            """
        )

        speak = menu.addAction("Say something")
        speak.triggered.connect(self._idle_speak)

        look_menu = menu.addMenu("Outfit")
        pose_group = QActionGroup(look_menu)
        pose_group.setExclusive(True)
        for index, pose in enumerate(POSES):
            action = QAction(pose["label"], pose_group)
            action.setCheckable(True)
            action.setChecked(index == self.pose_index)
            action.triggered.connect(
                lambda _checked=False, i=index: self._change_pose(i)
            )
            look_menu.addAction(action)

        size_menu = menu.addMenu("Size")
        size_group = QActionGroup(size_menu)
        size_group.setExclusive(True)
        for label, value in (
            ("Tiny", 0.82),
            ("Cozy", 1.0),
            ("Large", 1.2),
            ("Huge", 1.35),
        ):
            action = QAction(label, size_group)
            action.setCheckable(True)
            action.setChecked(abs(self.scale - value) < 0.035)
            action.triggered.connect(
                lambda _checked=False, s=value: self._change_scale(s)
            )
            size_menu.addAction(action)

        menu.addSeparator()
        words = menu.addAction("Edit phrases")
        words.triggered.connect(self._open_messages)
        corner = menu.addAction("Move to bottom-right")
        corner.triggered.connect(self._reset_corner)

        menu.addSeparator()
        top = menu.addAction("Always on top")
        top.setCheckable(True)
        top.setChecked(self.always_on_top)
        top.triggered.connect(self._set_always_on_top)

        autostart = menu.addAction("Start with Windows")
        autostart.setCheckable(True)
        autostart.setChecked(self._autostart_enabled())
        autostart.triggered.connect(self._set_autostart)

        menu.addSeparator()
        hide = menu.addAction("Hide in tray")
        hide.triggered.connect(self.hide)
        quit_action = menu.addAction("Quit StarryPocket")
        quit_action.triggered.connect(self._quit)
        return menu

    def _arrange_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = QIcon(str(ICON_PATH))
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip(f"{APP_NAME} · Click to show or hide")
        tray.setContextMenu(self._build_menu())
        tray.activated.connect(self._tray_activated)
        tray.show()
        self._tray = tray

    def _refresh_tray_menu(self) -> None:
        if self._tray is None:
            return
        old_menu = self._tray.contextMenu()
        self._tray.setContextMenu(self._build_menu())
        if old_menu is not None:
            old_menu.deleteLater()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show()
            self.raise_()
            self._change_pose()

    def _quit(self) -> None:
        self._quitting = True
        self._save_position()
        if self._tray is not None:
            self._tray.hide()
        QApplication.quit()

    def _spawn_sparkles(self, count: int) -> None:
        if self._sprite_rect.isEmpty():
            return
        palette = [
            QColor(255, 105, 158),
            QColor(255, 173, 197),
            QColor(122, 202, 255),
            QColor(255, 219, 124),
            QColor(201, 159, 255),
        ]
        now = time.monotonic()
        head_x = self._sprite_rect.center().x()
        head_y = self._sprite_rect.top() + self._sprite_rect.height() * 0.2
        for _ in range(count):
            shape = "heart" if random.random() < 0.72 else "star"
            self._particles.append(
                Sparkle(
                    x=head_x + random.uniform(-0.2, 0.2) * self._sprite_rect.width(),
                    y=head_y + random.uniform(-0.03, 0.12) * self._sprite_rect.height(),
                    vx=random.uniform(-16 * self.scale, 16 * self.scale),
                    vy=random.uniform(-54 * self.scale, -25 * self.scale),
                    born=now,
                    lifetime=random.uniform(1.2, 2.2),
                    size=random.uniform(7, 14) * self.scale,
                    color=random.choice(palette),
                    shape=shape,
                )
            )
        self.update()

    def _animate(self) -> None:
        now = time.monotonic()
        dt = min(0.08, now - self._last_tick)
        self._last_tick = now
        self.phase += dt * 1.65

        if now >= self._next_blink:
            self._blink_until = now + 0.13
            self._next_blink = now + random.uniform(3.3, 7.2)

        if self._particles:
            kept: list[Sparkle] = []
            for particle in self._particles:
                age = now - particle.born
                if age >= particle.lifetime:
                    continue
                particle.x += particle.vx * dt
                particle.y += particle.vy * dt
                particle.vy += 13 * self.scale * dt
                particle.vx *= 0.992
                kept.append(particle)
            self._particles = kept

        if self._speech:
            target = 1.0 if now < self._speech_until else 0.0
            speed = dt * 7.5
            if self._speech_alpha < target:
                self._speech_alpha = min(target, self._speech_alpha + speed)
            elif self._speech_alpha > target:
                self._speech_alpha = max(target, self._speech_alpha - speed)
            if target == 0.0 and self._speech_alpha <= 0.01:
                self._speech = ""
        self.update()

    def _draw_heart(
        self, painter: QPainter, center: QPointF, size: float, color: QColor
    ) -> None:
        path = QPainterPath()
        x, y = center.x(), center.y()
        path.moveTo(x, y + size * 0.42)
        path.cubicTo(
            x - size * 0.95,
            y - size * 0.1,
            x - size * 0.58,
            y - size * 0.83,
            x,
            y - size * 0.34,
        )
        path.cubicTo(
            x + size * 0.58,
            y - size * 0.83,
            x + size * 0.95,
            y - size * 0.1,
            x,
            y + size * 0.42,
        )
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)

    def _draw_star(
        self,
        painter: QPainter,
        center: QPointF,
        size: float,
        color: QColor,
        rotation: float = 0.0,
    ) -> None:
        painter.save()
        painter.translate(center)
        painter.rotate(rotation)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        path = QPainterPath()
        path.moveTo(0, -size)
        path.quadTo(size * 0.2, -size * 0.2, size, 0)
        path.quadTo(size * 0.2, size * 0.2, 0, size)
        path.quadTo(-size * 0.2, size * 0.2, -size, 0)
        path.quadTo(-size * 0.2, -size * 0.2, 0, -size)
        path.closeSubpath()
        painter.drawPath(path)
        painter.restore()

    def _draw_ambient_sparkles(
        self, painter: QPainter, body_rect: QRectF, now: float
    ) -> None:
        base_x = body_rect.center().x()
        for i in range(6):
            angle = now * (0.24 + i * 0.021) + i * 1.27
            x = base_x + math.cos(angle) * body_rect.width() * 0.47
            y = (
                body_rect.top()
                + body_rect.height() * (0.15 + i * 0.12)
                + math.sin(angle * 1.3) * 8 * self.scale
            )
            twinkle = 0.36 + 0.34 * (math.sin(now * 2.1 + i * 1.8) * 0.5 + 0.5)
            color = QColor(self.pose["accent"])
            color.setAlphaF(twinkle)
            self._draw_star(
                painter,
                QPointF(x, y),
                (2.7 + (i % 2) * 1.4) * self.scale,
                color,
                rotation=now * 28 + i * 21,
            )

    def _draw_blink(self, painter: QPainter, body_rect: QRectF, now: float) -> None:
        if not (time.monotonic() < self._blink_until):
            return
        face_x, face_y, face_w, face_h = self.pose["face"]
        left = body_rect.left() + body_rect.width() * face_x
        top = body_rect.top() + body_rect.height() * face_y
        width = body_rect.width() * face_w
        height = body_rect.height() * face_h
        eye_y = top + height * 0.47
        eye_dx = width * 0.27
        eye_len = width * 0.19
        pen = QPen(QColor(57, 36, 42, 225))
        pen.setWidthF(max(1.2, 1.8 * self.scale))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for direction in (-1, 1):
            x = left + width * 0.5 + direction * eye_dx
            path = QPainterPath(QPointF(x - eye_len / 2, eye_y))
            path.quadTo(x, eye_y + 2.2 * self.scale, x + eye_len / 2, eye_y)
            painter.drawPath(path)

    def _draw_speech(self, painter: QPainter, body_rect: QRectF) -> None:
        if not self._speech or self._speech_alpha <= 0.01:
            return
        bubble_w = min(self.width() - 20 * self.scale, 302 * self.scale)
        font = QFont("Segoe UI", round(10 * self.scale))
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        metrics = QFontMetricsF(font)
        text_w = bubble_w - 30 * self.scale
        bounds = metrics.boundingRect(
            QRectF(0, 0, text_w, 160 * self.scale),
            int(
                Qt.TextFlag.TextWordWrap
                | Qt.AlignmentFlag.AlignLeft
                | Qt.AlignmentFlag.AlignVCenter
            ),
            self._speech,
        )
        bubble_h = max(48 * self.scale, min(102 * self.scale, bounds.height() + 25 * self.scale))
        bubble = QRectF(
            (self.width() - bubble_w) / 2,
            6 * self.scale,
            bubble_w,
            bubble_h,
        )
        tail_x = min(
            bubble.right() - 28 * self.scale,
            max(bubble.left() + 28 * self.scale, body_rect.center().x()),
        )

        painter.save()
        painter.setOpacity(self._speech_alpha)
        shadow = QRectF(
            bubble.x(),
            bubble.y() + 3 * self.scale,
            bubble.width(),
            bubble.height(),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(66, 39, 54, 35))
        painter.drawRoundedRect(shadow, 17 * self.scale, 17 * self.scale)

        tail = QPainterPath()
        tail.moveTo(tail_x - 8 * self.scale, bubble.bottom() - 1)
        tail.lineTo(tail_x + 9 * self.scale, bubble.bottom() - 1)
        tail.lineTo(tail_x + 1 * self.scale, bubble.bottom() + 9 * self.scale)
        tail.closeSubpath()
        painter.setBrush(QColor(255, 250, 252, 248))
        painter.setPen(QPen(QColor(240, 184, 205, 210), 1.2))
        painter.drawRoundedRect(bubble, 17 * self.scale, 17 * self.scale)
        painter.drawPath(tail)

        accent = QColor(self.pose["accent"])
        accent.setAlpha(205)
        self._draw_heart(
            painter,
            QPointF(bubble.left() + 14 * self.scale, bubble.center().y()),
            6.2 * self.scale,
            accent,
        )
        text_rect = QRectF(
            bubble.left() + 24 * self.scale,
            bubble.top() + 6 * self.scale,
            bubble.width() - 34 * self.scale,
            bubble.height() - 12 * self.scale,
        )
        painter.setPen(QColor(73, 51, 62, 245))
        option = QTextOption()
        option.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        painter.drawText(text_rect, self._speech, option)
        painter.restore()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        now = time.monotonic()
        pixmap = self._sprite_pixmap()
        bottom = self.height() - 27 * self.scale
        sprite_rect = QRectF(
            (self.width() - pixmap.width()) / 2,
            bottom - pixmap.height(),
            pixmap.width(),
            pixmap.height(),
        )
        self._sprite_rect = sprite_rect

        accent = QColor(self.pose["accent"])
        aura = QRadialGradient(
            QPointF(self.width() * 0.5, sprite_rect.top() + sprite_rect.height() * 0.47),
            max(sprite_rect.height() * 0.55, 100 * self.scale),
        )
        aura_color = QColor(accent)
        aura_color.setAlpha(42)
        aura_edge = QColor(accent)
        aura_edge.setAlpha(0)
        aura.setColorAt(0.0, aura_color)
        aura.setColorAt(0.72, QColor(accent.red(), accent.green(), accent.blue(), 12))
        aura.setColorAt(1.0, aura_edge)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(aura)
        painter.drawEllipse(
            QRectF(
                sprite_rect.center().x() - sprite_rect.width() * 0.54,
                sprite_rect.top() + sprite_rect.height() * 0.09,
                sprite_rect.width() * 1.08,
                sprite_rect.height() * 0.84,
            )
        )

        shadow_alpha = 28 + int(10 * (math.sin(self.phase * 0.8) * 0.5 + 0.5))
        painter.setBrush(QColor(45, 27, 38, shadow_alpha))
        painter.drawEllipse(
            QRectF(
                sprite_rect.center().x() - sprite_rect.width() * 0.31,
                bottom - 10 * self.scale,
                sprite_rect.width() * 0.62,
                13 * self.scale,
            )
        )
        self._draw_ambient_sparkles(painter, sprite_rect, now)

        bob = math.sin(self.phase) * 2.8 * self.scale
        sway = math.sin(self.phase * 0.47 + 0.7) * 0.55
        breath = 1.0 + math.sin(self.phase * 0.9) * 0.0035

        painter.save()
        painter.translate(
            self.width() * 0.5,
            bottom + bob,
        )
        painter.rotate(sway)
        painter.scale(breath, breath)
        body_rect = QRectF(-pixmap.width() / 2, -pixmap.height(), pixmap.width(), pixmap.height())
        painter.drawPixmap(body_rect.topLeft(), pixmap)
        self._draw_blink(painter, body_rect, now)
        painter.restore()

        for particle in self._particles:
            age = max(0.0, now - particle.born)
            life = max(0.001, particle.lifetime)
            alpha = max(0.0, 1.0 - age / life)
            color = QColor(particle.color)
            color.setAlphaF(min(1.0, alpha * 0.9))
            if particle.shape == "heart":
                self._draw_heart(
                    painter,
                    QPointF(particle.x, particle.y),
                    particle.size * (0.8 + alpha * 0.25),
                    color,
                )
            else:
                self._draw_star(
                    painter,
                    QPointF(particle.x, particle.y),
                    particle.size * (0.65 + alpha * 0.25),
                    color,
                    rotation=age * 130,
                )

        self._draw_speech(painter, sprite_rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_global = event.globalPosition().toPoint()
            self._window_at_press = self.pos()
            self._dragging = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pressed_global is None:
            super().mouseMoveEvent(event)
            return
        delta = event.globalPosition().toPoint() - self._pressed_global
        if not self._dragging and delta.manhattanLength() >= 5:
            self._dragging = True
            self._tap_timer.stop()
        if self._dragging:
            self.move(self._window_at_press + delta)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            was_dragging = self._dragging
            self._dragging = False
            self._pressed_global = None
            if was_dragging:
                self._clamp_to_screen()
                self._save_position()
            elif not self._double_click_pending:
                self._tap_timer.start(230)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._tap_timer.stop()
            self._double_click_pending = True
            self._change_pose()
            QTimer.singleShot(320, self._clear_double_click)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _clear_double_click(self) -> None:
        self._double_click_pending = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        steps = event.angleDelta().y()
        if steps:
            delta = 0.08 if steps > 0 else -0.08
            self._change_scale(round(self.scale + delta, 2))
            self._set_speech("A good size?", 2.0)
            event.accept()
            return
        super().wheelEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self._build_menu()
        menu.exec(event.globalPos())
        menu.deleteLater()
        event.accept()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._animation_timer.isActive():
            self._last_tick = time.monotonic()
            self._animation_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._save_position()
        self._animation_timer.stop()

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
            return
        self.hide()
        event.ignore()


def create_application() -> tuple[QApplication, PetWindow]:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("StarryPocket")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(QIcon(str(ICON_PATH)))

    if "--preview" in sys.argv:
        window = PetWindow(SettingsStore())
        for pose in POSES:
            if f"--pose={pose['key']}" in sys.argv:
                window.pose_index = POSES.index(pose)
                break
        preview_message = "A little starlight for your desktop."
        for argument in sys.argv:
            if argument.startswith("--speech="):
                preview_message = argument.partition("=")[2]
                break
        window.show()
        window._set_speech(preview_message, 30)

        def save_preview() -> None:
            target = INSTALL_DIR / "_preview.png"
            window.grab().save(str(target), "PNG")
            app.quit()

        QTimer.singleShot(900, save_preview)
        return app, window

    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    if socket.waitForConnected(220):
        socket.write(b"show\n")
        socket.waitForBytesWritten(220)
        socket.disconnectFromServer()
        QTimer.singleShot(0, app.quit)
        return app, None  # type: ignore[return-value]

    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer(app)
    server.listen(SERVER_NAME)

    window = PetWindow(SettingsStore())
    window.show()

    def handle_instance_connection() -> None:
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is not None:
                connection.readAll()
                connection.disconnectFromServer()
        window.show()
        window.raise_()

    server.newConnection.connect(handle_instance_connection)
    app.aboutToQuit.connect(server.close)
    return app, window


def main() -> int:
    app, window = create_application()
    if window is None:
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
