# Technical Debt: windows-capture улучшения

> Создано: 2026-01-16
> Обновлено: 2026-03-27
> Версия проекта: v1.3.2
> Связан с: `plans/task-breakdown-v1.3.x-v1.5.0.md`

---

## ⚠️ Важное примечание

**Проект работает исключительно на Windows 10/11.** Это ограничение по дизайну — используется Windows Graphics Capture API через библиотеку `windows-capture`. Поддержка Linux/macOS не планируется.

---

## 📊 Текущее состояние windows-capture

### ✅ Что уже реализовано

| Компонент | Файл | Статус |
|-----------|------|--------|
| Windows Graphics Capture | `recorder/video_recorder.py` | ✅ Используется |
| Session wrapper | `_WindowsCaptureSession` | ✅ Реализован |
| Full screen capture | `CaptureArea.full_screen()` | ✅ Работает |
| Window capture | `CaptureArea.from_window()` | ✅ Работает |
| Rectangle capture | `CaptureArea.from_rect()` | ✅ Работает |
| Event-driven frames | `on_frame_arrived` | ✅ Реализован |
| BGRA → BGR conversion | В обработчике кадров | ✅ Работает |

### ⚠️ Ограничения

| Проблема | Критичность | Влияние |
|----------|-------------|---------|
| Нет выбора монитора | 🟡 P2 | Multi-monitor setups |
| Dropped frames при 60+ FPS | 🟡 P2 | High FPS recording |
| CPU-only кодирование | 🟢 P3 | Performance bottleneck |
| Нет обработки потери окна | 🔴 P1 | Stability |
| Курсор всегда отключен | 🟢 P3 | Usability |
| ~~Только Windows~~ | — | **По дизайну — не бага** |

---

## 📋 Задачи по улучшению

### T-TD.1 — Улучшение интеграции windows-capture

#### 🔴 T-TD.1.1 — Обработка ошибок capture (ВЫПОЛНЕНО)

**Приоритет:** P1  
**Файлы:** `recorder/video_recorder.py`

**Выполненные изменения:**
1. Добавлен callback `on_closed_callback` в `_WindowsCaptureSession`
2. Добавлен флаг `_capture_lost` для отслеживания потери захвата
3. Реализована обработка события `on_closed` с логированием
4. Добавлено свойство `is_capture_lost` для проверки состояния
5. Обновлён `_capture_loop` для проверки потери захвата
6. Добавлен флаг `_capture_lost` в `VideoRecorder`
7. Улучшена обработка ошибок при захвате кадров

**Чек-лист:**
- [x] Добавить обработку `on_closed` event
- [x] Добавить флаг потери захвата
- [x] Добавить graceful degradation при ошибке
- [x] Логировать все capture errors с контекстом
- [x] Добавить проверку в capture loop
- [ ] Протестировать сценарии:
  - [ ] Закрытие захваченного окна
  - [ ] Отключение монитора во время записи
  - [ ] Смена разрешения монитора

**Оценка:** 3h (выполнено)

---

#### 🟡 T-TD.1.2 — Multi-monitor поддержка (ВЫПОЛНЕНО)

**Приоритет:** P2  
**Файлы:** `recorder/video_recorder.py`, `recorder/utils.py`, `cli/parser.py`

**Выполненные изменения:**
1. Добавлен параметр `monitor_index` в `CaptureArea`
2. Реализована функция `get_available_monitors()` в `recorder/utils.py`
3. Обновлена инициализация `WindowsCapture` для передачи `monitor_index`
4. Обновлён `CaptureArea.full_screen()` для поддержки выбора монитора
5. Добавлен CLI флаг `--monitor INDEX`
6. Добавлена передача `monitor_index` в конфигурацию записи

**Чек-лист:**
- [x] Добавить `monitor_index` в `CaptureArea`
- [x] Реализовать `get_available_monitors()`
- [x] Обновить `WindowsCapture` для передачи monitor_index
- [x] Добавить CLI флаг `--monitor INDEX`
- [ ] Добавить GUI выбор монитора в CaptureView
- [ ] Добавить preview выбранного монитора
- [ ] Протестировать на multi-monitor setup

**Оценка:** 4h (выполнено)

---

#### 🟢 T-TD.1.5 — Hardware cursor capture (ВЫПОЛНЕНО)

**Приоритет:** P3  
**Файлы:** `recorder/video_recorder.py`, `cli/parser.py`

**Выполненные изменения:**
1. Добавлен параметр `include_cursor` в `CaptureArea`
2. Обновлена инициализация `WindowsCapture`: `cursor_capture=capture_area.include_cursor`
3. Добавлен CLI флаг `--cursor`
4. Добавлена передача `include_cursor` в конфигурацию записи

**Чек-лист:**
- [x] Добавить параметр `include_cursor` в `CaptureArea`
- [x] Обновить `WindowsCapture` initialization
- [x] Добавить CLI флаг `--cursor`
- [ ] Добавить GUI toggle для курсора в CaptureView
- [ ] Протестировать с курсором и без

**Оценка:** 2h (выполнено)

---

#### 🟡 T-TD.1.3 — Оптимизация для 60+ FPS (P2)

**Проблема:**
При FPS > 30 возможны dropped frames из-за overhead копирования кадров.

**Файлы:** `recorder/video_recorder.py`

**Текущее:**
```python
# Копирование кадра при каждом захвате
self._last_frame = np.array(bgr, copy=True)  # ~5-10ms overhead
```

**Решение:**

1. **Zero-copy с frame pool:**

```python
class _FramePool:
    """Pool предвыделенных кадров для zero-copy."""
    
    def __init__(self, shape: tuple, pool_size: int = 3):
        self._pool = [np.zeros(shape, dtype=np.uint8) for _ in range(pool_size)]
        self._index = 0
        self._lock = threading.Lock()
    
    def get_frame(self) -> np.ndarray:
        with self._lock:
            frame = self._pool[self._index]
            self._index = (self._index + 1) % len(self._pool)
            return frame

class _WindowsCaptureSession:
    def __init__(self, frame_shape: tuple):
        self._frame_pool = _FramePool(frame_shape)
    
    @capture.event
    def on_frame_arrived(self, frame, capture_control):
        # Zero-copy: используем предвыделенный буфер
        pooled_frame = self._frame_pool.get_frame()
        np.copyto(pooled_frame, bgr)  # Быстрое копирование
        self._last_frame = pooled_frame
```

2. **Ring buffer для frame queue:**

```python
from collections import deque

class _RingBuffer:
    """Ring buffer для кадров с предвыделением."""
    
    def __init__(self, shape: tuple, size: int = 100):
        self._buffer = deque(maxlen=size)
        self._shape = shape
    
    def put(self, frame: np.ndarray) -> None:
        self._buffer.append(frame)
    
    def get(self) -> Optional[np.ndarray]:
        return self._buffer.popleft() if self._buffer else None
    
    @property
    def dropped_frames(self) -> int:
        """Количество dropped frames (когда буфер был полон)."""
        return self._dropped
```

3. **Профилирование:**

```python
# Добавить метрики
self._metrics = {
    "frames_captured": 0,
    "frames_dropped": 0,
    "avg_capture_time_ms": 0,
    "max_capture_time_ms": 0,
}

def _capture_loop(self):
    while self._state == RecordingState.RECORDING:
        start_time = time.perf_counter()
        
        # Capture frame
        frame = self._capture_session.read_frame(timeout=...)
        
        capture_time_ms = (time.perf_counter() - start_time) * 1000
        self._update_metrics(capture_time_ms)
```

**Чек-лист:**
- [ ] Профилировать текущую реализацию при 30/60/120 FPS
- [ ] Реализовать `_FramePool` для zero-copy
- [ ] Реализовать `_RingBuffer` для frame queue
- [ ] Добавить метрики: captured/dropped frames, capture time
- [ ] Оптимизировать critical path в `_capture_loop`
- [ ] Добавить возможность записи метрик в файл
- [ ] Протестировать при 60/120 FPS на разном hardware

**Оценка:** 6h

---

#### 🟢 T-TD.1.4 — GPU-ускорение кодирования (P3)

**Проблема:**
OpenCV VideoWriter использует CPU для кодирования, что ограничивает производительность.

**Файлы:** Создать `recorder/encoders/`

**Архитектура:**

```
recorder/
  encoders/
    __init__.py
    base.py              # VideoEncoder protocol
    opencv_encoder.py    # CPU encoder (текущий)
    nvenc_encoder.py     # NVIDIA GPU encoder
    qsv_encoder.py       # Intel Quick Sync encoder
    amf_encoder.py       # AMD AMF encoder
    factory.py           # Autodetection factory
```

**Реализация:**

```python
# recorder/encoders/base.py

from typing import Protocol

class VideoEncoder(Protocol):
    """Protocol для видеокодировщиков."""
    
    def open(self, output_path: Path, width: int, height: int, fps: int) -> bool:
        """Открытие файла для записи."""
        ...
    
    def write(self, frame: np.ndarray) -> bool:
        """Запись кадра."""
        ...
    
    def close(self) -> None:
        """Закрытие файла."""
        ...
    
    @property
    def name(self) -> str:
        """Название encoder."""
        ...

# recorder/encoders/nvenc_encoder.py

class NVENCEncoder:
    """NVIDIA NVENC GPU encoder."""
    
    def __init__(self, bitrate: str = "5M", preset: str = "fast"):
        self._process = None
        self._bitrate = bitrate
        self._preset = preset
    
    def open(self, output_path: Path, width: int, height: int, fps: int) -> bool:
        cmd = [
            "ffmpeg", "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{width}x{height}",
            "-pix_fmt", "bgr24",
            "-r", str(fps),
            "-i", "-",
            "-c:v", "h264_nvenc",
            "-preset", self._preset,
            "-b:v", self._bitrate,
            str(output_path),
        ]
        self._process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        return self._process.poll() is None
    
    def write(self, frame: np.ndarray) -> bool:
        if self._process is None:
            return False
        try:
            self._process.stdin.write(frame.tobytes())
            return True
        except BrokenPipeError:
            return False
    
    def close(self) -> None:
        if self._process:
            self._process.stdin.close()
            self._process.wait()
    
    @property
    def name(self) -> str:
        return "NVIDIA NVENC"

# recorder/encoders/factory.py

def get_best_encoder() -> VideoEncoder:
    """Автовыбор лучшего доступного encoder."""
    
    # Проверка NVIDIA NVENC
    if _is_nvenc_available():
        logger.info("Using NVIDIA NVENC encoder")
        return NVENCEncoder()
    
    # Проверка Intel Quick Sync
    if _is_qsv_available():
        logger.info("Using Intel Quick Sync encoder")
        return QSVEncoder()
    
    # Fallback на OpenCV CPU
    logger.info("Using OpenCV CPU encoder")
    return OpenCVEncoder()
```

**Чек-лист:**
- [ ] Создать `recorder/encoders/` модуль
- [ ] Определить `VideoEncoder` protocol
- [ ] Реализовать `OpenCVEncoder` (wrapper текущего кода)
- [ ] Реализовать `NVENCEncoder` (NVIDIA GPU)
- [ ] Реализовать `QSVEncoder` (Intel Quick Sync)
- [ ] Реализовать `AMFEncoder` (AMD GPU)
- [ ] Добавить autodetection GPU capabilities
- [ ] Добавить CLI флаг `--encoder cpu/nvenc/qsv/amf/auto`
- [ ] Добавить GUI выбор encoder в VideoView
- [ ] Протестировать на разных GPU:
  - [ ] NVIDIA RTX 3060+
  - [ ] Intel UHD 630+
  - [ ] AMD RX 6000+

**Оценка:** 8h

---

#### 🟢 T-TD.1.5 — Hardware cursor capture (P3)

**Проблема:**
Текущая реализация отключает курсор: `cursor_capture=False`

**Файлы:** `recorder/video_recorder.py`, `cli/parser.py`

**Решение:**

```python
# В CaptureArea
@dataclass
class CaptureArea:
    type: str
    include_cursor: bool = False  # Добавить опцию
    # ... existing fields

# При создании WindowsCapture
capture = WindowsCapture(
    cursor_capture=capture_area.include_cursor,
    draw_border=False,
    monitor_index=monitor_index,
    window_name=window_name,
)
```

**Чек-лист:**
- [ ] Добавить параметр `include_cursor` в `CaptureArea`
- [ ] Обновить `WindowsCapture` initialization
- [ ] Добавить CLI флаг `--cursor` / `--no-cursor`
- [ ] Добавить GUI toggle для курсора в CaptureView
- [ ] Протестировать с курсором и без

**Оценка:** 2h

---

#### 🟡 T-TD.1.6 — Обновить версию windows-capture (P2)

**Задача:**
Проверить и обновить версию `windows-capture` до последней stable.

**Текущая версия:** `windows-capture>=1.5.0`

**Действия:**
- [ ] Проверить последнюю версию на PyPI: https://pypi.org/project/windows-capture/
- [ ] Прочитать changelog на GitHub: https://github.com/Nexuslrr/Windows-Capture
- [ ] Проверить breaking changes
- [ ] Обновить `requirements.txt` и `pyproject.toml`
- [ ] Протестировать совместимость с текущей реализацией
- [ ] Обновить документацию

**Оценка:** 2h

---

### T-TD.2 — ~~Cross-platform поддержка~~ (ОТМЕНЕНО)

**Статус:** ❌ ОТМЕНЕНО  
**Причина:** Проект работает исключительно на Windows 10/11 по дизайну. Используется Windows Graphics Capture API. Поддержка Linux/macOS не планируется.

---

## 📊 Сводная таблица

| ID | Задача | Приоритет | Оценка | Релиз | Статус |
|---|---|---|---|---|---|
| T-TD.1.1 | Обработка ошибок capture | 🔴 P1 | 3h | v1.3.2 | ✅ Выполнено |
| T-TD.1.2 | Multi-monitor поддержка | 🟡 P2 | 4h | v1.3.2 | ✅ Выполнено |
| T-TD.1.3 | Оптимизация для 60+ FPS | 🟡 P2 | 6h | v1.4.0 | ❌ |
| T-TD.1.4 | GPU-ускорение кодирования | 🟢 P3 | 8h | v1.5.0 | ❌ |
| T-TD.1.5 | Hardware cursor capture | 🟢 P3 | 2h | v1.3.2 | ✅ Выполнено |
| T-TD.1.6 | Обновить windows-capture | 🟡 P2 | 2h | v1.3.2 | ⚠️ Требует проверки |
| ~~T-TD.2~~ | ~~Cross-platform поддержка~~ | — | — | — | ❌ Отменено |

---

## 🎯 Приоритет на ближайшие релизы

### v1.3.2 (Critical)
1. **T-TD.1.1** — Обработка ошибок capture (P1) ✅
2. **T-TD.1.6** — Обновить windows-capture (P2)
3. **T-TD.1.2** — Multi-monitor поддержка (P2) ✅

### v1.4.0 (Performance)
4. **T-TD.1.3** — Оптимизация для 60+ FPS (P2)

### v1.5.0 (Advanced)
5. **T-TD.1.4** — GPU-ускорение кодирования (P3)
6. **T-TD.1.5** — Hardware cursor capture (P3) ✅
