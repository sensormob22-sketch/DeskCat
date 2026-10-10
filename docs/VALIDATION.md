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
