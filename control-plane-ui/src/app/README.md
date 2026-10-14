# Control Plane UI structure

Angular 20 standalone components, organized around control-plane capabilities rather than a single giant template.

## Layout

- `app.component.html`: application shell, navigation, and mounting active views/dialogs.
- `app.component.ts`: shared application state, polling, cross-feature orchestration and the existing public method surface.
- `features/<feature>/<feature>-view.component.{ts,html}`: a small, focused view for each feature (16).
- `features/<feature>/*.actions.ts`: domain operations delegated by the controller. Process operations are split into definitions, services, instances and presentation; resource operations are under `features/resources/`.
- `dialogs/execution-dialog/`: execution inspection.
- `dialogs/editor-dialog/`: common modal chrome and footer, composed from 8 focused, independently compiled domain forms.
- `api.service.ts` and `models.ts`: shared HTTP API and data contracts, intentionally unchanged.

Each child component receives a **typed** `AppComponent` input. There is **no generic `any`-based forwarding adapter**. Existing signals remain shared through the parent controller to preserve form bindings, polling and cross-screen actions, while feature/domain operations now live in dedicated files. This is a non-routing application.

Domain actions are pure module-level entry points bound to the controller, not independent injected state stores. This intentional migration seam retains existing behavior but should be revisited if the platform grows further: feature-owned facades with explicit typed inputs/outputs can eventually replace the remaining shared controller.

## Build verification

The `Control Plane UI build` GitHub Actions workflow installs dependencies and runs the Angular production build for pushes to `refactor/control-plane-ui` and pull requests.

```sh
cd control-plane-ui
npm install
npm run build
```

## Manual regression checklist

1. Navigate all 16 views; verify data and active navigation.
2. Create and inspect executions; review orchestration, artifacts, output Markdown and retry/pause controls.
3. Review and approve/reject an approval with comment.
4. Create/edit agent and skill assignments, prompts, tools, MCP servers and knowledge resources.
5. Create/inspect sessions; create/search/revoke memories.
6. Create/edit process definitions and steps; activate and run a process; inspect instances and human tasks.
7. Create/edit governance policies and budgets; run and inspect evaluations.
8. Open and cancel every editor modal; confirm saves refresh resource lists.
9. Check the Runtime health overview and refresh/polling behavior.

The build verifies template/type integrity but **does not** establish backend integration correctness or visual parity. A browser smoke run against the full stack is still necessary.
