# Phase 6: application tracker

## Scope

The signed-in extension has a Tracker tab for saving jobs and updating application records. Each record stores company, title, URL, location, resume version, status, applied date, notes, interview dates and follow-up dates. The list supports text search, status filtering, sorting and pagination. Records belong to the authenticated account; account deletion removes them.

## Submission rule

Creating a record always sets its status to `saved` with no applied date. Moving from a pre-submission status to `applied`, `assessment`, `interview`, `offer`, `rejected` or `withdrawn` requires `confirmSubmitted: true` in the manual update request. The UI presents a checkbox stating that the user submitted on the job website. Autofill never updates tracker status. A database check requires an applied date for those later statuses and forbids one for pre-submission statuses.

## Duplicate checks

The API normalizes a job URL by lowercasing its host, removing fragments and common tracking parameters, and sorting the remaining query parameters. A SHA-256 fingerprint of that normalized URL has a per-user unique constraint, so the same job cannot be added twice even if URL tracking parameters differ. Job ID parameters remain in the URL. If another record has the same normalized company and title but a different URL, the API returns `possible_duplicate`; the user can explicitly confirm that it is another role. The exact URL check cannot be bypassed.

## API

- `GET /api/v1/applications?q=&status=&sort=&limit=&offset=` lists the owner's matching records.
- `POST /api/v1/applications` saves a new record as `saved`.
- `GET /api/v1/applications/{id}` reads one owner record.
- `PUT /api/v1/applications/{id}` updates all fields and the manual status.
- `DELETE /api/v1/applications/{id}` removes one owner record.

The database migration `0004_phase6` creates the table, status/date constraints, indexes and Supabase RLS owner policies. Apply it with `alembic -c apps/api/alembic.ini upgrade head` after configuring the Phase 2 Supabase project.

## Review and verification

Phase 6 tests exercise saved defaults, duplicate URL normalization, possible duplicate override, submission confirmation, status/date transitions, dates, search/filter/sort, pagination, owner isolation, deletion and account deletion. `npm run check` runs the full local extension and API suite. A live Supabase migration, authenticated browser session and Chrome end-to-end run require a Supabase project; none is configured locally yet.
