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
