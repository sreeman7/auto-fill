# Phase 8: beta launch preparation

## Scope and result

The local beta candidate is version `0.8.0`. The Chrome Web Store listing copy, extension icons, promotional image, and two 1280 × 800 screenshots are under `release/store`. The screenshots show the built extension with synthetic data in a temporary Brave profile; the review screen uses a checked-in Greenhouse fixture. They are controlled demonstration captures, not evidence of compatibility with a live employer site. Capture and review the final listing in Chrome before store submission.

The first-run side panel now shows the data-use summary and a link to its bundled privacy page. It requires an affirmative checkbox before profile and account operations. Profile has a **Clear device profile** control. The [full privacy policy](privacy-policy.md) is a draft because the publisher contact and production hosting details do not exist yet.

The [listing draft](../release/store/listing.md), [tester invitation draft](beta-invite.md), and [feedback intake](beta-feedback.md) are ready for review. No tester was invited, no feedback was collected, and no store package was published.

## Review and tests

- `npm run check` passed with the project `.venv` active: TypeScript validation, lint, 24 extension tests, 35 API tests, extension build, and release asset validation. The system Python does not have the API test dependencies installed.
- `python3 tests/browser_beta_smoke.py --screenshot release/store/screenshot-review-1280x800.png` passed in headless Brave. It loaded a copy of the built extension with temporary localhost access, exercised the first-run consent flow, scanned Greenhouse, Lever and generic HTML fixtures, filled a synthetic email address, and confirmed zero submission events and untouched file inputs. The release manifest was not changed by this test.
- `git diff --check` passed.
- `npm run package:beta` was deliberately blocked by the publication gate because the policy still lacks a monitored privacy contact. This confirms the incomplete draft cannot be packaged through the release command.

These checks cover a local browser install and fixture behavior. They do not test the Chrome Web Store install, branded Chrome's side panel, Supabase authentication, Google sign-in, production hosting, or real employer sites. Those need the external accounts and service described below.

## Steps needed before a private beta

1. Set up a Supabase project and HTTPS API host, configure the extension and API environments, apply migrations, and test email and Google sign-in, resume upload, AI requests, account deletion, and the installed extension ID against the live beta service. Follow [Phase 2](../README.md#phase-2-cloud-setup) and [Phase 7](phase-7.md#staging-setup).
2. Provide a monitored support/privacy email. Replace the contact placeholder in both `docs/privacy-policy.md` and `apps/extension/public/privacy.html`. Confirm the policy matches the actual hosting provider, logging, retention, and data flow.
3. Publish the policy at a public HTTPS URL and save that URL in `release/store/public-policy-url.txt`. Open it without authentication and inspect the final page. The package gate checks URL syntax; a human must verify reachability and content.
4. Run `npm run build:staging` with the configured service origins, then `npm run check` and the browser smoke test. Review the permissions, install in Chrome through **Load unpacked**, and test the cloud flows in that installed build. Capture final Chrome listing screenshots.
5. Complete the Chrome Web Store developer account and privacy fields, check the listing and imagery against the final build, then run `npm run package:beta`. Review the generated ZIP before uploading it as a private item for trusted testers.
6. Supply the private store link and a private feedback channel in `docs/beta-invite.md`, select testers who have agreed to be contacted, and send invitations. Triage feedback using `docs/beta-feedback.md` before expanding distribution.

The store package command intentionally fails until the privacy contact, public policy URL, and configured cloud origins are present. It does not publish, invite users, or bypass dashboard review.
