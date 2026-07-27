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
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b-instruct
OLLAMA_REQUEST_TIMEOUT_SECONDS=120
OLLAMA_KEEP_ALIVE=5m
```

Не коммитить локальный `.env`.

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
