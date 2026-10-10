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
