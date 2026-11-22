# Beta feedback and reliability triage

No tester feedback has been collected yet. The [issue template](../.github/ISSUE_TEMPLATE/beta-feedback.yml) is prepared for a repository where issues are an appropriate feedback channel. If the repository is public, do not ask testers to post resumes, application answers, credentials, or screenshots with personal information. Choose a private channel before invitations if that risk cannot be managed.

Review reports weekly during the beta. Record browser/version, application platform, sanitized reproduction steps, expected and actual behavior, and whether the extension filled or merely suggested a value. Reproduce on a controlled fixture before changing an adapter. Never submit a real application during testing.

## Initial reliability priorities

1. **Release blocker:** Complete a live Supabase project, authenticated install flow, account deletion check, public privacy policy URL, and monitored contact. None can be verified with the current local-only setup.
2. **High:** Confirm Chrome Web Store install and toolbar-to-side-panel flow in branded Chrome; CLI loading is unavailable in current branded Chrome, so this needs a manual install test.
3. **High:** Test Greenhouse, Lever, generic, and dynamic forms on opted-in beta test pages. The fixture smoke test currently covers the first three; cross-origin iframes and custom widgets remain manual.
4. **Medium:** Improve narrower side-panel layouts and long field-review lists based on tester observations.
5. **Medium:** Assess whether process-local rate limiting and database readiness need an ingress-level replacement at real beta traffic levels.

Classify an issue as critical if it submits without user action, sends data to the wrong service, exposes another user's data, or silently fills a sensitive field. Stop distribution until a critical issue is fixed and verified. Prioritize other reports by user impact, frequency, and reproducibility; do not treat a single unverified report as confirmed behavior.
