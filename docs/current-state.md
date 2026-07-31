# Current State

2026-07-31

Работает:
✅ Ubuntu server
✅ SSH
✅ Docker
✅ n8n
✅ Gmail OAuth
✅ Orchestrator FastAPI API
✅ SQLAlchemy storage foundation
✅ Alembic
✅ SQLite persistent storage
✅ Docker deployment orchestrator на homeserver
✅ Worker FastAPI API
✅ Docker deployment worker на Windows 11
✅ Сетевая доступность worker с homeserver
✅ Sparse checkout каталога worker
✅ Ollama на Windows 11 worker
✅ Локальная модель qwen3:4b-instruct
✅ Доступ Worker API к Ollama через host.docker.internal
✅ POST /local-ai/analyze
✅ Structured local AI output
✅ GET /health/ollama
✅ Обработка ошибок интеграции Ollama
✅ Реальный локальный AI-запрос с русскоязычным текстом
✅ Доступ к Local AI endpoint с homeserver
✅ Vacancy persistence API
✅ VacancyAnalysis persistence API
✅ Idempotent vacancy upsert
✅ Idempotent analysis upsert
✅ Alembic migrations на homeserver
✅ First n8n workflow slice
✅ n8n → orchestrator
✅ n8n → worker
✅ Worker → Ollama
✅ Сохранение AI-анализа в SQLite
✅ Повторные workflow-прогоны без дублей
✅ HH search page HTTP client
✅ HH search results parser
✅ Salary extraction from HH search cards
✅ Remote flag extraction from HH search cards
✅ HH responsibility and requirement snippets
✅ POST /hh/search-preview
✅ HH full vacancy HTTP client
✅ HH full vacancy parser
✅ POST /hh/vacancy-details
✅ Full description normalization
✅ HH skills extraction
✅ HH publication date extraction
✅ Worker application logs in Docker
✅ HH real-network verification on target Worker

Phase 1 — Orchestrator foundation завершена.
Phase 2.1 — Worker API foundation завершена.
Phase 3 — Local LLM integration завершена.
Phase 4 — First workflow slice завершена.
Phase 5.1 — HH search page parser завершена и принята.
Phase 5.2 — HH full vacancy parser завершена и принята.

Создан и развернут на homeserver базовый backend оркестрационного слоя на FastAPI.
Работает endpoint `GET /health`.
Подготовлены SQLAlchemy storage foundation, Alembic migrations foundation и persistent SQLite storage в `orchestrator/data`.
Orchestrator запускается через Docker Compose; для деплоя используется sparse checkout каталога `orchestrator`.

Создан отдельный FastAPI API worker.
Worker запускается через Docker Compose на Windows 11 и публикует порт `8001`.
Homeserver успешно получает ответ worker по HTTP API через локальную сеть.
Worker не имеет прямого доступа к SQLite базе orchestrator.
Для деплоя worker используется sparse checkout каталога `worker`.

Локальная LLM является рабочей частью worker.
Ollama установлена нативно на Windows 11 worker, модель `qwen3:4b-instruct` загружена и доступна для Worker API через `http://host.docker.internal:11434`.
Worker API предоставляет технический endpoint `POST /local-ai/analyze` со structured output, JSON Schema и Pydantic-валидацией.
Это еще не полноценный анализ вакансий и не production pipeline.

Первый end-to-end pipeline работает в тестовом режиме:

``` text
n8n
→ orchestrator vacancy upsert
→ worker local AI analysis
→ orchestrator analysis upsert
→ SQLite
```

Реализованы persistence API для вакансий и результатов AI-анализа.
Повторное сохранение вакансии и анализа выполняется идемпотентно: дубликаты не создаются, измененные поля обновляются с сохранением id.
Первый n8n workflow slice использует environment variables и не хранит секреты в экспортированном workflow.

HH HTML parsing является рабочей частью Worker API.
`POST /hh/search-preview` получает одну страницу поисковой выдачи HH, извлекает краткие карточки вакансий, зарплату, признак удалённости, `responsibility_snippet` и `requirement_snippet`.
Для получения snippets в URL поисковой выдачи нужен параметр `enable_snippets=true`; без него HH может вернуть карточки без кратких обязанностей и требований.

`POST /hh/vacancy-details` получает одну полную страницу вакансии HH и возвращает нормализованный `HHVacancyDetails`: title, company, salary, полный description, skills, schedule, working hours, address и published_at при наличии.
Полный HTML обрабатывается без Playwright и Selenium.
Реальные сетевые проверки HH выполняются на целевом Windows 11 Worker без VPN; с текущим VPN-маршрутом HH возвращал HTTP 451.

Worker application logging настроен централизованно через `LOG_LEVEL=INFO`.
Application events уровня INFO выводятся в stdout контейнера и видны через `docker compose logs`; полный HTML и полный description не логируются.

Следующий этап определяется по `docs/project-roadmap-v1.1.md`.

Не реализовано:
⬜ пагинация HH
⬜ несколько поисковых профилей HH
⬜ массовый сбор вакансий
⬜ предварительный AI-фильтр поисковых карточек
⬜ автоматическая загрузка полной страницы после фильтра
⬜ запись полных HH данных в orchestrator
⬜ n8n HH collector workflow
⬜ расписание HH collector
⬜ массовая обработка вакансий
⬜ production filtering
⬜ персональный профиль пользователя
⬜ внешняя LLM
⬜ Telegram workflow
⬜ полноценный ежедневный pipeline
⬜ итоговый P1/P2/P3 анализ
⬜ автоматическая отправка откликов
