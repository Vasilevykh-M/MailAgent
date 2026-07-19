# План frontend dashboard

Документ описывает целевую архитектуру и пошаговый план реализации простого
read-only dashboard для просмотра результатов обработки писем. Базовый стек:
React + TypeScript.

## Цели

- Показать пользователю обработанные письма, их AI-сводки, классификацию,
  предупреждения и вложения.
- Дать быстрый обзор периода: количество писем, количество вложений,
  распределение по классам и статусам.
- Сохранить frontend простым: без сложного state management, без backend-логики
  в UI и без функций, которых нет в API.
- Учитывать реальные ограничения Results API: нет server-side поиска по тексту,
  нет фильтра по классу, нет списка mailbox, нет write-действий для frontend.

## Не цели MVP

- Ответы на письма, пересылка, изменение статусов писем.
- Ручная переклассификация писем.
- Редактирование summary, key facts или предупреждений.
- Загрузка новых писем или вложений.
- Управление пользователями и ролями.
- Сложная аналитика с произвольными drill-down запросами, которых API сейчас не
  поддерживает.

## Технологии

### Основной стек

- `React` — UI.
- `TypeScript` — строгие типы API и компонентов.
- `Vite` — сборка и dev server.
- `React Router` — маршруты dashboard и карточки письма.
- `TanStack Query` — загрузка, кеширование, refetch, состояния ошибок.
- `Zod` — runtime-валидация ответов API на границе клиента.
- `date-fns` — форматирование дат и работа с периодами.

### UI и стили

Рекомендуемый вариант для MVP:

- `Tailwind CSS` — быстрый, предсказуемый layout без тяжёлого UI framework.
- `lucide-react` — иконки.
- Небольшой набор собственных компонентов: `Button`, `Input`, `Select`, `Badge`,
  `Card`, `Table`, `Spinner`, `Alert`, `EmptyState`.

Причина: dashboard простой, а внешний UI-kit может добавить больше сложности,
чем пользы. Если позже потребуется ускорить визуальную полировку, можно добавить
`shadcn/ui`, но для первого этапа достаточно собственных компонентов на
Tailwind.

### Графики

- `Recharts` — простые bar/pie charts по `classifications`.

Причина: API отдаёт небольшие агрегаты, сложная BI-библиотека не нужна.

### Качество

- `ESLint` — статическая проверка TypeScript/React.
- `Prettier` — форматирование.
- `Vitest` — unit-тесты утилит, API client и mapper’ов.
- `React Testing Library` — тесты ключевых UI-состояний.

## Безопасность и доступ к API

Есть принципиальный нюанс: `READER_API_KEY` нельзя безопасно хранить в публичном
browser bundle. Любой ключ, переданный во frontend через env, будет доступен
пользователю в DevTools.

Допустимые варианты:

1. Доверенная LAN и `ALLOW_ANONYMOUS_READER=true`.
   - Самый простой вариант для локального dashboard.
   - Риск: каждый, кто имеет сетевой доступ к API, видит письма и вложения.

2. BFF/proxy для frontend.
   - Маленький server-side слой хранит `READER_API_KEY` и проксирует read-only
     запросы.
   - Безопаснее, но добавляет отдельный runtime.
   - Не должен импортировать `api-service`; только HTTP.

3. Reverse proxy с авторизацией.
   - Например, nginx/Caddy с basic auth, VPN или SSO перед dashboard/API.
   - Хороший вариант для внутренней сети.

Для MVP без отдельного backend разумное допущение: dashboard разворачивается в
доверенной сети, а доступ ограничивается сетью/VPN/firewall. Если потребуется
ключ, его нужно держать не в React-приложении, а на серверной стороне.

## Конфигурация frontend

Переменные окружения Vite:

```env
VITE_RESULTS_API_BASE_URL=http://192.168.88.32:8080
VITE_DEFAULT_MAILBOX=INBOX
```

Не рекомендуется:

```env
VITE_READER_API_KEY=...
```

Причина: значение попадёт в browser bundle.

Если всё же нужен режим ручного ключа для внутреннего dev-стенда, лучше сделать
его явно небезопасным и вводимым пользователем в UI/session storage, а не
коммитить в `.env`.

## Информационная архитектура

### Основной экран

Один dashboard layout:

- Верхняя панель:
  - название системы;
  - статус `/health/ready`;
  - выбранный base URL в техническом виде;
  - кнопка `Обновить`.

- Фильтры:
  - период: сегодня, 7 дней, 30 дней, текущий месяц, произвольный диапазон;
  - mailbox: поле/селект, по умолчанию `INBOX`;
  - локальный поиск по текущей загруженной странице: subject/from/summary;
  - локальный фильтр по статусу/классу для уже загруженных писем.

- KPI:
  - всего писем;
  - всего вложений;
  - писем `manual_review`;
  - писем `new_project`;
  - top class по количеству.

- Графики:
  - распределение по классам;
  - распределение по статусам.

- Список писем:
  - дата получения;
  - отправитель;
  - тема;
  - preview summary;
  - количество вложений;
  - confidence;
  - class/status, если письмо уже было открыто и detail закеширован.

- Детальная область:
  - карточка выбранного письма;
  - summary;
  - classification;
  - key facts;
  - warnings;
  - content;
  - attachments;
  - technical details.

### Навигация

Минимальные маршруты:

- `/` — dashboard со списком и выбранным письмом.
- `/emails/:recordId` — тот же dashboard layout, но выбранное письмо задаётся из
  URL.

Такой подход позволяет копировать ссылку на письмо без усложнения приложения.

## Маппинг API на UI

### `GET /api/v1/statistics`

Использование:

- KPI.
- Графики.
- Общая оценка потока писем за период.

Поля:

- `total_emails` → KPI `Писем`.
- `total_attachments` → KPI `Вложений`.
- `classifications[]` → bar/pie charts.
- `classifications[].status` → статусные бейджи.
- `classifications[].class_name_ru` → подписи классов.
- `classifications[].class_code` → стабильный внутренний ключ.

Ограничение:

- Нельзя кликнуть по сегменту графика и гарантированно получить список писем
  этого класса без нового backend endpoint. В MVP клик может только включать
  локальный фильтр по уже загруженным detail/list данным.

### `GET /api/v1/emails`

Использование:

- Основная лента/таблица писем.
- Пагинация через `next_cursor`.

Поля:

- `id`/`record_id` → ключ строки и ссылка на detail.
- `received_at` → дата/время.
- `from` → отправитель.
- `subject` → тема.
- `summary_preview` → краткое описание.
- `attachment_count` → бейдж вложений.
- `confidence` → индикатор уверенности.

Ограничение:

- Список не содержит полной классификации. Если нужно показывать класс в каждой
  строке, frontend должен либо:
  - отображать класс только после открытия письма;
  - подгружать detail для видимых строк, что увеличит число запросов;
  - запросить доработку API списка.

Рекомендация MVP:

- Не делать массовую догрузку detail для всех строк.
- Показывать в списке только поля list endpoint.
- Класс и статус показывать в detail.

### `GET /api/v1/emails/{record_id}`

Использование:

- Полная карточка письма.
- Вложения и ссылки скачивания.
- Техническая информация.

Поля верхнего уровня:

- `subject`, `from`, `received_at` → header карточки.
- `summary` → основной AI-вывод.
- `classification` → класс, статус, причина, confidence.
- `key_facts` → список фактов.
- `warnings` → заметный блок предупреждений.
- `content` → нормализованное тело письма.
- `attachments` → список вложений.
- `raw_download_url` → скачать `.eml`.

Технические поля:

- `record_id`.
- `processed_at`.
- `mailbox`.
- `uid`.
- `message_id`.
- `pipeline_version`.
- `processing_generation`.
- `original_email`.
- `agent_result`.

Рекомендация MVP:

- `original_email` и `agent_result` скрывать в collapsible `Технические данные`.
- `text_html` не рендерить как HTML. Показывать только как escaped text, если
  вообще нужно показывать.

### Download endpoints

Использование:

- `attachments[].download_url` → кнопка скачивания вложения.
- `raw_download_url` → кнопка скачивания исходного `.eml`.

Нюансы:

- URL относительные, frontend должен преобразовывать их в absolute URL через
  `new URL(path, apiBaseUrl)`.
- Ответ не JSON, а stream.
- Если нужна авторизация header’ом, обычная ссылка `<a href>` не сможет добавить
  `X-API-Key`. Тогда нужно скачивать через `fetch` с headers и создавать
  `Blob URL`.
- Если используется anonymous reader или cookie/reverse proxy auth, можно
  использовать обычную ссылку.

## Компонентная структура

```text
src/
  app/
    App.tsx
    router.tsx
    providers.tsx
  api/
    client.ts
    schemas.ts
    types.ts
    errors.ts
    downloads.ts
  features/
    dashboard/
      DashboardPage.tsx
      DashboardFilters.tsx
      StatisticsCards.tsx
      ClassificationChart.tsx
      EmailList.tsx
      EmailDetailPanel.tsx
      AttachmentsList.tsx
      TechnicalDetails.tsx
  shared/
    ui/
      Alert.tsx
      Badge.tsx
      Button.tsx
      Card.tsx
      EmptyState.tsx
      Input.tsx
      Select.tsx
      Spinner.tsx
    lib/
      date.ts
      format.ts
      queryKeys.ts
      url.ts
```

## Типы данных

Базовые типы должны соответствовать `api_reference.md`:

- `EmailListResponse`.
- `EmailListItem`.
- `EmailDetail`.
- `Attachment`.
- `StatisticsResponse`.
- `ClassificationStatisticsItem`.
- `ApiError`.

Для `classification` лучше начать с гибкого типа:

```ts
type Classification = {
  status?: 'classified' | 'new_project' | 'manual_review' | string
  class_code?: string | null
  class_name_ru?: string | null
  reason_ru?: string | null
  confidence?: number | null
  message_ru?: string | null
}
```

Причина: backend хранит `classification` как гибкий объект внутри
`agent_result`. Жёсткая схема может ломаться при расширении полей.

## State management

Использовать URL + TanStack Query:

- `from`, `to`, `mailbox`, `selectedEmailId` хранить в URL query/path.
- Загруженные данные хранить в кеше TanStack Query.
- Локальные UI-состояния хранить в React state:
  - открыт/закрыт technical block;
  - локальная строка поиска;
  - локальный фильтр текущей страницы;
  - режим отображения списка.

Не использовать Redux/Zustand в MVP: состояние несложное и в основном серверное.

## Обработка состояний

Каждый блок должен иметь отдельные состояния:

- loading;
- error;
- empty;
- stale/refetching;
- success.

Примеры:

- Если `/statistics` упал, список писем всё равно должен отображаться.
- Если detail письма упал с `not_found`, показывать понятное сообщение и
  предлагать вернуться к списку.
- Если `/health/ready` вернул `unavailable`, не блокировать весь dashboard, а
  показать предупреждение.

## Форматирование и отображение

### Даты

- API возвращает timezone-aware ISO datetime.
- В UI показывать локальное время пользователя.
- В tooltip или technical mode можно показывать исходное ISO значение.

### Confidence

Рекомендуемые пороги:

- `>= 0.8` — высокий.
- `>= 0.5` и `< 0.8` — средний.
- `< 0.5` — низкий.
- `null`/`undefined` — нет оценки.

### Вложения

Показывать:

- `filename`;
- `summary`;
- `key_facts`;
- `size`;
- `detected_content_type`;
- checksum `sha256` только в technical mode.

### Предупреждения

- Всегда показывать выше тела письма.
- Визуально отделять от обычных key facts.
- `manual_review` также должен быть заметным статусом.

## API client

Функции:

- `getHealthReady()`.
- `getEmails(params)`.
- `getEmail(recordId)`.
- `getStatistics(params)`.
- `downloadAttachment(url, filename?)`.
- `downloadRawEmail(url)`.

Требования:

- Централизованно добавлять base URL.
- Централизованно обрабатывать `ApiError`.
- Не логировать содержимое писем, headers, тело ответа, вложения или ключи.
- Для JSON-ответов валидировать Zod-схемами.
- Для download endpoints не пытаться парсить JSON при успешном ответе.

## Пагинация

MVP:

- Кнопка `Загрузить ещё`.
- Хранить массив загруженных страниц в TanStack Query infinite query.
- Передавать `cursor=next_cursor`, пока `has_more=true`.

Не делать offset pagination: API использует opaque keyset cursor.

## Фильтрация

Server-side:

- `from`.
- `to`.
- `mailbox`.
- `limit`.
- `cursor`.

Client-side для уже загруженных данных:

- поиск по `subject`, `from`, `summary_preview`;
- фильтр по низкому confidence;
- фильтр по наличию вложений;
- фильтр по классам только для писем, у которых уже есть detail в кеше.

Важно явно подписать такие фильтры как локальные, чтобы пользователь не думал,
что фильтруется вся база.

## UX ограничения, которые нужно явно учесть

- При смене периода или mailbox сбрасывать cursor и выбранное письмо, если оно
  не относится к текущему набору.
- При пустом списке показывать `За выбранный период писем нет`.
- При `unauthorized` показывать проблему доступа, а не технический stack trace.
- При `storage_unavailable` показывать, что данные временно недоступны.
- При download error показывать отдельное уведомление, не перезагружая страницу.
- Если `classification` равен `null`, показывать `Классификация отсутствует`.

## Accessibility

- Все интерактивные элементы доступны с клавиатуры.
- Таблица писем имеет корректные заголовки.
- Цветовые статусы дублируются текстом.
- У графиков есть текстовая таблица/легенда.
- Кнопки скачивания имеют понятные label.

## Производительность

- Не загружать detail для всех писем сразу.
- Использовать lazy loading detail только при выборе письма.
- Ограничить `limit` по умолчанию значением `25` или `50`.
- Использовать skeleton/loading states вместо блокировки всего экрана.
- Не рендерить большие `original_email`/`agent_result` по умолчанию.

## Тестирование

Минимальный набор:

- API client:
  - корректная сборка URL;
  - обработка JSON ошибок;
  - Zod-валидация ответов;
  - download через относительный URL.

- Mappers/formatters:
  - форматирование дат;
  - форматирование размера файла;
  - confidence label/color;
  - classification label fallback.

- UI:
  - dashboard показывает loading/error/empty/success;
  - список писем отображает данные list endpoint;
  - detail panel отображает summary, classification, warnings, attachments;
  - statistics cards отображают агрегаты;
  - `Load more` использует `next_cursor`.

## Пошаговая реализация

### Этап 1. Scaffold

- Создать Vite React + TypeScript проект внутри `frontend/`.
- Настроить `package.json`, `tsconfig`, `vite.config.ts`.
- Добавить ESLint, Prettier.
- Добавить Tailwind CSS.
- Добавить базовый layout приложения.

### Этап 2. API слой

- Описать TypeScript-типы API.
- Добавить Zod-схемы для runtime validation.
- Реализовать `api/client.ts`.
- Реализовать централизованную обработку ошибок.
- Реализовать helper для absolute download URL.

### Этап 3. Query слой

- Подключить TanStack Query provider.
- Сделать query keys.
- Реализовать hooks:
  - `useHealthReady`;
  - `useStatistics`;
  - `useEmailsInfinite`;
  - `useEmailDetail`.

### Этап 4. Базовый dashboard

- Собрать layout: header, filters, KPI, list, detail placeholder.
- Подключить `/statistics`.
- Подключить `/emails`.
- Добавить `Load more`.

### Этап 5. Карточка письма

- Подключить `/emails/{record_id}`.
- Реализовать detail panel.
- Добавить blocks: summary, classification, key facts, warnings, content.
- Добавить attachments list.
- Добавить technical details accordion.

### Этап 6. Downloads

- Реализовать скачивание вложений.
- Реализовать скачивание `.eml`.
- Учесть два режима:
  - обычная ссылка при anonymous/proxy auth;
  - `fetch` + Blob при header auth.

### Этап 7. Локальные фильтры и polish

- Добавить локальный поиск по текущей странице.
- Добавить фильтр по наличию вложений.
- Добавить фильтр по confidence.
- Добавить пустые состояния и понятные ошибки.
- Добавить responsive layout.

### Этап 8. Тесты и документация

- Добавить unit-тесты API client/formatters.
- Добавить базовые UI-тесты.
- Добавить `frontend/README.md` с запуском, env и режимами авторизации.
- Проверить `npm run lint`, `npm run test`, `npm run build`.

## Потенциальные доработки API

Эти пункты не блокируют MVP, но улучшат dashboard:

- `GET /api/v1/mailboxes` — список mailbox.
- `GET /api/v1/classes` — список классов и русских названий.
- Server-side фильтры для `/emails`:
  - `status`;
  - `class_code`;
  - `has_attachments`;
  - `min_confidence`;
  - `search`.
- Добавить в list endpoint поля `classification.status`, `class_code`,
  `class_name_ru`.
- Endpoint таймсерии для графика писем по дням.
- Endpoint экспорта CSV для выбранного периода.

## Рекомендуемый MVP scope

Для первой рабочей версии достаточно:

- Vite + React + TypeScript.
- Один экран dashboard.
- Период + mailbox фильтр.
- Health indicator.
- KPI и классификационная диаграмма.
- Список писем с пагинацией.
- Detail panel выбранного письма.
- Вложения и скачивание.
- Technical details accordion.

Всё остальное лучше добавлять после проверки MVP на реальных данных.
