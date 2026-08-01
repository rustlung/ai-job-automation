# Workflows

## AI Job Automation — First Slice

### Назначение

Технический end-to-end smoke workflow для проверки распределенной архитектуры.

Workflow проверяет связку:

``` text
n8n
→ orchestrator
→ worker
→ Ollama
→ orchestrator
→ SQLite
```

### Текущий поток

``` text
Manual Trigger
→ Test Vacancy
→ Save Vacancy
→ Analyze Vacancy
→ Save Analysis
→ Workflow Result
```

### Environment variables

Workflow использует environment variables n8n:

``` text
ORCHESTRATOR_API_URL
WORKER_API_URL
AI_PROVIDER
AI_MODEL
AI_PROMPT_VERSION
```

Значения задаются в deployment-конфигурации n8n и не хранятся в экспортированном workflow.

### Поведение

- тестовая vacancy задается вручную в node `Test Vacancy`;
- `Save Vacancy` выполняет idempotent vacancy upsert в orchestrator;
- `Analyze Vacancy` отправляет description в Worker API;
- Worker API выполняет local AI structured analysis через Ollama;
- `Save Analysis` выполняет idempotent analysis upsert в orchestrator;
- повторные прогоны workflow не создают дубликаты вакансии или анализа.

### Ограничения

- тестовая вакансия задается вручную;
- n8n workflow еще не подключен к HH parser;
- нет batch processing;
- нет расписания;
- нет уведомлений;
- нет внешней LLM;
- нет production scoring profile.

### Экспорт

Актуальный экспорт workflow:

``` text
workflows/n8n/vacancy-first-slice.json
```

Промежуточные версии workflow в Git не хранятся.

## Планируемый HH collection flow

Статус: planned, not yet implemented.

Этот workflow пока не собран в n8n. Он описывает направление развития после
проверки HH parser, normalization, batch deduplication, processing history и
discovery counters.

Планируемый поток:

``` text
Schedule / Manual Trigger
→ build HH search profiles
→ Worker /hh/search-preview
→ exact search deduplication
→ local preliminary analysis
→ Worker /hh/vacancy-details
→ normalization
→ normalized deduplication
→ Orchestrator POST /vacancies with seen_at
→ explicit processing events
→ detailed analysis
→ VacancyAnalysis persistence
→ notification
```

Планируемая роль двухступенчатой обработки:

-   `POST /hh/search-preview` получает одну страницу поисковой выдачи HH и
    возвращает краткие карточки;
-   `POST /vacancies/deduplicate/search` убирает точные дубли search cards
    внутри batch;
-   локальная LLM выполняет дешевый предварительный отсев;
-   `POST /hh/vacancy-details` вызывается только для перспективных
    вакансий;
-   `POST /vacancies/normalize` объединяет краткую и полную карточку в
    `NormalizedVacancy`;
-   `POST /vacancies/deduplicate/normalized` убирает точные дубли
    нормализованных вакансий внутри batch;
-   полное description используется для подробного анализа;
-   orchestrator сохраняет выбранные вакансии через `POST /vacancies` с
    `seen_at`;
-   этапы обработки фиксируются явными calls в processing event API;
-   полный AI-результат сохраняется в `VacancyAnalysis`.

Ограничения текущего состояния:

-   нет реализованного n8n HH collector workflow;
-   нет автоматического построения поисковых URL;
-   нет пагинации;
-   нет batch processing;
-   нет автоматического предварительного AI-фильтра;
-   нет автоматической загрузки полных карточек;
-   Worker пока не вызывает Orchestrator автоматически;
-   n8n и Worker пока не пишут processing events автоматически;
-   нет production P1/P2/P3 scoring;
-   нет ProxyAPI fallback;
-   нет автоматической отправки откликов.
