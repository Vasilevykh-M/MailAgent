# Справочник Python API

## Создание сервиса

### Из `.env`

```python
from yandex_mail import YandexMailService

service = YandexMailService.from_env(".env")
```

`from_env()` загружает файл без изменения глобального `os.environ`. Переменные
окружения процесса имеют приоритет над значениями файла.

### Явная конфигурация

```python
from yandex_mail import YandexMailConfig, YandexMailService

config = YandexMailConfig(
    client_id="client-id",
    client_secret="client-secret",
    email="user@yandex.ru",
    redirect_uri="https://oauth.yandex.ru/verification_code",
    oauth_scope="mail:imap_full",
    imap_host="imap.yandex.com",
    imap_port=993,
    imap_mailbox="INBOX",
    token_file=".tokens.json",
)
service = YandexMailService(config)
```

Конфигурация проверяется перед сетевой операцией. Обязательны `client_id`,
`client_secret`, `email`, стандартный Redirect URI и scope `mail:imap_full`.

## Авторизация и токены

```python
token = service.authorize(force=False)
access_token = service.get_access_token()
```

| Метод | Поведение |
| --- | --- |
| `authorize(False)` | Использует действующий токен, обновляет истёкший или запускает OAuth |
| `authorize(True)` | Всегда запускает интерактивный OAuth flow |
| `get_access_token()` | Возвращает действующий access token, обновляя его при необходимости |

Методы не печатают и не записывают в логи значения токенов.

## Список писем

```python
from datetime import date

page = service.list_messages(
    mailbox="INBOX",
    status="unread",
    limit=50,
    offset=0,
    sort_by="date",
    descending=True,
    sender="sender@example.com",
    recipient="user@yandex.ru",
    subject="Documents",
    text="contract",
    since=date(2026, 1, 1),
    before=date(2026, 8, 1),
    has_attachments=True,
    larger_than=1024,
    smaller_than=10_000_000,
    batch_size=200,
)
```

### Параметры `list_messages`

| Параметр | Тип | Описание |
| --- | --- | --- |
| `mailbox` | `str` | Ящик IMAP; по умолчанию `INBOX` |
| `status` | `str` | `all`, `read`, `unread`, `important`, `not-important`, `answered`, `unanswered`, `draft`, `deleted`, `recent` |
| `limit` | `int \| None` | Размер страницы; `None` возвращает всё |
| `offset` | `int` | Смещение страницы |
| `sort_by` | `str` | `date`, `uid`, `sender`, `subject` или `size` |
| `descending` | `bool` | Новые письма первыми, если `True` |
| `unread_only` | `bool \| None` | Совместимый shortcut; конфликт со `status` вызывает ошибку |
| `before_uid` | `str \| None` | Включать UID, меньшие указанного |
| `batch_size` | `int` | Число UID в одном `FETCH` |

Фильтры `sender`, `recipient`, `subject`, `text`, `since`, `before`,
`has_attachments`, `larger_than` и `smaller_than` передаются в `UID SEARCH`.
При обычном листинге загружаются только заголовки и метаданные, не полное тело.

Результат — `MessagePage`:

```python
print(page.total, page.offset, page.has_more, page.next_offset)
for item in page.items:
    print(item.uid, item.subject, item.is_read)
```

## Обработка всех сообщений

```python
# Генератор хранит в памяти только текущую порцию метаданных.
for summary in service.iter_messages(mailbox="INBOX", status="unread", batch_size=200):
    print(summary.uid, summary.subject)

# Если нужен именно список:
summaries = service.get_all_messages(mailbox="INBOX", status="all", batch_size=200)
```

`iter_messages()` — предпочтительный вариант для большого ящика. Метод
сначала получает набор UID, а затем выполняет пакетные запросы метаданных и
выдаёт объекты `MessageSummary` по одному.

## Актуальные флаги

```python
status = service.get_message_status("12345", mailbox="INBOX")
statuses = service.get_message_statuses(["12345", "12346"], mailbox="INBOX")
range_statuses = service.get_message_statuses("12345:12400", mailbox="INBOX")
```

Для этих методов используется `UID FETCH (UID FLAGS)`. `MessageStatus` всегда
отражает ответ сервера на момент запроса, а не флаги из ранее построенного списка.

```python
print(status.is_read)       # \Seen присутствует
print(status.is_unread)     # \Seen отсутствует
print(status.is_important)  # \Flagged присутствует
print(status.custom_flags)  # не стандартные IMAP-флаги и keywords
```

Системные флаги распознаются без учёта регистра: `\Seen`, `\Flagged`,
`\Answered`, `\Draft`, `\Deleted`, `\Recent`.

## Чтение полного письма

```python
from pathlib import Path

message = service.read_message(
    uid="12345",
    mailbox="INBOX",
    mark_read=True,
    attachments_dir=Path("downloads") / "12345",
    raw_file=Path("downloads") / "12345" / "message.eml",
)

print(message.subject)
print(message.text_plain)
print(message.text_html)
```

`mark_read=False` применяет `BODY.PEEK[]`, не меняя `\Seen`. После чтения и
любого изменения флага SDK повторно получает `FLAGS`, поэтому поля состояния в
`MailMessage` актуальны.

Вложение содержит бинарные данные сразу после разбора:

```python
for attachment in message.attachments:
    print(attachment.filename, attachment.content_type, attachment.size_bytes)
    # attachment.data: bytes

paths = message.save_attachments("downloads/12345")
message.save_eml("downloads/12345/message.eml")
```

## Изменение флагов

```python
# Одна операция
service.mark_as_read("12345")
service.mark_as_unread("12345")
service.mark_as_important("12345")
service.mark_as_not_important("12345")

# Несколько UID: один UID STORE, где это возможно
service.mark_many_as_read(["12345", "12346"])
service.mark_many_as_unread(["12345", "12346"])
service.mark_many_as_important(["12345", "12346"])
service.mark_many_as_not_important(["12345", "12346"])

# Произвольная валидная комбинация
status = service.update_flags(
    "12345",
    add={"\\Seen", "\\Flagged"},
    remove={"\\Answered"},
    mailbox="INBOX",
)
```

Один и тот же флаг нельзя одновременно добавлять и удалять. Допускаются
стандартные системные флаги и безопасные пользовательские keywords. UID должен
быть положительным десятичным числом.

## Модели и JSON

### `Attachment`

| Поле | Описание |
| --- | --- |
| `filename` | Декодированное имя файла |
| `content_type` | MIME-тип |
| `content_disposition` | `attachment`, `inline` или `None` |
| `content_id` | Content-ID, если задан |
| `charset` | Кодировка MIME-части |
| `size_bytes` | Размер `data` в байтах |
| `data` | Бинарное содержимое `bytes` |
| `is_inline` | Является ли часть inline-вложением |

```python
attachment.to_dict()                    # без бинарных данных
attachment.to_dict(include_data=True)   # data в Base64
attachment.save("downloads/report.pdf")
```

### `MessageStatus`

Содержит `uid`, `mailbox`, `flags`, булевы поля `is_read`, `is_unread`,
`is_important`, `is_answered`, `is_draft`, `is_deleted`, `is_recent` и
`custom_flags`. Вызов `to_dict()` сортирует множества для JSON.

### `MessageSummary`

Содержит UID, mailbox, номер последовательности, тему, адреса, дату,
`message_id`, размер, флаги и признаки вложений. Это лёгкий объект для списков,
а `attachment_count` может быть `None`, поскольку точный подсчёт не требует
загружать структуру каждого MIME-сообщения.

### `MailMessage`

Дополнительно содержит `bcc`, `reply_to`, `in_reply_to`, `references`,
`headers`, `text_plain`, `text_html`, `attachments` и `raw_bytes`. `headers`
сохраняют порядок и повторяющиеся имена заголовков.

```python
safe = message.to_dict()
with_data = message.to_dict(include_attachment_data=True, include_raw=True)
```

В `safe` не входят вложения в Base64 и исходные байты письма. Даты сериализуются
в ISO 8601, а `raw_date` сохраняет исходную строку заголовка Date.

## Исключения

Все ожидаемые ошибки наследуются от `YandexMailError`:

| Исключение | Когда возникает |
| --- | --- |
| `ConfigurationError` | Нет или неверны параметры конфигурации |
| `OAuthError` | Общая ошибка OAuth |
| `AuthorizationCodeError` | Код авторизации пуст или отклонён |
| `TokenStorageError` | Невозможно безопасно прочитать/записать файл токенов |
| `TokenRefreshError` | Невозможно обновить токен |
| `ImapConnectionError` | Ошибка подключения или IMAP-команды |
| `ImapAuthenticationError` | XOAUTH2 не прошёл после одной повторной попытки |
| `MailboxError` | Невозможно выбрать или закрыть mailbox |
| `MessageNotFoundError` | UID не найден в выбранном mailbox |
| `MessageFlagError` | Некорректная или отклонённая операция с флагами |
| `AttachmentSaveError` | Вложение не удалось безопасно сохранить |
| `MessageParseError` | Не удалось распарсить MIME-письмо |

Пример обработки:

```python
from yandex_mail import MessageNotFoundError, YandexMailError

try:
    message = service.read_message("12345")
except MessageNotFoundError:
    print("Проверьте UID и mailbox.")
except YandexMailError as error:
    print(f"Ошибка почтового клиента: {error}")
```
