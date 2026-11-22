# auto-fill privacy policy — beta draft

**Last updated:** 22 November 2026

**Publisher contact:** [Add a monitored support and privacy email before inviting testers or submitting to the Chrome Web Store.]

auto-fill is a browser extension that helps you review and fill job application forms. You choose when to save information, scan a page, use cloud tools, or submit an application. auto-fill never clicks the final application submit button for you.

## Information the extension uses

- **Local profile:** Name, contact, education and profile links you enter are stored in Chrome extension local storage on your device. The extension reads them to propose and fill matching form fields when you ask it to scan and fill a page.
- **Application page:** When you click Scan, the extension reads visible form labels, field types, values needed to detect already-filled fields, validation messages, and the current page URL. This information is used in the side panel to show a review and validation report. When you explicitly request job analysis or a screening draft, selected job description or question text can be sent to the API. The extension does not continuously record your browsing history.
- **Account and cloud data:** If you choose to sign in, Supabase processes your email, authentication credentials and session. The API stores your account profile, uploaded resume files, approved career facts, AI draft records, approved screening answers, and application tracker records in the configured Supabase project. Resume text is extracted on the API to propose facts for your approval.
- **AI requests:** When you request a tailoring analysis or screening answer, the API sends the job description or question and relevant approved career facts to OpenAI. The API requests `store: false`, but OpenAI processes the request under its own service terms and policies. The API stores the resulting draft and token counts so you can review the output and the service can enforce use limits. AI text is not put into an application without your review.
- **Operational data:** The API logs a random request ID, route template, method, status code and duration. It does not log request bodies, search terms, authentication tokens, resume contents or raw job URLs. A hosting provider may process connection information needed to deliver requests; the production host and its retention settings must be confirmed before beta distribution.

## Sharing and purpose

The extension uses Chrome's local storage and, if you opt into cloud features, sends data to the configured auto-fill API and Supabase. OpenAI receives the specific information described above only when you request an AI feature. Google may process sign-in information if you choose Google sign-in. The job website receives the values you choose to fill on that site and any application you submit there under that website's own privacy practices. auto-fill does not sell your data or use it for advertising.

## Your choices and deletion

You can edit or clear your local profile in the extension. Signing out removes the active cloud session from the extension. You can delete approved facts and tracker records individually. **Delete account and cloud data** requests deletion of your account data, including stored resumes and drafts, from the API and Supabase. If the deletion reports an error, some deletion steps may need to be retried; contact support once the beta contact address is published. Removing the extension also removes its local extension storage from that browser profile. Cloud records are retained until you delete them or the account; expired drafts are not automatically purged from storage.

## Security

Cloud URLs must use HTTPS outside loopback development. Account data is scoped to the signed-in user with server-side authorization and database row-level security. Server-only keys are kept out of the extension. Browser permissions are limited to user-invoked page access and configured cloud origins. No system can guarantee absolute security.

## Changes and contact

The publisher will update this policy before changing material data practices. The beta version must not be distributed until a working support and privacy contact and public policy URL are added to the listing and confirmed against the production hosting setup.
