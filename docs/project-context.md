# Project Context --- AI Job Automation

## Назначение файла

Этот файл содержит правила работы с проектом для AI-ассистентов и
разработчиков.

Он отвечает на вопрос:

"Как правильно работать с этим проектом?"

Источник архитектурных решений: - docs/architecture.md

Текущее состояние: - docs/current-state.md

План развития: - docs/project-roadmap-v1.1.md

---

## Язык проекта

Документация:

- русский язык.

Код:

- английские имена сущностей;
- английские технические термины;
- комментарии добавляются только там, где они действительно нужны.

---

# Общие принципы разработки

## 1. Архитектура важнее реализации

Перед изменением кода необходимо понимать:

- какую проблему решает изменение;
- соответствует ли оно текущей архитектуре;
- не создает ли оно лишнюю связанность.

Нельзя менять архитектуру проекта без предварительного обсуждения.

---

# 2. Работа выполняется по этапам

Разработка ведется итерациями:

    Планирование

    ↓

    Обсуждение решения

    ↓

    Подготовка задачи

    ↓

    Реализация

    ↓

    Проверка

    ↓

    Фиксация результата

Один этап может включать несколько итераций исправлений.

---

# 3. Правила работы с Codex

Codex используется как исполнитель технических задач.

Codex НЕ должен:

- самостоятельно менять архитектуру;
- добавлять новые технологии без согласования;
- считать запланированные компоненты реализованными;
- выполнять масштабные изменения без разбивки.

Перед изменениями Codex должен:

1.  Изучить текущую структуру проекта.
2.  Прочитать актуальную документацию.
3.  Понять ограничения текущего этапа.
4.  Сформировать план изменений.

---

# 4. Обсуждение решений

Все архитектурные вопросы обсуждаются отдельно.

Если возникает:

- неоднозначность;
- необходимость выбора технологии;
- изменение архитектуры;
- спорное решение;

сначала обсуждение проводится вне Codex.

После принятия решения оно фиксируется в документации.

---

# 5. Ограничение области изменений

Каждая задача должна иметь ограниченную область.

Пример:

Хорошая задача:

"Создать слой хранения вакансий через SQLAlchemy."

Плохая задача:

"Сделать всю систему хранения вакансий."

---

# 6. Git workflow

Git используется для фиксации проверенных изменений.

Правила:

- commit выполняется только после проверки;
- push выполняется только после согласования;
- автоматический commit запрещен.

Перед commit необходимо показать:

- измененные файлы;
- выполненные проверки;
- возможные риски.

---

# 7. Формат commit messages

Использовать Conventional Commits.

## feat

Новая функциональность.

Пример:

    feat(worker): add vacancy parser service

## fix

Исправление ошибки.

Пример:

    fix(storage): correct vacancy duplicate check

## docs

Изменения документации.

Пример:

    docs: update architecture description

## refactor

Изменение структуры без изменения поведения.

Пример:

    refactor(worker): split parser modules

## test

Добавление или изменение тестов.

Пример:

    test(storage): add repository tests

## chore

Служебные изменения.

Пример:

    chore: update project configuration

---

# 8. Документация

Документация является частью проекта.

После важных изменений необходимо обновлять:

- architecture.md --- если изменились архитектурные решения;
- current-state.md --- если появился рабочий компонент;
- project-roadmap-v1.1.md --- если изменился план;
- decisions/ADR --- если принято важное решение;
- lessons-learned.md --- если появился важный опыт.

---

# 9. Разделение planned и implemented

Очень важно разделять:

## Implemented

То, что реально работает и проверено.

## Planned

То, что описано в архитектуре или roadmap.

Нельзя считать запланированный компонент существующим.

---

# 10. Текущие архитектурные ограничения

Основные принципы:

- n8n используется как orchestration layer;
- worker используется как compute layer;
- тяжелая обработка выполняется на worker;
- локальная LLM используется как основной AI-инструмент для массовых
  задач;
- внешние AI API используются точечно для задач, где требуется
  дополнительное качество;
- SQLite используется на текущем этапе с возможностью миграции
  PostgreSQL;
- управление инфраструктурой не является частью workflow.

Текущее распределение ответственности:

- Worker реализует HH parsing, normalization, exact batch deduplication и
  локальный AI как преимущественно stateless compute layer;
- Worker реализует HH search collection profiles и routing transport по
  `source_type`;
- Worker реализует full enrichment/scoring и persistence bridge в Orchestrator
  через HTTP API;
- Orchestrator владеет постоянной БД, `Vacancy`, `VacancyAnalysis`,
  `VacancyProcessingEvent`, idempotent upsert, discovery counters и final
  `UNIQUE(source, external_id)`;
- Orchestrator DB является source of truth для автоматических данных vacancy
  pipeline;
- processing history находится в Orchestrator; для `POST /pipeline-results`
  события создаются автоматически в persistence transaction item;
- n8n должен работать с Orchestrator через HTTP API, а не напрямую с SQLite.

Preliminary local AI filtering decisions:

- preliminary filtering оптимизирован на recall, а не на идеальное
  ранжирование;
- false positive на этом этапе допустимы;
- false negative нежелательны и считаются более опасными;
- filter работает только с краткими search-card данными и не делает
  финальный `P1/P2/P3`;
- локальная модель `qwen3:4b-instruct` получает компактную задачу;
- текущая prompt version preliminary filter — `v4`;
- LLM не должна воспроизводить business/external identifiers вакансий;
- внутри batch используются короткие локальные `item_id`, а Python сохраняет
  соответствие `item_id → vacancy → external_id/provenance`;
- role-aware deterministic policy по title применяется до LLM для clear
  role-family reject и после LLM как safety invariant; snippets являются только
  дополнительным контекстом;
- QA (Manual QA/AQA/SDET) остается допустимым ALT track, а technical support как
  core role отсекается даже при incidental SQL/API/Python/Docker markers;
- deterministic Python rules используются для очевидных фактов, safety rules,
  positive guardrails и fail-open fallback;
- AI failure не должен приводить к reject: поврежденные items и batch должны
  уходить в `uncertain` fallback;
- `PRELIMINARY_FILTER_BATCH_SIZE=1` допустим для MVP до оптимизации, если это
  нужно для стабильной работы локальной модели;
- cloud model должна быть optional и вызываться только для малого числа лучших
  или спорных вакансий;
- до рабочего MVP не добавлять RAG, vector DB, embeddings pipeline или сложный
  AI stack без необходимости.

Preliminary track decisions:

- AI не является обязательным условием для всех main-вакансий;
- MAIN AI и MAIN Python являются независимыми направлениями;
- отсутствие AI не является негативным фактором для Python/backend,
  automation, QA, analytics и других допустимых track;
- отсутствие backend не является негативным фактором для AI automation,
  prompt engineering и LLM workflow ролей;
- ALT является допустимым альтернативным IT-track для QA, API/backend testing,
  integration testing, data/system/business analysis, AI evaluation,
  technical implementation и engineering-heavy technical support.

Full vacancy enrichment decisions:

- Phase 5.8 реализована как гибридный full analysis, а не как `full vacancy →
  большой prompt → LLM решает всё`;
- vertical pipeline: HH collection → preliminary filter → full vacancy fetch →
  normalization → deterministic feature extraction → compact semantic
  assessment → deterministic scoring → `P1/P2/P3/ALT`;
- `reject` из preliminary filter не отправляется на full enrichment;
- после full analysis результаты `P1`, `P2`, `P3` и `ALT` не удаляются и
  остаются доступными для ручной проверки;
- Python отвечает за objective facts: salary, geography, office/relocation,
  experience, seniority, technical signals, hard blockers и final priority;
- local LLM отвечает только за semantic assessment задач и характера роли;
- final score и `P1/P2/P3/ALT` назначает Python, а не LLM;
- hard blockers должны быть консервативными;
- false negative опаснее false positive, особенно для AI/LLM/Python/automation
  и adjacent IT roles;
- `vacancy.location` сам по себе не является офисным blocker;
- missing salary не является автоматическим negative decision;
- salary risk отделён от technical/task fit;
- 1-3 года, commercial experience и Middle не являются автоматическими
  blockers;
- `clearly_nontechnical` требует явного nontechnical signal и отсутствия
  сильных technical signals;
- forced nontechnical roles сохраняют приоритет: например, преподаватель
  Python детям остаётся нерелевантным;
- `responsibility_stretch` не должен назначаться почти любой технической
  вакансии и требует реальных признаков senior/lead/head/ownership/5+ years;
- `FULL_ANALYSIS_BATCH_SIZE=1` допустим для MVP, если pipeline стабилен и
  укладывается в практичное время;
- cloud AI остается optional и может использоваться позже только для лучших,
  спорных или low-confidence cases;
- tuning scoring откладывается до накопления реальных ежедневных результатов;
- Worker сохраняет принятые full enrichment results в Orchestrator через
  `POST /hh/collect-filter-enrich-and-persist`;
- stateless endpoint `POST /hh/collect-filter-and-enrich` остается доступным
  для диагностики и тестирования без записи в БД.

Persistence bridge decisions:

- Worker остается stateless processing node и не владеет основной БД;
- batch persistence выполняется через Orchestrator endpoint
  `POST /pipeline-results`;
- стабильная identity вакансии: `source + external_id`;
- repeated vacancy discovery не создает новую `Vacancy` row;
- same-run retry для той же `vacancy + pipeline_run_id` не создает новую
  `VacancyAnalysis`, не создает повторные processing events и не увеличивает
  `seen_count`;
- новый pipeline run для существующей vacancy создает новую analysis revision,
  обновляет `last_seen_at`, увеличивает `seen_count` и сохраняет
  `first_seen_at`;
- `VacancyAnalysis` хранит историю analyses by run: `run_id`, `final_score`,
  `priority`, preliminary snapshot, deterministic features snapshot, semantic
  assessment snapshot, score breakdown, hard blockers, risks, provenance,
  vacancy snapshot, provider/model/prompt metadata и timestamps;
- валидные historical analyses не должны перезаписываться новым run;
- read API для следующих фаз: `GET /pipeline-results/runs/{run_id}`,
  `GET /pipeline-results/analyses/latest`, `GET /vacancies/{vacancy_id}/analyses`
  и `GET /processing-runs/{run_id}/events`;
- raw prompt, raw response, полный HTML, full description, cookies, storage
  state, resume identifiers и secrets не должны попадать в logs, docs или Git.

CRM and external integration decisions:

- Google Sheets является пользовательской CRM-витриной, а не вторым source of
  truth;
- автоматическая синхронизация идет в направлении Orchestrator DB → n8n →
  Google Sheets;
- n8n читает результаты конкретного run через
  `GET /pipeline-results/runs/{run_id}`;
- Google Sheets integration не реализуется Python-модулем в Worker или
  Orchestrator;
- external integrations belong to orchestration layer: n8n запускает pipeline,
  проверяет Worker response, читает current run, синхронизирует CRM и отправляет
  email digest;
- n8n не выполняет HH parsing, AI inference, semantic scoring, final priority
  calculation или canonical persistence;
- отказ Google Sheets, email или другой внешней интеграции не должен приводить
  к потере vacancy: DB persistence выполняется раньше внешних интеграций;
- существующая CRM spreadsheet называется `CRM_поиска_работы_и_заказов`;
- основной лист CRM — `Вакансии`, acceptance sheet — `Вакансии_TEST`;
- CRM identity key — `source + external_id`, например `hh:135997123`;
- title, company, row number или URL alone не используются как primary identity;
- legacy rows без CRM Key сопоставляются только через HH URL fallback с
  извлечением external id; fuzzy matching по title/company не используется;
- пользовательские поля `Отклик`, `Ответ`, `Интервью`, `Итог`, `Комментарий`
  не должны затираться автоматической синхронизацией;
- AI short reason пишется в system-managed `AI причина`, а не в пользовательский
  `Комментарий`;
- последний CRM столбец X `Профили поиска` является диагностическим полем и
  получает только canonical `analysis.provenance.profile_ids` в стабильном
  provenance order; empty provenance оставляет его пустым;
- в CRM синхронизируются P1, P2 и ALT; P3 остается DB-only;
- Gmail OAuth credential и Google Sheets Service Account credential в n8n
  разделены;
- service account имеет доступ только к CRM spreadsheet;
- email является первым надежным notification channel для MVP;
- Telegram deferred и не является blocker Phase 5.10;
- public HTTPS открыт только для n8n на `https://n8n.vsigaev.ru`; Worker и
  Orchestrator остаются LAN-only;
- acceptance limits Phase 5.10 не являются production policy;
- full manual production run без acceptance overrides выполнен;
- current MVP готов к practical/manual use;
- Manual Trigger является production trigger, потому что Windows Worker не
  работает постоянно;
- перед каждым production run пользователь вручную включает или будит Worker,
  проверяет Docker, Worker services, Ollama health и выключенный VPN для HH,
  затем запускает n8n workflow через Manual Trigger;
- preflight health checks перед долгим Worker pipeline реализованы: Orchestrator,
  Worker и Ollama всегда; HH auth storage и live HH session — только при
  выбранном resume profile;
- основной n8n Worker request имеет timeout `7200000 ms` как safety margin;
- `PRELIMINARY_FILTER_MAX_ITEMS=1000` является production safety cap, а не
  целевым размером batch;
- controlled partial errors и per-vacancy isolation являются частью production
  behavior;
- Schedule Trigger не входит в текущий production process и не является
  незавершенной частью MVP;
- следующие reliability priorities: Compute/GPU preflight, затем Async Worker
  pipeline; filter calibration и near-duplicate suppression остаются follow-up
  backlog и не блокируют принятый milestone.

HH search collection decisions:

- персональные HH-подборки требуют авторизованного browser context;
- анонимный resume query может вернуть fallback и не должен приниматься как
  подтвержденный результат;
- авторизация HH выполняется только вручную через SMS в headed Chromium на
  Windows Worker;
- приложение не хранит логин/пароль, номер телефона и SMS-код;
- Playwright storage state хранится вне Git, считается секретом активной
  пользовательской сессии и монтируется в контейнер read-only;
- resume profiles используют Playwright/Chromium и `authenticated_browser`;
- public expanded/ALT profiles используют `httpx`;
- custom keyword profiles `ai_automation_keywords`, `vibecoding_keywords`,
  `python_backend_keywords` и `python_automation_keywords` также используют
  `httpx` и выбираются в n8n boolean map;
- browser page size для resume profiles — 100;
- public httpx page size — 20;
- public profiles передают HH policy `work_format=REMOTE`, допустимый experience
  и `search_period=3` (последние три дня);
- `request.max_pages_override` может только уменьшать configured limit;
- `count < items_on_page` не является универсальным признаком последней
  страницы;
- parser не должен знать о transport;
- deduplication identity остается `source + external_id`;
- transport не входит в identity вакансии.

Custom keyword profiles и n8n selector приняты на целевой инфраструктуре:
keyword-only run пропускает authenticated HH preflight, а mixed run сохраняет
strict auth/session preflight для resume profile. Exact deduplication намеренно
не объединяет разные HH external_id; business/regional near-duplicates остаются
отдельным follow-up для CRM/Web UI. Filter calibration для keyword search также
является quality follow-up, не blocker принятого pipeline.

Search direction decisions:

- support не является целевым направлением;
- телефонная поддержка исключена;
- чат/email support могут рассматриваться только как крайний резерв;
- automatic semantic filtering поддержки еще не реализован;
- автоматические отклики не реализуются.

Планируемое AI-решение проверяется отдельно:

- для сравнительного теста локальной модели используется CRM-набор 5 P1, 5 P2,
  5 P3 и 5 ALT вакансий;
- ALT является самостоятельной категорией, а не разновидностью P3;
- решение о ProxyAPI fallback принимается после сравнительного теста.

---

# 11. Приоритет проекта

Async Worker pipeline execution реализован: n8n v9 запускает Worker коротким
`POST /hh/pipeline-runs`, затем poll'ит status. Один Worker допускает один
heavy run; lifecycle state intentionally in-memory, поэтому после restart нужно
проверить Orchestrator и использовать existing-run recovery только для
persisted results.

Web backend foundation реализован в Orchestrator: persistent `PipelineRun` и
singleton `OperationalSettings` поддерживают React + TypeScript Web UI. Первый
frontend milestone реализует Dashboard, запуск поиска и историю Runs; target
LAN acceptance ещё предстоит. Web full run starts through an internal n8n webhook with an
Orchestrator-generated `run_id`; manual n8n runs retain their own run-id
generation and register the same persistent history. `existing_run_id` remains
only a late-stage replay tool.

Главная цель:

Создать работающую систему.

Не усложнять архитектуру раньше времени.

Предпочтение:

рабочий минимальный компонент

идеальная архитектура без реализации.
