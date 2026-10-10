# Короткая проверка на Windows 11

В checkout ветки work установите Python 3.11 и `pip install -e '.[dev,three-d]'`
в .venv (полные команды в README). Удалите QT_QPA_PLATFORM=offscreen и
DESKCAT_PANDA_DISPLAY=p3tinydisplay, если они перенесены из CI: ручная проверка
должна идти в настоящей сессии Windows с обычным pandagl.

```powershell
New-Item -ItemType Directory -Force diagnostics\windows-100 | Out-Null
.\.venv\Scripts\python.exe -u -m deskcat --renderer panda --diagnostics diagnostics/windows-100 2>&1 | Tee-Object -FilePath diagnostics\windows-100\console.txt
```

1. Поставьте системный Scale 100%, запустите команду. Расположите кошку поверх
   контрастных обоев и окна с текстом: вокруг неё должен быть виден настоящий фон.
2. Magenta рамка — весь кадр, cyan — alpha bounds, текст — DPR и render time.
   F7 убирает рамки/текст для чистой визуальной проверки. F8 сохраняет RGBA PNG
   и запись JSONL; **это не снимок рабочего стола и не доказательство DWM**.
3. Win+Shift+S: снимите кошку вместе с фоном/окном под ней, сохраните
   `desktop-100.png` в ту же папку. Проверьте отсутствие прямоугольника/шлейфа,
   topmost, drag, правое меню, Space, колесо, стрелки, разворот walk у края экрана.
4. Закройте через Escape. Повторите при системном Scale 150%, используя папку
   `diagnostics/windows-150`; screenshot — `desktop-150.png`. При mixed-DPI мониторах
   перетащите между ними. QT_SCALE_FACTOR не заменяет эту проверку.
5. В каждой папке сохраните `observations.txt`: Windows build, GPU/driver,
   actual scale, какие шаги PASS/FAIL, клики на прозрачной области, заметные задержки.
   Соберите папки в ZIP и приложите к PR #1. Убедитесь, что screenshots не содержат
   приватных окон/данных, которые вы не хотите публиковать.

session.jsonl содержит версии ОС/Python/Qt/Panda/importer, renderer/backend,
window flags/position/active/visible, DPI/physical size, alpha bounds/edge clipping,
последний render_ms и frame_interval_ms, клип-карту/времена/веса, mouse/key events,
startup_error/render_error. Console.txt сохраняет также сообщения Panda3D.
ОС и paths могут содержать имя локального пользователя; журнал не дампит env/ключи.

Если модель не загрузилась, журнал фиксирует startup_error, процесс возвращает 1.
Если renderer упал во время кадра — render_error, окно закрывается и exit 1.
Если фон непрозрачен, или нет реальных screenshots, Windows visual gate не считается
пройденным даже при alpha=0 в PNG и зелёном CI. Полный checklist — WINDOWS11_CHECKLIST.md.
