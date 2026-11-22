# Phase 2: profiles and resume review

## Implemented

- Supabase email/password registration and sign-in, optional Google OAuth through Chrome Identity, optional recovery-code reset, sign-out, and account deletion.
- FastAPI bearer-token validation against Supabase Auth, strict profile API, SQLAlchemy models, Alembic migration, account ownership checks, PostgreSQL RLS policies, and a private Storage bucket.
- Account-scoped local profile caching and explicit cloud profile load. Signed-out profile data does not appear in another signed-in account.
- PDF/DOCX upload validation (5 MB limit, type sniffing, DOCX archive bounds, PDF page bound), a 20-resume daily account limit, duplicate detection, text extraction, and source-linked proposals.
- Explicit selection/editing/approval of proposed facts. Existing verified contact values are not overwritten.
- Account owners can list, correct and remove approved career facts from the profile panel.

## Data and trust boundaries

The extension contains only the Supabase publishable key and API URL. It stores the Supabase session in `chrome.storage.local` through a custom storage adapter. The API verifies each token with Supabase Auth before private operations. It runs PostgreSQL requests under `authenticated` with a transaction-local user claim. Storage uploads and removals use the user's JWT, allowing bucket policies to enforce ownership. The server-only secret key is used only to delete an Auth account after its files and database rows are removed.

Resume suggestions are deterministic and unverified. The user must select and approve each item. Approved items become `career_facts` with the source excerpt and an edited-by-user flag. The raw resume is in private Storage; the database stores suggestion excerpts rather than the entire extracted text.

## Review and verification

`npm run check` passed with 11 extension tests, 9 API tests, typecheck, lint, and a production build. The extension tests cover local profile separation, response validation and Phase 1 autofill. API tests cover authentication gating, cross-user profile, resume and fact access, invalid files, duplicate upload, explicit approval, preservation of existing profile values, fact edits and account deletion logic. The Alembic migration rendered offline with `DATABASE_URL='postgresql+psycopg://user:pass@localhost/postgres' alembic -c apps/api/alembic.ini upgrade head --sql`.

## Limits before use with real accounts

- Live Supabase Auth, Storage, PostgreSQL RLS and Chrome OAuth have not been exercised because no project credentials or configured extension ID were supplied. Run the setup and end-to-end smoke test before using real resumes.
- Password recovery needs the Supabase recovery email template to include an OTP code. The button stays hidden unless enabled in the extension build.
- Image-only PDFs cannot be parsed. Parsing extracts straightforward lines and contact details; it is not an AI resume parser. Every proposal needs review.
- Account deletion spans Storage, PostgreSQL and Auth and is not atomic. A failed Auth deletion may require a retry; this flow needs live staging validation before release.
- The broader career editor, advanced education/work history structure, resume version history, and ATS adapters belong to later phases.
