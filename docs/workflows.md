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
- нет HH parser;
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
