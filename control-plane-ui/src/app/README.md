# Control Plane UI architecture

The Angular control plane uses standalone components organized by feature.

- `features/<name>/`: the 16 feature view templates and component declarations.
- `dialogs/execution-dialog/`: execution details and artifacts.
- `dialogs/editor-dialog/`: resource, process, governance and evaluation forms.
- `shared/control-plane-view.base.ts`: temporary compatibility adapter.
- `app.component.*`: application shell, navigation, polling and existing orchestration controller.
- `api.service.ts` and `models.ts`: unchanged API contracts.

This is a behavior-preserving template extraction; API endpoints, data model and UX are unchanged.
The shared view base forwards the existing controller's methods/state to feature templates,
including two-way form bindings. **This is a transitional architecture**: migrate feature
state/actions into typed feature facades, then remove the shared forwarding adapter.

Validation (must run in an environment with dependencies available):

```sh
cd control-plane-ui
npm ci
npm run build
```

Smoke-test navigation, process designer, execution explorer, approvals, CRUD,
session/memory screens, governance/evals, modal save/cancel flows.
