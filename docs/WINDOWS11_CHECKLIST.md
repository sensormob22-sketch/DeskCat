# Обязательный Windows 11 gate

Статус: **не запускался**. Нет доступной Windows-машины в этой облачной сессии.
Не принимать архитектуру для целевой платформы только по Linux-тестам.

## Подготовка и запуск

Из checkout DeskCat в PowerShell, с Python 3.11+:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev,three-d]'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m deskcat --renderer panda --position 500 400
```

Не задавать QT_QPA_PLATFORM=offscreen для интерактивной проверки. Не использовать
QT_SCALE_FACTOR для имитации системного DPI. Записать Windows build, Python/Qt/
Panda versions, GPU/driver, размеры и масштаб каждого монитора.

## Реальная прозрачность и мышь

1. Разместить кота над рабочим столом с контрастными обоями и над окном с текстом.
   Фон и текст видны вокруг модели; нет чёрного/белого/непрозрачного прямоугольника.
2. Выбрать walk, затем drag: нет следов старых кадров и прямоугольников на старом месте.
   Проверить края модели на светлом и тёмном фоне.
3. Проверить отсутствие рамки/title bar, модель поверх обычных окон и после Alt-Tab.
   Exclusive fullscreen не входит в обещание topmost.
4. ЛКМ на модели — drag; отпускание восстанавливает walk. ПКМ — меню, Escape — выход.
   Колесо меняет масштаб модели, стрелки положение, R сбрасывает. Нет второго
   видимого окна Panda3D, mouse capture не остаётся после закрытия.
5. Отдельно щёлкнуть по прозрачной области: записать, проходит ли клик приложению
   под котом. Полный pixel-perfect click-through пока не реализован; это известный
   незакрытый вопрос, а не основание утверждать успешный hit testing.
6. Переключить все состояния, наблюдать деформацию лап и хвоста, плавное смешивание.
   Fixture клипы диагностические, реалистичность поведения не критерий этого этапа.

## DPI 100% и 150%

В Windows Settings → System → Display выбрать Scale 100%, перезапустить приложение,
провести проверки выше. Повторить при 150%, выполнить повторный вход, если Windows
просит. Если два монитора имеют разный DPI, перетащить между ними и проверить
масштаб, чёткость, ограничение availableGeometry и позицию курсора.

```powershell
.\.venv\Scripts\python.exe -m deskcat --renderer panda --smoke-test
```

JSON показывает DPR и физический размер. Для логического окна 240×220 ожидаются
240×220 при DPR=1 и 360×330 при DPR=1.5. Это вспомогательный контроль, не замена
визуальной проверке DWM и физических мониторов.

## Производительность и ошибки

```powershell
.\.venv\Scripts\python.exe -m deskcat --benchmark 120
.\.venv\Scripts\python.exe -m deskcat --benchmark 120 --scale 1.5
.\.venv\Scripts\python.exe -m deskcat --renderer panda --model assets/3d/missing.glb
```

Последняя команда должна завершиться exit 1 с Model not found и без зависания.
Benchmark включает анимацию/render/readback/QImage, исключает Qt paint/DWM.
Также наблюдать CPU/GPU в Task Manager, отзывчивость drag и cadence окна в течение
минуты. Timer 16 мс — целевой cadence, не доказанные 60 FPS.

Результат записать в docs/VALIDATION.md: дата, машина, что выполнено, фактические
pass/fail и screenshots рабочего стола (не только offscreen QImage).
Если прозрачность не проходит, gate = FAIL; предложенные альтернативы изложены
в ARCHITECTURE.md. До такой проверки Windows integration = NOT VERIFIED.
