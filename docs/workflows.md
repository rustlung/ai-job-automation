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

## Daily Search CRM Digest

Статус: Phase 5.10 implemented и принят на целевой инфраструктуре.

Актуальный export:

``` text
workflows/n8n/ai-job-daily-search.json
```

Workflow name:

``` text
AI Job Automation — Daily Search CRM Digest
```

Export не содержит credentials. Workflow `active=false`; node
`Schedule Trigger (disabled until workflow activation)` отключен до явного
production activation.

### Назначение

n8n оркестрирует уже реализованный Worker persistence pipeline и внешние
интеграции:

``` text
Manual Trigger
→ n8n
→ Worker POST /hh/collect-filter-enrich-and-persist
→ Orchestrator DB
→ Orchestrator GET /pipeline-results/runs/{run_id}
→ Google Sheets CRM sync
→ Gmail email digest
```

n8n не выполняет HH parsing, AI inference, semantic scoring, final priority
calculation или canonical persistence.

### Topology

Success branch:

``` text
Manual Trigger / Schedule Trigger (disabled until workflow activation)
→ Config
→ Generate Run ID
→ HTTP Worker Pipeline
→ Check Worker Result
→ Pipeline OK?
→ Get Current Run
→ Read CRM Rows
→ Prepare CRM Rows
→ Legacy URL Match?
→ CRM Upsert by CRM Key / CRM Upsert Legacy by URL
→ Prepare Success Email
→ Gmail Send Digest
```

Failure branch:

``` text
Pipeline OK?
→ Prepare Failure Email
→ Gmail Send Failure
```

### Source of truth

Orchestrator DB является source of truth для автоматических vacancy pipeline
данных. Google Sheets является пользовательской CRM-витриной. Направление
синхронизации:

``` text
Orchestrator DB → n8n → Google Sheets
```

Current-run CRM sync использует:

``` text
GET /pipeline-results/runs/{run_id}
```

`GET /pipeline-results/analyses/latest` не используется для синхронизации
конкретного run.

### CRM Sync

CRM spreadsheet: `CRM_поиска_работы_и_заказов`.

Листы:

- `Вакансии_TEST` — acceptance sheet;
- `Вакансии` — production sheet после приемки.

Существующие A:O user columns сохранены. Добавлены P:V system-managed columns:

``` text
Score
AI причина
Риски
Hard blockers
CRM Key
Run ID
Анализ обновлён
```

System-managed fields:

``` text
Компания
Должность
Тип
Приоритет
ЗП
Формат
Стек
Дата
Ссылка
Score
AI причина
Риски
Hard blockers
CRM Key
Run ID
Анализ обновлён
```

User-managed fields protected from automation:

``` text
Отклик
Ответ
Интервью
Итог
Комментарий
```

AI short reason writes to `AI причина`, not to `Комментарий`.

CRM Key:

``` text
source + external_id
```

Example:

``` text
hh:135997123
```

Accepted behavior:

- no CRM Key and no legacy row → `match_strategy=new`, `crm_action=new`;
- existing row with CRM Key → `match_strategy=crm_key`, `crm_action=update`;
- old row without CRM Key → extract HH external id from URL, update legacy row,
  add CRM Key;
- no fuzzy matching by title/company;
- no duplicate row on accepted update paths.

P1, P2 and ALT are synchronized to CRM. P3 remains DB-only.

### Email Digest

Gmail digest is the first production notification channel.

Digest includes `run_id`, status/warnings, collection count, preliminary filter
count, fully analyzed count, DB persistence count, P1/P2/ALT/P3 summary, CRM
new/update/error counts, Worker duration, top vacancies, short reason, risks,
vacancy links and CRM link if configured.

Warning subject may indicate that search finished with warnings. Partial errors
must not hide already saved results.

### Google Credentials

Gmail node uses Google OAuth credential in n8n.

Google Sheets node uses a separate Google Service Account credential. The
service account has sharing permission only for the existing CRM spreadsheet.
Google Sheets API is enabled.

Credentials, private keys, tokens, spreadsheet IDs and real sheet URLs are not
stored in Git.

### Acceptance Limits

The accepted test run used intentionally small limits:

``` text
max_pages_override=1
max_filter_items_override=10
max_enrich_items_override=5
```

These values are not production policy. Next operational step: switch the
workflow to production config and run a full manual production run before
enabling schedule.

## HH collection flow

Статус: реализован на Worker и используется n8n Phase 5.10 workflow через
vertical endpoint.

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

Текущий integrated Worker flow:

``` text
Worker /hh/collect-search
→ local preliminary analysis
→ Worker /hh/vacancy-details
→ normalization
→ normalized deduplication
→ detailed analysis
→ Orchestrator POST /pipeline-results
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
-   orchestrator сохраняет выбранные вакансии, analyses, provenance и processing
    events через `POST /pipeline-results`;
-   полный AI-результат сохраняется в `VacancyAnalysis`;
-   n8n читает сохраненный current run и выполняет CRM/email external
    integrations.

Ограничения текущего состояния:

-   production schedule еще не включен;
-   acceptance limits еще нужно заменить production config;
-   scoring calibration предварительная;
-   нет ProxyAPI fallback;
-   нет автоматической отправки откликов.
