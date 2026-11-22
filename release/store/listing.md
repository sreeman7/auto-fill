# Chrome Web Store beta listing draft

**Name:** auto-fill BETA

**Short description:** Review and fill job applications with a profile you control. You submit each application yourself.

**Category:** Productivity

**Detailed description:**

THIS EXTENSION IS FOR BETA TESTING.

auto-fill helps you review job application forms, see which fields match a profile you saved, and fill supported fields after you approve the preview. It reports missing required fields, website errors, and controls that need your own input. It never clicks the final submit button.

The local profile works without an account. Optional account features include private resume upload with rule-based fact suggestions and an application tracker. Those account features require a configured cloud service and may not be available in a local-only build.

Greenhouse, Lever and generic HTML application forms have been tested with controlled fixtures. Real employer sites can differ; file uploads, sensitive questions, CAPTCHA, and complex widgets remain manual. Review every value and website message before submitting yourself.

**Single purpose:** Help users review, fill and track their own job applications under their control.

**Privacy practices draft:** Declare personally identifiable information, authentication information, website content, web browsing activity limited to user-invoked job pages, and user-generated content. Check the exact dashboard choices against the final configured build and the published policy. Local profile data is stored on device; cloud account data is sent to the configured API and Supabase. No advertising or sale of data.

**Permission explanations:**

- `activeTab`: access the job page the user invokes the extension on.
- `scripting`: scan and fill that page after user action.
- `storage`: save the local profile, privacy choice and optional account session.
- `sidePanel`: display review and account controls beside the application.
- `identity` (cloud build only): complete optional Google sign-in.
- Exact API and Supabase host origins (cloud build only): communicate with the user's configured cloud service.

**Store assets:** `apps/extension/public/icons/icon-128.png` for the extension and store icon, `release/store/promo-small-440x280.png` for the small tile, and `release/store/screenshot-review-1280x800.png` for the tested review flow. `screenshot-privacy-1280x800.png` is an optional second image. All screenshots come from the built extension in a temporary browser with synthetic test data. Replace or supplement them with a final Chrome capture before submission.

**Before submission:** Replace the draft privacy contact, publish a public privacy policy URL, configure production or staging cloud origins, create and review the final release ZIP, complete the dashboard privacy declarations, and run the account and store-install tests. Use **Private / trusted testers** for the first distribution.
