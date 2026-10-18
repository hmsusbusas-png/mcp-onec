# mcp-onec

MCP-сервер для 1С:Предприятия в Claude Desktop. Читает справочники, документы и регистры через стандартный интерфейс OData. Записывать ничего не может: HTTP-клиент отклоняет любой метод кроме GET ещё до отправки запроса.

## Инструменты

| Инструмент | Что делает |
|---|---|
| `onec_entities` | что опубликовано: количество по видам или список имён одного вида |
| `onec_fields` | поля с типами, табличные части с колонками и виртуальные таблицы объекта |
| `onec_query` | любое чтение: `$filter`, `$select`, `$orderby`, `$expand`, постранично |
| `onec_count` | число записей, можно с фильтром |
| `onec_search_catalog` | поиск в справочнике по подстроке в наименовании |
| `onec_get` | один объект любого вида по Ref_Key вместе с табличными частями |
| `onec_search_documents` | документы за период, по номеру, только проведённые |
| `onec_balances` | остатки регистра накопления или бухгалтерии на дату |
| `onec_turnovers` | обороты за период |
| `onec_balance_turnovers` | начальный остаток, обороты и конечный остаток |
| `onec_slice` | срез последних или первых значений регистра сведений (цены, курсы) |
| `onec_postings` | движения регистра за период |
| `onec_run_report` | вызов HTTP-сервиса 1С методом GET, только из белого списка |

Виды объектов для `onec_entities`: catalog, document, journal, constant, enum, exchange_plan, chart_of_accounts, chart_of_characteristic_types, chart_of_calculation_types, information, accumulation, accounting, calculation, business_process, task.

Имена объектов, Ref_Key и даты проверяются. Строки в фильтрах экранируются, кириллица в URL кодируется. Даты передаются как `YYYY-MM-DD` или `YYYY-MM-DDTHH:MM:SS`, конец периода без времени считается до 23:59:59. В ответе есть `total` и `next_offset` для следующей страницы.

## Публикация OData в 1С

1. Конфигуратор, Администрирование, Публикация на веб-сервере. Нужен IIS или Apache на сервере 1С.
2. Включить «Публиковать стандартный интерфейс OData».
3. В режиме 1С:Предприятие задать состав интерфейса: обработка «Настройка стандартного интерфейса OData» с ИТС или метод `УстановитьСоставСтандартногоИнтерфейсаOData`. Без этого `$metadata` будет пустым.
4. Завести отдельного пользователя только с правами на чтение.
5. Проверить в браузере `http://server/base/odata/standard.odata/$metadata`.

## Установка

Нужны Windows, [uv](https://docs.astral.sh/uv/) и Claude Desktop.

```powershell
git clone https://github.com/hmsusbusas-png/mcp-onec C:\mcp\mcp-onec
cd C:\mcp\mcp-onec
uv sync
copy config.example.toml config.toml
copy .env.example .env
```

В `config.toml` укажите `base_url` публикации, в `.env` логин и пароль пользователя 1С. Оба файла в `.gitignore`.

## Подключение к Claude Desktop

Settings, Developer, Edit Config. Путь к uv нужен полный, его покажет `where.exe uv`.

```json
{
  "mcpServers": {
    "onec": {
      "command": "C:\\Users\\<имя>\\.local\\bin\\uv.exe",
      "args": ["run", "--directory", "C:\\mcp\\mcp-onec", "python", "-m", "onec"]
    }
  }
}
```

После правки полностью закройте Claude Desktop из трея и запустите снова.

## Проверка

```powershell
uv run pytest
```

Тесты поднимают локальный поддельный сервер OData и проверяют, какие запросы уходят в 1С: кодирование кириллицы, экранирование, пагинацию, виртуальные таблицы и то, что методы записи не уходят в сеть.
