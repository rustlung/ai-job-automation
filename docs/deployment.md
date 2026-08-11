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
ресурсов Worker допустима стабильная конфигурация:

``` text
PRELIMINARY_FILTER_BATCH_SIZE=1
```

`batch_size=1` не является постоянным финальным решением, но приемлем для
первого рабочего MVP, если полный daily pipeline укладывается в практичное
время. Приоритет на этом этапе: стабильность и recall выше скорости.
Увеличение batch size до `3`, `5` или выше требует повторной target acceptance
проверки.

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

Workflow `AI Job Automation — Daily Search CRM Digest` запускается в n8n на
homeserver. Актуальный export:

``` text
workflows/n8n/ai-job-daily-search.json
```

Export хранит topology и node settings, но не хранит credentials. Workflow
`active=false`; schedule trigger в export отключен до явного production
activation.

Принятый flow:

``` text
Manual Trigger / Schedule Trigger (disabled until workflow activation)
→ Config
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
Pipeline OK?
→ Prepare Failure Email
→ Gmail Send Failure
```

n8n responsibilities:

- запускает Worker `POST /hh/collect-filter-enrich-and-persist`;
- создает `pipeline_run_id`;
- проверяет Worker result;
- читает текущий run через Orchestrator
  `GET /pipeline-results/runs/{run_id}`;
- синхронизирует Google Sheets CRM;
- отправляет Gmail digest;
- в будущем может запускаться по расписанию.

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

Existing user-managed columns are preserved. Automation must not overwrite:

``` text
Отклик
Ответ
Интервью
Итог
Комментарий
```

CRM Key:

``` text
source + external_id
```

Example:

``` text
hh:135997123
```

CRM Key is the primary idempotent key. Do not use title, company, row number or
URL alone as primary identity. Legacy rows without CRM Key are matched only by
extracting HH external id from the HH URL; fuzzy matching by title/company is not
used.

Acceptance workflow used intentionally small limits:

``` text
max_pages_override=1
max_filter_items_override=10
max_enrich_items_override=5
```

These values are not production policy. Before enabling schedule, switch the
workflow to production config and run a full manual production run.

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
