# Control on Android / Samsung Galaxy Fold

## Current one-tap workflow

1. Visit https://control-api-production-0cff.up.railway.app/app from Chrome or Samsung Internet on the Fold.
2. In Chrome: **⋮ → Add to Home screen → Install** (or Install app); in Samsung Internet use the install / Add page to home screen feature.
3. Open the new Control icon. The first time, unlock it using the `CONTROL_API_KEY` value in Railway → control-api → Variables. Enter only on the `*.up.railway.app` Control domain. Never paste the key into chat or GitHub.
4. Use **Thought** to save the exact original text to a separate inbox, or **Task** for a direct task. The app displays pending captures and open tasks. Marking a capture Reviewed removes it from the pending inbox but preserves its original data for export.
5. Use the phone keyboard microphone for optional voice dictation. Control does not record audio itself.
6. Tap **ChatGPT ↗** to open ChatGPT; invoke the installed Control Connector and ask it to read your Control context and thought inbox.

The mobile login uses a secure, HttpOnly cookie. The access key is **not stored in browser localStorage**. Session duration is currently up to 30 days. Control requires internet connectivity to save a thought or task. There is no offline queue, background notification, or scheduled reminder engine yet.

## Home-screen shortcuts vs. Samsung widget

The PWA manifest defines **Capture thought** and **New task** shortcuts. Android launcher/browser support differs; some devices show them by long-pressing the app icon. If they do not appear, the main Control icon still opens the capture page directly.

A **real resizable Samsung home-screen widget** requires an Android APK with an AppWidgetProvider (or Jetpack Glance). A PWA does not create these widgets. Proposed native widget:
- Resizable size 2x1 (Quick capture) and 4x2 (Next tasks)
- Thought button / Task button launch the appropriate deep link into the installed app
- Native quick-capture sheet, once added, will authenticate through Android Keystore rather than embedding the API secret
- Optional next-task display via secure background sync
- Privacy: no sensitive note content on lock screen by default

Until it exists, do not mistake the PWA home-screen icon for a full native widget.

## Browser and security

The GitHub repo is currently public but contains source code only. Personal notes live in the Railway volume. Change GitHub repository visibility to private if desired. The app is a single-user prototype; plan for stronger per-device authentication, backups, audit and recovery before storing very sensitive records.

## Current validation

Railway startup and persistent DB confirmed. The existing ChatGPT Connector can read context, open tasks and the raw pending inbox through `/api/context`. Browser-specific install, task capture, session storage, and native widget behavior require testing on the actual Fold.
