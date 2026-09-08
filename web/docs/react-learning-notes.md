# React Learning Notes

This UI intentionally uses small, direct patterns before extracting reusable
modules.

## Component and props

`src/components/HealthCard.tsx` is a React component. Its `title`, `status` and
`detail` props are a TypeScript interface describing what a parent must pass.

## Local state

`src/pages/StartRunPage.tsx` stores checkbox choices in
`Record<string, boolean>`. This is local UI state: it exists only while the
form is open. `profileIdsFromSelection` turns it into the API `profile_ids`
array at submit time.

## TypeScript DTOs

`src/types/api.ts` contains the shared shapes returned by Orchestrator, such as
`SystemHealth` and `PipelineRunDetail`. Keeping them in one place avoids `any`
and duplicate interfaces.

## React Query: server state

`src/hooks/useOrchestrator.ts` reads server state with `useQuery` and starts a
run with `useMutation`. Server state belongs to Orchestrator and can become
stale; local checkbox state belongs to the component.

## Polling

`useRun(runId)` passes `runPollingInterval` to React Query. It requests a short
run-status endpoint every four seconds only while a run is `accepted` or
`running`; terminal states return `false` and stop polling.

## Routing

`src/app/router.tsx` maps URLs to pages. `:runId` is a route parameter read in
`RunDetailPage` with `useParams`.

## Detail pages

`src/pages/VacancyDetailPage.tsx` reads `presentationKey` from the route and
passes it to `useVacancyDetail`. The query key identifies one server entity,
while conditional rendering keeps loading, not-found, error and success states
separate. A list link stores its current URL in Router state, so the back link
can preserve filters without global state.

`src/components/VacancyDescription.tsx` renders saved vacancy content as React
text, not with `dangerouslySetInnerHTML`. Current Orchestrator descriptions are
normalized text; should an unexpected HTML fragment arrive, React displays it
without executing tags or handlers.

## Lists, filters and pagination

`src/pages/VacanciesPage.tsx` renders `items.map(...)` from the paginated
Orchestrator response. Its filter values live in React Router search params, so
refresh, browser navigation and a copied URL retain the current list view.
`useVacancies(filters)` includes the filter object in its React Query key: a
different period, profile or page is different server state and receives its
own request. `src/features/vacancies/dateFilters.ts` keeps the date-preset
calculation small and testable for later reuse by Statistics.

## Mutations and controlled forms

`src/components/ApplicationSection.tsx` keeps Application form values in
`useState`, so text survives a failed save. `useCreateApplication` and
`useUpdateApplication` use React Query `useMutation`; an edit builds a partial
PATCH payload, where omitted fields remain unchanged and a cleared nullable
field becomes `null`. On success the hooks invalidate the vacancy detail,
Vacancies list, and Applications list instead of maintaining a second local
copy of server data.

`src/components/ApplicationStatusBadge.tsx` is one shared status mapping used
by Vacancy Detail, Vacancies, and `/applications`. The special text `Без
отклика` is a UI presentation for a missing record, not an Application status.

`src/pages/ApplicationsPage.tsx` is another URL-synchronised list. Its
application filters and pagination are query state, while the API returns a
backend-owned `presentation_key` for navigation to the grouped vacancy detail.

## Build-time environment

`VITE_API_BASE_URL` is read by `src/api/client.ts`. Vite puts it into the
compiled browser bundle, so it is public configuration and Docker must rebuild
after it changes.

Potential patterns for a later extraction: typed API client, `HealthCard`,
`RunStatusBadge`, shared states, run polling, profile-selection form,
`DateRangeFilter`, `FilterBar`, simple data table, pagination and URL-synced
filters, entity detail header, metadata sidebar, safe rich-text renderer,
back navigation with preserved filters, CRUD detail form, shared status badge,
mutation plus invalidation, URL enum filter and entity-list-to-detail navigation.
