# Phase 1: foundation

## Architecture

The browser toolbar click opens the side panel and grants temporary `activeTab` access. On an explicit scan or fill action, the panel injects the bundled content script with `chrome.scripting`. The content script inventories visible native controls in the active page. The panel maps only clear labels to profile values, shows the proposed values, and sends the reviewed plan back to the content script. The filler rescans the page, refuses a changed inventory, writes via native setters and DOM events, and reads values back. No code path clicks or submits a form.

The profile is validated with Zod and stored in `chrome.storage.local`. It is sent only to the active page as the minimal proposed values when the user chooses to fill. The extension has no backend, AI calls, remote scripts or host permissions in this phase. `activeTab`, `scripting`, `storage` and `sidePanel` are the only declared permissions.

The Python project is configured with FastAPI and exposes a health endpoint for the later API phases. Phase 1 extension functions independently of it.

## Review gates

- Profile must be explicitly saved; required name and email are validated.
- Scan lists visible native fields and marks sensitive or file fields for manual handling.
- Existing values are never overwritten automatically.
- Only deterministic field matches with a nonempty profile value enter the plan.
- First and last name fields require separately entered values; the extension does not guess their split from a full name.
- Fill requires a current scan; a changed form inventory stops the operation.
- Success means the control value was read back after writing. The user still reviews website validation and submits manually.

## Current coverage and limits

The first slice supports common text inputs, textareas and native selects. Radio buttons, checkboxes, file controls, custom widgets, cross-origin frames, dynamic multi-step forms, and ATS-specific layouts are listed for manual handling. The generic adapter and Greenhouse/Lever coverage are Phase 3. Website validation errors are not yet audited. Browser compatibility beyond Chrome 116+ is unverified.

## Verification

Run `npm run check`, then perform the Chrome fixture smoke test in the README. The unit tests cover detection, sensitive fields, deterministic mapping, existing values, select filling, read-back, changed forms, the checked-in fixture, and no form submission. The Chrome UI smoke test has not yet been run in this environment because computer-use access was unavailable.
