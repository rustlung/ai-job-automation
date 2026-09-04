# Architecture.md --- AI Automation Lab

## 1. Назначение проекта

Проект: автоматизированная система поиска и анализа вакансий с
использованием n8n, Python-сервисов, LLM и распределенной домашней
инфраструктуры.

Основные цели:

-   автоматизировать сбор вакансий;
-   сократить время ручного просмотра предложений;
-   использовать AI для интеллектуальной оценки соответствия вакансий
    профилю кандидата;
-   получить практический опыт работы с n8n, AI automation,
    интеграциями, локальными LLM и распределенной архитектурой;
-   создать полноценный портфолио-проект для направлений:
    -   AI Automation Engineer;
    -   AI Integration Engineer;
    -   Python Backend Developer.

------------------------------------------------------------------------

## 1.1. Current MVP Architecture

Текущий рабочий MVP pipeline:

``` text
HH
↓
Worker
├── collection
├── preliminary local AI
├── full fetch
├── normalization
├── deterministic extraction
├── semantic local AI
├── scoring
└── persistence bridge
↓
Orchestrator API
↓
Orchestrator DB
↓
n8n
├── Google Sheets CRM
└── Gmail digest
```

Control plane:

``` text
Manual Trigger
↓
Preflight
↓
Async Worker start
↓
Worker status polling
```

Public exposure:

-   public HTTPS открыт только для n8n;
-   Worker и Orchestrator остаются LAN-only;
-   Orchestrator DB является source of truth для автоматических vacancy
    pipeline данных;
-   Google Sheets является пользовательской CRM-витриной.

Web backend foundation:

``` text
React Web UI
↓ /api
Orchestrator API
├── PipelineRun and OperationalSettings persistence
├── safe Worker profile/health proxy
└── internal n8n webhook start
```

The Orchestrator is the only frontend boundary. Google Sheets remains a
reporting mirror; it is not a source of truth for user-owned application data.

Production процесс осознанно ручной: Windows Worker не работает постоянно,
поэтому пользователь включает Worker, проверяет Docker/Ollama/HH access и
запускает n8n workflow через Manual Trigger.

------------------------------------------------------------------------

# 2. Принятые архитектурные принципы

## 2.1. Разделение orchestration и execution

Архитектура разделяет:

-   слой управления процессами (orchestration);
-   слой выполнения тяжелых задач (workers).

n8n используется как orchestration engine.

Тяжелые операции не должны быть жестко привязаны к n8n и могут
выполняться отдельными сервисами.

------------------------------------------------------------------------

# 3. Текущая инфраструктура

## 3.1. Homeserver

Статус: подготовлен и работает.

ОС:

-   Ubuntu Server 24.04 LTS

Характеристики:

-   старый ноутбук;
-   используется как on-demand сервер;
-   не предполагается постоянная круглосуточная работа.

Роль:

## On-demand orchestration layer

Функции:

-   запуск n8n;
-   хранение состояния workflow;
-   хранение истории обработки;
-   работа с базой данных;
-   управление легкими сервисами.

Сервер включается только при необходимости.

------------------------------------------------------------------------

## 3.2. Текущее состояние homeserver

Пользователь:

``` text
rustlung
```

Hostname:

``` text
homeserver
```

Docker:

``` text
установлен
Docker version 29.2.1
```

Ресурсы:

RAM:

``` text
4 GB
```

Диски:

SSD:

``` text
~112 GB
```

LVM:

``` text
ubuntu-vg
```

Корневой раздел расширен:

``` text
/
~108 GB
```

Docker:

-   установлен;
-   контейнеров на момент проектирования нет, кроме создаваемых сервисов
    n8n.

------------------------------------------------------------------------

# 4. n8n

Статус:

-   установлен;
-   запущен через Docker;
-   проверена работа workflow;
-   опубликован через HTTPS на `https://n8n.vsigaev.ru` за Nginx reverse proxy.

docker-compose:

``` yaml
services:
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped

    ports:
      - "5678:5678"

    environment:
      - TZ=Europe/Samara
      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
      - N8N_SECURE_COOKIE=true
      - N8N_HOST=n8n.vsigaev.ru
      - N8N_PROTOCOL=https
      - N8N_EDITOR_BASE_URL=https://n8n.vsigaev.ru
      - WEBHOOK_URL=https://n8n.vsigaev.ru/

    volumes:
      - ./data:/home/node/.n8n
```

Публичный доступ ограничен n8n:

``` text
Internet
→ router 80/443 forwarding
→ homeserver
→ Nginx
→ 127.0.0.1:5678
→ n8n
```

Worker и Orchestrator остаются LAN-only и не публикуются в Internet.
Nginx проксирует `n8n.vsigaev.ru` на `http://127.0.0.1:5678`, передает
`Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` и поддерживает
websocket upgrade. Для домена выпущен Let's Encrypt certificate через Certbot,
HTTP перенаправляется на HTTPS, renewal проверен через `certbot renew --dry-run`.
UFW настроен с default deny incoming; для публичного n8n открыт профиль
`Nginx Full`, остальные правила, включая SSH и TeamSpeak, ведутся отдельно.

------------------------------------------------------------------------

## Подключенные интеграции

Google Gmail:

-   OAuth2 настроен;
-   OAuth2 callback переведен на public HTTPS n8n domain;
-   отправка email digest проверена.

Используется как первоначальный канал уведомлений.

Google Sheets:

-   используется существующая CRM spreadsheet `CRM_поиска_работы_и_заказов`;
-   production sync проверен на основном листе `Вакансии`;
-   acceptance sync проверялся на листе `Вакансии_TEST`;
-   n8n использует отдельный Google Service Account credential для Sheets;
-   service account имеет доступ только к CRM spreadsheet.

Gmail OAuth credential и Google Sheets Service Account credential являются
разными n8n credentials. Client secrets, OAuth tokens, service account private
keys, spreadsheet IDs и реальные URLs не хранятся в Git.

------------------------------------------------------------------------

# 5. Управление инфраструктурой

Включение и выключение серверов НЕ является частью workflow.

Это отдельный слой управления инфраструктурой.

## Принцип:

Не:

    n8n включает сервер
    ↓
    workflow запускается

А:

    Пользователь включает сервер
    ↓
    Пользователь запускает workflow

------------------------------------------------------------------------

Планируется реализовать:

## Start script

Функции:

-   отправка Wake-on-LAN пакета;
-   ожидание запуска;
-   проверка доступности SSH.

## Stop script

Функции:

-   удаленное выключение сервера через SSH.

------------------------------------------------------------------------

# 6. Worker node

## 6.1. Worker laptop

ОС:

Windows 11

Характеристики:

-   NVIDIA RTX 3060 Laptop;
-   16 GB RAM.

Роль:

## On-demand compute layer

Worker не работает постоянно.

Используется только во время выполнения тяжелых задач.

------------------------------------------------------------------------

Функции worker:

-   локальная LLM;
-   тяжелый парсинг;
-   браузерная автоматизация;
-   VPN-зависимые сервисы;
-   Telegram-интеграции;
-   тестовые окружения.

------------------------------------------------------------------------

# 7. Взаимодействие homeserver и worker

Связь:

HTTP API.

Предполагаемая архитектура:

    n8n
     |
     HTTP API
     |
    worker services
     |
    +-- parser
    +-- LLM
    +-- notifications

Перед выполнением задач n8n проверяет состояние worker.

Пример:

    GET /health

Ответ:

``` json
{
  "status": "ready",
  "services": [
    "parser",
    "llm",
    "telegram"
  ]
}
```

------------------------------------------------------------------------

# 8. Локальная LLM

Локальная модель используется на worker как local-first AI layer.

Реализованный стек:

-   Ollama;
-   модель `qwen3:4b-instruct`;
-   Worker API в Docker;
-   Ollama нативно на Windows 11 host.

Worker API обращается к Ollama через:

``` text
http://host.docker.internal:11434
```

Внутри Worker API интеграция изолирована по слоям:

-   HTTP route;
-   service layer;
-   Pydantic schemas;
-   Ollama HTTP client.

Ollama client не находится внутри route handler.
Ответ локальной модели запрашивается как structured output через JSON Schema,
разбирается как JSON и валидируется через Pydantic.

Реализованный первый end-to-end flow:

``` text
n8n
↓
Orchestrator API
↓
Worker API
↓
Ollama
↓
Orchestrator API
↓
SQLite
```

Текущий workflow является техническим smoke-срезом: он создает тестовую
вакансию, сохраняет ее в orchestrator, отправляет описание в Worker API,
получает structured local AI result от Ollama и сохраняет результат анализа
обратно в orchestrator.

Это не является готовым production pipeline: HH parser, массовая обработка,
production filtering, персональный профиль, внешняя LLM и уведомления еще не
реализованы.

Основной сценарий:

Локальная модель:

-   массовая первичная обработка;
-   классификация;
-   выделение технологий;
-   предварительный scoring.

Облачная LLM:

-   глубокий анализ лучших вакансий;
-   подготовка рекомендаций;
-   помощь с откликами.

------------------------------------------------------------------------

Архитектура:

    500 вакансий

    ↓

    Local LLM

    ↓

    50 релевантных

    ↓

    Cloud LLM

    ↓

    10 лучших

------------------------------------------------------------------------

# 9. Планируемый pipeline поиска вакансий

## Ежедневный режим

    HH collector

    ↓

    получение вакансий

    ↓

    проверка истории

    ↓

    фильтрация

    ↓

    получение полного текста вакансий

    ↓

    AI анализ

    ↓

    отчет

------------------------------------------------------------------------

## Расширенный режим

1-2 раза в неделю:

Цель:

найти вакансии, которые могут быть пропущены строгими фильтрами.

Принцип:

-   широкая выборка;
-   минимальные исключающие фильтры;
-   AI-классификация.

------------------------------------------------------------------------

# 10. Работа с HH

Официальный API для соискателей:

-   прекращен HH с 15 декабря 2025.

Использование:

-   HTML-парсинг страниц поиска;
-   получение карточек вакансий;
-   получение полного текста вакансии из карточки.

Найденные особенности:

-   страницы доступны через HTTP;
-   присутствуют стабильные data-qa атрибуты;
-   возможен парсинг без браузерной автоматизации.

## 10.1. Текущее состояние HH parsing в Worker

Реализованные компоненты Worker:

``` text
Worker
├── HH HTTP client
├── HH search parser
├── HH full vacancy parser
├── Local AI service
└── API routes
```

Текущие диагностические потоки:

``` text
POST /hh/search-preview
→ HH search HTML
→ HH search parser
→ HHSearchVacancy[]
```

``` text
POST /hh/vacancy-details
→ HH vacancy HTML
→ HH full vacancy parser
→ HHVacancyDetails
```

Worker умеет получать одну страницу поисковой выдачи HH через диагностический
`POST /hh/search-preview`, одну полную страницу вакансии HH через
`POST /hh/vacancy-details`, а также выполнять batch collection поисковой
выдачи через `POST /hh/collect-search`.

Для public search и full vacancy endpoints используется HTTP-клиент на
`httpx`. Для персональных resume-based подборок в общем collector используется
авторизованный Playwright browser context. Selenium, proxy и обход
антибот-защиты не используются.

Разделение ответственности:

-   HTTP client выполняет только сетевой запрос, проверяет status code,
    Content-Type, redirects, размер ответа и final URL;
-   parser принимает HTML string и URL, но не выполняет сетевые запросы;
-   service координирует client и parser;
-   API route принимает запрос, вызывает service и преобразует ошибки;
-   parser не выполняет AI-анализ и не сохраняет данные;
-   service не содержит parsing logic.
-   browser client отвечает за авторизацию, navigation и DOM stabilization;
-   collector оркестрирует profiles, query variants, pages и transport routing;
-   deduplication не зависит от transport;
-   persistence bridge отправляет результаты принятого enrichment pipeline в
    Orchestrator через HTTP API.

Контракт краткой карточки `HHSearchVacancy`:

-   source;
-   external_id;
-   url;
-   title;
-   company;
-   location;
-   salary_text;
-   is_remote;
-   responsibility_snippet;
-   requirement_snippet.

В краткий контракт не входят `published_at`, experience, полный
description, skills, подробные условия и AI-поля. Snippets являются
сокращенными фрагментами поисковой выдачи. Для их получения в URL поиска
нужен параметр `enable_snippets=true`.

Контракт полной карточки `HHVacancyDetails`:

-   source;
-   external_id;
-   url;
-   title;
-   company;
-   salary_text;
-   description;
-   skills;
-   schedule_text;
-   working_hours_text;
-   address;
-   published_at.

Полный description хранится как исходный нормализованный текст, пригодный
для последующего AI-анализа. HTML-теги удаляются, логические переносы
абзацев и списков сохраняются, соседние блоки страницы не включаются.
Семантическое выделение требований, обязанностей, стека и уровня
кандидата будет выполняться LLM на следующих этапах.

Canonical URL используется только если он относится к `hh.ru` или
поддомену и содержит тот же `external_id`; tracking query parameters
удаляются. Redirect на внешний домен запрещён.

## 10.2. Двухступенчатая обработка вакансий HH

Архитектурное направление для production pipeline:

``` text
Поисковая выдача HH
→ краткие карточки и snippets
→ дешёвый предварительный анализ локальной LLM
→ отсев явно нерелевантных вакансий
→ загрузка полной страницы только для перспективных вакансий
→ подробный AI-анализ полного description
→ сохранение результата
```

Цель подхода:

-   уменьшить число запросов к полным страницам;
-   снизить нагрузку на HH;
-   уменьшить объём обработки;
-   сократить расход токенов внешней LLM;
-   использовать локальную LLM для дешёвого первичного отсева;
-   не принимать окончательное решение по обрезанным snippets.

Краткой карточки достаточно для:

-   отсева явно нерелевантных профессий;
-   предварительного определения направления вакансии;
-   проверки зарплаты, если она указана;
-   проверки признака удалённости;
-   предварительного анализа обязанностей и требований;
-   решения, нужно ли загружать полную страницу.

Краткой карточки недостаточно для:

-   итогового P1/P2/P3;
-   окончательного решения об отклике;
-   проверки полного стека;
-   оценки жёсткости требований;
-   поиска требований по английскому;
-   поиска офисных ограничений;
-   проверки командировок;
-   анализа тестового задания;
-   оценки полного объёма ответственности.

Полная карточка является основным источником для подробного анализа.

Планируемый производственный поток:

``` text
n8n / collector
→ HH search page
→ search cards
→ local LLM preliminary screening
→ fetch selected full vacancy pages
→ detailed AI analysis
→ orchestrator persistence
```

На текущем этапе реализованы search collection batch кратких карточек,
preliminary local AI filter поверх deduplicated search vacancies, full vacancy
enrichment для кандидатов `keep_main`, `keep_alt` и `uncertain`, а также
persistence bridge в Orchestrator DB через `POST /pipeline-results`.
Phase 5.10 добавила n8n orchestration поверх Worker persistence endpoint,
чтение текущего run через Orchestrator API, Google Sheets CRM sync и Gmail
digest.

## 10.2.1. Preliminary local AI filter

Статус: implemented и принят на целевом Windows 11 Worker.

Текущий поток:

``` text
HH collection
↓
deduplication
↓
Preliminary local AI filter
↓
role-aware deterministic pre-filter
↓
LLM compact classification
↓
deterministic safety/positive guardrails
↓
keep_main / keep_alt / uncertain / reject
```

Endpoints:

``` text
POST /vacancies/preliminary-filter
POST /hh/collect-and-preliminary-filter
```

Preliminary filter работает только с краткими search-card данными:

-   title;
-   location;
-   salary;
-   remote flag;
-   responsibility snippet;
-   requirement snippet.

Он не загружает полную карточку, не сохраняет данные, не вызывает
Orchestrator, не использует cloud AI и не назначает окончательные `P1/P2/P3`.

Используется локальная модель:

``` text
qwen3:4b-instruct
```

Текущая prompt version:

``` text
v4
```

Цель модели — high-recall preliminary routing. Перед вызовом модели единый
role-aware policy по title (snippets являются только дополнительным контекстом)
отсекает только clear role-family mismatch без сильного technical protection.
Это уменьшает очевидные false positive, не превращая фильтр в blacklist слов.

Decision taxonomy:

-   `keep_main` — явный кандидат основного AI/Python/automation/integration
    track;
-   `keep_alt` — явный кандидат альтернативного допустимого IT-track;
-   `uncertain` — данных недостаточно или нужна проверка полной карточки;
-   `reject` — только достаточно очевидно нерелевантная вакансия.

AI не является обязательным условием для всех main-вакансий.

Независимые направления:

-   MAIN AI: AI Automation, AI Integration, applied AI, LLM, AI agents,
    prompt engineering, n8n/Dify/Flowise, AI workflows, AI product/integration
    roles;
-   MAIN Python: Python backend, FastAPI, API, integrations, SQL/PostgreSQL,
    Docker, bots, parsers, Python automation, internal services;
-   ALT: QA, API/backend testing, integration testing, data/system/business
    analysis, AI evaluation, technical implementation, engineering-heavy
    technical support.

LLM получает компактную задачу и возвращает structured output с локальным
`item_id`. Реальный `external_id` вакансии не воспроизводится моделью.
Python сохраняет соответствие:

``` text
item_id
→ исходная vacancy
→ настоящий external_id/provenance
```

После LLM применяется deterministic Python layer:

-   тот же role-aware safety invariant, который не позволяет LLM повысить
    clear role-family mismatch;
-   positive guardrails для защиты от false negative;
-   score floors для сохраненных кандидатов;
-   `uncertain` fallback при ошибках local AI.

Приоритет правил:

1.  forced reject;
2.  positive guardrail;
3.  валидный LLM result;
4.  uncertain fallback.

Forced reject до LLM и после него покрывает clear role-family mismatch:
marketing/content/visual AI, assistant/admin, commercial/community,
procurement, finance без technical core, HR, education, 1C-only, support,
system administration/operations и security tracks без реальной
AI/Python/backend implementation. QA (включая Manual QA/AQA/SDET) остается
допустимым ALT направлением. Strong Python/backend/integration/AI/LLM/ML/CV
title защищает вакансию от incidental domain words, например от упоминания 1C
или finance в integration context.
Media Buyer/media buying относится к commercial reject; Marketplace Manager
отклоняется только при отсутствии такого strong engineering title.
Positive guardrails покрывают явные Python/backend/automation, AI/LLM,
QA/API/testing карточки. Technical support как core role больше не получает
engineering-heavy promotion: он должен быть отсеян до full enrichment.
Positive guardrail не перекрывает очевидный forced reject.

Fail-open requirement:

``` text
local AI failure
↓
uncertain fallback
```

AI failure не должен приводить к `reject` и не должен терять вакансию.

Runtime batch size configurable. Для текущих ограниченных ресурсов допустимо
использовать `PRELIMINARY_FILTER_BATCH_SIZE=1`, если это повышает стабильность
`qwen3:4b-instruct`. Это не финальное performance-решение MVP; оптимизация
batch size, модели или inference откладывается до момента, когда pipeline уже
приносит практическую пользу.

Целевая acceptance-проверка на 10 реальных HH-вакансиях подтвердила:

-   `input_count = 10`;
-   `processed_count = 10`;
-   `keep_main_count = 3`;
-   `keep_alt_count = 3`;
-   `uncertain_count = 3`;
-   `reject_count = 1`;
-   `fallback_count = 0`;
-   `failed_batch_count = 0`;
-   `prompt_version = v4`.

Это acceptance run, а не постоянный benchmark.

## 10.2.2. Full vacancy enrichment and scoring

Статус: implemented и принят на целевом Windows 11 Worker.

Интегрированный endpoint:

``` text
POST /hh/collect-filter-and-enrich
```

Pipeline:

``` text
HH collector
↓
deduplication
↓
Phase 5.7 preliminary filter
↓
keep_main / keep_alt / uncertain
↓
full vacancy fetch
↓
normalization
↓
deterministic features
↓
compact local semantic assessment
↓
deterministic scoring
↓
P1 / P2 / P3 / ALT
```

`reject` из preliminary filter не отправляется на full enrichment. После full
analysis вакансии не удаляются: `P1`, `P2`, `P3` и `ALT` остаются в result.

Full vacancy fetch переиспользует существующий HH vacancy-details слой.
Отдельный второй fetcher не создавался. Ошибка загрузки или normalization одной
вакансии не останавливает весь batch и возвращается как controlled batch error.
Identity остается `source + external_id`.

Normalization переиспользует `VacancyNormalizationService`, который объединяет
search-card и full details в `NormalizedVacancy`. Логика объединения не
дублируется внутри enrichment service.

Ключевое архитектурное решение Phase 5.8: full vacancy analysis не строится как
`full vacancy → большой prompt → LLM решает всё`.

Используется гибрид:

``` text
NormalizedVacancy
↓
Python deterministic extraction
↓
compact facts
↓
Qwen semantic assessment
↓
Python final scoring
```

Python отвечает за objective facts и проверяемые правила: зарплату, географию,
офис, релокацию, опыт, seniority, технические сигналы и hard blockers. LLM
отвечает только за семантическую оценку задач и характера роли. Это снижает
нагрузку на небольшую локальную модель, нестабильность structured output,
стоимость будущего cloud analysis и непрозрачность итогового решения.

Deterministic feature extraction извлекает:

-   формат работы: remote, explicit office, office city, relocation, travel;
-   финансы: salary min/max, currency, gross/net, salary risks, missing salary;
-   опыт: required years, commercial experience, seniority;
-   язык: explicit English requirements;
-   роль: support, phone support, sales, teaching children, nontechnical role,
    seniority/management indicators;
-   technical signals: Python, backend, FastAPI, API, SQL/PostgreSQL,
    SQLAlchemy, Docker, AI/LLM, prompt engineering, automation, integrations,
    n8n, QA/testing, analytics и adjacent signals.

Географическое правило: `vacancy.location` само по себе не означает
обязательный офис. Москва, Санкт-Петербург или другой город не являются
негативным фактором, если нет явного требования посещать офис. Hard blocker
возможен только при подтвержденном обязательном офисе или обязательном гибриде
вне Самары. Офис/гибрид в Самаре допустим. Обязательная релокация является
blocker.

Salary анализируется детерминированно. Отсутствующая зарплата не является
автоматическим negative decision. Низкая зарплата выражается отдельным risk:
релевантность вакансии и финансовая пригодность оффера разделены.

Experience/responsibility правила консервативны: 1-3 года, commercial
experience и Middle не являются автоматическим blocker. Senior/Lead/Head и
реальная высокая ответственность дают risk/blocker по фактическим признакам.
`responsibility_stretch` используется только при явных признаках повышенного
уровня ответственности, а не для любой самостоятельной технической работы.

`clearly_nontechnical` вычисляется консервативно: явный nontechnical signal
плюс отсутствие сильных technical signals. AI/LLM/Python/backend/automation/
integration/QA/technical-support signals защищают техническую роль от ложного
hard blocker. Explicit nontechnical role имеет приоритет: например,
преподаватель Python детям остается нерелевантным.

Semantic layer использует локальную модель `qwen3:4b-instruct` и compact
contract:

-   `task_fit`;
-   `target_track`;
-   `responsibility_level`;
-   `role_nature`;
-   `semantic_risk`;
-   `short_reason`.

Текущая full semantic prompt version: `v1`. LLM использует локальный `item_id`,
не возвращает HH `external_id`, URL, salary decision, location decision, final
score или `P1/P2/P3`.

Semantic AI failure не приводит к потере вакансии: deterministic features
сохраняются, semantic layer получает безопасный fallback, а вакансия остается
доступной для дальнейшей обработки и ручной проверки.

Final score `0..100` рассчитывается Python-кодом. Используются группы факторов:
semantic/task fit, stack/technical fit, experience/responsibility, work
format/location, salary и дополнительные alignment-факторы. Текущая priority
logic:

-   `ALT` для ALT semantic tracks без hard blockers;
-   `P3` при hard blockers;
-   `P1` при score `>= 75`;
-   `P2` при score `>= 55`;
-   ниже — `P3`.

Worker сохраняет full enrichment results в Orchestrator через persistence
bridge endpoint `POST /hh/collect-filter-enrich-and-persist`. Stateless
endpoint `POST /hh/collect-filter-and-enrich` остается доступным для
диагностики и возвращает результат только в API response.

## 10.3. HH search collection profiles

Статус: implemented для Worker search collection.

Общий endpoint:

``` text
POST /hh/collect-search
```

Collector использует заранее настроенные профили:

-   `ai_resume_recommendations`;
-   `python_resume_recommendations`;
-   `ai_expanded_search`;
-   `python_expanded_search`;
-   `alt_opportunities`.

Пользователь не передает произвольные URL, query strings, cookies, storage
paths или resume identifiers в API. Реальные resume search URLs находятся
только в локальных environment variables:

``` text
HH_AI_RESUME_SEARCH_URL
HH_PYTHON_RESUME_SEARCH_URL
```

Эти значения не находятся в Git и не выводятся в API response или логи.

Текущая схема transport routing:

``` text
Search profiles
        |
        +--> resume_recommendations
        |        |
        |        v
        |   authenticated Playwright
        |        |
        |        v
        |   auth + resume verification
        |        |
        |        v
        |   DOM stabilization
        |
        +--> expanded_search / alt
                 |
                 v
              httpx

Both transports
        |
        v
HHSearchParser
        |
        v
provenance aggregation
        |
        v
VacancyDeduplicationService
        |
        v
HHSearchCollectionResult
```

Resume-based profiles:

-   используют Playwright, Chromium, сохраненный storage state,
    авторизованный browser context, проверку авторизации и проверку resume
    context;
-   используют `items_on_page=100`;
-   не имеют fallback на анонимный `httpx`.

Public expanded/ALT profiles:

-   используют существующий `httpx` HH client;
-   используют обычный HTML search response;
-   используют `items_on_page=20`.

`HHSearchParser` не знает о transport. Он получает HTML и извлекает краткие
карточки по стабильным `data-qa` и защищенным fallback-правилам. Transport не
входит в vacancy identity.

Public profiles используют query variants. Актуальная конфигурация вариантов
зафиксирована в `worker/api/app/services/hh_search_profiles.py`; документация
описывает логические группы, потому что конкретные query texts могут
корректироваться по статистике.

Логические группы:

-   `ai_expanded_search` — компактные варианты AI-поиска;
-   `python_expanded_search` — `python_backend` и `fastapi`;
-   `alt_opportunities` — QA, data analyst, system analyst, business analyst,
    AI trainer/evaluation.

Телефонная поддержка не является целевым направлением и исключена. Чат/email
support может рассматриваться только как крайний резерв; semantic filtering
поддержки ещё не реализован.

Configured page limits:

-   AI expanded variants — до 5 страниц;
-   Python expanded variants — до 5 страниц;
-   ALT variants — до 3 страниц.

`request.max_pages_override` может только уменьшать configured limit.
Effective max pages вычисляется как минимум из profile/variant config и
request override. Реальные лимиты могут корректироваться после накопления
статистики.

Условия остановки pagination:

-   достигнут effective max pages;
-   пустая страница;
-   повтор identity set предыдущей страницы;
-   controlled page error;
-   auth verification failure;
-   global raw vacancy limit.

`count < items_on_page` не используется как универсальный признак последней
страницы.

## 10.4. Ручная HH-авторизация

HH использует вход по номеру телефона и SMS-коду. Приложение не хранит
логин/пароль, номер телефона и SMS-код.

Вход выполняется вручную в headed Chromium непосредственно в Windows-сессии
Worker через скрипт:

``` text
worker/tools/hh_auth_setup.py
```

После входа Playwright сохраняет storage state. Storage state хранится
локально вне Git, считается секретом активной пользовательской сессии и
монтируется в контейнер read-only. API не обновляет storage state. При
истечении сессии пользователь повторно запускает ручную авторизацию.

## 10.5. Playwright runtime и DOM stabilization

Worker Docker image для Playwright зафиксирован на Debian Bookworm:

``` text
python:3.12-slim-bookworm
```

Плавающий `python:3.12-slim` приводил к Debian Trixie, где используемая
версия Playwright не могла корректно установить системные зависимости.
Chromium устанавливается во время Docker build, а не при каждом старте
контейнера.

Используется общий runtime path:

``` text
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

Это важно, потому что runtime user непривилегированный и имеет
`HOME=/nonexistent`. Browser binaries доступны runtime user, storage state не
копируется в image, а secrets mount подключается read-only.

Подтвержденная проблема DOM: сразу после navigation DOM мог содержать только
около 20 карточек, хотя окончательно загруженный browser DOM содержал до 100.
Parser искусственного лимита 20 не имел и корректно находил реальные карточки
в полном DOM; служебный заголовок "Вакансии на карте" не принимался за
вакансию.

Решение:

-   browser client не вызывает `page.content()` сразу после navigation;
-   ожидает появления vacancy links;
-   ждёт hydration;
-   считает уникальные vacancy IDs в DOM;
-   ждёт стабилизации количества с bounded timeout;
-   не требует строго 100 карточек;
-   после стабилизации передает HTML существующему `HHSearchParser`;
-   после запроса закрывает page, context, browser и Playwright runtime.

На целевой проверке resume-профили возвращали по 100 вакансий на page 0 и
page 1 для AI и Python resume profiles.

## 10.6. Worker application logging

Application logging Worker настроен централизованно.

До исправления:

-   root logger имел уровень WARNING;
-   root logger не имел stdout handler;
-   application logger не имел собственного handler;
-   INFO-события HH не отображались в `docker compose logs`;
-   были видны только стандартные Uvicorn access logs.

После исправления:

-   `LOG_LEVEL` задаётся через environment;
-   значение по умолчанию — `INFO`;
-   application events выводятся в stdout контейнера;
-   handlers не создаются в каждом модуле;
-   сообщения не дублируются;
-   Uvicorn access logs не дублируются application logging;
-   полный HTML и полный description не логируются.

На реальном запросе подтверждены события:

-   `hh_vacancy_fetch_started`;
-   `hh_vacancy_fetch_succeeded`;
-   `hh_vacancy_parse_started`;
-   `hh_vacancy_parse_succeeded`;
-   `hh_vacancy_details_completed`.

Безопасные поля для логирования:

-   sanitized URL или hostname/path без query string;
-   profile_id;
-   query_variant_id;
-   transport;
-   page;
-   final domain;
-   status code;
-   response size;
-   duration;
-   counts;
-   error codes;
-   auth/resume verification booleans;
-   DOM stabilization metrics;
-   description length;
-   skills count;
-   признаки наличия optional fields.

Не логируются resume identifiers, session query identifiers, query text,
cookies, storage state, phone, SMS, vacancy IDs, title/company/snippets и HTML.
Успешный лог каждой отдельной search-card находится на DEBUG. Parser summary
остаётся на INFO.

## 10.7. Риски HTML HH

HH может изменить:

-   data-qa атрибуты;
-   HTML-структуру;
-   meta-теги;
-   правила доступа;
-   допустимый размер страницы;
-   поведение snippets.

Parser защищён автоматическими тестами и контролируемыми ошибками, но
требует наблюдения после изменений HTML HH.

## 10.8. Normalization

Статус: implemented.

Worker реализует stateless-слой нормализации:

``` text
HHSearchVacancy
HHVacancyDetails
→ VacancyNormalizationService
→ NormalizedVacancy
```

Диагностический endpoint:

``` text
POST /vacancies/normalize
```

`NormalizedVacancy` является внутренним контрактом между parsing layer и
дальнейшей обработкой. Он содержит:

-   source;
-   external_id;
-   url;
-   title;
-   company;
-   location;
-   salary_text;
-   description;
-   skills;
-   schedule_text;
-   working_hours_text;
-   address;
-   published_at;
-   collected_at;
-   search_is_remote;
-   responsibility_snippet;
-   requirement_snippet.

Правила:

-   URL, title, company, salary_text, description, skills, schedule,
    working hours, address и published_at берутся из полной карточки, если
    применимо;
-   location и search_is_remote сохраняют сведения поисковой выдачи;
-   snippets не добавляются в description;
-   skills нормализуются и дедуплицируются без учета регистра;
-   collected_at является timezone-aware и приводится к UTC;
-   source, external_id, title и company проверяются на согласованность.

При конфликте валидных search/details объектов Worker возвращает HTTP 409.
Нормализация не выполняет сетевые запросы, не обращается к Orchestrator, не
использует AI и не сохраняет данные.

## 10.9. Deduplication

Статус: implemented для точной batch-дедупликации на Worker.

Worker реализует раннюю stateless-дедупликацию внутри одного batch:

``` text
HHSearchVacancy[] / NormalizedVacancy[]
→ exact identity key: source + external_id
→ unique ordered batch
```

Диагностические endpoints:

``` text
POST /vacancies/deduplicate/search
POST /vacancies/deduplicate/normalized
```

Назначение Worker-дедупликации:

-   сократить повторную обработку внутри одного запуска;
-   не загружать полную страницу одной и той же вакансии несколько раз;
-   сохранить порядок первого появления;
-   объединить безопасные optional-поля;
-   вернуть controlled conflict при несовместимых обязательных данных.

Разные поддомены HH считаются одной вакансией, если совпадают `source` и
`external_id`.

Search batch объединяет salary, remote flag и snippets. Normalized batch
дополнительно проверяет description после безопасной whitespace-нормализации,
объединяет skills без учета регистра, выбирает минимальный collected_at и
объединяет search_is_remote через OR.

В `POST /hh/collect-search` общий batch объединяет результаты разных страниц,
resume profiles, expanded variants, tracks и transports. Для уникальной
вакансии сохраняется provenance:

-   `profile_ids`;
-   `query_variant_ids`;
-   `tracks`;
-   `first_profile_id`;
-   `first_query_variant_id`;
-   `occurrence_count`.

Не реализованы fuzzy matching, Levenshtein, embeddings и cross-source
deduplication. Отдельно от exact dedup реализован conservative business
presentation grouping: разные HH `external_id` не удаляются и не меняют
canonical identity, но одинаковые normalized company/title/full description
получают persistent business fingerprint для CRM/Web UI view.

------------------------------------------------------------------------

# 11. Хранение вакансий и обработки

Статус: implemented для базовых сущностей Orchestrator.

Цели:

-   исключить повторную обработку;
-   хранить постоянное состояние вакансий;
-   отслеживать новые и повторно найденные вакансии;
-   хранить результаты AI-анализа;
-   хранить append-only историю этапов обработки.

## 11.1. Vacancy persistence

Worker передает результаты полного pipeline в Orchestrator через batch
persistence endpoint:

``` text
POST /pipeline-results
```

Внутри batch persistence Orchestrator выполняет `Vacancy` upsert, создает
`VacancyAnalysis` revision, сохраняет provenance, snapshots анализа,
processing events и `run_id`. Диагностический `POST /vacancies` также остается
доступен как идемпотентный upsert. Финальная защита постоянного хранилища:

``` text
UNIQUE(source, external_id)
```

Worker-дедупликация не заменяет constraint в БД. Orchestrator-upsert не
заменяет раннюю batch-дедупликацию Worker.

Текущие поля `Vacancy` включают:

-   source;
-   external_id;
-   url;
-   title;
-   company;
-   location;
-   salary_text;
-   description;
-   published_at;
-   first_seen_at;
-   last_seen_at;
-   seen_count;
-   collected_at;
-   created_at;
-   updated_at.

Один и тот же `external_id` с изменившимся description пока не ведет историю
версий description. Это отдельная будущая задача.

## 11.2. Discovery state

Статус: implemented.

`POST /vacancies` принимает необязательный `seen_at`.

При первом успешном upsert:

-   `first_seen_at = effective_seen_at`;
-   `last_seen_at = effective_seen_at`;
-   `seen_count = 1`.

При повторном успешном upsert для той же пары `source + external_id`:

-   `first_seen_at` не изменяется;
-   `last_seen_at = max(existing last_seen_at, effective_seen_at)`;
-   `seen_count` увеличивается на 1;
-   остальные поля обновляются по существующим правилам upsert.

`effective_seen_at` — это переданный timezone-aware `seen_at`, приведенный к
UTC, либо текущее серверное UTC-время. Naive datetime запрещен.

Discovery counters показывают агрегированное состояние вакансии. Они не
заменяют подробную историю обработки.

Для pipeline persistence действует дополнительное distinction:

-   same-run retry для той же `vacancy + run_id` не увеличивает `seen_count`,
    не меняет `first_seen_at` и не создает ложное повторное обнаружение;
-   новый collection/pipeline run для существующей вакансии обновляет
    `last_seen_at`, увеличивает `seen_count` и сохраняет `first_seen_at`.

Persistence retry не считается новым обнаружением vacancy.

## 11.3. Processing history

Статус: implemented.

Orchestrator хранит append-only журнал:

``` text
vacancy_processing_events
```

Событие связано с вакансией:

``` text
vacancy_processing_events.vacancy_id
→ vacancies.id
→ ON DELETE CASCADE
```

API:

``` text
POST /vacancies/{vacancy_id}/processing-events
GET /vacancies/{vacancy_id}/processing-events
GET /processing-events/{event_id}
GET /processing-runs/{run_id}/events
```

Поддерживаемые stage:

-   discovered;
-   details_fetched;
-   normalized;
-   deduplicated;
-   preliminary_analyzed;
-   fully_analyzed;
-   saved;
-   notified.

Поддерживаемые status:

-   started;
-   succeeded;
-   failed;
-   skipped.

Правила:

-   история append-only: update/delete endpoints отсутствуют;
-   повторный идентичный POST создает новое событие;
-   failed требует error_code;
-   не-failed запрещает error_code;
-   succeeded для AI-этапов требует provider, model и prompt_version;
-   metadata должны быть JSON object и ограничены 16 KiB UTF-8;
-   полный HTML, полный description и полные AI responses в metadata не
    хранятся.

Полный AI-результат хранится в `VacancyAnalysis`, а не в event metadata.
Processing events могут создаваться явными API-вызовами, а для
`POST /pipeline-results` создаются автоматически внутри успешной persistence
transaction конкретного item.

## 11.4. Текущее разделение Worker и Orchestrator

Worker отвечает за:

-   HTTP-запросы к HH;
-   parsing search page;
-   parsing full vacancy page;
-   normalization;
-   batch deduplication;
-   local AI;
-   вычислительные и сетевые операции.

Worker преимущественно stateless и не владеет постоянной БД вакансий.

Orchestrator отвечает за:

-   постоянную SQLite БД;
-   Vacancy;
-   VacancyAnalysis;
-   VacancyProcessingEvent;
-   idempotent upsert;
-   final unique constraint;
-   first_seen_at;
-   last_seen_at;
-   seen_count;
-   API постоянного хранилища.

Реализованный persistence flow:

``` text
HH
↓
Worker
collect/filter/enrich/score
↓
Persistence Bridge
↓
Orchestrator API
↓
Orchestrator DB
├── Vacancy
├── VacancyAnalysis history
└── Processing events
```

Worker остается stateless processing node. Orchestrator DB является source of
truth для автоматических данных vacancy pipeline. n8n и будущая CRM-витрина
должны читать данные через HTTP API, а не напрямую из SQLite.

Read API для следующих фаз:

``` text
GET /pipeline-results/runs/{run_id}
GET /pipeline-results/runs/{run_id}/grouped
GET /pipeline-results/analyses/latest?priority=P1&limit=100&offset=0
GET /vacancies/{vacancy_id}/analyses
GET /processing-runs/{run_id}/events
```

`GET /pipeline-results/runs/{run_id}` возвращает canonical `run_id`, `count` и
список `analyses`. `GET /pipeline-results/runs/{run_id}/grouped` возвращает
отдельный presentation contract: groupable regional copies объединяются по
persistent fingerprint, Samara publication выбирается representative, а
canonical source records и analysis history сохраняются. Для CRM конкретного
run n8n использует grouped endpoint. `GET /pipeline-results/analyses/latest`
остается read API для диагностических и обзорных сценариев, но не заменяет
current-run sync.

## 11.5. CRM and notification flow

Статус: implemented и принят в Phase 5.10.

Принятый поток:

``` text
Manual Trigger
↓
n8n
↓
Preflight health checks
↓
Worker POST /hh/collect-filter-enrich-and-persist
↓
Orchestrator DB
↓
Orchestrator GET /pipeline-results/runs/{run_id}/grouped
↓
n8n
├── Google Sheets CRM sync
└── Gmail email digest
```

n8n запускает pipeline, создает `pipeline_run_id`, проверяет Worker response,
читает результаты текущего run из Orchestrator, синхронизирует CRM и отправляет
email digest. n8n не владеет HH parsing, AI inference, semantic scoring, final
priority calculation или canonical persistence.

Google Sheets не является вторым независимым хранилищем анализа. Orchestrator
DB хранит подробные technical/system данные, а Google Sheets является рабочей
CRM-витриной. Автоматическая синхронизация идет в направлении:

``` text
Orchestrator DB → n8n → Google Sheets
```

Интеграция Google Sheets не реализуется Python-модулем в Worker или
Orchestrator. Она выполняется через n8n. Отказ Google Sheets, Gmail или другой
external integration не должен приводить к потере результатов, потому что DB
persistence выполняется до внешней синхронизации.

CRM sync работает с существующей таблицей `CRM_поиска_работы_и_заказов`.
Основной лист: `Вакансии`; acceptance лист: `Вакансии_TEST`. Существующие
колонки A:W сохранены. System-managed колонки P:V: `Score`, `AI причина`,
`Риски`, `Hard blockers`, `CRM Key`, `Run ID`, `Анализ обновлён`; последний
диагностический столбец X `Профили поиска` получает union `profile_ids` со всех
известных members business group для оценки качества search profiles.

Canonical identity имеет формат `source + external_id`. CRM presentation key
для groupable vacancy имеет формат `business:<fingerprint>` и сохраняется при
появлении новых regional copies между runs; без fingerprint используется
canonical fallback. Новая groupable vacancy создает строку, а поздняя Samara
copy обновляет существующую business row без дубля. Legacy row без CRM Key может
быть сопоставлена только через HH URL
fallback: n8n извлекает external id из URL, обновляет найденную строку и
добавляет CRM Key. Fuzzy matching по title/company не используется.

Пользовательские поля `Отклик`, `Ответ`, `Интервью`, `Итог`, `Комментарий`
защищены от перезаписи автоматизацией. AI short reason пишется в `AI причина`,
а не в `Комментарий`. В CRM синхронизируются P1, P2 и ALT; P3 остается DB-only.

Email является первым надежным notification channel для MVP. Telegram не входит
в critical path Phase 5.10: Gmail digest принят и работает, а Telegram остается
optional/future через proxy, отдельный route, relay или небольшой bot/relay на
VPS.

Production workflow перед долгим Worker pipeline проверяет Orchestrator health,
Worker health, Ollama health, HH auth storage и live authenticated HH session.
Live HH session проверяется через authenticated preview, потому что один только
storage state не подтверждает resume context и не ловит VPN redirect на
`/vpncheeck`.

Full manual production run выполнен без acceptance overrides. Основной Worker
HTTP timeout в n8n увеличен до `7200000 ms` как safety margin после реального
run, который превысил старые `1800000 ms`. Worker сохраняет результаты в
Orchestrator до CRM/email-интеграций, поэтому сбой внешней интеграции не должен
терять pipeline result.

## 11.6. Future AI evaluation decision

Статус: planned.

Для сравнительного теста локальной модели будет использоваться CRM-набор:

-   5 вакансий P1;
-   5 вакансий P2;
-   5 вакансий P3;
-   5 вакансий ALT.

Итого: 20 вакансий.

Тест должен выполняться вслепую: модель не получает CRM priority и ручные
комментарии. Анализируются полные карточки, затем результат сравнивается с
эталоном.

ALT — самостоятельная категория. Она не относится напрямую к основному
карьерному треку и не является разновидностью P3.

Для теста планируется сохранять vacancy id, эталон CRM, модель,
prompt_version, structured response, confidence, тип расхождения, время
выполнения и необходимость ProxyAPI fallback.

Возможные будущие архитектуры:

-   только local LLM;
-   local LLM + ProxyAPI fallback;
-   local LLM только для prescreen;
-   более крупная локальная модель.

Тест качества local full-vacancy AI evaluation еще не выполнен.

------------------------------------------------------------------------

# 12. Возможное развитие: собственный orchestration engine

После завершения n8n-версии возможно создание отдельного проекта:

"From n8n workflow to custom AI orchestration engine"

Идея:

оставить worker-сервисы неизменными и заменить только orchestration
слой.

Сравнение:

n8n:

-   скорость разработки;
-   удобство визуального workflow.

Custom engine:

-   потребление ресурсов;
-   контроль;
-   гибкость;
-   работа с распределенными задачами.

------------------------------------------------------------------------

# 13. Документация проекта

Структура:

    docs/

    architecture.md
    decisions/
    api.md
    deployment.md
    benchmarks.md
    lessons-learned.md

Архитектурные решения фиксируются отдельно в ADR.

------------------------------------------------------------------------

# 14. Текущий статус

Готово:

-   Ubuntu homeserver подготовлен;
-   SSH настроен;
-   Docker установлен;
-   n8n запущен;
-   Gmail OAuth настроен;
-   первый workflow протестирован;
-   архитектура распределенной системы определена;
-   Orchestrator хранит вакансии, AI-анализы, processing events и discovery
    counters;
-   Worker реализует HH parsing, normalization, exact batch deduplication,
    local AI, HH search collection profiles, preliminary local AI filter и
    full vacancy enrichment/scoring;
-   Worker передает принятые enrichment/scoring results в Orchestrator через
    persistence bridge;
-   Orchestrator DB является source of truth для автоматических данных vacancy
    pipeline;
-   Phase 5.9 принята на целевых узлах;
-   Phase 5.10 n8n orchestration, Google Sheets CRM sync, Gmail digest и public
    HTTPS n8n приняты на целевой инфраструктуре;
-   full manual production run выполнен без acceptance overrides;
-   production workflow имеет preflight health checks и `7200000 ms` timeout для
    основного Worker request;
-   Worker поддерживает controlled partial failure semantics и per-vacancy
    error isolation.

Следующие шаги:

1.  Подготовить portfolio packaging / public project presentation.

2.  Продолжать production calibration и AI improvements как backlog, а не как
    blockers завершенного MVP.
