# MAX-бот: поиск номенклатуры 1С:УНФ по изображению

Интеллектуальный чат-бот для **MAX** и **Telegram**: фото товара → Yandex Vision/GPT → поиск в **1С:УНФ** → остатки, цены, характеристики, фото из карточки.

## Состав репозитория

| Компонент | Каталог | Описание |
|-----------|---------|----------|
| Интеграционный сервис | `bot-service/` | Python, FastAPI, PostgreSQL, MAX/Telegram |
| Расширение 1С | `1С_ChatBot/` | HTTP API `nomenclature_bot` |
| Документация | `docs/` | Пример публикации Apache |

> Полная выгрузка типовой УНФ (`1С_Configuration/`) и локальный Apache (`tools/`) **не входят в репозиторий** — только локально.

## Архитектура

```
MAX / Telegram
      ↓  webhook или long polling
bot-service (Python, FastAPI, PostgreSQL)
      ↓                    ↓
 Yandex Vision/GPT     HTTP API 1С:УНФ
                       (расширение 1С_ChatBot)
```

## Быстрый старт (Docker)

### Требования

- Docker и Docker Compose
- Токен MAX и/или Telegram
- API-ключ и каталог [Yandex Cloud](https://yandex.cloud/) (Vision + YandexGPT)
- 1С:УНФ с загруженным расширением и опубликованным HTTP-сервисом

### Запуск

```bash
cp .env.example .env
# отредактируйте .env

docker compose up --build
```

- Health: `GET http://localhost:8000/health`
- Webhook MAX: `POST /webhooks/max`
- Webhook Telegram: `POST /webhooks/telegram`

При `POLLING_ENABLED=true` (dev) webhook не нужен.

### 1С: публикация HTTP-сервиса

1. Загрузите расширение `1С_ChatBot` → обновите конфигурацию БД.
2. Создайте пользователя 1С (например `BotAPI`) с ролью `ЧБ_ОсновнаяРоль`.
3. Опубликуйте базу на веб-сервере; в `default.vrd` включите сервис `nomenclature_bot`  
   (пример: [`docs/apache-publish-example.vrd`](docs/apache-publish-example.vrd)).
4. Проверка: `powershell -File scripts/verify-onec-api.ps1`

## Переменные окружения

Скопируйте [`.env.example`](.env.example) в `.env`. **Не коммитьте `.env`.**

| Переменная | Назначение |
|------------|------------|
| `MAX_BOT_TOKEN` | Токен MAX (если используете MAX) |
| `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN` | Telegram |
| `YANDEX_API_KEY`, `YANDEX_FOLDER_ID` | Yandex Vision + GPT |
| `ONEC_BASE_URL`, `ONEC_USERNAME`, `ONEC_PASSWORD` | HTTP API 1С |
| `AUTH_ENABLED` | Авторизация по телефону пользователя 1С |
| `POLLING_ENABLED` | Long polling для dev |

Полный список — в `.env.example`.

## HTTP API 1С

Базовый путь: `{ONEC_BASE_URL}/hs/nomenclature_bot/v1/`

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/ping` | Проверка доступности |
| GET/POST | `/search` | Поиск номенклатуры (POST — умный каскад) |
| GET | `/stock?ref=` | Остатки по складам |
| GET | `/details?ref=` | Характеристики и цены |
| GET | `/image?ref=` | Фото из карточки 1С |
| GET/POST | `/auth/verify` | Проверка телефона пользователя ИБ |

## Сценарий бота

1. (Опционально) Авторизация по номеру телефона — привязка к пользователю 1С.
2. Пользователь отправляет фото товара.
3. Yandex Vision OCR + YandexGPT → параметры поиска.
4. 1С возвращает до 5 кандидатов с inline-кнопками.
5. После выбора — остатки, цены, характеристики, фото.

## MAX и Telegram

| | Telegram | MAX |
|---|:---:|:---:|
| Поиск по фото, 1С, диалог | ✅ | ✅ |
| Авторизация по телефону | ✅ | ✅ |
| Кнопка «Поделиться номером» | ✅ | — (ввод текстом) |

Оба канала могут работать одновременно.

## Локальный запуск без Docker

```powershell
copy .env.example .env
powershell -File scripts/start-local.ps1
```

Нужны Python 3.12+ и PostgreSQL.

## Безопасность

См. [`SECURITY.md`](SECURITY.md). Все секреты — только в `.env`.

## Лицензия

[MIT](LICENSE)
