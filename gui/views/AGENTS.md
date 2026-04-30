<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# gui/views/

## Purpose
PyQt6 виджеты-представления (View в MVC). Каждый файл — отдельная вкладка или диалоговый компонент главного окна. Представления отображают состояние и испускают сигналы; бизнес-логика находится в `gui/controllers/`.

## Key Files

| Файл | Описание |
|------|----------|
| `capture_view.py` | Вкладка «Захват»: выбор области (полный экран/окно/прямоугольник), список мониторов/окон |
| `audio_view.py` | Вкладка «Аудио»: выбор источника звука, уровень громкости |
| `video_view.py` | Вкладка «Видео»: FPS, кодек, битрейт, разрешение |
| `output_view.py` | Вкладка «Вывод»: путь сохранения, формат файла, шаблон имени |
| `api_settings_view.py` | Вкладка «API»: порт, API-ключ, включение/отключение сервера |
| `diagnostics_view.py` | Вкладка «Диагностика»: системная информация, лог |
| `readiness_center_view.py` | Вкладка «Готовность»: статус компонентов (FFmpeg, аудио, диск) |
| `recording_indicator.py` | Индикатор записи: плавающий оверлей с таймером и кнопками управления |
| `area_selector.py` | `AreaSelectorDialog` — интерактивный выбор прямоугольной области экрана |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Представления — только UI: не содержат бизнес-логику, не вызывают `ApplicationFacade` напрямую.
- Все взаимодействия с логикой — через сигналы PyQt6, которые подключают контроллеры.
- `accessibility.py` (`apply_accessible_metadata`) вызывается в каждом представлении для ARIA-атрибутов.
- `area_selector.py` открывает полноэкранное прозрачное окно для выбора прямоугольника.
- `recording_indicator.py` — отдельное floating окно поверх всех, без родительского виджета.
- Стили — только через `gui/styles/theme.py`.

### Testing Requirements
- `tests/unit/test_gui_views.py` — общие тесты views
- `tests/unit/test_capture_view.py` — тесты CaptureView
- `tests/unit/test_audio_view.py` — тесты AudioView
- `tests/unit/test_video_view.py` — тесты VideoView
- `tests/unit/test_api_settings_view.py` — тесты ApiSettingsView
- `tests/unit/test_readiness_center_view.py` — тесты ReadinessCenterView
- `tests/unit/test_recording_indicator.py` — тесты индикатора
- `tests/unit/test_capture_area_selector.py` — тесты диалога выбора области
- `tests/unit/test_view_accessibility.py` — тесты accessibility атрибутов

### Common Patterns
```python
class CaptureView(QWidget):
    area_changed = pyqtSignal(str)   # сигнал изменения области

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        apply_accessible_metadata(self)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        # ...

    def get_capture_area(self) -> CaptureArea:
        # читает UI и возвращает значение
        ...
```

## Dependencies

### Internal
- `gui/models/` — типы данных (CaptureType, AudioSettings, etc.)
- `gui/styles/theme.py` — цветовая схема
- `gui/accessibility.py` — ARIA-атрибуты
- `recorder/utils.py` — список мониторов и окон
- `gui/views/area_selector.py` — используется из `capture_view.py`

### External
- `PyQt6.QtWidgets`, `PyQt6.QtCore`, `PyQt6.QtGui`

<!-- MANUAL: -->
