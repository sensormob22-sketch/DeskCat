# 3D-архитектура — этап 2

## Реализовано

`PandaRenderer` загружает настоящий GLB через panda3d-gltf 1.3.0, создаёт Actor,
нормализует bounds модели, освещает её и каждый кадр применяет веса StateMachine.
Семь клипов получают циклические fractional frame poses; frameBlend включён.
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
- Прототип поддерживает ровно один скелет и семь клипов с именами состояний.
  Для Tripo нужен import acceptance test, карта имён/внешние клипы при необходимости.
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
