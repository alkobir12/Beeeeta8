# 05 — Frontend Integration Map

**Source files**:
- `/app/frontend/src/App.js`
- `/app/frontend/src/components/Layout.jsx`
- `/app/frontend/src/components/assistant/AssistantProvider.jsx`
- `/app/frontend/src/components/assistant/UnifiedAssistantDrawer.jsx`
- `/app/frontend/src/hooks/useAssistant.js` (re-export only)
- `/app/frontend/package.json`

## Mount points

| Layer | Component | File | Line |
|---|---|---|---|
| App-root provider | `<AssistantProvider>` wraps the whole React tree | `App.js` | 182–249 |
| Per-page UI | `<UnifiedAssistantDrawer />` rendered inside `<Layout>` | `Layout.jsx` | 334 |
| Route exclusion | `isEditorWorkspace` flag drops the drawer | `Layout.jsx` | 45 + 334 |

```
App
├── ErrorBoundary
│   └── QueryClientProvider
│       └── ThemeProvider
│           └── AssistantProvider  ← shared sessionId / messages / alerts
│               └── Router
│                   └── <Routes>
│                       ├── /login          (NO Layout → NO bot)
│                       ├── /approval/:token (NO Layout)
│                       ├── /report/:token   (NO Layout)
│                       ├── /track/:trackingId (NO Layout)
│                       └── /* (Protected → <Layout>)
│                              └── <Outlet />
│                              └── <UnifiedAssistantDrawer />  ← unless isEditorWorkspace
```

## Per-route visibility

| Route / Page | FAB Visible? | Drawer Available? | Page-aware Suggestions? | Notes |
|---|---|---|---|---|
| `/` (Dashboard) | ✅ | ✅ | ✅ (default suggestions) | wrapped by `<Layout>` |
| `/customers` | ✅ | ✅ | ✅ (4 AR-focused chips) | |
| `/suppliers` | ✅ | ✅ | ✅ (4 AP-focused chips) | |
| `/parts` | ✅ | ✅ | ✅ (4 inventory chips) | |
| `/parts-dashboard` | ✅ | ✅ | ✅ (default — no `/parts-dashboard` prefix specialised) | |
| `/operations` | ✅ | ✅ | ✅ (4 ops chips) | |
| `/accounting/firewall` | ✅ | ✅ | ✅ (4 firewall chips) | |
| `/accounting/chart-of-accounts` | ✅ | ✅ | default | |
| `/accounting/journal-entries` | ✅ | ✅ | default | |
| `/accounting/comprehensive` | ✅ | ✅ | default | |
| `/finance/invoices` | ✅ | ✅ | default | |
| `/finance/taxes` | ✅ | ✅ | default | |
| `/technicians` | ✅ | ✅ | default | |
| `/vehicle/:id` | ✅ | ✅ | default | |
| `/customer/:id` | ✅ | ✅ | default | |
| `/debts-followup` | ✅ | ✅ | default | |
| `/parts` | ✅ | ✅ | parts-specific | |
| `/services` | ✅ | ✅ | default | |
| `/settings` | ✅ | ✅ | default | |
| `/archive` | ✅ | ✅ | default | |
| `/quotations` | ✅ | ✅ | default | |
| `/invoice-templates` | ✅ | ✅ | default | |
| `/print` | ✅ | ✅ | default | |
| `/templates` | ✅ | ✅ | default | |
| `/database-setup` | ✅ | ✅ | default | |
| `/denso-diagnostics` | ✅ | ✅ | default | |
| `/fault-knowledge` | ✅ | ✅ | default | |
| `/moltbot` | ❌ | ❌ | — | excluded by `isEditorWorkspace === true` |
| `/system-audit` | ✅ | ✅ | default | |
| `/login` | ❌ | ❌ | — | not in `<Layout>` |
| `/track/:trackingId` (public customer tracking) | ❌ | ❌ | — | not in `<Layout>` — no auth, no bot |
| `/approval/:token` | ❌ | ❌ | — | public route |
| `/report/:token` | ❌ | ❌ | — | public route |

## FAB & drawer DOM contract

| `data-testid` | Element | Purpose |
|---|---|---|
| `unified-assistant-fab` | `<button>` bottom-right | Opens drawer |
| `assistant-fab-badge` | `<span>` on FAB | Shows critical-alert count |
| `unified-assistant-drawer` | `<div>` 420×640 | The drawer itself |
| `assistant-settings-btn` | `<button>` in header | Toggles tiny settings panel |
| `assistant-close-btn` | `<button>` in header | Closes drawer |
| `assistant-settings-panel` | `<div>` | Shows message count + reset button |
| `assistant-reset-btn` | `<button>` | Clears the current session |
| `assistant-messages` | `<div>` | Scroll container of messages |
| `assistant-msg-{i}` | `<div>` | Individual message |
| `assistant-msg-body-{i}` | `<div>` | Markdown-rendered body (assistant only) |
| `assistant-typing` | `<div>` | "يفكّر..." typing indicator |
| `assistant-suggestion-{i}` | `<button>` | Starter chip |
| `assistant-input` | `<input>` | Text field |
| `assistant-send-btn` | `<button>` | Send |

## Markdown rendering

| Library | Version (package.json) | Status |
|---|---|---|
| `react-markdown` | ^10.1.0 | ✅ installed |
| `remark-gfm` | ^4.0.1 | ✅ installed |

Configured in `UnifiedAssistantDrawer.jsx::MD_COMPONENTS` (~line 47) with
custom components for `p`, `strong`, `em`, `ul`, `ol`, `li`, `code`, `pre`,
`table`, `th`, `td`, `a`. Wired in via `<ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>`.

✅ Renders GFM tables, **bold**, inline `code`, lists, and external links.

User messages render as plain `whitespace-pre-wrap` text (no markdown,
correct for user input).

## Suggestion chips

✅ Yes — `SUGGESTIONS_BY_PATH` map + `getSuggestionsForPath()` selects 4–5
starter chips based on `useLocation().pathname`. See `01_FLOATING_BOT_CAPABILITY_MAP.md`
for the full mapping.

The chips:
- Render only when `messages.length === 0` (empty state).
- Disappear after the first user/assistant exchange.
- Click → calls `handleSuggestion(text)` → `sendMessage(text)` (clears input).

## Streaming UI

❌ **None.** The drawer awaits the full `POST /api/assistant/chat` response.
While waiting, `<div data-testid="assistant-typing">` shows a spinner + "يفكّر...".

The single full response is then appended atomically via `setMessages([...prev, assistantMsg])`.

## Provider behaviour (`AssistantProvider.jsx`)

| State | Source | Persistence |
|---|---|---|
| `sessionId` | `useState` initialised from `localStorage.assistant.session_id` | localStorage — survives reload |
| `messages` | `useState([])`; rehydrated on mount via `GET /api/assistant/session/{sid}` | server (with TTL 1h) + optimistic local |
| `open` | `useState(false)` | not persisted; resets on reload |
| `busy` | `useState(false)` | runtime only |
| `activeAgent` | `useState(null)` | runtime only |
| `alerts` | `useState([])`; fetched from `GET /api/assistant/alerts` (debounced 8s) | runtime only |
| `stats` | `useState(null)`; fetched once on mount from `GET /api/assistant/stats` | runtime only |

Events:
- Listens to `window.addEventListener('finance:updated', ...)` → debounced re-fetch of alerts.
- Listens to `Ctrl+Shift+B` global keyboard shortcut → toggles drawer.

## Other "bot" components in the codebase

| Component | File | Mounted in production tree? |
|---|---|---|
| `UnifiedBotWidget.jsx` | `/app/frontend/src/components/` | **No** — referenced only in legacy comments; `Sidebar.jsx` confirms "أُزيل من القائمة الجانبية — البوتات أصبحت موحدة في UnifiedAssistantDrawer". |
| `MoltBot` page | `/app/frontend/src/pages/MoltBot.jsx` | Yes, but excluded from floating bot (route `/moltbot`). |

## Summary

- **One** floating bot mounted: `UnifiedAssistantDrawer` inside `Layout`.
- **Provider** wraps the entire app → shared session/state across routes.
- **Excluded routes**: `/moltbot`, `/login`, `/approval/:token`, `/report/:token`, `/track/:trackingId`.
- **Markdown rendering**: enabled via react-markdown + remark-gfm.
- **Page-aware suggestions**: implemented for 5 route prefixes.
- **Streaming UI**: not implemented (full-response only).
