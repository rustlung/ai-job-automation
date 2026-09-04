# Deployment

## Orchestrator

Проверенный способ развертывания orchestrator на homeserver использует sparse checkout только каталога `orchestrator`.

Каталог на homeserver:

``` text
~/services/ai-job-automation
```

### First Deploy

``` bash
mkdir -p ~/services
cd ~/services
git clone --filter=blob:none --sparse <repository-url> ai-job-automation
cd ai-job-automation
git sparse-checkout set orchestrator
```

Создать файл окружения для FastAPI приложения на основе примера:

``` bash
cp orchestrator/api/.env.example orchestrator/api/.env
```

Файл `.env` не должен попадать в Git. Не хранить в нем реальные секреты в репозитории.

Запустить orchestrator:

``` bash
cd orchestrator
docker compose up -d
```

### Verification

Проверить статус контейнера:

``` bash
docker compose ps
```

Проверить health endpoint:

``` bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

``` json
{"status":"ok"}
```

Проверить Alembic внутри контейнера:

``` bash
docker compose exec api alembic current
```

Команда должна успешно подключиться к SQLite базе в persistent storage.

### Update

Обновить код с сохранением sparse checkout:

``` bash
cd ~/services/ai-job-automation
git pull --ff-only
git sparse-checkout set orchestrator
cd orchestrator
cp data/app.db "data/app.db.backup-before-orchestrator-migrations-$(date +%Y%m%d-%H%M%S)"
docker compose build
docker compose run --rm api alembic heads
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic current
docker compose up -d
```

После обновления повторить проверки:

``` bash
docker compose ps
curl http://localhost:8000/health
docker compose run --rm api alembic current
```

Текущий Alembic head после реализации processing history и vacancy seen fields:

``` text
20260810_0001
```

Перед миграциями SQLite обязателен timestamped backup `orchestrator/data/app.db`.
Особенно это важно для миграций processing history, vacancy seen fields и
pipeline results persistence.

Persistence endpoint `POST /pipeline-results` предназначен для внутренней LAN
связи Worker → Orchestrator. Если service authentication еще не включена, этот
endpoint нельзя публиковать наружу.

Проверить создание processing event:

``` bash
curl -s -X POST "http://localhost:8000/vacancies/${VACANCY_ID}/processing-events" \
  -H "Content-Type: application/json" \
  -d '{"run_id":"manual-check","stage":"discovered","status":"started","metadata":{"source":"manual"}}'
```

Проверить повторный `POST /vacancies` с `seen_at`:

``` bash
curl -s -X POST "http://localhost:8000/vacancies" \
  -H "Content-Type: application/json" \
  -d '{"source":"hh","external_id":"999999991","url":"https://hh.ru/vacancy/999999991","title":"Тестовая вакансия","company":"Test Company","location":"Самара","salary_text":null,"description":"Техническая тестовая запись","published_at":null,"seen_at":"2026-08-01T12:00:00+04:00"}'
```

Повторный вызов с тем же `source` и `external_id` должен вернуть тот же `id`,
`created=false`, увеличить `seen_count` и не уменьшать `last_seen_at`.

Homeserver использует локальную timezone `Europe/Samara` для удобства
системных логов. API-даты и значения, которыми управляет приложение, хранятся
и передаются преимущественно в UTC.

Orchestrator application logging пока не настроен централизованно аналогично
Worker; не считать INFO application events обязательным критерием deployment
проверки Orchestrator.

## Worker

### Async Pipeline Recovery

Production workflow v9 starts Worker through `POST /hh/pipeline-runs` and polls
`GET /hh/pipeline-runs/{run_id}`. The Worker accepts one heavy run at a time.
Its lifecycle registry is in-memory: after a Worker restart the old run returns
`404 run_not_found`; check Orchestrator by `run_id` before using existing-run
CRM/email recovery. Worker cancellation is not implemented.

### Web Backend Foundation

The future browser calls only Orchestrator `/api/...`. Configure
`WORKER_API_URL`, `N8N_WEBHOOK_URL`, `N8N_WEBHOOK_SECRET` and, when internal
run lifecycle endpoints are protected, `ORCHESTRATOR_INTERNAL_API_TOKEN` in the
Orchestrator environment. These values remain environment-only and must never
be placed in a frontend, operational settings, or a committed workflow export.

The v9 webhook is an internal start boundary; it accepts quickly and does not
hold a connection for Worker processing. Manual n8n full runs still register a
`PipelineRun`, while `existing_run_id` remains a replay-only service path.

Worker разворачивается на целевом узле Windows 11 через Docker Desktop.
Для деплоя используется sparse checkout только каталога `worker`.

### Requirements

- Windows 11;
- Docker Desktop запущен;
- Git доступен в терминале.

### First Deploy

``` powershell
mkdir ~/services
cd ~/services
git clone --filter=blob:none --sparse <repository-url> ai-job-automation
cd ai-job-automation
git sparse-checkout set worker
```

Создать файл окружения для FastAPI приложения worker на основе примера:

``` powershell
Copy-Item worker/api/.env.example worker/api/.env
```

Файл `.env` не должен попадать в Git. Не хранить в нем реальные секреты в репозитории.

Запустить worker:

``` powershell
cd worker
docker compose up -d --build
```

### Verification

Проверить статус контейнера:

``` powershell
docker compose ps
```

Проверить worker локально на Windows 11:

``` powershell
curl http://localhost:8001/health
```

Ожидаемый ответ:

``` json
{"status":"ok","component":"worker"}
```

Проверить доступность worker с homeserver по локальному IP worker:

``` bash
curl http://<worker-local-ip>:8001/health
```

Не фиксировать реальные IP-адреса в документации или в Git.

### Update

Обновить код с сохранением sparse checkout:

``` powershell
cd ~/services/ai-job-automation
git pull --ff-only
git sparse-checkout set worker
cd worker
docker compose up -d --build
```

После обновления повторить проверки:

``` powershell
docker compose ps
curl http://localhost:8001/health
```

И с homeserver:

``` bash
curl http://<worker-local-ip>:8001/health
```

### Local LLM

Ollama устанавливается нативно на Windows 11 worker.
Docker-контейнер worker обращается к Ollama через:

``` text
http://host.docker.internal:11434
```

Загрузить модель:

``` powershell
ollama pull qwen3:4b-instruct
```

Или запустить модель:

``` powershell
ollama run qwen3:4b-instruct
```

Проверить список моделей:

``` powershell
ollama list
```

Проверить Ollama API с Windows host:

``` powershell
curl http://localhost:11434/api/tags
```

Проверить доступ к Ollama API из worker-контейнера:

``` powershell
docker compose exec api curl http://host.docker.internal:11434/api/tags
```

Worker использует настройки из `worker/api/.env`:

``` text
LOG_LEVEL=INFO
HH_BASE_URL=https://hh.ru
HH_USER_AGENT=AIJobAutomation/0.1 (contact: configured-locally)
HH_REQUEST_TIMEOUT_SECONDS=30
HH_REQUEST_DELAY_SECONDS=1
HH_MAX_RESPONSE_BYTES=1048576
HH_AI_RESUME_SEARCH_URL=
HH_PYTHON_RESUME_SEARCH_URL=
HH_COLLECTION_MAX_RAW_VACANCIES=2000
HH_AUTH_STORAGE_STATE_PATH=/run/secrets/hh/hh-storage-state.json
HH_AUTH_BROWSER_TIMEOUT_SECONDS=30
HH_AUTH_PAGE_LOAD_TIMEOUT_SECONDS=45
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b-instruct
OLLAMA_REQUEST_TIMEOUT_SECONDS=120
OLLAMA_KEEP_ALIVE=5m
PRELIMINARY_FILTER_BATCH_SIZE=10
PRELIMINARY_FILTER_MAX_ITEMS=100
FULL_ENRICHMENT_MAX_ITEMS=30
FULL_ANALYSIS_BATCH_SIZE=1
ORCHESTRATOR_API_URL=http://localhost:8000
ORCHESTRATOR_REQUEST_TIMEOUT_SECONDS=30
```

Не коммитить локальный `.env`.
Не перезаписывать рабочий `worker/api/.env` файлом `.env.example`, если в нем уже есть локальные настройки.
После изменения `.env` контейнер нужно пересоздать.

`PRELIMINARY_FILTER_BATCH_SIZE` является runtime-настройкой preliminary local
AI filter. Для текущей локальной модели `qwen3:4b-instruct` и ограниченных
ресурсов Worker текущая production MVP конфигурация:

``` text
PRELIMINARY_FILTER_MAX_ITEMS=1000
PRELIMINARY_FILTER_BATCH_SIZE=1
```

`worker/api/.env.example` содержит generic/default values и не является полным
production `.env`. `PRELIMINARY_FILTER_MAX_ITEMS=1000` является safety cap, а не
целевым размером batch. `batch_size=1` не является постоянным финальным
performance-решением, но принят для текущего production MVP ради стабильности.
Увеличение batch size до `3`, `5` или выше требует повторной target acceptance.

`FULL_ENRICHMENT_MAX_ITEMS` ограничивает число вакансий, которые integrated
endpoint `POST /hh/collect-filter-and-enrich` отправляет на full vacancy fetch,
normalization, full semantic assessment и scoring. Request
`max_enrich_items_override` может только уменьшить этот лимит.

`FULL_ANALYSIS_BATCH_SIZE` управляет batch size compact full-vacancy semantic
assessment. Для текущей локальной модели и ограниченных ресурсов допустима
консервативная конфигурация:

``` text
FULL_ANALYSIS_BATCH_SIZE=1
```

Стабильность важнее скорости. Увеличение full analysis batch size требует
отдельной target acceptance проверки.

`ORCHESTRATOR_API_URL` задает базовый URL Orchestrator API для Worker
persistence bridge. `ORCHESTRATOR_REQUEST_TIMEOUT_SECONDS` задает timeout
запроса к Orchestrator. Worker должен иметь сетевой доступ к Orchestrator
внутри trusted LAN. Реальные IP-адреса, локальные URL и секреты не фиксировать
в Git.

HH проверяется на Worker без VPN. С текущим VPN-маршрутом HH возвращал HTTP 451.
Public HH endpoints используют `httpx`. Authenticated resume profiles используют
Playwright/Chromium, сохраненный storage state и read-only secrets mount.
Selenium и proxy не используются.

После изменения кода или настроек пересобрать worker:

``` powershell
docker compose up -d --build
```

Проверить Worker API:

``` powershell
curl http://localhost:8001/health
curl http://localhost:8001/health/ollama
```

Проверить vertical persistence endpoint без фиксации реальных URL или secrets:

``` powershell
$body = @{
  profile_ids = @("python_expanded_search")
  max_pages_override = 5
  max_filter_items_override = 20
  max_enrich_items_override = 20
  pipeline_run_id = "manual-phase-5-9-check"
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Uri "http://localhost:8001/hh/collect-filter-enrich-and-persist" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

Stateless diagnostic endpoint `POST /hh/collect-filter-and-enrich` остается
доступным, но не сохраняет результаты в Orchestrator DB.

Проверить локальный AI endpoint:

``` powershell
$body = @{
  text = "Ищем Python-разработчика с опытом FastAPI, PostgreSQL, Docker и интеграций с внешними API."
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://localhost:8001/local-ai/analyze `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

PowerShell 7 предпочтителен для ручных русскоязычных API-запросов, чтобы корректно передавать UTF-8 и кириллицу.

Проверить endpoint с homeserver:

``` bash
curl http://<worker-local-ip>:8001/health/ollama
```

Для `POST /local-ai/analyze` с кириллицей с homeserver использовать клиент, который явно отправляет UTF-8.
Не фиксировать реальные IP-адреса, локальные `.env` и чувствительные данные в Git.

### Docker Worker And Playwright

Worker image использует Debian Bookworm base:

``` text
python:3.12-slim-bookworm
```

Bookworm зафиксирован намеренно: плавающий `python:3.12-slim` переходил на
Debian Trixie, где используемая версия Playwright не могла корректно
установить системные зависимости.

Chromium устанавливается во время Docker build и не устанавливается при
каждом старте контейнера:

``` dockerfile
RUN python -m playwright install --with-deps chromium
```

Browser binaries расположены в общем runtime path:

``` text
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

Это нужно, потому что контейнер запускается от непривилегированного runtime
user, а `HOME` для него может быть `/nonexistent`.

Storage state не копируется в image. Каталог `worker/secrets` монтируется в
контейнер read-only:

``` yaml
volumes:
  - ./secrets:/run/secrets/hh:ro
```

Контейнер может стартовать без storage state. В этом случае public profiles и
обычные health endpoints остаются доступны, а authenticated resume profiles
завершаются controlled failure.

### HH Manual Auth Setup

HH авторизация выполняется вручную на Windows 11 Worker в GUI-сессии.
Приложение не хранит логин/пароль, номер телефона или SMS-код.

Подготовить host venv и зависимости Worker:

``` powershell
cd ~/services/ai-job-automation/worker/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Установить Chromium для host Playwright:

``` powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

Запустить ручную авторизацию из каталога `worker`:

``` powershell
cd ~/services/ai-job-automation/worker
.\api\.venv\Scripts\python.exe .\tools\hh_auth_setup.py
```

В открывшемся headed Chromium выполнить вход по SMS. После успешного входа
скрипт сохраняет Playwright storage state в локальный файл. Содержимое файла
не выводить и не коммитить.

После генерации state обычно достаточно перезапустить контейнер, rebuild не
нужен, если volume уже настроен:

``` powershell
docker compose restart api
```

Проверить наличие state через API без раскрытия содержимого:

``` powershell
Invoke-RestMethod http://localhost:8001/health/hh-auth
```

### HH Verification

Проверить Worker API:

``` powershell
Invoke-RestMethod http://localhost:8001/health
```

Проверить поисковую выдачу HH.
Для получения snippets нужен параметр `enable_snippets=true`:

``` powershell
$searchBody = @{
  url = "https://hh.ru/search/vacancy?text=Python&enable_snippets=true"
} | ConvertTo-Json

$searchResponse = Invoke-RestMethod `
  -Uri http://localhost:8001/hh/search-preview `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $searchBody

$searchResponse | Format-List
$searchResponse.vacancies | Select-Object -First 5
```

Проверить одну полную карточку вакансии:

``` powershell
$detailsBody = @{
  url = "https://hh.ru/vacancy/123456789"
} | ConvertTo-Json

$detailsResponse = Invoke-RestMethod `
  -Uri http://localhost:8001/hh/vacancy-details `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $detailsBody

$detailsResponse | Format-List
$detailsResponse.description.Length
$detailsResponse.description -split "`n" | Select-Object -First 30
$detailsResponse.skills
$detailsResponse.published_at
```

URL в примере нужно заменить на актуальный публичный URL вакансии HH.
Не использовать resume id, cookies, персональные query parameters, токены или локальные секреты.

Проверить authenticated preview для разрешенного resume profile:

``` powershell
$authBody = @{
  profile_id = "ai_resume_recommendations"
  page = 0
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri http://localhost:8001/hh/authenticated-search-preview `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $authBody
```

Проверить общий HH collector для public Python profiles:

``` powershell
$body = @{
  profile_ids = @("python_expanded_search")
  max_pages_override = 5
} | ConvertTo-Json -Depth 5

$publicTest = Invoke-RestMethod `
  -Uri "http://localhost:8001/hh/collect-search" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body

$publicTest.page_results |
  Select-Object profile_id,query_variant_id,page,transport,raw_vacancy_count,status,stop_reason |
  Format-Table -AutoSize
```

Для public/httpx profiles ожидается `items_on_page=20` и последовательная
пагинация `page=0`, `page=1`, `page=2` без пропуска позиций 21+.

Проверить общий HH collector для resume profiles:

``` powershell
$body = @{
  profile_ids = @("ai_resume_recommendations", "python_resume_recommendations")
  max_pages_override = 1
} | ConvertTo-Json -Depth 5

$resumeTest = Invoke-RestMethod `
  -Uri "http://localhost:8001/hh/collect-search" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body $body

$resumeTest.page_results |
  Select-Object profile_id,query_variant_id,page,transport,raw_vacancy_count,authenticated,resume_context_confirmed,stabilization_status |
  Format-Table -AutoSize
```

Для resume profiles ожидается transport `authenticated_browser`,
подтвержденные `authenticated` и `resume_context_confirmed`, а также DOM
stabilization diagnostics. Resume profiles не должны fallback-иться на
anonymous `httpx`.

Проверить application logs:

``` powershell
docker compose logs -f api
```

В логах должны быть видны application events Worker:

``` text
hh_vacancy_fetch_started
hh_vacancy_fetch_succeeded
hh_vacancy_parse_started
hh_vacancy_parse_succeeded
hh_vacancy_details_completed
```

Для HH collection также ожидаются безопасные события вида:

``` text
hh_collection_started
hh_query_variant_started
hh_page_fetch_started
hh_page_collected
hh_browser_dom_stabilized
hh_collection_completed
```

В логах не должны появляться полный HTML, полный description, полный URL с
query string, query text, resume identifiers, session query identifiers,
cookies, XSRF token, storage state contents, телефон, SMS-код или содержимое
`.env`.

### Vacancy Normalization And Deduplication Verification

Проверить диагностические endpoints Worker после деплоя:

``` powershell
Invoke-RestMethod http://localhost:8001/health
docker compose logs --tail=100 api
```

Endpoints:

``` text
POST /vacancies/normalize
POST /vacancies/deduplicate/search
POST /vacancies/deduplicate/normalized
```

Эти endpoints используются для проверки normalization и exact batch
deduplication. Они не выполняют сетевые запросы к HH, не обращаются к
Orchestrator, не используют AI и не сохраняют данные в БД.

В логах Worker должны быть видны application events normalization и
deduplication, например:

``` text
vacancy_normalization_started
vacancy_normalization_succeeded
vacancy_deduplication_started
vacancy_duplicate_detected
vacancy_deduplication_succeeded
```

Не фиксировать в документации реальные IP-адреса, cookies, resume id,
локальные `.env`, XSRF token или чувствительные query parameters.

## n8n Public HTTPS

n8n опубликован через постоянный public HTTPS endpoint:

``` text
https://n8n.vsigaev.ru
```

Проверенная схема:

``` text
Internet
→ router 80/443 forwarding
→ homeserver
→ Nginx
→ 127.0.0.1:5678
→ n8n
```

Worker и Orchestrator остаются LAN-only. Их HTTP endpoints не публикуются в
Internet и используются n8n через локальную сеть.

Nginx reverse proxy:

- `n8n.vsigaev.ru` проксируется на `http://127.0.0.1:5678`;
- передаются `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`;
- включена поддержка websocket upgrade.

UFW:

- default policy для incoming traffic остается deny;
- для public n8n открыт профиль `Nginx Full`;
- SSH и TeamSpeak правила ведутся отдельно;
- firewall не считается глобально открытым.

TLS:

- Let's Encrypt certificate выпущен для `n8n.vsigaev.ru`;
- Certbot интегрирован с Nginx;
- HTTP redirects to HTTPS;
- `certbot renew --dry-run` прошел.

n8n environment:

``` text
N8N_HOST=n8n.vsigaev.ru
N8N_PROTOCOL=https
N8N_SECURE_COOKIE=true
N8N_EDITOR_BASE_URL=https://n8n.vsigaev.ru
WEBHOOK_URL=https://n8n.vsigaev.ru/
```

LAN endpoints Worker и Orchestrator задаются через отдельные environment
variables. Не фиксировать реальные IP-адреса, локальные URL, tokens, cookies,
query strings, spreadsheet IDs, OAuth secrets или service account private keys в
Git.

После изменения environment variables пересоздать контейнер n8n:

``` bash
docker compose up -d --force-recreate
```

Проверить переменные внутри контейнера:

``` bash
docker compose exec n8n printenv N8N_HOST
docker compose exec n8n printenv N8N_PROTOCOL
docker compose exec n8n printenv N8N_EDITOR_BASE_URL
docker compose exec n8n printenv WEBHOOK_URL
docker compose exec n8n printenv ORCHESTRATOR_API_URL
docker compose exec n8n printenv WORKER_API_URL
```

Google OAuth callback для n8n:

``` text
https://n8n.vsigaev.ru/rest/oauth2-credential/callback
```

Этот URL добавлен в Authorized redirect URIs. Gmail OAuth reconnect прошел,
Gmail Send работает.

Во время настройки был локальный DNS quirk: homeserver использовал router DNS
resolver, который временно возвращал NXDOMAIN для нового subdomain. Это не
заблокировало public HTTPS, Let's Encrypt или Google OAuth и не считается
постоянным ограничением.

## n8n Workflow Configuration

Workflow export `AI Job Automation — Daily Search CRM Digest v4` подготовлен
для импорта в n8n на homeserver. Актуальный export:

``` text
workflows/n8n/AI Job Automation — Daily Search CRM Digest v4.json
```

Export хранит topology и node settings, но не хранит credentials. Workflow
`active=false`. Export v3 сохраняется как historical production baseline и не
перезаписывается. Каноничный production trigger — `Manual Trigger`; Schedule
Trigger в текущем export отсутствует и не является частью production process.

Принятый flow:

``` text
Manual Trigger
→ Config
→ Use Existing Run?
→ Search Profiles — EDIT BEFORE RUN
→ Build Selected Profile IDs
→ Preflight Orchestrator
→ Preflight Worker
→ Preflight Ollama
→ Resume Profiles Selected?
→ Preflight HH Auth / Skip HH Auth Preflight (keyword-only)
→ Preflight HH Session (resume only)
→ Validate Preflight
→ Preflight OK?
→ Generate Run ID
→ HTTP Worker Pipeline
→ Check Worker Result
→ Pipeline OK?
→ Get Current Run
→ Read CRM Rows
→ Prepare CRM Rows
→ Legacy URL Match?
→ CRM Upsert by CRM Key / CRM Upsert Legacy by URL
→ Prepare Success Email
→ Gmail Send Digest
```

Failure branch:

``` text
Preflight OK?
→ Stop Preflight Failed

Pipeline OK?
→ Prepare Failure Email
→ Gmail Send Failure
```

n8n responsibilities:

- предоставляет boolean selector для `ai_resume_recommendations`,
  `python_resume_recommendations`, `ai_automation_keywords`,
  `vibecoding_keywords`, `python_backend_keywords` и
  `python_automation_keywords`;
- преобразует выбранные `true` values в Worker `profile_ids` и прекращает run с
  `No search profiles selected`, если список пуст;
- проверяет Orchestrator, Worker и Ollama короткими preflight checks; HH auth
  storage и live HH session проверяются только при выбранном resume profile;
- запускает Worker `POST /hh/collect-filter-enrich-and-persist` только после
  успешного preflight;
- создает `pipeline_run_id`;
- проверяет Worker result;
- читает текущий run через Orchestrator
  `GET /pipeline-results/runs/{run_id}/grouped` for CRM presentation;
- синхронизирует Google Sheets CRM;
- отправляет Gmail digest.

Manual Trigger является production trigger. Перед каждым поиском пользователь
вручную включает или будит Windows Worker, проверяет Docker, Worker services и
Ollama health, затем запускает workflow в n8n. Schedule Trigger не является
частью текущего production process.

Always-on preflight checks:

``` text
Orchestrator GET /health
Worker GET /health
Worker GET /health/ollama
```

Resume-only preflight checks:

``` text
Worker GET /health/hh-auth
Worker POST /hh/authenticated-search-preview
```

Каждый preflight HTTP request использует короткий timeout. Если preflight
падает, workflow останавливается до `HTTP Worker Pipeline`, не запускает долгий
pipeline и не отправляет Gmail failure digest.

Timeouts:

- Orchestrator/Worker/Ollama/HH auth storage health checks: `10000 ms`;
- live HH session preview: `45000 ms`;
- main `HTTP Worker Pipeline`: `7200000 ms`.

Live HH session timeout длиннее обычных health checks, потому что Playwright
navigation и DOM stabilization могут занимать десятки секунд. Main Worker
timeout был увеличен со старого `1800000 ms`: реальный full run превысил 30
минут, а Worker продолжил выполнение и сохранил результаты в Orchestrator после
n8n timeout. `7200000 ms` является safety margin, не SLA.

n8n не выполняет HH parsing, AI inference, semantic scoring, final priority
calculation или canonical persistence. Orchestrator DB остается source of truth.

Google credentials:

- Gmail node использует Google OAuth credential в n8n;
- Google Sheets node использует отдельный Google Service Account credential;
- service account имеет доступ только к существующей CRM spreadsheet;
- Google Sheets API включен;
- credential exports и secret values не коммитятся.

CRM:

- spreadsheet title: `CRM_поиска_работы_и_заказов`;
- production sheet: `Вакансии`;
- acceptance test sheet: `Вакансии_TEST`;
- sync direction: Orchestrator DB → n8n → Google Sheets;
- P1, P2 и ALT синхронизируются в CRM;
- P3 остается DB-only.

System-managed CRM columns P:V:

``` text
Score
AI причина
Риски
Hard blockers
CRM Key
Run ID
Анализ обновлён
```

Existing A:W columns remain unchanged. The final diagnostic column X,
`Профили поиска`, is populated from grouped `analysis.provenance.profile_ids`
for both new and updated CRM rows. It is blank when provenance is unavailable
and does not contain query variants, tracks, source type or run id.

Existing user-managed columns are preserved. Automation must not overwrite:

``` text
Отклик
Ответ
Интервью
Итог
Комментарий
```

CRM Key for a grouped presentation row:

``` text
business:<business_fingerprint>
```

Example:

``` text
hh:135997123
```

Canonical `source + external_id` remains the DB identity. A grouped CRM key is
stable across regional HH copies and later Samara representatives; vacancies
without a full-description fingerprint retain the canonical CRM key. Historical
CRM rows are not mass-cleaned. Do not use title, company, row number or URL
alone as primary identity. Legacy rows without CRM Key are matched only by
extracting HH external id from the HH URL; fuzzy matching by title/company is not
used.

Acceptance workflow used intentionally small limits:

``` text
max_pages_override=1
max_filter_items_override=10
max_enrich_items_override=5
```

These values are not production policy. Production workflow is started manually
and now passes `max_pages_override`, `max_filter_items_override` and
`max_enrich_items_override` as `null`/absent so Worker runtime config is used.
Full Manual Trigger production run has been completed.

Email digest includes:

- `run_id`;
- status and warnings;
- collection count;
- preliminary filter count;
- fully analyzed count;
- DB persistence count;
- P1/P2/ALT/P3 summary;
- CRM new/update/error counts;
- Worker duration;
- top vacancies;
- short reason;
- risks;
- vacancy links;
- CRM link if configured.
