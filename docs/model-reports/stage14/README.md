# DeskCat: точечная проверка поверхности — Stage 14

Пакет для добровольца или 3D-специалиста: **нужно определить принадлежность граней, не исправлять сетку и не создавать production rig**. База `74199b9`; [review](https://github.com/sensormob22-sketch/DeskCat/pull/2#issuecomment-6108736188). Шесть блокирующих групп: D04, D06, D09, D14, D17, D24. Четыре T-junction отдельно: D05, D07, D15, D18. Все ID — zero-based source triangle IDs.

[Скачать компактный ZIP](DeskCat_Topology_Review.zip?raw=true). Архив содержит инструкцию RU/EN, панель Blender, локальные маски с vertex aliases, десять парных крупных планов, таблицы возврата и ссылки с SHA-256. Большие исходники в архив не скопированы. ZIP распаковать; нужен только доступ к существующей Blender-сессии специалиста, API-ключи и платные сервисы не нужны. Устанавливать Blender на компьютер владельца DeskCat не требуется.

## Русская инструкция

1. Скачайте [исходную сцену](https://raw.githubusercontent.com/sensormob22-sketch/DeskCat/74199b9/assets/rigging/deskcat_retopo_exact_weld_proxy_01.blend) и откройте в Blender 4.3.2 или совместимой версии. SHA-256: `844c4316dd841d4f943f80da7810d32abde64290c5f29b84e7ce4bfb3242667a`. Текстуры уже упакованы в сцену. Другие ресурсы и хеши: `source_links.json`.
2. В Text Editor откройте `blender_review_selector.py` **как файл из распакованного пакета**, рядом с `review_manifest.json`, и нажмите Run Script. Скрипт имеет явно описанный код: он меняет только выделение и видимость объектов во viewport; не сохраняет сцену и не редактирует геометрию, UV, материалы, кости или веса.
3. В 3D View нажмите N → DeskCat. Выберите Cluster и Surface: `EXACT_WELD_PROXY_NO_WEIGHTS` — временная сетка; `RETOPO_RIGIFY_TRIAL_ORIGINAL_SURFACE` — неизменённая кошка с UV. Выберите Core либо Core + one-ring. Нажмите Select exact source faces; оранжевое выделение покажет нужные грани. Панель проверяет порядок граней перед выбором и отказывается работать с другой топологией. Fan = -1 выбирает всю группу; 0..N — отдельный веер (порядок: `fan_groups`, затем `fan_source_face_groups` в JSON).
4. Осмотрите каждую грань/веер снаружи и изнутри, сбоку, спереди/сзади и снизу. При необходимости включите X-Ray (Alt+Z), Face Orientation или Wireframe. Core + one-ring помогает увидеть крепление, **не является маской удаления**. У D04/D09/D24 нет раздельного веера: оценивайте грани/ребра. D06 содержит ветвящиеся ребра без split fan; D14/D17 имеют явно перечисленные веера.
5. Заполните `face_decisions.csv` для всех предложенных граней и `fan_decisions.csv` для каждого веера. Каждая строка: **BODY** — несущая поверхность тела; **COSMETIC** — декоративная шерсть/лист, который должен сохраняться на render-модели; **KEEP SEPARATE** — самостоятельная поверхность, не соединять с телом при подготовке solver; **UNCERTAIN** — данных недостаточно. Добавьте причину, особенно для неоднозначного крепления. Указание COSMETIC не разрешает удалять внешний вид. Контекстные грани можно добавить отдельными строками с их точными ID и пометкой context.
6. T-junction D05/D07/D15/D18: оцените принадлежность основной поверхности и допустимость **будущего** разделения длинного ребра на solver-копии. Крышку не делать: площадь равна нулю. Исходные грани для предполагаемого разделения — 3003 / 6329 / 14146 / 14078. Ничего не применяйте сейчас.
7. Верните таблицы + короткие комментарии/скриншоты **либо** отдельную сцену `deskcat_topology_review_<name>.blend` через Save As, с размеченными гранями и легендой BODY/COSMETIC/KEEP SEPARATE/UNCERTAIN. Одна текущая selection сама по себе не хранит решения всех кластеров: приложите таблицу или явно именованные annotation masks. Не перезаписывайте исходную сцену. В ответе укажите версию Blender, просмотренные группы, неуверенные строки и предлагаемые операции без их применения.

Не менять вершины/грани/UV/текстуры/материалы/веса/кости, не делать remesh, merge by distance, cap, Bone Heat, Automatic Weights, экспорт GLB или анимации. Четыре отдельные полоски усов C1–C4 сохраняются; они не являются отверстиями. Существующие 46 DEF-костей Rigify сохраняются, проверка принадлежности поверхности не означает пригодность рига к анимации. Все глаза, уши, мордочка, окрас, пропорции и декоративные листы остаются нетронутыми.

## English instructions

**Scope: surface ownership review only. No mesh repair, automatic binding or production rigging.** Download the pinned `.blend` through `source_links.json`; verify its SHA-256. Textures are packed. Open it in Blender 4.3.2 or compatible, then open the extracted `blender_review_selector.py` in Text Editor with its adjacent `review_manifest.json` and Run Script.

Open 3D View → N → DeskCat. Select cluster, original render surface or temporary proxy, Core or Core + one-ring, then Select exact source faces. Orange faces are selection only. The script checks face-order hashes, changes viewport visibility/selection only, and never saves the file. Fan -1 selects all; nonnegative values select individual fans in manifest order. Orbit and inspect inner/outer layers with X-Ray, Wireframe and Face Orientation as needed. Context faces are not a removal mask.

Classify every listed source face and every ambiguous fan using **BODY / COSMETIC / KEEP SEPARATE / UNCERTAIN**. BODY is anatomical skin; COSMETIC is visible decorative fur that must remain on the render mesh; KEEP SEPARATE is an independent surface that must not be joined to the solver body; UNCERTAIN requires further evidence. Give reasons, especially attachment ownership. T-junctions D05/D07/D15/D18 are collinear: review the proposed later solver-only long-edge subdivision, never add a zero-area cap. No operation is approved by this packet.

Return completed `face_decisions.csv` and `fan_decisions.csv` plus annotated screenshots/reasons, **or** a separately named Save As Blender scene with persistent labelled masks and a decision legend. A single selected region is insufficient to record all decisions. Preserve IDs and report Blender version, reviewed groups and uncertainty. Do not overwrite originals. Do not edit topology, UV, textures, weights, bones, whiskers, or use remesh, Bone Heat, Automatic Weights, exports or animation. Four detached whisker components and the existing 46 Rigify DEF bones stay intact. No paid services or API keys are needed.

## Крупные планы / closeups

Цвета из Stage 13: жёлтый — открытое ребро; красный — >2 грани; белый — раздельный веер; фиолетовый — incident triangles; серый — one-ring. Слева текстура, справа solid с другой стороны; линии просвечивают через поверхность. Это точные вырезки существующих атласов, не новые или исправленные деформации. Координаты камер: [Stage 13 image metadata](https://github.com/sensormob22-sketch/DeskCat/blob/74199b9/docs/model-reports/stage13/image_metadata.json). Вид спины D09 и уха D24 уточняется свободным вращением в Blender.

| Неоднозначные / ambiguous | Данные для решения |
|---|---|
| [D04 — таз](images/D04.png) | Почти коллинеарная трещина; не подтверждённое отверстие |
| [D06 — живот](images/D06.png) | Три остаточных ветвящихся ребра; принадлежность слоёв |
| [D09 — спина/шея](images/D09.png) | Перекрывающиеся граничные цепочки; нет единого длинного ребра |
| [D14 — живот](images/D14.png) | Два остаточных ветвящихся ребра и два split fan |
| [D17 — низ живота](images/D17.png) | Шестирёберный контур и два веера у одной вершины |
| [D24 — ухо/голова](images/D24.png) | Четыре грани одного неманифолдного ребра; защищённая форма головы |

| T-junction proposals (not applied) | Source face to subdivide later |
|---|---|
| [D05](images/D05.png) | 3003 |
| [D07](images/D07.png) | 6329; соседние нормали отличаются, не сглаживать складку |
| [D15](images/D15.png) | 14146 |
| [D18](images/D18.png) | 14078 |

Полные точные ID, one-ring, фан-группы, vertex aliases и T-junction параметры: `review_manifest.json`. Полная обратимая таблица 19 464 исходных вершин → 8 253 proxy positions доступна по pinned ссылке в `source_links.json`. При будущих fan splits потребуется явное соответствие по incident source faces; координатного совпадения недостаточно для принадлежности. Проверять реальные UV seam aliases отдельно от независимых совпадающих листов.

## Приёмка результата / acceptance

Достаточно человеческой классификации с обоснованием и точными ID; платный production rig не нужен. Все строки шести групп и их вееров должны иметь решение (UNCERTAIN допустимо и должно быть объяснено). Четыре T-junction рассмотрены отдельно. Неуверенность сохраняется честно; сама таблица не разрешает автоматическое исправление. Исходная геометрия и внешний вид должны оставаться неизменными; любые будущие операции требуют отдельного согласования.

Пакет не рассылается сообществу автоматически. Владелец может отправить эту ссылку выбранному специалисту. Проверки этого этапа: см. `verification.json` и `test-results.txt` в репозитории; headless проверка выбора не заменяет фактический просмотр панелей в GUI специалистом.

## Выполненные проверки

Linux / Blender 4.3.2 headless: **52 успешных выбора** core, one-ring и отдельных вееров на оригинальной и временной сетке; проверен face-order hash обеих сеток. Сигнатуры координат, граней, UV, слотов материалов, весов, костей и упакованных текстур до/после совпали; исходный `.blend` не сохранён и его SHA-256 неизменен. Панель зарегистрировалась; её интерактивное использование в GUI не проверялось.

Полный pytest: **126 passed in 25.78s**. После уточнения заголовков крупных планов пакет собран повторно, его 3 теста прошли за 0.05s. Fontconfig сообщил о недоступном cache, но PNG и архив созданы. Проверки подтверждают пакет/выбор/сохранность данных, не качество скиннинга или анимации. GLB Validator не запускался: GLB не создавался. Windows не проверялась.

Повторная сборка: `.venv/bin/python tools/build_stage14_review_package.py`; read-only smoke: `blender -b --factory-startup --python-exit-code 1 --python tools/blender_stage14_selection_check.py`. Новых Blender-сцен и GLB, правок сетки и попыток привязки: **0**.
