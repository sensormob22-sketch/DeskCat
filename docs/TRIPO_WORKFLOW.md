# Tripo: будущий 3D-кот

В этом этапе задания Tripo не отправлялись, кредиты не расходовались.
Используется подключённый навык tripo-3d: команды выполняются через
`npx tripo-cli@latest`. Нужен Node.js LTS. Генерацию и обработку запускать только
после отдельного явного подтверждения плана с ценой каждого вызова API.

## 1. Подготовить модель

Референсы: полный рост, спокойная стойка на четырёх лапах, хвост и лапы разделены,
однотонный фон, согласованные front / left / back / right.
Цель: фотореалистичная **трёхцветная кошка calico**, максимально похожая на
исходного персонажа CatDesk: белая основа шерсти, чёрные и рыже-оранжевые пятна.
Не заменять её произвольным tabby-котом. Конкретный рисунок пятен, пропорции,
форма морды и глаз должны определяться исходными референсами CatDesk.
В репозитории исходные референсы пока отсутствуют: перед генерацией нужен
предоставленный пользователем оригинал или согласованные виды. Текстовое описание
не доказывает сходство с CatDesk и не заменяет такой референс.

Предварительный текст (без выдумывания расположения пятен):

> Photorealistic short-haired female calico cat, white fur with black and orange patches, match the original CatDesk character reference, full body, neutral standing
> quadruped pose, separated paws, anatomically correct proportions, relaxed tail,
> realistic fur PBR textures, no pedestal, no accessories.

Бесплатный план (команда не отправляет задания и не требует API-ключа):

```sh
npx tripo-cli@latest make "Photorealistic short-haired female calico cat, white fur with black and orange patches, match the original CatDesk character reference, full body, neutral standing quadruped pose, separated paws, anatomically correct proportions, relaxed tail, realistic fur PBR textures, no pedestal, no accessories" --model tripo-v3.1 -p texture_quality=detailed -p auto_size=true --dry-run --json
```

В этом плане не используем preset game-pc: он добавляет платную конверсию FBX.
Нативный результат генерации уже GLB. CLI alias tripo-v3.1 → v3.1-20260211.
Ориентир: text-to-model с текстурами 20 + detailed 10 = ~30 кредитов;
фактический план и цены необходимо заново проверить перед подтверждением.
Не добавлять `--yes` и не удалять `--dry-run` до подтверждения.

Перед первым разрешённым запуском выполнить `npx tripo-cli@latest doctor`.
Если нужна авторизация, использовать device login:
`npx tripo-cli@latest login --region ov --yes`; открыть показанный URL, ввести код
и Authorize. Не передавать ключ в чат и не коммитить его.

После подтверждения выполнить согласованный план, дождаться окончания, проверить
preview.png и геометрию. `--out ./assets` создаёт вложенный
`assets/tripo-out/<name>-<id>/`; это не конечный путь `assets/3d/cat.glb`.

## 2. Скелет и клипы — отдельный план и подтверждение

Сначала бесплатный rig-check проверяет GLB и определяет rig_type. Для кошки нужен
quadruped; не полагаться на default biped. Rig с v2.5-20260210 и GLB — ~25 кредитов.
Retarget — ~10 за клип; базовые preset:idle и preset:quadruped:walk нужно проверить
на совместимость. Два клипа и rig дают ~45 дополнительно, общий ориентир ~75.
В каждом плане перечислить API endpoint, model wire value, параметры, файлы и цену.
Не отправлять цепочку rig/retarget автоматически после генерации.

sit, stand_up, groom, sleep и drag не заявлены как готовые пресеты Tripo:
подготовить в Blender или через проверенный совместимый animation workflow.
Сохранить одну иерархию костей, bind pose, названия клипов; walk экспортировать
in-place. Не использовать humanoid Mixamo как замену quadruped rig.

## 3. Экспорт и проверка

Предпочтителен GLB glTF 2.0 с embedded текстурами, skin, joints, weights и clips.
В Blender проверить нормали, PBR base color / metallic-roughness / normal,
лапки на уровне земли, масштабы в метрах и ориентацию. Quads требуют FBX и не
хранятся в GLB; их не заказывать для конечного runtime ассета.

Перенести проверенный GLB в `assets/3d/cat.glb`; клипы/метаданные — в
`assets/animations/`. Сохранить task id, seeds, wire model version, авторство,
лицензию и фактически списанные кредиты без ключей и временных download URL.
Большие бинарные ассеты хранить в Git LFS после отдельной настройки. Проверить
импорт в реальном Panda3D-бэкенде, deformation, все клипы и переходы.
Не утверждать, что ассет совместим, до фактической проверки.

## 4. Импорт в DeskCat без полного набора клипов

Достаточно корректного skin со скелетом. Отсутствие всех семи анимаций больше не
блокирует загрузку. Модель без клипов отображается в bind pose; сообщение
`missing clips (NOT played)` перечисляет недоступные состояния. Если запрошен
отсутствующий клип, это явно сообщается и никакая другая анимация под его именем
не воспроизводится. State/desktop movement не считаются доказательством анимации.

Доступны один skin и активная scene. Имена клипов берутся из GLB. По умолчанию
карта сопоставляет только точные имена состояний; для Tripo используйте свой JSON:

```json
{"idle": "Rest", "walk": "WalkCycle", "sit": null}
```

Это пример имён, не обещание имён Tripo. Подставьте реальные имена из GLB.
Не указанные в JSON состояния используют только точное совпадение; null явно
отключает клип. Ссылка на несуществующий клип — ошибка, а не silent fallback.

```powershell
.\.venv\Scripts\python.exe -m deskcat --renderer panda --model assets/3d/cat.glb --clips assets/animations/clips.json --diagnostics diagnostics/tripo-import
```

CLI smoke/diagnostic log выводит карту и missing_states. Проверьте bind pose,
деформации, масштаб и ориентацию до подключения дополнительных клипов.
`--forward-heading` калибрует направление модели так, чтобы она смотрела вправо
экрана при движении вправо. `--playback-speed` меняет скорость локальных часов;
Space приостанавливает их и движение окна. Нормализованная синхронизация фаз
idle → walk — базовый механизм; реальное совпадение контакта лап нужно проверить
и настроить на окончательных клипах. Tripo операции в этом этапе не запускались.
