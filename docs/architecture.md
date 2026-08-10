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
-   проверена работа workflow.

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
      - N8N_SECURE_COOKIE=false
      - N8N_HOST=localhost
      - N8N_PROTOCOL=http

    volumes:
      - ./data:/home/node/.n8n
```

------------------------------------------------------------------------

## Подключенные интеграции

Google Gmail:

-   OAuth2 настроен;
-   отправка тестовых писем проверена.

Используется как первоначальный канал уведомлений.

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
-   Orchestrator из Worker collector пока не вызывается.

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

На текущем этапе реализованы search collection batch кратких карточек и
preliminary local AI filter поверх deduplicated search vacancies.
Автоматическая загрузка полных карточек после предварительного фильтра,
запись полных HH данных в orchestrator и n8n HH collector workflow ещё не
реализованы.

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

Цель модели — high-recall preliminary routing. На этом этапе false positive
допустимы, а false negative считаются значительно более опасными.

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

-   negative safety rules для очевидного мусора;
-   positive guardrails для защиты от false negative;
-   score floors для сохраненных кандидатов;
-   `uncertain` fallback при ошибках local AI.

Приоритет правил:

1.  forced reject;
2.  positive guardrail;
3.  валидный LLM result;
4.  uncertain fallback.

Forced reject покрывает очевидно нерелевантные роли: преподавание
программирования детям, телефонную поддержку/call-центр, холодные продажи,
бухгалтерию, курьера, авторов студенческих работ и похожие случаи.
Positive guardrails покрывают явные Python/backend/automation, AI/LLM,
QA/API/testing и engineering-heavy technical support карточки.
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

## 10.2.2. Phase 5.8 direction

Следующий этап не должен превращаться в архитектуру:

``` text
full vacancy
↓
большой prompt
↓
LLM решает всё
```

Планируемый гибридный поток:

``` text
kept vacancies
↓
full vacancy fetch
↓
normalization
↓
deterministic extraction
↓
compact local semantic assessment
↓
scoring / routing
```

Python отвечает за объективные признаки и правила. LLM отвечает только за
семантику, которую трудно надежно определить обычным кодом. Это должно снизить
нагрузку на `qwen3:4b-instruct`, повысить explainability и сократить будущие
расходы на cloud AI.

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

Не реализовано: fuzzy matching, Levenshtein, embeddings, cross-source
deduplication и объединение разных external_id.

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

`NormalizedVacancy` в будущем будет передаваться в Orchestrator через:

``` text
Orchestrator POST /vacancies
```

Сейчас endpoint уже реализован как идемпотентный upsert. Финальная защита
постоянного хранилища:

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
используют `run_id` и не заменяют подробную историю обработки.

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
Processing events создаются только явными API-вызовами. Автоматическая запись
событий из Worker или n8n пока не реализована.

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

Планируемый архитектурный поток:

``` text
Worker
→ NormalizedVacancy
→ batch deduplication
→ Orchestrator POST /vacancies
→ Vacancy persistence
→ explicit processing event calls
→ AI analysis persistence
```

Автоматический end-to-end HH pipeline пока не реализован.

## 11.5. Future AI evaluation decision

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
    local AI, HH search collection profiles и preliminary local AI filter;
-   Phase 5.7 принята на целевом Worker.

Следующие шаги:

1.  Реализовать Phase 5.8: загрузку полных карточек для вакансий,
    прошедших preliminary filter, normalization, deterministic feature
    extraction, compact semantic assessment и scoring/routing.

2.  Передавать выбранные вакансии из Worker/n8n в Orchestrator.

3.  Собрать n8n HH collector workflow.

4.  Добавить расписание, уведомления и production scoring.
