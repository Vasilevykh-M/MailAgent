# Mail Agent Dashboard

Frontend dashboard для read-only просмотра результатов обработки писем из
Results API.

## Стек

- `React`
- `TypeScript`
- `Vite`
- `React Router`
- `TanStack Query`
- `Zod`
- `CSS Modules`
- `Recharts`
- `Vitest`
- `Oxlint`
- `Oxfmt`

## Локальный запуск

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Настройки:

```env
# Используется только в dev режиме. Preview/prod используют host frontend server и port 8080.
VITE_RESULTS_API_BASE_URL=http://192.168.88.32:8080
VITE_DEFAULT_MAILBOX=INBOX
VITE_ENABLE_API_MOCKS=true
```

В `npm run preview` и production build запросы к API строятся от
`window.location.protocol`, `window.location.hostname` и фиксированного port
`8080`. Например, если frontend открыт на `http://192.168.88.32:4173`, API будет
вызываться на `http://192.168.88.32:8080`. Для такого режима backend или reverse
proxy должны обслуживать `/health/*` и `/api/v1/*` на этом адресе.

Не храните `READER_API_KEY` в `VITE_*` переменных: такие значения попадают в
browser bundle. Для защищённого доступа нужен trusted LAN режим, reverse
proxy/BFF или другой server-side слой авторизации.

## Моки API

В dev режиме подключается `MSW` и имитирует Results API из `api_reference.md`.
Это позволяет разрабатывать dashboard без включённого backend.

- Моки запускаются только при `import.meta.env.DEV`.
- В `npm run preview` и production build моки не стартуют.
- Чтобы отключить моки в dev режиме, задайте `VITE_ENABLE_API_MOCKS=false`.
- Service worker лежит в `public/mockServiceWorker.js`.
- Mock login принимает любой непустой `username` и `password`.

## Аутентификация

- Страница `/login` вызывает `POST /api/v1/auth/login` с `username` и
  `password`.
- Полученный opaque token хранится в `localStorage` и передаётся во все API
  запросы как `Authorization: Bearer <access-token>`.
- При загрузке приложения сохранённая сессия проверяется через
  `GET /api/v1/auth/me`.
- Кнопка `Выйти` вызывает `POST /api/v1/auth/logout`, очищает локальный token и
  кеш запросов.

## Что уже работает

- Вход через пользовательскую Bearer-сессию Results API.
- Проверка готовности API через `/health/ready`.
- Фильтрация периода и `mailbox` через query параметры API.
- Локальный поиск по загруженным страницам списка.
- Локальные фильтры по вложениям, confidence и кешированному статусу detail.
- KPI по `/api/v1/statistics`.
- Графики по статусам и классам через `Recharts`; страница статистики
  загружается отдельным lazy chunk.
- Список писем с автоматической догрузкой следующих страниц.
- Выбор письма через route `/emails/:recordId`.
- Detail panel: summary, classification, key facts, warnings, content,
  attachment summaries, attachments и technical JSON.
- Скачивание вложений и исходного `.eml` через API download endpoints.

## Ограничения

- API не поддерживает server-side поиск по теме, отправителю или тексту.
- API не поддерживает server-side фильтры по `class_code`, `status`,
  `has_attachments`, `confidence`.
- API не отдаёт список mailbox, поэтому `mailbox` вводится вручную.
- Фильтр по статусу в UI работает только для писем, detail которых уже есть в
  TanStack Query cache.

## Команды

```bash
npm run dev
npm run build
npm run lint
npm run format
npm run test
npm run preview
```

## Документация

- `api_reference.md` — контракт Results API.
- `dashboard_plan.md` — план реализации dashboard.
- `design_system.md` — базовая дизайн-система и UI-принципы.
