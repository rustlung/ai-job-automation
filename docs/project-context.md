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
- Orchestrator владеет постоянной БД, `Vacancy`, `VacancyAnalysis`,
  `VacancyProcessingEvent`, idempotent upsert, discovery counters и final
  `UNIQUE(source, external_id)`;
- processing history находится в Orchestrator и создается только явными API
  calls;
- automatic HH collector pipeline с записью в Orchestrator пока не реализован.

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
- Worker пока не сохраняет full enrichment results в Orchestrator.

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
- browser page size для resume profiles — 100;
- public httpx page size — 20;
- `request.max_pages_override` может только уменьшать configured limit;
- `count < items_on_page` не является универсальным признаком последней
  страницы;
- parser не должен знать о transport;
- deduplication identity остается `source + external_id`;
- transport не входит в identity вакансии.

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

Главная цель:

Создать работающую систему.

Не усложнять архитектуру раньше времени.

Предпочтение:

рабочий минимальный компонент

идеальная архитектура без реализации.
