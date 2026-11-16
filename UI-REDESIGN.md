# UI redesign notes

## Flow
- Home (`/`) -> Internships (`/internships?stream=...`) -> Apply (`/apply?role=&stream=&classes=`) -> email after selection -> Login (`/login`) -> `/app` (student) or `/admin` (admin / mentor).
- Home also links to Programme (`/programme`: 30-day plan, optional classes, FAQ), the Pune class directory (`/classes`) and Register (`/register`).
- Register offers two paths: apply for an internship, or create a free account to review classes.
- Students and staff are separated by the existing role guard: students only reach `/app/*`, admins and mentors only `/admin/*`.

## Where things are
- `src/styles.css`: design tokens (indigo + coral on lavender), type scale, public navbar, phone bottom tabs, split-screen auth, dashboard shell.
- `src/catalog.js`: the three streams (CS & IT, Commerce, Arts), programme classes and FAQ. Roles still come from the admin Settings page and are grouped into streams by keyword.
- `src/components/Public.jsx`: `PublicShell` (navbar, mobile drawer, footer, bottom tabs). `AuthLayout.jsx`: sign-in / register layout.
- `src/App.jsx`: signed-in shell (light sidebar, top bar, bottom tabs on phones) and routes.

## Notes
- Stream and selected classes are written at the top of the application message, so no backend change is needed.
- Run `npm install && npm test` (backend running) to execute the smoke tests, three new ones cover the new pages.
