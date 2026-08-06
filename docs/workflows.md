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

## HH collection flow

Статус: частично реализован на Worker, n8n workflow пока не собран.

Worker уже предоставляет общий endpoint:

``` text
POST /hh/collect-search
```

Endpoint выполняет selection заранее настроенных HH profiles, sequential page
collection, provenance aggregation и exact deduplication внутри response.
Он не сохраняет результат в Orchestrator и не создает processing events.

Transport routing:

-   `ai_resume_recommendations` и `python_resume_recommendations` используют
    authenticated Playwright browser context, storage state, auth/resume
    verification и DOM stabilization;
-   `ai_expanded_search`, `python_expanded_search` и `alt_opportunities`
    используют `httpx`;
-   оба transport передают HTML в один `HHSearchParser`.

Public profiles используют query variants. Актуальная конфигурация находится
в `worker/api/app/services/hh_search_profiles.py`.

Pagination:

-   resume profiles используют `items_on_page=100`;
-   public/httpx profiles используют `items_on_page=20`;
-   страницы запрашиваются последовательно;
-   `request.max_pages_override` может только уменьшать configured limit;
-   `count < items_on_page` не используется как универсальный stop condition.

Partial success:

-   если часть страниц или profiles завершилась controlled failure, но есть
    успешные страницы, collection result получает `completed_with_errors`;
-   expected profile/page errors возвращаются внутри response;
-   deduplication identity conflict остается HTTP 409;
-   invalid request или unknown profile остаются HTTP 422.

Ручное обновление auth state:

-   выполняется через `worker/tools/hh_auth_setup.py` в GUI Windows-сессии;
-   storage state хранится вне Git и монтируется read-only;
-   при истечении сессии пользователь повторяет ручную авторизацию.

Ниже описан будущий n8n flow поверх уже реализованного Worker collector.

Планируемый поток:

``` text
Schedule / Manual Trigger
→ Worker /hh/collect-search
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

-   `POST /hh/collect-search` получает batch кратких карточек из нескольких
    profiles/pages/variants/transports, сохраняет provenance и убирает точные
    дубли search cards внутри response;
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
-   нет автоматического предварительного AI-фильтра;
-   нет автоматической загрузки полных карточек;
-   Worker пока не вызывает Orchestrator автоматически;
-   n8n и Worker пока не пишут processing events автоматически;
-   нет production P1/P2/P3 scoring;
-   нет ProxyAPI fallback;
-   нет автоматической отправки откликов.
