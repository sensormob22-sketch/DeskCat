# Выполненные проверки

Проверено 2026-10-10 в облачной Linux-среде, Python 3.12.14:

- Установка `.[dev,three-d]` через uv: успешно.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`: 11 passed.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m deskcat --smoke-test`:
  exit 0, visible=true, state=idle, размер 240×220; Qt event loop выполнен.
- Импорт `panda3d.core` и `gltf`: успешно. Это не проверка загрузки модели.

Qt offscreen сообщает, что raise() не поддерживается: topmost в этом режиме
не проверяется. Fontconfig сообщил об отсутствии writable cache directory;
это не помешало завершению запуска или тестов.

Не выполнено: запуск на Windows 11, проверка DWM-прозрачности, разных DPI,
нескольких физических мониторов, GPU-рендеринг, загрузка GLB, скелетная анимация,
диалог Ollama, генерация/обработка Tripo. 3D-бэкенд ещё не реализован.

## Этап 2 — 2026-10-10

Записи выше относятся к первому этапу. Во втором этапе 3D-бэкенд реализован,
но Windows-проверки всё ещё не выполнялись.

Среда: Linux, Python 3.12.14, PySide6 6.8.3, Panda3D 1.10.15,
panda3d-gltf 1.3.0, EGL offscreen, Mesa llvmpipe (LLVM 19.1.7, 256 bits).

- `QT_QPA_PLATFORM=offscreen MESA_SHADER_CACHE_DIR=/tmp/deskcat-mesa .venv/bin/python -m pytest -q`:
  **27 passed**, включая 11 проверок первого этапа. Изначально 8 тестов ошибочно
  обращались к несуществующему Actor.getControlEffect; исправлено на фактическое
  PartBundle.getControlEffect. Дополнительный тест конкретного имени типа буфера
  исправлен на isinstance(GraphicsBuffer), так как EGL использует подкласс.
- Реальный GLB загружен, обнаружены 6 joints и 7 клипов по 60 кадров.
- Проверена деформация mesh vertices, а не только наличие animation metadata;
  веса idle/walk = 0.5/0.5 посреди перехода, затем 0/1.
- Все семь клипов рендерятся; фон alpha=0, присутствуют непрозрачные пиксели модели.
  Проверена Qt-композиция над magenta QImage и alpha=0 в углу QWidget.grab().
- Новый 3D-процесс запускается и завершает smoke-test; drag/возврат walk и клавиатурное
  смещение модели проверены с реальными Qt mouse/key events в отдельном процессе.
- Отсутствующая модель: exit 1 с понятной ошибкой, без traceback. Повреждённый GLB
  отклоняется; прежняя загруженная модель продолжает работать.
- Qt offscreen при QT_SCALE_FACTOR=1 и 1.5: физические буферы 240×220 и 360×330.
  Это эмуляция DPR, не системная Windows DPI-проверка.
- Khronos glTF Validator `gltf-validator@2.0.0-dev.3.10`, validateBytes:
  **0 errors, 0 warnings, 0 infos, 0 hints**. Проверен конечный test_cat.glb.
  Валидатор установлен вне проекта; генератор GLB воспроизводится тестом byte-for-byte.

### Измеренный benchmark

120 кадров после 10 прогревочных, анимация walk, простой тестовый mesh:

| Буфер | Median, мс | p95, мс | Mean throughput, кадров/с |
| --- | ---: | ---: | ---: |
| 240×220 | 0.464 | 0.524 | 2038.89 |
| 360×330 | 0.955 | 1.490 | 888.78 |

Команды: `.venv/bin/python -m deskcat --benchmark 120` и та же с `--scale 1.5`,
с MESA_SHADER_CACHE_DIR=/tmp/deskcat-mesa. Измерены animation + offscreen rendering
+ RGBA readback + QImage copy. Qt paint/event loop/DWM исключены. Это throughput
маленького тестового ассета, не FPS интерактивного приложения и не прогноз для
Tripo-модели. Таймер окна 16 мс; его фактический cadence не измерялся.

### Ограничения проверки

Linux EGL предупреждает о default display и /dev/input, но использует рабочий
llvmpipe context. Qt offscreen не поддерживает raise(); topmost не проверен.
Проверены исходники документации Qt/Panda3D через официальные GitHub-репозитории.

Windows 11 gate = **NOT VERIFIED**: нет проверки DWM, прямоугольников/шлейфов,
физических DPI 100/150%, multi-monitor drag, реального mouse hit testing или Windows
GPU. Полный процесс описан в WINDOWS11_CHECKLIST.md. Полноценный Tripo-ассет,
фотореалистичные материалы и Ollama не проверены и не реализованы.

Повторно выполнен сохраняемый install script: установка, 27 тестов и оба smoke-test
успешны. XDG_CACHE_HOME=/tmp/deskcat-cache устранил предупреждение fontconfig;
EGL и Qt raise() сообщения остаются ожидаемыми ограничениями offscreen окружения.

## Этап 3 — 2026-10-10

### Linux (выполнено)

Python 3.12.14, PySide6 6.8.3, Panda3D 1.10.15, panda3d-gltf 1.3.0.
34 теста прошли с EGL/llvmpipe; те же 34 теста прошли с явно выбранным
p3tinydisplay. Проверены также installation refresh и диагностический smoke-test.

Новые проверки: rig-only GLB без единого clip, partial/renamed clips и явный map,
отказ неверного mapping без потери рабочей модели, NOT played для отсутствующего
состояния, локальные clocks/speed/pause/seek, phase alignment idle→walk, отсутствие
reset при прерванном crossfade, heading/пауза движения при развороте, JSONL/PNG
capture, startup error и инъекция render failure в реальный Qt event loop.

Первый rig-only тест обнаружил удаление пустого Character импортёром. Исправлено
identity wrapper в памяти, без изменения файла или добавления fake animation.
Первый TinyDisplay прогон обнаружил отсутствие BFResizeable у буфера. Исправлено
явным созданием RGBA8/depth24 offscreen GraphicsBuffer с BFResizeable. Конечные
прогоны соответствующих suites прошли; проверки не отключались и не заменялись skip.

Qt offscreen по-прежнему не поддерживает raise(); TinyDisplay на Linux сообщает
о недоступном X display, но успешно использует offscreen buffer. Это не проверка
рабочего стола. Производительность этапа 2 нельзя переносить на новые компоненты
или будущий Tripo ассет; новые значения frame timing собирает diagnostics.

### Windows CI (отдельно)

Добавлен .github/workflows/windows.yml: windows-latest / Python 3.11, установка,
импорты Panda/glTF/fixture, полная suite, Qt/Panda smoke, JUnit и diagnostic artifact.
Renderer явно p3tinydisplay, Qt offscreen. Run/conclusion нужно проверять в GitHub
Actions для соответствующего SHA; наличие файла workflow или Linux PASS не является
Windows CI PASS. Итог доступного CI run сообщается отдельно в отчёте PR/задачи.

### Реальная Windows 11 visual session (не выполнено)

NOT VERIFIED. Не запускались Windows DWM, actual DPI 100/150%, topmost,
реальное hit testing, desktop screenshots, GPU/pandagl или mixed-DPI мониторы.
Для gate нужны DIAGNOSTICS.md + WINDOWS11_CHECKLIST.md и наблюдения пользователя.
CI runner не заменяет эту графическую сессию, даже если все его checks зелёные.

Tripo генерация/rig/retarget не запускались, кредиты не расходовались. Исходных
референсов CatDesk пока нет; в workflow указана calico кошка с необходимостью
проверить сходство по оригиналу до платной генерации.
