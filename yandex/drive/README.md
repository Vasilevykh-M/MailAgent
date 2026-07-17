# Yandex Drive SDK

`yandex-drive-sdk` — самостоятельная библиотека Python 3.11+ и CLI
`yandex-drive` для [REST API Яндекс Диска](https://yandex.com/dev/disk-api/doc/en/).
Она выполняет прямые запросы через `requests`, использует OAuth 2.0 и
обрабатывает каждый ресурс как произвольные бинарные данные. Пакет не зависит
от `yandex_mail` и не импортирует его.

## Установка

```bash
cd mail_agent/yandex/drive
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

В Windows PowerShell активируйте окружение командой:

```powershell
.venv\Scripts\Activate.ps1
```

Для разработки:

```bash
python -m pip install -e ".[dev]"
pytest
```

## Настройка OAuth и авторизация

Создайте приложение в Yandex OAuth, включите разрешения `cloud_api:disk.read`
и `cloud_api:disk.write`, настройте Redirect URI
`https://oauth.yandex.ru/verification_code`. Укажите Client ID и Client Secret
в локальном файле `.env` (начните с `.env.example`):

```bash
cp .env.example .env
yandex-drive auth
```

SDK хранит учётные данные Диска в `.drive_tokens.json` отдельно от токенов
Почты. У OAuth-токена Почты могут отсутствовать разрешения Диска. Один Client
ID можно использовать совместно, только если приложение и выданный токен
включают указанные выше разрешения Диска.

## CLI

```bash
yandex-drive diagnose

yandex-drive download /reports/report.xlsx \
  --output ./downloads/report.xlsx

yandex-drive download /photos/image.png \
  --output ./downloads/image.png

yandex-drive upload ./archive.zip /backups/archive.zip --overwrite

yandex-drive metadata /backups/archive.zip --json
```

`metadata` работает и с файлами, и с каталогами. Имена без расширения допустимы
во всех командах, например: `yandex-drive upload ./data disk:/archive/data`.
Используйте `--env PATH`, `--verbose` или `--debug` перед командой.

## Python API

```python
from pathlib import Path

from yandex_drive import YandexDriveService

service = YandexDriveService.from_env(".env")
service.authorize()

data = service.download_file("/documents/report.pdf")

path = service.download_file_to(
    "/backups/archive.zip",
    Path("downloads/archive.zip"),
)

resource = service.upload_file(
    Path("image.png"),
    "/photos/image.png",
    overwrite=True,
)

copy = service.upload_bytes(data, "/documents/report-copy.pdf", overwrite=True)
print(resource.path, copy.size)
```

`download_file` намеренно загружает ответ целиком в память. Для больших
ресурсов используйте `download_file_to`: метод передаёт данные потоком во
временный файл в каталоге назначения и атомарно заменяет целевой файл только
после успешного завершения передачи.

## Обработка ошибок и встраивание

```python
from yandex_drive import (
    AuthenticationError,
    DownloadError,
    ResourceNotFoundError,
    UploadError,
    YandexDriveError,
)

try:
    data = service.download_file("/documents/report.pdf")
except ResourceNotFoundError:
    ...
except DownloadError:
    ...
except AuthenticationError:
    ...
except YandexDriveError:
    ...
```

Публичные методы сервиса ничего не выводят в стандартный поток. Можно внедрять
реализации хранилища токенов, OAuth-клиента, API-клиента, HTTP-сессии и
интерактивные callback-функции. Сервис подходит для бэкендов, воркеров,
планировщиков задач, скриптов и других CLI.

## Работа с файлами и безопасность

Файлы всегда обрабатываются как непрозрачные бинарные данные: SDK не разбирает
и не изменяет их, не накладывает ограничений на расширения, MIME-типы или
форматы. Поддерживаются пустые файлы и файлы без расширения. Локальные файлы
загружаются потоком, а `upload_bytes` использует бинарный поток в памяти.

Файлы токенов сохраняются атомарно: через временный файл в том же каталоге,
`fsync`, `os.replace` и права `0600` там, где они поддерживаются. Для временных
файлов загрузки применяется такая же безопасная очистка. После `401` клиент
повторяет только аутентифицированный запрос метаданных или временного URL; он
никогда не повторяет прямую, потенциально частично завершённую загрузку файла.
Учётные данные, OAuth-коды, подписанные URL передачи и содержимое файлов не
попадают в логи. См. [указатель документации](docs/README.md).
