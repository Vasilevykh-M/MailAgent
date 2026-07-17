# Справочник API

Базовый префикс рабочих эндпоинтов: `/api/v1`. Все ответы содержат заголовок `X-Request-ID`. Безопасный идентификатор из одноимённого заголовка входящего запроса сохраняется; в остальных случаях сервис создаёт UUID.

## Проверки состояния

### `GET /health/live`

Подтверждает, что процесс запущен. Не загружает модели и не выполняет сетевые операции.

```json
{"status":"ok"}
```

### `GET /health/ready`

Проверяет настройки, доступность каталогов моделей и временных файлов, а также реестр возможностей. Тяжёлые модели не загружаются.

```json
{"status":"ready","device":"cpu","loaded_models":0}
```

## Возможности

### `GET /api/v1/capabilities`

Возвращает поддерживаемые задачи, реальные идентификаторы моделей, доступные языки, значения по умолчанию, допустимые форматы и лимиты. Используйте этот эндпоинт вместо жёсткого кодирования значений на клиенте.

Текущие задачи:

- `ocr`: `pp-ocrv6` (`en`), `pp-ocrv5` (`en`, `ru`);
- `document_parsing`: `pp-structurev3` (`en`, `ru`).

## OCR

### `POST /api/v1/ocr`

Тип запроса: `multipart/form-data`.

| Поле | Обязательно | Описание |
| --- | --- | --- |
| `file` | Да | JPEG, PNG или PDF. |
| `model` | Нет | Идентификатор OCR-модели из `/capabilities`. |
| `language` | Нет | Совместимый с моделью язык. |
| `return_boxes` | Нет | По умолчанию `true`; включает полигоны строк. |
| `return_confidence` | Нет | По умолчанию `true`; включает оценку уверенности. |

Для PDF результат возвращается отдельно по каждой странице. Если `return_boxes=false` или `return_confidence=false`, соответствующее поле строки содержит `null`.

```json
{
  "request_id": "uuid",
  "task": "ocr",
  "model": "pp-ocrv5",
  "language": "ru",
  "page_count": 1,
  "text": "Распознанный текст",
  "pages": [{
    "page_index": 0,
    "width": 2480,
    "height": 3508,
    "text": "Распознанный текст",
    "lines": [{"text":"Распознанный текст","confidence":0.98,"polygon":[[10,10],[200,10],[200,40],[10,40]]}]
  }],
  "processing_time_ms": 1234
}
```

## Разбор документа

### `POST /api/v1/documents/parse`

Тип запроса: `multipart/form-data`.

| Поле | Обязательно | Описание |
| --- | --- | --- |
| `file` | Да | JPEG, PNG или PDF. |
| `model` | Нет | Идентификатор модели разбора документа. |
| `language` | Нет | Совместимый с моделью язык. |
| `output_format` | Нет | `json` (по умолчанию), `markdown` или `both`. |

Элемент может включать идентификатор, тип, текст, уверенность, координаты, порядок чтения, HTML таблицы, структурированные табличные данные, формулу и безопасные метаданные — если их предоставил PP-StructureV3.

При `output_format=json` Markdown не генерируется. При `markdown` и `both` ответ содержит поле верхнего уровня `markdown`.

## Ошибки

Все ошибки имеют единый формат:

```json
{
  "error": {
    "code": "unsupported_model",
    "message": "Model 'x' is not supported for task 'ocr'",
    "details": {},
    "request_id": "uuid"
  }
}
```

| HTTP | Примеры кодов | Причина |
| --- | --- | --- |
| `413` | `file_too_large` | Файл превышает лимит размера. |
| `415` | `unsupported_file_format` | MIME-тип, расширение или фактический формат не поддерживается. |
| `422` | `unsupported_model`, `unsupported_language`, `incompatible_model_language`, `corrupted_pdf` | Ошибка параметров, совместимости модели/языка или валидации содержимого. |
| `502` | `inference_failed` | PaddleOCR не смог завершить инференс. |
| `503` | `model_loading_failed`, `model_download_failed`, `unavailable_device`, `insufficient_gpu_memory` | Модель или устройство недоступны. |
| `504` | `inference_timeout` | Инференс превысил `REQUEST_TIMEOUT_SECONDS`. |
