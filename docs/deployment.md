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
git pull
git sparse-checkout set orchestrator
cd orchestrator
docker compose up -d --build
```

После обновления повторить проверки:

``` bash
docker compose ps
curl http://localhost:8000/health
docker compose exec api alembic current
```

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
git pull
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
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b-instruct
OLLAMA_REQUEST_TIMEOUT_SECONDS=120
OLLAMA_KEEP_ALIVE=5m
```

Не коммитить локальный `.env`.
Не перезаписывать рабочий `worker/api/.env` файлом `.env.example`, если в нем уже есть локальные настройки.
После изменения `.env` контейнер нужно пересоздать.

HH проверяется на Worker без VPN. С текущим VPN-маршрутом HH возвращал HTTP 451.
Worker API не использует авторизацию HH, cookies, proxy, Playwright или Selenium.

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

В логах не должны появляться полный HTML, полный description, cookies, XSRF token или содержимое `.env`.

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
