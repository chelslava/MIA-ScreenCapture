"""
Диалог управления профилями записи
===================================

Предоставляет пользовательский интерфейс для создания, редактирования,
удаления, импорта, экспорта и применения профилей настроек записи.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config import AudioSettings, CaptureSettings, VideoSettings
from core.profiles import ProfileStorage, RecordingProfile, get_profile_storage
from gui.accessibility import apply_accessible_metadata
from gui.styles.theme import Theme
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class ProfileDialog(QDialog):
    """Диалог управления профилями записи."""

    profile_applied = pyqtSignal(str)
    profiles_changed = pyqtSignal()

    def __init__(
        self,
        storage: ProfileStorage | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """
        Инициализация диалога профилей.

        Args:
            storage: Хранилище профилей (по умолчанию синглтон).
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._storage = storage or get_profile_storage()
        self._current_profile_id: str | None = None

        self.setWindowTitle("Управление профилями записи")
        self.resize(750, 520)
        self.setModal(True)

        self._setup_ui()
        self._load_profiles_list()

    def _setup_ui(self) -> None:
        """Настройка графического интерфейса диалога."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(
            Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN
        )
        main_layout.setSpacing(Theme.SPACING)

        # Левая колонка: список профилей и действия над ними
        left_layout = QVBoxLayout()
        left_layout.setSpacing(Theme.SPACING)

        list_label = QLabel("Сохраненные профили:")
        list_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(list_label)

        self._profile_list = QListWidget()
        self._profile_list.currentRowChanged.connect(self._on_profile_selected)
        left_layout.addWidget(self._profile_list)

        # Кнопки управления списком
        btn_layout_1 = QHBoxLayout()
        self._btn_create = QPushButton("➕ Новый")
        self._btn_create.clicked.connect(self._create_new_profile)
        self._btn_duplicate = QPushButton("📋 Копия")
        self._btn_duplicate.clicked.connect(self._duplicate_selected_profile)
        btn_layout_1.addWidget(self._btn_create)
        btn_layout_1.addWidget(self._btn_duplicate)
        left_layout.addLayout(btn_layout_1)

        btn_layout_2 = QHBoxLayout()
        self._btn_set_default = QPushButton("⭐ По умолчанию")
        self._btn_set_default.clicked.connect(self._set_selected_default)
        self._btn_delete = QPushButton("🗑️ Удалить")
        self._btn_delete.clicked.connect(self._delete_selected_profile)
        btn_layout_2.addWidget(self._btn_set_default)
        btn_layout_2.addWidget(self._btn_delete)
        left_layout.addLayout(btn_layout_2)

        btn_layout_3 = QHBoxLayout()
        self._btn_import = QPushButton("📥 Импорт")
        self._btn_import.clicked.connect(self._import_profile)
        self._btn_export = QPushButton("📤 Экспорт")
        self._btn_export.clicked.connect(self._export_profile)
        btn_layout_3.addWidget(self._btn_import)
        btn_layout_3.addWidget(self._btn_export)
        left_layout.addLayout(btn_layout_3)

        main_layout.addLayout(left_layout, 1)

        # Правая колонка: форма редактирования и параметры профиля
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(Theme.SPACING)

        details_group = QGroupBox("Параметры выбранного профиля")
        details_layout = QVBoxLayout(details_group)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        form_layout = QFormLayout(scroll_content)
        form_layout.setSpacing(8)

        # Общие поля
        self._edit_name = QLineEdit()
        form_layout.addRow("Название:", self._edit_name)

        self._edit_desc = QLineEdit()
        form_layout.addRow("Описание:", self._edit_desc)

        self._edit_icon = QLineEdit()
        self._edit_icon.setMaxLength(8)
        form_layout.addRow("Иконка:", self._edit_icon)

        # Видео настройки
        self._combo_fps = QComboBox()
        self._combo_fps.addItems(["15", "24", "30", "60", "120"])
        form_layout.addRow("FPS:", self._combo_fps)

        self._combo_codec = QComboBox()
        self._combo_codec.addItems(["libx264", "libx265", "libvpx-vp9"])
        form_layout.addRow("Кодек видео:", self._combo_codec)

        self._combo_bitrate = QComboBox()
        self._combo_bitrate.addItems(
            ["1M", "2M", "3M", "5M", "8M", "12M", "16M"]
        )
        form_layout.addRow("Битрейт видео:", self._combo_bitrate)

        self._combo_format = QComboBox()
        self._combo_format.addItems(["mp4", "mkv", "avi", "mov", "webm"])
        form_layout.addRow("Формат контейнера:", self._combo_format)

        self._combo_preset = QComboBox()
        self._combo_preset.addItems(
            [
                "ultrafast",
                "superfast",
                "veryfast",
                "faster",
                "fast",
                "medium",
                "slow",
            ]
        )
        form_layout.addRow("Пресет кодирования:", self._combo_preset)

        # Аудио настройки
        self._combo_audio_mode = QComboBox()
        self._combo_audio_mode.addItems(
            [
                "Только микрофон",
                "Только системный звук",
                "Микрофон и системный звук",
                "Без звука",
            ]
        )
        form_layout.addRow("Источник звука:", self._combo_audio_mode)

        self._spin_sample_rate = QSpinBox()
        self._spin_sample_rate.setRange(8000, 192000)
        self._spin_sample_rate.setValue(44100)
        self._spin_sample_rate.setSingleStep(4000)
        form_layout.addRow("Частота дискретизации:", self._spin_sample_rate)

        # Захват настройки
        self._combo_area = QComboBox()
        self._combo_area.addItems(
            ["Весь экран (full)", "Окно (window)", "Область (rect)"]
        )
        form_layout.addRow("Область захвата:", self._combo_area)

        self._edit_window_title = QLineEdit()
        self._edit_window_title.setPlaceholderText("Имя или заголовок окна")
        form_layout.addRow("Заголовок окна:", self._edit_window_title)

        scroll_area.setWidget(scroll_content)
        details_layout.addWidget(scroll_area)

        # Кнопки сохранения и применения
        action_btn_layout = QHBoxLayout()
        self._btn_save_changes = QPushButton("💾 Сохранить изменения")
        self._btn_save_changes.clicked.connect(self._save_current_profile)
        self._btn_apply = QPushButton("🚀 Применить профиль")
        self._btn_apply.setStyleSheet("font-weight: bold;")
        self._btn_apply.clicked.connect(self._apply_current_profile)

        action_btn_layout.addWidget(self._btn_save_changes)
        action_btn_layout.addWidget(self._btn_apply)
        details_layout.addLayout(action_btn_layout)

        right_layout.addWidget(details_group)

        # Нижняя кнопка закрытия
        close_btn_layout = QHBoxLayout()
        close_btn_layout.addStretch()
        self._btn_close = QPushButton("Закрыть")
        self._btn_close.clicked.connect(self.close)
        close_btn_layout.addWidget(self._btn_close)
        right_layout.addLayout(close_btn_layout)

        main_layout.addWidget(right_widget, 2)

        # Accessibility
        apply_accessible_metadata(
            self._profile_list,
            "Список профилей",
            "Содержит доступные профили конфигураций записи",
        )

    def _load_profiles_list(self) -> None:
        """Загружает список профилей в список виджета."""
        self._profile_list.clear()
        profiles = self._storage.list_profiles()

        target_row = 0
        for index, profile in enumerate(profiles):
            label_parts = [profile.icon, profile.name]
            if profile.is_default:
                label_parts.append("[по умолчанию]")
            if profile.is_builtin:
                label_parts.append("[системный]")

            item = QListWidgetItem(" ".join(label_parts))
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            self._profile_list.addItem(item)

            if self._current_profile_id == profile.id:
                target_row = index

        if profiles:
            self._profile_list.setCurrentRow(target_row)
        else:
            self._clear_form()

    def _on_profile_selected(self, row: int) -> None:
        """Обработка выбора профиля из списка."""
        if row < 0 or row >= self._profile_list.count():
            self._clear_form()
            return

        item = self._profile_list.item(row)
        if not item:
            return

        profile_id = item.data(Qt.ItemDataRole.UserRole)
        profile = self._storage.get_profile(profile_id)
        if not profile:
            return

        self._current_profile_id = profile.id
        self._populate_form(profile)

        # Системные профили защищены от удаления
        self._btn_delete.setEnabled(not profile.is_builtin)
        self._btn_set_default.setEnabled(not profile.is_default)

    def _populate_form(self, profile: RecordingProfile) -> None:
        """Заполняет форму значениями профиля."""
        self._edit_name.setText(profile.name)
        self._edit_desc.setText(profile.description)
        self._edit_icon.setText(profile.icon)

        # Video
        idx = self._combo_fps.findText(str(profile.video.fps))
        if idx >= 0:
            self._combo_fps.setCurrentIndex(idx)
        else:
            self._combo_fps.setCurrentText(str(profile.video.fps))

        idx = self._combo_codec.findText(profile.video.codec)
        if idx >= 0:
            self._combo_codec.setCurrentIndex(idx)

        idx = self._combo_bitrate.findText(profile.video.bitrate)
        if idx >= 0:
            self._combo_bitrate.setCurrentIndex(idx)

        idx = self._combo_format.findText(profile.video.format)
        if idx >= 0:
            self._combo_format.setCurrentIndex(idx)

        idx = self._combo_preset.findText(profile.video.preset)
        if idx >= 0:
            self._combo_preset.setCurrentIndex(idx)

        # Audio
        if profile.audio.record_mic and profile.audio.record_system:
            self._combo_audio_mode.setCurrentIndex(2)
        elif profile.audio.record_mic:
            self._combo_audio_mode.setCurrentIndex(0)
        elif profile.audio.record_system:
            self._combo_audio_mode.setCurrentIndex(1)
        else:
            self._combo_audio_mode.setCurrentIndex(3)

        self._spin_sample_rate.setValue(profile.audio.sample_rate)

        # Capture
        area_map = {"full": 0, "window": 1, "rect": 2}
        self._combo_area.setCurrentIndex(
            area_map.get(profile.capture.area_type, 0)
        )
        self._edit_window_title.setText(profile.capture.window_title or "")

    def _clear_form(self) -> None:
        """Очищает форму."""
        self._current_profile_id = None
        self._edit_name.clear()
        self._edit_desc.clear()
        self._edit_icon.setText("⚙️")
        self._edit_window_title.clear()
        self._btn_delete.setEnabled(False)
        self._btn_set_default.setEnabled(False)

    def _save_current_profile(self) -> None:
        """Сохраняет измененные значения профиля."""
        if not self._current_profile_id:
            return

        name = self._edit_name.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Ошибка", "Название профиля не может быть пустым."
            )
            return

        desc = self._edit_desc.text().strip()
        icon = self._edit_icon.text().strip() or "⚙️"

        # Сбор video settings
        try:
            fps = int(self._combo_fps.currentText())
        except ValueError:
            fps = 30

        video = VideoSettings(
            fps=fps,
            codec=self._combo_codec.currentText(),
            bitrate=self._combo_bitrate.currentText(),
            format=self._combo_format.currentText(),
            preset=self._combo_preset.currentText(),
        )

        # Сбор audio settings
        audio_mode = self._combo_audio_mode.currentIndex()
        record_mic = audio_mode in (0, 2)
        record_system = audio_mode in (1, 2)
        audio = AudioSettings(
            record_mic=record_mic,
            record_system=record_system,
            sample_rate=self._spin_sample_rate.value(),
        )

        # Сбор capture settings
        area_types = ["full", "window", "rect"]
        area_type = area_types[self._combo_area.currentIndex()]
        window_title = (
            self._edit_window_title.text().strip()
            if area_type == "window"
            else None
        )
        capture = CaptureSettings(
            area_type=area_type,
            window_title=window_title,
        )

        self._storage.update_profile(
            profile_id=self._current_profile_id,
            name=name,
            description=desc,
            icon=icon,
            video=video,
            audio=audio,
            capture=capture,
        )

        self._load_profiles_list()
        self.profiles_changed.emit()
        QMessageBox.information(
            self, "Успех", f"Профиль '{name}' успешно сохранен."
        )

    def _apply_current_profile(self) -> None:
        """Применяет текущий профиль к конфигурации."""
        if not self._current_profile_id:
            return

        success = self._storage.apply_profile_to_config(
            self._current_profile_id
        )
        if success:
            self.profile_applied.emit(self._current_profile_id)
            QMessageBox.information(
                self, "Успех", "Настройки профиля успешно применены!"
            )
        else:
            QMessageBox.warning(
                self, "Ошибка", "Не удалось применить профиль."
            )

    def _create_new_profile(self) -> None:
        """Создает новый профиль на основе текущей формы."""
        base_name = "Новый профиль"
        new_prof = self._storage.create_profile(
            name=base_name,
            description="Пользовательский профиль",
            icon="✨",
        )
        self._current_profile_id = new_prof.id
        self._load_profiles_list()
        self.profiles_changed.emit()

    def _duplicate_selected_profile(self) -> None:
        """Дублирует выбранный профиль."""
        if not self._current_profile_id:
            return

        copy_prof = self._storage.duplicate_profile(self._current_profile_id)
        if copy_prof:
            self._current_profile_id = copy_prof.id
            self._load_profiles_list()
            self.profiles_changed.emit()

    def _delete_selected_profile(self) -> None:
        """Удаляет выбранный профиль."""
        if not self._current_profile_id:
            return

        profile = self._storage.get_profile(self._current_profile_id)
        if not profile:
            return

        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить профиль '{profile.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            success, error = self._storage.delete_profile(
                self._current_profile_id
            )
            if success:
                self._current_profile_id = None
                self._load_profiles_list()
                self.profiles_changed.emit()
            else:
                QMessageBox.warning(
                    self, "Ошибка", error or "Не удалось удалить профиль."
                )

    def _set_selected_default(self) -> None:
        """Делает выбранный профиль дефолтным."""
        if not self._current_profile_id:
            return

        if self._storage.set_default_profile(self._current_profile_id):
            self._load_profiles_list()
            self.profiles_changed.emit()

    def _export_profile(self) -> None:
        """Экспортирует выбранный профиль в JSON файл."""
        if not self._current_profile_id:
            return

        data = self._storage.export_profile(self._current_profile_id)
        if not data:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт профиля записи",
            f"profile_{self._current_profile_id}.json",
            "JSON Files (*.json)",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(
                    self, "Успех", f"Профиль экспортирован в {file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка", f"Не удалось экспортировать профиль: {e}"
                )

    def _import_profile(self) -> None:
        """Импортирует профиль из JSON файла."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт профиля записи",
            "",
            "JSON Files (*.json)",
        )
        if file_path:
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                imported = self._storage.import_profile(data)
                self._current_profile_id = imported.id
                self._load_profiles_list()
                self.profiles_changed.emit()
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Профиль '{imported.name}' успешно импортирован!",
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Ошибка", f"Не удалось импортировать профиль: {e}"
                )
