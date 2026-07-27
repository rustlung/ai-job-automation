# Changelog

## 2026-07-27

### Added

- базовый FastAPI API worker;
- Docker Compose для worker;
- endpoint проверки состояния;
- развертывание worker на Windows 11;
- подтвержденная связь homeserver → worker по HTTP.

## 2026-07-21

### Added

- слой хранения оркестратора на SQLAlchemy;
- конфигурация Alembic;
- persistent SQLite storage;
- Docker Compose для orchestrator;
- развертывание orchestrator на homeserver через sparse checkout.

## 2026-07-20

### Added

- создан базовый FastAPI backend оркестратора;
- добавлена структура приложения;
- подготовлена основа для дальнейшей работы с API и storage layer.
