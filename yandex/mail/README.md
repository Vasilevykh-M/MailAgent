# Yandex Mail SDK

Готовый Python-пакет и CLI `yandex-mail` для работы с Яндекс Почтой. Пакет
использует OAuth 2.0 Authorization Code Flow, стандартный модуль `imaplib` и
IMAP по SSL/TLS с аутентификацией XOAUTH2. Неофициальные библиотеки Яндекс Почты
не используются.

## Подробная документация

- [Быстрый старт и настройка](docs/getting-started.md)
- [Справочник CLI](docs/cli.md)
- [Python API и модели данных](docs/python-api.md)
- [Архитектура, безопасность и устранение проблем](docs/architecture-and-security.md)

## Возможности

- Консольная OAuth-авторизация с безопасным локальным хранением токенов
- Автоматическое обновление `access_token` и замена `refresh_token` при ротации
- Подключение к IMAP через SSL/TLS и XOAUTH2 с одной попыткой обновления токена
- Списки писем по UID, пакетная загрузка метаданных и потоковая обработка больших ящиков
- Серверные фильтры по статусу, отправителю, получателю, теме, тексту, датам и размеру
- Получение актуальных IMAP-флагов и массовое изменение статусов
- Полный MIME-разбор: plain text, HTML, вложенные multipart, кодированные заголовки,
  Unicode-имена файлов, inline-части и бинарные вложения
- Безопасное сохранение вложений без выхода за пределы каталога
- Сохранение исходного письма в `.eml` и JSON-совместимые модели для интеграции

## Требования и установка

Нужен Python 3.11 или новее. Создайте виртуальное окружение и установите пакет:

```bash
python -m venv .venv
source .venv/bin/activate                # Windows: .venv\Scripts\Activate.ps1
pip install -e .
```

Для запуска тестов установите дополнительную зависимость:

```bash
pip install -e '.[dev]'
pytest
```

После установки доступна команда `yandex-mail`.

## Настройка Яндекс OAuth

Создайте OAuth-приложение в Яндекс OAuth и укажите строго следующий Redirect URI:

```text
https://oauth.yandex.ru/verification_code
```

Пакет запрашивает разрешение `mail:imap_full`. Не заменяйте его на
`mail:imap_ro`: проект должен изменять IMAP-флаги `\Seen` и `\Flagged`.

Скопируйте пример конфигурации и заполните значения из кабинета Яндекс OAuth:

```bash
cp .env.example .env
```

```dotenv
YANDEX_CLIENT_ID=ваш-client-id
YANDEX_CLIENT_SECRET=ваш-client-secret
YANDEX_EMAIL=user@yandex.ru

YANDEX_REDIRECT_URI=https://oauth.yandex.ru/verification_code
YANDEX_OAUTH_SCOPE=mail:imap_full

YANDEX_IMAP_HOST=imap.yandex.com
YANDEX_IMAP_PORT=993
YANDEX_IMAP_MAILBOX=INBOX

YANDEX_TOKEN_FILE=.tokens.json
```

Файлы `.env` и `.tokens.json` исключены из Git. Не публикуйте их содержимое и
не добавляйте секреты или токены в исходный код, логи и тикеты.

Для первой авторизации выполните:

```bash
yandex-mail auth
```

Команда выведет и попробует открыть URL Яндекса. После предоставления доступа
Яндекс покажет код подтверждения — вставьте его в терминал. При успехе выводится:

```text
Authorization completed.
Tokens saved.
```

Токены записываются через временный файл с последующей атомарной заменой
целевого файла. Там, где это поддерживается, для файла устанавливаются права
`0600`. Перед запросом просроченный токен обновляется автоматически. Если Яндекс
выдаёт новый `refresh_token`, он сохраняется вместо прежнего. При неудачном
обновлении запускается новая OAuth-авторизация. Чтобы принудительно пройти её
заново, используйте `yandex-mail auth --force`.

## CLI

Глобальные параметры передаются перед командой:

```bash
yandex-mail --env path/to/.env --verbose diagnose
yandex-mail --debug list --unread
```

`--debug` выводит traceback. Без него CLI показывает понятное сообщение и
завершается с ненулевым кодом при ошибке. OAuth-секрет, коды и токены намеренно
не попадают в логи.

### Диагностика

```bash
yandex-mail diagnose
```

Команда показывает наличие конфигурации, несекретные параметры подключения,
состояние файла токенов и факт истечения сохранённого access token. Значения
Client Secret и токенов никогда не выводятся.

### Список писем

```bash
yandex-mail list
yandex-mail list --limit 20 --offset 100 --mailbox INBOX
yandex-mail list --status unread
yandex-mail list --read
yandex-mail list --important --json
```

Допустимые статусы: `all`, `read`, `unread`, `important`, `not-important`,
`answered`, `unanswered`, `draft`, `deleted`, `recent`. Для них есть сокращения:
`--all`, `--unread`, `--read`, `--important`, `--not-important`, `--answered`,
`--unanswered`, `--draft`, `--deleted` и `--recent`. Конфликтующие сокращения
отклоняются.

Дополнительные серверные фильтры и сортировка:

```bash
yandex-mail list \
  --unread --sender sender@example.com --recipient user@yandex.ru \
  --subject Documents --text contract --since 2026-01-01 --before 2026-08-01 \
  --has-attachments --larger-than 1024 --smaller-than 10000000 \
  --sort date --descending
```

Обычный список сначала выполняет `UID SEARCH`, затем пакетно загружает заголовки
и метаданные. Полные тела писем при этом не скачиваются. `--has-attachments`
выполняет серверный поиск по заголовку `Content-Type` — это переносимое
IMAP-приближение поиска писем с вложениями.

Для обработки всех совпадающих писем используйте потоковый режим:

```bash
yandex-mail list --status all --no-limit --batch-size 200
yandex-mail list --unread --no-limit --json-lines
```

`--json` выводит страницу или массив JSON; `--json-lines` удобнее для больших
выгрузок, поскольку печатает по одному JSON-объекту на строку.

### Статус и полное содержимое письма

```bash
yandex-mail status 12345
yandex-mail status 12345 12346 --json

yandex-mail read 12345
yandex-mail read 12345 --peek
yandex-mail read 12345 --attachments-dir downloads/12345 \
  --raw-file downloads/12345/message.eml
yandex-mail read 12345 --json --include-attachment-data --include-raw
```

`status` всегда выполняет актуальный серверный запрос `UID FETCH (UID FLAGS)`.
`read` возвращает все заголовки в исходном порядке, включая повторяющиеся,
версии тела `text/plain` и `text/html`, а также все вложения. По умолчанию
команда отмечает письмо прочитанным. Параметр `--peek` использует `BODY.PEEK[]`
и не меняет флаг `\Seen`.

В JSON бинарные данные вложений и исходные байты письма не включаются по
умолчанию. `--include-attachment-data` и `--include-raw` добавляют их в Base64.

Чтобы сохранить все вложения, не изменяя `\Seen`:

```bash
yandex-mail attachments 12345 --output downloads/12345
```

Имена, полученные из письма, приводятся к безопасному basename, не могут выйти
за пределы каталога вывода, а дубликаты сохраняются как `document_2.pdf`,
`document_3.pdf` и т. д.

### Изменение флагов

```bash
yandex-mail mark-read 12345 12346
yandex-mail mark-unread 12345
yandex-mail mark-important 12345 12346
yandex-mail mark-not-important 12345
```

Для нескольких UID по возможности выполняется один `UID STORE`. После операции
программа повторно считывает флаги с сервера и выводит итоговый статус каждого
письма.

## Использование как Python-библиотеки

Основной публичный импорт — `YandexMailService`:

```python
from pathlib import Path

from yandex_mail import YandexMailService

service = YandexMailService.from_env(".env")
service.authorize()  # использует сохранённый токен, обновляет его или запускает OAuth

page = service.list_messages(mailbox="INBOX", status="unread", limit=20)
for item in page.items:
    print(item.uid, item.subject, item.from_, item.is_important)

if page.items:
    uid = page.items[0].uid
    print(service.get_message_status(uid).to_dict())
    message = service.read_message(
        uid,
        mark_read=True,
        attachments_dir=Path("downloads") / uid,
        raw_file=Path("downloads") / uid / "message.eml",
    )
    print(message.text_plain, message.text_html)
    for attachment in message.attachments:
        print(attachment.filename, attachment.size_bytes)
```

Можно передать конфигурацию напрямую:

```python
from yandex_mail import YandexMailConfig, YandexMailService

config = YandexMailConfig(
    client_id="...",
    client_secret="...",
    email="user@yandex.ru",
    redirect_uri="https://oauth.yandex.ru/verification_code",
    oauth_scope="mail:imap_full",
)
service = YandexMailService(config)
```

Полезные методы библиотеки:

```python
service.mark_as_read(uid)
service.mark_as_unread(uid)
service.mark_as_important(uid)
service.mark_as_not_important(uid)

for summary in service.iter_messages(status="unread", batch_size=200):
    print(summary.uid, summary.subject)

all_summaries = service.get_all_messages(status="all", batch_size=200)
statuses = service.get_message_statuses(["12345", "12346"])
service.update_flags("12345", add={"\\Seen", "\\Flagged"}, remove={"\\Answered"})
```

## Модели данных

- `MessagePage` — данные пагинации и элементы `MessageSummary`.
- `MessageSummary` — метаданные и флаги, полученные без загрузки MIME-тела.
- `MessageStatus` — текущие флаги и удобные булевы поля (`is_read`,
  `is_important`, `is_answered` и др.), а также пользовательские IMAP-метки.
- `MailMessage` — полное распарсенное письмо, упорядоченные заголовки с
  дубликатами, текстовые части, вложения и исходные байты.
- `Attachment` — MIME-метаданные и бинарное поле `data`; `save()` безопасно
  сохраняет вложение.

У каждой модели есть `to_dict()`. Распарсенные даты сериализуются как ISO 8601,
множества — как отсортированные JSON-массивы. При `include_data=True` и
`include_raw=True` бинарные значения кодируются в Base64.

## Частые ошибки и ограничения IMAP

- **Нет конфигурации.** Выполните `yandex-mail diagnose`, затем заполните `.env`.
- **Код авторизации отклонён.** Проверьте OAuth-приложение, Redirect URI и код;
  при необходимости выполните `yandex-mail auth --force`.
- **Ошибка IMAP-аутентификации.** SDK один раз обновляет токен и повторяет вход.
  Убедитесь, что IMAP разрешён для аккаунта, и при необходимости авторизуйтесь заново.
- **Письмо не найдено.** UID уникален только в пределах конкретного mailbox.
  Выберите правильный ящик параметром `--mailbox`.
- **Фильтр вложений.** В стандартном IMAP нет универсального критерия «есть
  вложение», поэтому используется эффективный серверный поиск по заголовку, без
  скачивания всех тел писем.
- **Сортировка.** Если сервер не поддерживает IMAP SORT, сортировка метаданных
  выполняется на стороне клиента.

Для реальной OAuth-авторизации и работы с IMAP нужны Client ID, Client Secret и
аккаунт Яндекс Почты. Автоматические тесты не используют реальный аккаунт и
подменяют HTTP/IMAP-взаимодействия:

```bash
pytest
```
