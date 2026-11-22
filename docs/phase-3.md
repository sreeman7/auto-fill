# Phase 3: application support

## Implemented

- Generic adapter selects the most likely application `<form>` and confines scanning and filling to it.
- Greenhouse and Lever adapters recognize hosted application URLs or form actions and map common platform field names to profile fields.
- Dynamic form observer reports added, removed, and changed fields to the side panel. Filling waits briefly for conditional fields, then shows a fresh inventory. A changed form, page URL, required flag, or select option list requires a new preview.
- Pre-submit review reports missing required fields, invalid native values, website errors, sensitive questions, manual file/radio/checkbox controls, custom autocomplete controls, cross-origin embedded applications, and failed or unverified fills.
- The user reviews proposed values before filling and submits each application manually.

## Compatibility review

| Form | Automatic fields | Manual or limited fields |
| --- | --- | --- |
| Generic HTML | Profile fields with exact, supported labels in the selected application form | Unrecognized labels, file uploads, choices, custom widgets |
| Greenhouse hosted form | Common name, email, phone, LinkedIn and GitHub fields | Custom questions, attachments, sensitive answers and controls that change with the site |
| Lever hosted form | Common full name, email, phone, LinkedIn and GitHub fields | Location autocomplete, attachments, custom questions and sensitive answers |

The adapter uses page structure and field labels. A site redesign, embedded form, or unusual custom control can require manual entry. No adapter clicks submit, chooses sensitive answers, uploads a file, or fabricates a value.

## Review and verification

Run `npm run check` from the repository root. The extension fixture tests cover adapter detection, form scoping, mapping, dynamic fields, stale preview rejection, validation reporting, and the no-submit rule. The API suite is also part of the full check. Local fixtures are available at `tests/fixtures/greenhouse.html`, `lever.html`, and `dynamic.html` for a manual Chrome smoke test.

No live Greenhouse or Lever account or application was used for this phase. The local fixture tests verify the implementation against representative HTML; a live staging smoke test is still needed before relying on an adapter for a particular employer. Phase 2 live Supabase testing also remains pending because no project has been created.
