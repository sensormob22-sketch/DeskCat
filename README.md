# DeskCat — этап 2

Интерактивный 3D-кот поверх рабочего стола Windows 11: Python 3.11+, PySide6,
Panda3D и panda3d-gltf. Технический прототип содержит настоящий skinned GLB
с тестовыми клипами и живым 3D-рендерингом. Это простая геометрическая модель,
не окончательный фотореалистичный ассет. Tripo и Ollama при запуске не вызываются.

**Интеграция на Windows 11 ещё не подтверждена.** Проверки выполнены только
в Linux Qt offscreen; реальная прозрачность DWM — обязательный следующий gate.

## Windows 11, PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev,three-d]'
.\.venv\Scripts\python.exe -m deskcat --renderer panda
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m deskcat --renderer panda --smoke-test
```

Запускать из checkout DeskCat: установка пока рассчитана на editable/source workflow.
Первый этап сохранён: `python -m deskcat --renderer qt` (также режим по умолчанию).
Подробная обязательная проверка Windows — [docs/WINDOWS11_CHECKLIST.md](docs/WINDOWS11_CHECKLIST.md).

## Управление

- ЛКМ: перетащить кота; walk при этом приостанавливается.
- ПКМ: выбрать idle / walk / sit / stand_up / groom / sleep, либо Exit.
- Колесо: масштаб 3D-модели, стрелки: положение модели внутри окна, R: сброс.
- Escape: выход. `--scale 1.5` увеличивает окно в логических пикселях Qt.

```powershell
.\.venv\Scripts\python.exe -m deskcat --renderer panda --scale 1.5 --model-scale 0.8 --model-x 0.2 --model-z 0.1 --position 500 400
.\.venv\Scripts\python.exe -m deskcat --renderer panda --model assets/3d/test_cat.glb
.\.venv\Scripts\python.exe -m deskcat --benchmark 120
```

Qt применяет DPI, renderer получает физический размер = размер окна × DPR.
Модель со скелетом должна иметь семь именованных клипов; неподдерживаемая модель
даёт понятную ошибку, без автоматического перехода на 2D. Тестовые sit/groom и
остальные клипы пока диагностические; они не изображают реалистичное поведение.
Прозрачные области окна могут перехватывать мышь; pixel-perfect click-through
ещё не реализован. Нет автозапуска, трея, записи в реестр или сетевых запросов.

## Архитектура и структура

GLB → gltf importer → Panda3D Actor → смешивание скелетных клипов → offscreen RGBA
→ QImage → QPainter прозрачного QWidget. Отдельного видимого окна Panda3D нет.
Это live 3D; предварительно отрисованные PNG не используются.

- `src/deskcat/`: Qt-окна, состояния, offscreen renderer, benchmark, контракт Ollama.
- `assets/3d/`: оригинальный CC0 `test_cat.glb`; будущая модель Tripo подключается через `--model`.
- `assets/animations/`: место для будущих клипов/метаданных.
- `tools/generate_test_cat.py`: воспроизводимый генератор GLB без внешних сервисов.
- `tests/`: запуск, состояния, реальные загрузка/skinning/blending/render/readback.
- [Архитектура](docs/ARCHITECTURE.md), [отчёт](docs/VALIDATION.md), [Tripo](docs/TRIPO_WORKFLOW.md).

## Linux cloud

```sh
UV_CACHE_DIR=/tmp/deskcat-uv-cache uv venv .venv
UV_CACHE_DIR=/tmp/deskcat-uv-cache uv pip install --python .venv/bin/python -e '.[dev,three-d]'
QT_QPA_PLATFORM=offscreen MESA_SHADER_CACHE_DIR=/tmp/deskcat-mesa .venv/bin/python -m pytest -q
QT_QPA_PLATFORM=offscreen MESA_SHADER_CACHE_DIR=/tmp/deskcat-mesa .venv/bin/python -m deskcat --renderer panda --smoke-test
MESA_SHADER_CACHE_DIR=/tmp/deskcat-mesa .venv/bin/python -m deskcat --benchmark 120
```

Без DISPLAY выбран EGL p3headlessgl. На Windows используется обычный Panda3D
OpenGL backend. Qt offscreen не проверяет Windows DWM или физический DPI.
