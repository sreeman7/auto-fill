# Phase 5: screening question assistant

## Implemented workflow

1. The user pastes a question or selects text on the application page. **Use selected page text** copies that selection into the side panel for review; it does not send it to the model.
2. The API checks the question for work authorization, immigration, disability, demographics, veteran status, criminal or security history, personal identifiers and pay. Recognized sensitive questions return a manual-answer notice before any model call. If the model flags another question as sensitive, the server also returns a manual notice and stores no draft.
3. For ordinary questions, the model returns a structured interpretation, up to three approved fact IDs and an optional exact job-context quote. The server validates every ID and quote. It assembles a draft from the exact approved fact text, within the selected 60, 120 or 200 word limit. It does not let the model write new career claims.
4. The user reviews the considered facts and editable answer. Questions about personal motivation start with an empty answer so the user can add their own reason. Saving requires an explicit approval checkbox and API confirmation. Saved answers can be copied into an application or deleted. No screening answer is inserted or submitted automatically.

Drafts and approved answers are private, owner-scoped and signed with the server-only `TAILOR_SIGNING_KEY`. Approval verifies the draft signature and checks that referenced approved facts have not changed. A draft cannot be approved twice or after 24 hours. Saved answers have their own signature; edited answers are marked as user edits and do not claim automatic fact provenance. Account deletion removes both screening drafts and saved answers.

## Limits and review findings

The server's composed wording deliberately stays close to approved facts. It may read less smoothly than a free-form model answer, and the user can edit it. Once a user edits an answer, the app records that action but cannot independently verify new claims the user adds. Sensitive answers are neither drafted nor stored in this phase. The classifier is conservative but may miss unusual wording; the model can flag additional sensitive questions, and users should review every question and answer.

Screening drafts stop being approvable after 24 hours, but old draft rows are not yet automatically purged. Twenty successful screening drafts per account per day are allowed. Model token counts are stored with each draft. The OpenAI request uses strict structured output and `store: false`, following the [official Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs).

## Setup and verification

Use the Phase 2 cloud setup and Phase 4 server-only keys. With the virtual environment active, run `python -m pip install -e './apps/api[dev]'` and `alembic -c apps/api/alembic.ini upgrade head`. Restart the API, then run `npm run check` and reload `apps/extension/dist` in Chrome.

`npm run check` passed with 22 extension tests, 25 API tests, TypeScript, lint and a production build. Automated tests cover local sensitive interception before model use, model-sensitive responses, approved-fact grounding, length limits, explicit confirmation, user edits, saved-answer ownership, deletion, tamper detection, changed facts and account deletion. The Phase 5 migration rendered successfully as offline PostgreSQL SQL. A live Supabase, OpenAI and Chrome end-to-end run remains pending because no project or credentials have been supplied.
