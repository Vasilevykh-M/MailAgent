# Быстрый старт и настройка

## 1. Требования

- Python 3.11 или новее;
- зарегистрированное OAuth-приложение Яндекса;
- почтовый аккаунт Яндекса с доступом по IMAP;
- Client ID и Client Secret приложения.

Пакет использует только `requests`, `python-dotenv` и стандартную библиотеку
Python для OAuth, MIME и IMAP. В частности, IMAP реализован через `imaplib`.

## 2. Установка

В Unix-подобной системе:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

В PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

Проверьте установку:

```bash
python -c "from yandex_mail import YandexMailService; print('import ok')"
yandex-mail --help
```

## 3. Создание OAuth-приложения

В настройках OAuth-приложения укажите следующий Redirect URI без изменений:

```text
https://oauth.yandex.ru/verification_code
```

SDK рассчитан на консольный Authorization Code Flow. После входа и согласия
Яндекс отображает verification code на странице этого URI; приложение получает
его от пользователя через стандартный ввод в терминале.

Нужная область доступа:

```text
mail:imap_full
```

`mail:imap_ro` не подходит: он не позволяет менять флаги `\Seen` и `\Flagged`.

## 4. Файл `.env`

Скопируйте шаблон:

```bash
cp .env.example .env
```

Заполните `.env`:

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

### Значения параметров

| Переменная | Назначение | Значение по умолчанию |
| --- | --- | --- |
| `YANDEX_CLIENT_ID` | Идентификатор OAuth-приложения | обязательно |
| `YANDEX_CLIENT_SECRET` | Секрет OAuth-приложения | обязательно |
| `YANDEX_EMAIL` | Полный адрес ящика для XOAUTH2 | обязательно |
| `YANDEX_REDIRECT_URI` | Redirect URI OAuth | `https://oauth.yandex.ru/verification_code` |
| `YANDEX_OAUTH_SCOPE` | OAuth scope | `mail:imap_full` |
| `YANDEX_IMAP_HOST` | Хост IMAP | `imap.yandex.com` |
| `YANDEX_IMAP_PORT` | SSL-порт IMAP | `993` |
| `YANDEX_IMAP_MAILBOX` | Ящик по умолчанию | `INBOX` |
| `YANDEX_TOKEN_FILE` | Файл OAuth-токенов | `.tokens.json` |

Относительный путь `YANDEX_TOKEN_FILE` интерпретируется относительно каталога
самого `.env`, а не относительно текущей рабочей директории.

Значения переменных окружения процесса имеют приоритет над значениями в `.env`.
Это удобно для CI/CD, но не передавайте секреты в аргументах командной строки.

## 5. Диагностика до авторизации

```bash
yandex-mail --env .env diagnose
```

Команда безопасно показывает:

- найден ли `.env`;
- заполнены ли Client ID и Client Secret;
- email, Redirect URI, scope и настройки IMAP;
- путь и наличие файла токенов;
- наличие access/refresh token и факт истечения access token.

Секреты и значения токенов не печатаются.

## 6. Первая авторизация

```bash
yandex-mail --env .env auth
```

Порядок действий:

1. CLI выводит URL авторизации и пытается открыть его в браузере.
2. Войдите в Яндекс и подтвердите выдачу доступа.
3. Скопируйте показанный Яндексом код подтверждения.
4. Вставьте код в терминал.
5. SDK получает `access_token`, `refresh_token` и время истечения.
6. Токены сохраняются в файл из `YANDEX_TOKEN_FILE`.

Чтобы не использовать сохранённый токен и пройти авторизацию заново:

```bash
yandex-mail --env .env auth --force
```

## 7. Автоматическое обновление токенов

Перед запросом SDK проверяет `expires_at` с запасом в 60 секунд. Если access
token скоро истечёт или уже истёк, выполняется OAuth refresh grant. Если сервер
вернул новый refresh token, он заменяет прежний в файле. Если refresh token
отклонён, сервис запускает новую интерактивную авторизацию.

При IMAP-ошибке аутентификации SDK дополнительно пытается обновить access token
и подключиться ещё один раз. Бесконечных циклов повторных подключений нет.

## 8. Первая операция с почтой

```bash
# Показать 20 непрочитанных писем
yandex-mail --env .env list --unread --limit 20

# Получить актуальные флаги одного письма
yandex-mail --env .env status 12345

# Прочитать письмо и сохранить вложения
yandex-mail --env .env read 12345 --attachments-dir downloads/12345
```

UID `12345` — пример. Получите реальные UID из вывода `list`.

## 9. Быстрый старт в Python

```python
from yandex_mail import YandexMailService

service = YandexMailService.from_env(".env")
service.authorize()

for summary in service.iter_messages(status="unread", batch_size=200):
    print(summary.uid, summary.subject, summary.from_)
```

Подробности методов и моделей приведены в [справочнике Python API](python-api.md).
