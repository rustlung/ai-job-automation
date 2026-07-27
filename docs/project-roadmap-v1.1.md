# Project Roadmap v1.1 — AI Job Automation

## Общая цель проекта

Создать self-hosted AI Automation систему для автоматизации поиска и анализа вакансий.

Система должна:

- собирать вакансии;
- хранить историю;
- исключать дубликаты;
- использовать AI-анализ;
- отправлять результаты пользователю;
- разделять orchestration и execution.

## Архитектурный принцип

### Local-first AI architecture

Массовые операции выполняются локально при достаточном качестве результата.

Внешние AI API используются для задач, где требуется дополнительное качество анализа.

---

# Phase 0. Project foundation

Статус: выполняется.

## Цель

Подготовить чистую основу проекта.

## Задачи

- архитектурная документация;
- чистый GitHub repository;
- README;
- .gitignore;
- baseline commit.

---

# Phase 1. Orchestrator foundation

Статус: завершена.

## Цель

Создать базовый backend-слой оркестратора, который будет работать на стороне homeserver.

Оркестратор отвечает за:

- хранение состояния системы;
- работу с данными;
- предоставление API для n8n;
- взаимодействие с worker-компонентами;
- управление бизнес-сущностями приложения.

На этом этапе создается только технический фундамент.

Бизнес-логика вакансий, интеграции и AI-обработка реализуются на следующих этапах.

---

# Phase 1.1. Orchestrator API foundation

Статус: завершен.

## Цель

Создать базовое FastAPI-приложение для оркестрационного слоя.

## Создать:

Структуру:

orchestrator/
└── api/
├── app/
│ ├── main.py
│ ├── core/
│ ├── database/
│ ├── models/
│ ├── repositories/
│ └── schemas/
├── alembic/
├── tests/
├── requirements.txt
├── Dockerfile
└── .env.example

## Технологии:

- Python;
- FastAPI;
- SQLAlchemy;
- Alembic;
- SQLite.

## Реализовать:

- запуск FastAPI приложения;
- базовую конфигурацию через переменные окружения;
- подключение к базе данных;
- health endpoint;
- базовую структуру для дальнейшего расширения.

Пример:

GET /health
{
"status": "ok"
}

## Результат

Создан базовый FastAPI backend оркестратора.
Подготовлена структура `orchestrator/api` для дальнейшего развития API, storage layer и взаимодействия с worker-компонентами.
Health endpoint реализован и проверен тестами.

---

# Phase 1.2. Storage foundation

Статус: завершен.

## Цель

Создать надежный слой хранения данных.

## Текущее решение:

SQLite.

Архитектура должна позволять миграцию PostgreSQL без переработки бизнес-логики.

## Требования:

- использование ORM;
- repository layer;
- миграции через Alembic;
- отсутствие SQLite-специфичной логики в приложении;
- изоляция доступа к данным.

Схема:

Application layer
|
Repository layer
|
ORM
|
Database adapter
|
SQLite

## Persistence

Определить:

- расположение файла базы данных;
- способ хранения;
- backup;
- восстановление.

## Ограничения:

На этом этапе не создавать:

- модели вакансий;
- HH collector;
- worker API;
- AI-компоненты;
- n8n workflow.

---

## Результат Phase 1

Фаза завершена.

- существует backend оркестратора;
- приложение запускается локально и через Docker Compose;
- `GET /health` успешно отвечает локально и на homeserver;
- есть подключение к SQLite через SQLAlchemy;
- Alembic подключен к SQLAlchemy metadata и выполняется внутри контейнера;
- persistent storage расположен в `orchestrator/data`;
- deployment orchestrator выполняется на homeserver через sparse checkout каталога `orchestrator`;
- архитектура готова к дальнейшему расширению и миграции PostgreSQL.

# Phase 2. Worker foundation

Статус: завершена.

## Цель

Создать отдельный вычислительный слой.

Worker отвечает за:

- парсинг вакансий;
- обработку данных;
- очистку;
- дедупликацию;
- AI-анализ;
- работу локальных моделей;
- работу внешних AI API;
- уведомления;
- интеграции.

Основа:

- Windows 11;
- Docker;
- FastAPI;
- Ollama.

Первый этап:

- worker API;
- health check;
- базовая связь с n8n.

Схема:

```
n8n
 |
HTTP API
 |
worker
 |
response
```

---

# Phase 2.1. Worker API foundation

Статус: завершен.

## Цель

Создать базовый FastAPI-компонент worker для будущих вычислительных и сетевых задач.

## Результат

- создан отдельный компонент `worker`;
- реализован FastAPI API worker;
- работает endpoint `GET /health`;
- worker запускается через Docker Compose на Windows 11;
- контейнер worker успешно работает на целевом ноутбуке;
- наружу опубликован порт `8001`;
- homeserver успешно получает ответ от worker по локальной сети;
- worker не имеет прямого доступа к SQLite базе orchestrator;
- связь между homeserver/orchestrator и worker строится через HTTP API;
- для деплоя worker используется sparse checkout каталога `worker`.

---

# Phase 3. Local LLM integration

Статус: завершена.

## Цель

Подключить локальную AI-обработку.

Стек:

- Ollama;
- локальная LLM.

Сценарий:

```
vacancy text
 |
local LLM
 |
structured result
```

Проверяем:

- скорость;
- качество;
- потребление ресурсов.

---

# Phase 3.1. Ollama setup on worker

Статус: завершен.

## Результат

- Ollama установлена нативно на Windows 11 worker;
- модель `qwen3:4b-instruct` выбрана как первая рабочая локальная модель;
- Ollama API доступен на порту `11434`;
- Ollama использует NVIDIA RTX 3060 Laptop;
- контейнер Worker API обращается к Ollama через `http://host.docker.internal:11434`.

---

# Phase 3.2. Ollama integration in Worker API

Статус: завершен.

## Результат

- создан изолированный асинхронный Ollama HTTP client;
- HTTP route, service, schemas и integration client разделены;
- реализован `POST /local-ai/analyze`;
- реализован `GET /health/ollama`;
- базовый `GET /health` не зависит от доступности Ollama;
- используется structured output через JSON Schema;
- ответ модели разбирается как JSON и валидируется через Pydantic;
- Worker API возвращает валидированный structured result;
- реализована контролируемая обработка timeout, connection error и malformed response;
- тесты клиента, сервиса, схем и API не требуют реальной Ollama, GPU или интернета.

---

# Phase 4. First workflow slice

Статус: следующая активная фаза.

## Цель

Проверить полный цикл:

```
n8n
 |
worker
 |
LLM
 |
database
 |
notification
```

Используются тестовые данные.

Результат:

Первый вертикальный срез системы.

---

# Phase 5. Vacancy collector

## Цель

Получить реальные вакансии.

Компоненты:

- HH collector;
- HTML parsing;
- нормализация;
- дедупликация;
- история обработки.

Поток:

```
HH
 |
Parser
 |
Storage
 |
Processing
```

---

# Phase 6. Advanced AI pipeline

## Цель

Разделить массовый анализ и глубокую оценку.

Локальная модель:

```
500 вакансий
 |
local LLM
 |
50 релевантных
```

Внешняя модель:

```
50 вакансий
 |
API LLM
 |
10 лучших
```

---

# Phase 7. Production workflow

Полный pipeline:

```
Collect
 |
Deduplicate
 |
Store
 |
Local AI filtering
 |
Cloud AI analysis
 |
Ranking
 |
Report
 |
Notification
```

---

# Phase 8. Optimization and evolution

Направления:

- benchmark моделей;
- оптимизация;
- развитие worker;
- SQLite → PostgreSQL;
- сравнение n8n и собственного orchestrator;
- материалы для портфолио.

---

# Правила разработки

Цикл работы:

```
Планирование
 |
Обсуждение решений
 |
Промпт Codex
 |
Реализация
 |
Проверка
 |
Корректировки
 |
Фиксация результата
```

Правила Codex:

- не принимает архитектурные решения самостоятельно;
- работает в рамках согласованной задачи;
- один промпт соответствует одной логически ограниченной задаче;
- этап может включать несколько итераций;
- перед изменениями изучает документацию;
- commit и push только после согласования.

---

# Формат commit messages

Использовать Conventional Commits:

```
feat: новая функциональность
fix: исправление ошибки
docs: документация
refactor: изменение структуры
test: тесты
chore: служебные изменения
```
