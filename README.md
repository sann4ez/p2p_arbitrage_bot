# Crypto P2P Scanner Bot

Telegram-бот для перегляду P2P-ордерів Binance та OKX з персональними фільтрами, пагінацією, кешуванням запитів і базовою адмін-панеллю.

Бот орієнтований на сценарій пошуку USDT/UAH P2P-оголошень, де важливо швидко відсіювати небажані умови мерчантів: оплата від третіх осіб, кілька платежів, ФОП/ТОВ/IBAN, Monobank "банка", довгий час виконання або слабка статистика мерчанта.

## Можливості

- Перегляд P2P-ордерів Binance та OKX.
- Напрямки UAH -> USDT та USDT -> UAH.
- Пагінація результатів у Telegram.
- Персональні P2P-фільтри для кожного користувача.
- Фільтрація за часом угоди, кількістю угод, рейтингом і відсотком виконання.
- Фільтрація за типами оплати: ФОП/ТОВ/IBAN, фізособа/карта, інші методи.
- Перевірка описів ордерів через Regex, GPT або Regex + GPT.
- Окремі фільтри для оплати від третіх осіб, кількох платежів і Monobank "банки".
- Кешування списків ордерів, деталей ордерів і GPT-класифікацій.
- Rate limiting для захисту домашнього або серверного IP.
- PostgreSQL для користувачів, налаштувань, ролей і довідників.
- RBAC: User, Admin, Super Admin з правами доступу.
- Адмін-панель у Telegram для керування валютами з контрольованого списку.
- Автоматичне створення таблиць і seed базових довідників при старті.

## Стек

- Python
- aiogram 3
- aiohttp
- SQLAlchemy 2 async
- asyncpg
- PostgreSQL
- OpenAI Responses API для GPT-перевірки описів

## Структура проєкту

```text
handlers/       Telegram handlers і меню
keyboards/      Reply/inline клавіатури
services/       Бізнес-логіка, клієнти бірж, фільтри, форматування
repositories/   Доступ до БД
db/models/      SQLAlchemy моделі
db/dto/         DTO і константи
db/migrations/  Легкі runtime-міграції
db/seeders/     Початкові ролі, права, валюти, біржі, методи оплати
filters/        Permission filters для aiogram
fsm/            FSM стани
scripts/        Допоміжні скрипти для БД
```

## Швидкий старт

1. Створити та активувати virtualenv:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Встановити залежності:

```powershell
pip install -r requirements.txt
```

3. Створити `.env` на основі `.env.example` і заповнити мінімальні змінні:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=p2p_bot
```

Або вказати повний URL:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/p2p_bot
```

4. Запустити бота:

```powershell
python main.py
```

При `DB_AUTO_CREATE_TABLES=true` бот сам створить таблиці та заповнить базові довідники.

## Railway

У проєкті є `Procfile`:

```text
worker: python main.py
```

Для Railway потрібно додати variables:

```env
TELEGRAM_TOKEN=
DATABASE_URL=
DB_AUTO_CREATE_TABLES=true
DB_AUTO_SEED_REFERENCE_DATA=true
LOG_LEVEL=INFO
```

Якщо використовується OpenAI-перевірка описів:

```env
OPENAI_API_KEY=
OPENAI_P2P_MODEL=gpt-5-nano
OPENAI_P2P_CLASSIFIER_TIMEOUT=60
OPENAI_P2P_CLASSIFICATION_CACHE_TTL_SECONDS=600
```

## Основні env-змінні

| Змінна | Опис |
| --- | --- |
| `TELEGRAM_TOKEN` | Токен Telegram-бота з BotFather |
| `LOG_LEVEL` | Рівень логів: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SUPER_ADMIN_TELEGRAM_IDS` | Telegram ID супер-адмінів через кому |
| `DATABASE_URL` | Повний async PostgreSQL URL |
| `DB_AUTO_CREATE_TABLES` | Автоматично створювати таблиці при старті |
| `DB_AUTO_SEED_REFERENCE_DATA` | Автоматично додавати ролі, права і довідники |
| `OPENAI_API_KEY` | API key для OpenAI Responses API |
| `OPENAI_P2P_MODEL` | Модель для класифікації описів |
| `OPENAI_VECTOR_STORE_ID` / `OPENAI_VECTOR_STORE_IDS` | Опційні vector stores для file search |
| `P2P_USER_COOLDOWN_SECONDS` | Cooldown для одного Telegram-користувача |
| `P2P_GLOBAL_COOLDOWN_SECONDS` | Глобальний cooldown між реальними запитами до бірж |
| `P2P_CACHE_TTL_SECONDS` | TTL кешу списків ордерів |
| `P2P_DETAILS_CACHE_TTL_SECONDS` | TTL кешу деталей ордерів |
| `P2P_ORDERS_PER_PAGE` | Кількість ордерів на сторінку в Telegram |
| `OKX_AUTHORIZATION` | Опційний web Authorization token для OKX detail descriptions |

Повний список змінних є в `.env.example`.

## P2P-фільтри

Користувач може налаштувати:

- максимальний час угоди;
- мінімальну кількість угод мерчанта;
- мінімальну оцінку;
- мінімальний відсоток виконання;
- допустимі типи методів оплати;
- чи дозволяти оплату від третіх осіб;
- чи дозволяти оплату кількома платежами;
- чи дозволяти Monobank "банку";
- режим перевірки опису: Regex, GPT, Regex + GPT;
- кількість ордерів для виводу;
- кількість кандидатів для перевірки описів.

## Binance та OKX описи ордерів

Для Binance бот використовує detail endpoint і намагається отримати `remarks` / `autoReplyMsg`.

Для OKX detail endpoint може вимагати авторизований web-контекст. `OKX_AUTHORIZATION` можна задати через env, але це опційний і нестабільний спосіб: токен може протухати, а біржа може вимагати додаткові cookies або підписані headers. Не коміть реальні токени в репозиторій.

Якщо опис OKX не вдалося отримати, а увімкнені фільтри по опису, такі ордери краще вважати неперевіреними.

## Корисні команди

Створити таблиці вручну:

```powershell
python scripts/create_tables.py
```

Додати P2P filter columns вручну:

```powershell
python scripts/add_p2p_filter_columns.py
```

Заповнити довідники вручну:

```powershell
python scripts/seed_reference_data.py
```

Перевірити імпорти/синтаксис:

```powershell
python -m compileall .
```

## Безпека

- Не додавай `.env` у git.
- Не публікуй `OPENAI_API_KEY`, `TELEGRAM_TOKEN`, `OKX_AUTHORIZATION` або cookies.
- Якщо випадково засвітив OKX web-токен, краще завершити активну сесію OKX і отримати новий токен.
- Для публічного тестування увімкни кеш і cooldown, щоб зменшити кількість запитів до бірж.

## Статус

Проєкт активно розвивається. Основний фокус зараз: стабільний P2P-сканер, якісні фільтри описів і зручне керування налаштуваннями через Telegram.
