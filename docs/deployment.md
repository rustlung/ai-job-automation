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
20260801_0002
```

Перед миграциями SQLite обязателен timestamped backup `orchestrator/data/app.db`.
Особенно это важно для миграций processing history и vacancy seen fields.

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
```

Не коммитить локальный `.env`.
Не перезаписывать рабочий `worker/api/.env` файлом `.env.example`, если в нем уже есть локальные настройки.
После изменения `.env` контейнер нужно пересоздать.

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

## n8n Workflow Configuration

Workflow `AI Job Automation — First Slice` запускается в n8n на homeserver.
Конфигурация сервисов задается через environment variables в `docker-compose.yml` n8n.

Минимальные переменные для текущего workflow:

``` text
ORCHESTRATOR_API_URL=<orchestrator-api-url>
WORKER_API_URL=<worker-api-url>
AI_PROVIDER=local_ollama
AI_MODEL=qwen3:4b-instruct
AI_PROMPT_VERSION=v1
```

Не фиксировать реальные IP-адреса, локальные URL, токены или секреты в Git.

После изменения environment variables пересоздать контейнер n8n:

``` bash
docker compose up -d --force-recreate
```

Проверить переменные внутри контейнера:

``` bash
docker compose exec n8n printenv ORCHESTRATOR_API_URL
docker compose exec n8n printenv WORKER_API_URL
docker compose exec n8n printenv AI_PROVIDER
docker compose exec n8n printenv AI_MODEL
docker compose exec n8n printenv AI_PROMPT_VERSION
```

В workflow использовать expressions через `$env`, например:

``` text
{{ $env.ORCHESTRATOR_API_URL }}
{{ $env.WORKER_API_URL }}
{{ $env.AI_PROVIDER }}
{{ $env.AI_MODEL }}
{{ $env.AI_PROMPT_VERSION }}
```

Если текущая версия n8n блокирует доступ к environment variables в node expressions, в конфигурации n8n используется:

``` text
N8N_BLOCK_ENV_ACCESS_IN_NODE=false
```

Credentials создаются только в UI n8n.
Secret values не должны экспортироваться в workflow.
Credentials exports не коммитятся.
Workflow export хранится отдельно в Git в каталоге `workflows/n8n/`.
