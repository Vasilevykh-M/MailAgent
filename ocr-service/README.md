# FastAPI-сервис PaddleOCR

Изолированный HTTP-сервис для двух официальных конвейеров PaddleOCR 3.7.0:

- стандартное OCR через `PaddleOCR` (`/api/v1/ocr`);
- разбор структуры документов через `PPStructureV3` (`/api/v1/documents/parse`).

Публичный API остаётся стабильным при изменении внутренней структуры результатов PaddleOCR: адаптеры создают конвейеры, а нормализаторы формируют документированные JSON-схемы. Роутеры не создают объекты PaddleOCR напрямую.

## Архитектура

`роуты FastAPI → ProcessingService → проверка файлов / реестр возможностей / ModelManager → адаптеры PaddleOCR → нормализаторы результатов`

`CapabilitiesRegistry` — единый источник сведений о задачах, идентификаторах моделей, языках, значениях по умолчанию и совместимости задачи с моделью. `ModelManager` лениво создаёт конвейер при первом использовании, предотвращает дублирующую загрузку блокировкой по ключу, кэширует экземпляры по задаче/модели/языку/устройству/параметрам и вытесняет неиспользуемые записи по LRU. `InferenceLimiter` выполняет блокирующие операции в потоках, ограничивает параллелизм и сериализует доступ к каждому экземпляру конвейера.

Сервис принимает JPEG, PNG и PDF. Загрузки читаются порциями с ограничением размера; проверяются MIME-тип, расширение и сигнатура файла; изображения валидируются Pillow, а PDF — pypdf. Количество страниц PDF ограничено, а временный файл PDF с случайным именем удаляется в блоке `finally`. Документы пользователей и извлечённый текст не сохраняются и не попадают в логи.

## Требования и установка

Требуется Python **3.11–3.13**. По умолчанию устанавливается CPU-вариант.

```bash
cd ocr-service
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install '.[dev]'
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Зафиксированные зависимости времени выполнения: Python 3.11+, FastAPI 0.115.12, Uvicorn 0.34.3, Pydantic 2.11.5, PaddleOCR 3.7.0 с официальной дополнительной группой `doc-parser`, PaddlePaddle 3.3.0 (CPU), Pillow 11.2.1 и pypdf 5.5.0. В `uv.lock` зафиксировано полное разрешённое дерево зависимостей; оно используется при Docker-сборке.

PaddleOCR загружает артефакты модели при первом запросе к ней. Они сохраняются в `PADDLE_MODEL_HOME` через `PADDLE_PDX_CACHE_HOME` от PaddleX; в production следует подключить этот каталог как постоянный том. Проверка готовности не загружает и не инициализирует модели.

### GPU

Набор зависимостей по умолчанию намеренно содержит только CPU-версию PaddlePaddle. Для совместимой установки NVIDIA/CUDA замените `paddlepaddle==3.3.0` на точный GPU-wheel, указанный в [официальном мастере установки PaddlePaddle](https://www.paddlepaddle.org.cn/en/install/quick), затем установите `PADDLE_DEVICE=gpu:0` и `MAX_CONCURRENT_INFERENCES=1`. Не устанавливайте CPU- и GPU-wheel PaddlePaddle одновременно.

На CPU oneDNN/MKL-DNN выключен по умолчанию (`PADDLE_ENABLE_MKLDNN=false`): это обходит известный сбой Paddle при выполнении некоторых моделей через новый PIR-исполнитель. Включайте его только после проверки реальным запросом к OCR.

Для CPU-развёртывания на Linux подготовлен несекретный
[cpu.env.example](cpu.env.example): он открывает сервис для агента на отдельном
хосте, использует русскоязычные модели и ограничивает инференс и кэш моделей
единицей. Доступ к TCP/8000 необходимо ограничить firewall только IP агента.
CPU- и GPU-варианты `paddlepaddle` нельзя устанавливать в одном окружении.

## Настройка

Скопируйте `.env.example` и при необходимости измените значения.

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `PADDLE_DEVICE` | `cpu` | Устройство Paddle; `gpu:0` включает настроенный GPU. |
| `PADDLE_ENABLE_MKLDNN` | `false` | Использовать oneDNN/MKL-DNN на CPU. По умолчанию выключен для совместимости с PIR. |
| `PADDLE_MODEL_HOME` | `./models` | Доступный для записи постоянный кэш моделей PaddleX. |
| `PADDLE_MODEL_SOURCE` | `huggingface` | Источник моделей PaddleX: `huggingface`, `bos`, `modelscope` или `aistudio`. |
| `MAX_UPLOAD_SIZE_MB` | `25` | Строгое ограничение размера потоковой загрузки. |
| `MAX_PDF_PAGES` | `50` | Максимальное количество принимаемых страниц PDF. |
| `MAX_CONCURRENT_INFERENCES` | `2` | Общее для процесса ограничение параллельных инференсов. |
| `MODEL_CACHE_SIZE` | `4` | Ёмкость LRU-кэша конвейеров. |
| `REQUEST_TIMEOUT_SECONDS` | `300` | Тайм-аут одного инференса. Поток с истёкшим тайм-аутом удерживает блокировки до завершения. |
| `TEMP_DIR` | `<model home>/tmp` | Закрытый каталог для временных PDF. |
| `DEFAULT_*` | см. `.env.example` | Допустимая модель/язык по умолчанию для задачи. |

## API

Каждый ответ содержит заголовок `X-Request-ID`. Чтобы сохранить свой безопасный идентификатор, передайте его в одноимённом заголовке запроса. Ошибки имеют вид:

```json
{"error":{"code":"unsupported_model","message":"Model 'x' is not supported for task 'ocr'","details":{},"request_id":"uuid"}}
```

Опции OCR `return_boxes=false` и `return_confidence=false` возвращают `null` в соответствующих полях строк. При `output_format=json` Markdown не генерируется; при `markdown` и `both` добавляется поле верхнего уровня `markdown`.

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/v1/capabilities

curl -X POST http://localhost:8000/api/v1/ocr \
  -F file=@sample.png \
  -F model=pp-ocrv5 \
  -F language=ru \
  -F return_boxes=true \
  -F return_confidence=true

curl -X POST http://localhost:8000/api/v1/documents/parse \
  -F file=@document.pdf \
  -F model=pp-structurev3 \
  -F language=en \
  -F output_format=json

curl -X POST http://localhost:8000/api/v1/documents/parse \
  -F file=@document.png \
  -F output_format=markdown
```

Ответ OCR содержит `pages[].lines[]` с нормализованным текстом, необязательной уверенностью и необязательными полигонами. Ответ разбора документа содержит `pages[].elements[]` со стабильными идентификаторами, типом, текстом, координатами, порядком чтения, таблицами/формулами там, где их возвращает PP-StructureV3, а также необязательным Markdown. Сгенерированный контракт OpenAPI и примеры доступны по `/docs`.

## Тесты и проверки

```bash
cd ocr-service
ruff format --check app tests
ruff check app tests
pytest
python -c 'from app.main import app; print(sorted(route.path for route in app.routes))'
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Модульные и API-тесты подставляют лёгкие имитации адаптеров, поэтому не загружают модели, не требуют GPU и доступа к сети. Smoke-тест с реальной моделью намеренно помечен и по умолчанию пропускается:

```bash
RUN_PADDLE_SMOKE=1 pytest -m integration
```

## Docker

```bash
cd ocr-service
docker build -t ocr-service .
docker run --rm -p 8000:8000 \
  -v paddle-models:/models \
  --env-file .env \
  ocr-service
```

Образ использует только CPU, запускается от непривилегированного пользователя, подключает `/models` для постоянного хранения весов, исключает локальные файлы окружения и документы, а также проверяет `/health/live`. Файл Compose не добавлен, поскольку в репозитории нет общей конфигурации Compose.

## Ограничения

PP-StructureV3 требует заметных ресурсов CPU/RAM и при первом запросе может загрузить несколько подмоделей; для постоянного разбора документов настоятельно рекомендуется GPU. Результаты зависят от качества документа и языков, поддерживаемых официальной моделью. После локальной структурной проверки PDF передаются официальным конвейерам; слишком большие файлы, PDF с превышенным количеством страниц, повреждённые PDF и неподдерживаемые форматы отклоняются до инференса.

## Дополнительная документация

- [Навигация по документации](docs/README.md)
- [Архитектура](docs/architecture.md)
- [Справочник API](docs/api.md)
- [Эксплуатация и развёртывание](docs/operations.md)
