# Документация Yandex Mail SDK

Этот каталог содержит подробные руководства по использованию пакета. Если вы
впервые запускаете проект, начните с [быстрого старта](getting-started.md).

| Документ | Что в нём описано |
| --- | --- |
| [Быстрый старт и настройка](getting-started.md) | Установка, `.env`, OAuth и первая проверка подключения |
| [Справочник CLI](cli.md) | Все команды `yandex-mail`, параметры, примеры и форматы вывода |
| [Python API](python-api.md) | Сервис, модели, фильтры, чтение писем и изменение флагов в коде |
| [Архитектура и безопасность](architecture-and-security.md) | Компоненты, хранение токенов, IMAP-ограничения, диагностика и тестирование |

## Короткая схема работы

```text
.env ──> YandexMailConfig ──> OAuthClient ──> TokenStore
                                      │              │
                                      └──── token ───┘
                                                    │
YandexMailService ──> ImapClient ──> IMAP XOAUTH2 ─┘
        │                    │
        ├── parser.py ──> MailMessage / Attachment
        └── models.py ──> MessageSummary / MessageStatus / MessagePage
```

Работа начинается с `YandexMailService.from_env(".env")`. Сервис получает
действующий OAuth-токен, открывает одно IMAP-подключение на операцию, выбирает
нужный mailbox и всегда идентифицирует письма UID, а не порядковыми номерами.

## Минимальный пример

```python
from yandex_mail import YandexMailService

service = YandexMailService.from_env(".env")
service.authorize()

page = service.list_messages(status="unread", limit=10)
for message in page.items:
    print(message.uid, message.subject)
```

Для работы из терминала это эквивалентно:

```bash
yandex-mail --env .env auth
yandex-mail --env .env list --unread --limit 10
```
