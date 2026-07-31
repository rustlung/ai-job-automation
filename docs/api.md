# API

## Worker API

Worker API работает на Windows 11 worker через Docker Compose и публикуется
наружу на порт `8001`.

### Health

``` text
GET /health
```

Назначение: проверка доступности Worker API.

Ответ:

``` json
{
  "status": "ok",
  "component": "worker"
}
```

### Local AI health

``` text
GET /health/ollama
```

Назначение: техническая проверка доступности Ollama и выбранной локальной
модели.

### Local AI analyze

``` text
POST /local-ai/analyze
```

Назначение: технический endpoint для structured local AI analysis через
Ollama.

Текущий endpoint используется в первом n8n workflow slice. Это ещё не
production-анализ реальных HH вакансий.

### HH search preview

``` text
POST /hh/search-preview
```

Назначение: диагностический endpoint для получения и разбора одной страницы
поисковой выдачи HH.

Request:

``` json
{
  "url": "https://hh.ru/search/vacancy?text=Python&enable_snippets=true"
}
```

Response:

``` json
{
  "count": 1,
  "vacancies": [
    {
      "source": "hh",
      "external_id": "123456789",
      "url": "https://hh.ru/vacancy/123456789",
      "title": "Python разработчик",
      "company": "Компания",
      "location": "Москва",
      "salary_text": "от 150 000 ₽",
      "is_remote": true,
      "responsibility_snippet": "Краткие обязанности из поисковой выдачи",
      "requirement_snippet": "Краткие требования из поисковой выдачи"
    }
  ]
}
```

Ограничения:

-   разбирается только одна страница выдачи;
-   пагинация не выполняется;
-   полные карточки вакансий не открываются;
-   данные не сохраняются в orchestrator;
-   AI-анализ не запускается.

Для получения snippets нужен параметр `enable_snippets=true`.

### HH vacancy details

``` text
POST /hh/vacancy-details
```

Назначение: диагностический endpoint для получения и разбора одной полной
страницы вакансии HH.

Request:

``` json
{
  "url": "https://hh.ru/vacancy/123456789"
}
```

Response:

``` json
{
  "source": "hh",
  "external_id": "123456789",
  "url": "https://hh.ru/vacancy/123456789",
  "title": "Python разработчик",
  "company": "Компания",
  "salary_text": "от 150 000 ₽",
  "description": "Полный нормализованный текст вакансии...",
  "skills": [
    "Python",
    "SQL",
    "PostgreSQL"
  ],
  "schedule_text": "5/2",
  "working_hours_text": "8",
  "address": "Город, улица",
  "published_at": "2026-07-20"
}
```

Ограничения:

-   обрабатывается только одна вакансия;
-   внешний домен отклоняется валидацией;
-   данные не сохраняются в orchestrator;
-   AI-анализ не запускается;
-   browser automation, авторизация HH, cookies, proxy и CAPTCHA handling не
    используются.

## Orchestrator API

Orchestrator API работает на homeserver и отвечает за хранение состояния и
данных.

Подробные persistence endpoints будут расширяться по мере развития
collector pipeline.
