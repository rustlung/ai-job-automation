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

Статус: следующая активная фаза.

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

# Phase 3. Local LLM integration

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

# Phase 4. First workflow slice

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
