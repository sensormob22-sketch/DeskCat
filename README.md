# DeskCat

Проект интерактивного фотореалистичного 3D-кота поверх рабочего стола Windows 11.
Python 3.11+ и PySide6. **Версия 0.1 — запускаемый 2D-прототип**, а не готовый
фотореалистичный кот: пока нет GLB, GPU-рендерера, скелетных клипов и диалога.

## Запуск в Windows 11 (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m deskcat
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m deskcat --smoke-test
```

Также подходит установленный Python 3.12+. Для будущего 3D-бэкенда:
`python -m pip install -e '.[three-d,dev]'`.

Левая кнопка — перетаскивание; правая — меню состояний и Exit; Escape — выход.
Выберите walk для движения, sit / stand_up / groom / sleep для проверки состояний.
`python -m deskcat --scale 1.5` меняет размер в логических пикселях Qt; масштаб DPI
применяет Qt. Кот ограничен доступной областью монитора, при перетаскивании можно
сменить монитор. Прозрачные участки окна пока могут перехватывать мышь;
click-through и системный трей запланированы. Нет автозапуска и записи в реестр.

## Структура и этапы

- `src/deskcat/`: окно, машина состояний, интерфейс рендерера, контракт Ollama.
- `assets/3d/`: будущий `cat.glb`; `assets/animations/`: клипы и метаданные.
- `tests/`: переходы, запуск процесса и свойства окна / перетаскивание.
- `docs/ARCHITECTURE.md`: выбор рендерера и интеграция.
- `docs/TRIPO_WORKFLOW.md`: подготовка 3D-ассета без расхода кредитов.

Сначала проверить окно на реальном Windows 11. Затем реализовать Panda3D-бэкенд,
загрузить проверенный rigged GLB, подключить клипы и освещение. После этого —
локальный диалог Ollama в отдельном рабочем потоке.

## Проверки в Linux/cloud

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m deskcat --smoke-test
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
```

Offscreen проверяет создание окна и работу event loop. Он не доказывает корректную
композицию прозрачности Windows DWM, поведение поверх других приложений, GPU,
фотореализм или скелетную анимацию. Итоги фактически выполненных проверок —
в `docs/VALIDATION.md`.
