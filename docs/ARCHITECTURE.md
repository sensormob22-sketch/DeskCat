# 3D-архитектура — этап 3

## Реализовано

`PandaRenderer` загружает настоящий GLB через panda3d-gltf 1.3.0, создаёт Actor,
нормализует bounds модели, освещает её и каждый кадр применяет веса StateMachine.
Доступные клипы получают циклические fractional frame poses; frameBlend включён.
Кадры и деформация вершин проверяются тестами. Это воспроизведение скелетной
анимации с ручным шагом времени Qt, без второго блокирующего Panda event loop.

`ThreeDWindow` наследует работающие движение/drag/меню первого этапа, заменяет
только рисование. Panda GraphicsBuffer работает offscreen, alpha clear=0,
RTMCopyRam сохраняет RGBA. QImage владеет копией данных, переворачивает изображение
из bottom-up и передаёт straight alpha Qt. Qt рисует изображение в прозрачном
QWidget. Размер буфера учитывает DPR и обновляется при смене размера/DPI.

Модель имеет отдельные root nodes скелета и меша — допустимую glTF структуру.
Actor извлекает Character и иначе оставляет sibling geometry вне себя. Адаптер
переподчиняет геометрию Character с сохранением трансформаций и создаёт Actor
без копирования, сохраняя joint bindings. Поддержан один скелет. GLB fixture
валидирован Khronos validator без ошибок/предупреждений.

Первый CatWindow остаётся доступен через `--renderer qt`; `--renderer panda`
включает live 3D. Загрузка неподдерживаемого/отсутствующего файла не маскируется
рисованной заглушкой. Ollama по-прежнему выключен.

## Почему этот путь вместо native embedding

Поддержка Python, glTF skinning и Actor blending делает Panda3D подходящим
кандидатом. Встраивание дочернего HWND Panda3D рискует обойти Qt raster backing
store: alpha framebuffer не гарантирует прозрачность всего native окна.
Отдельные native surfaces также требуют согласования DPI, z-order и мыши.
Прямое встраивание в Windows не испытано; мы не заявляем доказанный отказ.

Выбран путь offscreen → RGBA → Qt, в котором финальной композицией и мышью
управляет одно Qt-окно. PNG-последовательности не используются. Альфа пикселей
и композиция поверх цветного QImage проверены в Linux, но это ещё не доказательство
прозрачности поверх рабочего стола Windows 11.

Официальная документация Qt 6.8.3 требует WA_TranslucentBackground и неopaque
рисование, а на Windows — FramelessWindowHint. Атрибуты выставляются до show().
Проверено по исходнику Qt:
https://github.com/qt/qtbase/blob/v6.8.3/src/widgets/kernel/qwidget.cpp#L745

Panda3D явно описывает RTM_copy_ram как копирование буфера в RAM каждый кадр:
https://github.com/panda3d/panda3d/blob/v1.10.15/panda/src/display/graphicsOutput.h#L77
Эти исходники прочитаны. Прямой доступ к doc.qt.io/docs.panda3d.org блокировался
сетевой политикой; ссылкам не приписывается проведённая Windows-проверка.

## Ограничения и следующие шаги

- Реальная Windows 11 DWM-прозрачность, отсутствие прямоугольника/шлейфа,
  topmost, hit testing и DPI 100/150% остаются непроверенными. Пока gate не пройден,
  архитектуру нельзя считать подтверждённой для целевой платформы.
- CPU/GPU readback и копии QImage синхронны в Qt-потоке; большой ассет может тормозить
  UI. Benchmark исключает Qt paint/DWM. Измерить конечный workflow на Windows.
- Поддерживается один skin/скелет активной scene. Анимации необязательны, карта
  state → actual clip задаётся через --clips. External clip import пока не реализован.
  Для окончательного Tripo ассета всё ещё нужен import acceptance test.
- Только стандартные непрозрачные материалы и базовый свет; PBR/IBL/fur/tone mapping
  ещё не подготовлены. Полупрозрачные материалы могут требовать отдельной проверки
  straight/premultiplied alpha и краёв.
- Модель нормализуется по bounds, pivot у лап; GLB Y-up → Panda Z-up выполняет
  импортёр. Walk — in-place, движение — в логических координатах окна.
- Настоящие клипы sit/groom/sleep/stand_up не готовы. Тестовые движения демонстрируют
  API. Stand_up по-прежнему возвращается в idle через 0.8 с первого этапа; для нового
  ассета потребуется длина реального клипа и отдельный playback policy.
- Альфа не задаёт автоматически контракт click-through. Нужно отдельно проверить
  фактическое Windows поведение и при необходимости добавить alpha-aware hit test.
- Сборка wheel пока не включает asset; поддержан editable/source checkout.

Если Qt raster transparency не пройдёт Windows gate, сначала проверить composition
и alpha в Qt-only окне, затем рассмотреть Win32 layered window с UpdateLayeredWindow
и premultiplied BGRA из того же live Panda renderer. Это усложнит DPI/hit testing.
Если readback станет узким местом, кандидат — Qt Quick 3D с Qt-native composition
или D3D/DirectComposition sharing. Ни одна альтернатива не считается проверенной.

## Изменения этапа 3

Windows CI использует Python 3.11, Qt offscreen и явно p3tinydisplay. OpenGL/pandagl
остаётся обычным Windows backend, Linux без DISPLAY — EGL p3headlessgl.
DESKCAT_PANDA_DISPLAY позволяет явно выбрать один из этих backend, что отражается
в диагностике. Буфер создаётся с BFRefuseWindow | BFResizeable и RGBA8/depth24:
это устранило обнаруженную несовместимость resize между разными renderer.

gltf_scene.py оборачивает sibling scene roots в identity root в памяти перед
импортом. У panda3d-gltf 1.3.0 пустой Character может быть удалён, если rig не
имеет анимаций и mesh стоит отдельно. Общий root сохраняет joint bindings и
bind pose без synthetic clips. Используется внутренний Converter API pinned
версии; обновление импортёра требует повторной проверки этих тестов.

clip_map по умолчанию сопоставляет точные имена, missing_states показывает пробелы.
Пользовательские переименования задаются JSON. Ошибочная ссылка на clip отклоняется;
failed reload не уничтожает рабочую модель. Missing state не подменяется idle/walk:
веса отсутствующего clip не применяются, меню помечает его `no clip` и отключает.
При программном/drag запросе missing state журнал явно сообщает NOT played.
Если все запрошенные clips отсутствуют, модель остаётся без анимационного влияния
(bind pose); плавность перехода к несуществующему clip не обещается.

ClipClock хранит времена отдельных clips, замораживает неактивные, поддерживает
speed/pause/seek. При первом ненулевом весе входящий clip получает normalized phase
доминирующего предыдущего. Пока clip виден, phase не сбрасывается, в том числе при
прерванном переходе. Это не гарантирует совпадение контактов лап у произвольно
авторских clips; потребуются phase markers/offsets и проверка Tripo animation assets.

Heading привязан к _direction. Поворот ограничен 540 град/с, путь выбирается по
кратчайшему углу. Пока heading не согласован с новым direction, движение окна
приостановлено; Walk clock продолжает идти, чтобы не сбрасывать gait. Heading offset
калибрует исходную модель. Space замораживает clocks и desktop locomotion.

Diagnostics opt-in: border/bounds/DPI/render_ms overlay, JSONL раз в секунду,
local frame capture и сообщения startup/render errors. Sampling/Qt paint/DWM
не входят в render_ms; frame_interval_ms отражает задержки event loop. Diagnostics
сама увеличивает нагрузку. Запись JSONL/PNG не считается desktop screenshot.
