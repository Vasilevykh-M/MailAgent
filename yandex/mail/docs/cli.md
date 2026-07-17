# Справочник CLI

## Общий синтаксис

```text
yandex-mail [--env ПУТЬ] [--verbose] [--debug] КОМАНДА [ПАРАМЕТРЫ]
```

| Глобальный параметр | Описание |
| --- | --- |
| `--env ПУТЬ` | Файл конфигурации; по умолчанию `.env` |
| `--verbose` | Включает информационные сообщения журнала |
| `--debug` | Включает отладочные сообщения и traceback при ошибке |

Без `--debug` ожидаемые ошибки выводятся как одно понятное сообщение в stderr с
ненулевым кодом завершения. Не передавайте токены или Client Secret параметрам
CLI: инструмент их не требует и не должен получать таким способом.

## `diagnose`

```bash
yandex-mail diagnose
yandex-mail --env config/production.env diagnose
```

Не обращается к OAuth или IMAP. Используйте для проверки конфигурации перед
авторизацией или при проблемах с файлом токенов.

## `auth`

```bash
yandex-mail auth
yandex-mail auth --force
```

Без `--force` команда использует действующий сохранённый токен, либо обновляет
просроченный. С `--force` всегда запускается новый Authorization Code Flow.

## `list`

Получает список метаданных, не скачивая полные MIME-тела писем.

```bash
yandex-mail list [ПАРАМЕТРЫ]
```

### Пагинация и mailbox

| Параметр | Описание |
| --- | --- |
| `--mailbox ИМЯ` | IMAP mailbox; по умолчанию `INBOX` |
| `--limit ЧИСЛО` | Число строк в странице; по умолчанию `50` |
| `--offset ЧИСЛО` | Смещение страницы с нуля |
| `--before-uid UID` | Получать только UID, меньшие указанного; полезно для стабильной UID-пагинации |
| `--no-limit` | Потоково вывести все совпадающие сообщения |
| `--batch-size ЧИСЛО` | Размер пакета `UID FETCH`; по умолчанию `200` |

`--no-limit` предназначен для больших ящиков. Используйте `--json-lines`, если
результат передаётся другой программе.

### Статусы

Передайте один `--status` или один shortcut:

| Статус | Shortcut | IMAP-критерий |
| --- | --- | --- |
| `all` | `--all` | без критерия |
| `read` | `--read` | `SEEN` |
| `unread` | `--unread` | `UNSEEN` |
| `important` | `--important` | `FLAGGED` |
| `not-important` | `--not-important` | `UNFLAGGED` |
| `answered` | `--answered` | `ANSWERED` |
| `unanswered` | `--unanswered` | `UNANSWERED` |
| `draft` | `--draft` | `DRAFT` |
| `deleted` | `--deleted` | `DELETED` |
| `recent` | `--recent` | `RECENT` |

Пример:

```bash
yandex-mail list --status unread --limit 20
yandex-mail list --important --mailbox INBOX
```

Нельзя одновременно передать конфликтующие shortcut-флаги, например `--read`
и `--unread`.

### Дополнительные фильтры

| Параметр | IMAP-поиск | Пример |
| --- | --- | --- |
| `--sender EMAIL` | `FROM` | `--sender sender@example.com` |
| `--recipient EMAIL` | `TO` | `--recipient user@yandex.ru` |
| `--subject ТЕКСТ` | `SUBJECT` | `--subject Documents` |
| `--text ТЕКСТ` | `TEXT` | `--text contract` |
| `--since YYYY-MM-DD` | `SINCE` | `--since 2026-01-01` |
| `--before YYYY-MM-DD` | `BEFORE` | `--before 2026-08-01` |
| `--has-attachments` | поиск `Content-Type: multipart` | `--has-attachments` |
| `--no-attachments` | отрицание этого поиска | `--no-attachments` |
| `--larger-than БАЙТЫ` | `LARGER` | `--larger-than 1024` |
| `--smaller-than БАЙТЫ` | `SMALLER` | `--smaller-than 10000000` |

Фильтр вложений не скачивает тела всех писем. У стандартного IMAP нет
универсального критерия наличия вложения, поэтому это серверное приближение по
заголовку `Content-Type`.

### Сортировка и вывод

| Параметр | Значения |
| --- | --- |
| `--sort` | `date`, `uid`, `sender`, `subject`, `size` |
| `--ascending` | сортировка по возрастанию |
| `--descending` | сортировка по убыванию, используется по умолчанию |
| `--json` | JSON-страница или JSON-массив в режиме `--no-limit` |
| `--json-lines` | один `MessageSummary` JSON-объект на строку |

Примеры:

```bash
yandex-mail list --unread --sort sender --ascending
yandex-mail list --status all --no-limit --json-lines > messages.jsonl
yandex-mail list --offset 100 --limit 50 --json
```

## `status`

```bash
yandex-mail status UID [UID ...] [--mailbox ИМЯ] [--json]
```

Примеры:

```bash
yandex-mail status 12345
yandex-mail status 12345 12346 12347 --json
```

Команда запрашивает актуальные флаги через один пакетный `UID FETCH`, где это
возможно. Не использует кэш и не скачивает тело сообщения.

## `read`

```bash
yandex-mail read UID [--mailbox ИМЯ] [--peek] [--json]
                 [--include-attachment-data] [--include-raw]
                 [--attachments-dir КАТАЛОГ] [--raw-file ПУТЬ]
```

По умолчанию письмо помечается прочитанным. `--peek` читает с `BODY.PEEK[]` и
сохраняет флаг `\Seen` без изменений.

| Параметр | Действие |
| --- | --- |
| `--attachments-dir КАТАЛОГ` | Сохранить все вложения в указанный каталог |
| `--raw-file ПУТЬ` | Сохранить исходный RFC 5322 в `.eml` |
| `--json` | Вывести безопасное JSON-представление `MailMessage` |
| `--include-attachment-data` | Включить данные вложений в Base64 в JSON |
| `--include-raw` | Включить `raw_bytes` в Base64 в JSON |

Пример экспорта без изменения статуса:

```bash
yandex-mail read 12345 --peek \
  --attachments-dir downloads/12345 \
  --raw-file downloads/12345/message.eml
```

## `attachments`

```bash
yandex-mail attachments UID --output КАТАЛОГ [--mailbox ИМЯ]
```

Загружает сообщение через `BODY.PEEK[]`, поэтому не меняет `\Seen`, и печатает
пути созданных файлов. Имена безопасно очищаются; уже существующие файлы не
перезаписываются.

```bash
yandex-mail attachments 12345 --output downloads/12345
```

## Команды изменения флагов

```bash
yandex-mail mark-read UID [UID ...] [--mailbox ИМЯ] [--json]
yandex-mail mark-unread UID [UID ...] [--mailbox ИМЯ] [--json]
yandex-mail mark-important UID [UID ...] [--mailbox ИМЯ] [--json]
yandex-mail mark-not-important UID [UID ...] [--mailbox ИМЯ] [--json]
```

Операции соответствуют следующим IMAP-командам:

| CLI | IMAP |
| --- | --- |
| `mark-read` | `+FLAGS.SILENT (\Seen)` |
| `mark-unread` | `-FLAGS.SILENT (\Seen)` |
| `mark-important` | `+FLAGS.SILENT (\Flagged)` |
| `mark-not-important` | `-FLAGS.SILENT (\Flagged)` |

Для набора UID выполняется один `UID STORE`, после чего флаги каждого найденного
письма считываются снова. Если один из UID отсутствует, команда завершается
ошибкой, а не возвращает устаревший статус.
