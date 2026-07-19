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

# Phase 1. Application foundation

## Цель

Создать базовый runtime приложения.

## Storage layer

Решение:

SQLite.

Архитектура должна позволять миграцию PostgreSQL без переработки бизнес-логики.

Требования:

- ORM;
- repository layer;
- миграции;
- отсутствие SQLite-специфичной логики в приложении.

Схема:

```
Application
    |
Repository layer
    |
ORM
    |
SQLite
```

## Persistence

Определить:

- расположение базы;
- хранение;
- backup;
- восстановление.

---

# Phase 2. Worker foundation

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
