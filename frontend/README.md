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
VITE_RESULTS_API_BASE_URL=http://192.168.88.32:8080
VITE_DEFAULT_MAILBOX=INBOX
```

Не храните `READER_API_KEY` в `VITE_*` переменных: такие значения попадают в
browser bundle. Для защищённого доступа нужен trusted LAN режим, reverse
proxy/BFF или другой server-side слой авторизации.

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
