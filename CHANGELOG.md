# KIKO unified local agent — November 2026

## Integrated into one project

- Windows Start app discovery via Get-StartApps and Start-menu shortcuts.
- Open specifically named, installed games and applications with no hardcoded app names.
- Ask the learner which installed app they mean when more than one matches; never silently choose a random game.
- Voice-to-task flow in English, Telugu and Hindi (browser speech recognition may be cloud-backed).
- Direct Windows Settings, Downloads and browser-tab actions.
- Automatic Windows accessibility inspection and click-through pointer ring when a grounded target is found.
- Local Ollama vision fallback for unfamiliar screens, with an accessibility-only fallback when capturing a window is blocked.
- Retry/I'm stuck, user-controlled clicking, and local practice history.
- Single source tree and startup script; no external API key.

## Boundaries

This is not guaranteed to control every installed application. An app that blocks accessibility inspection, hides its controls, uses exclusive fullscreen, or resists screenshot capture may need manual navigation or may remain unsupported. KIKO is a navigation teacher: it doesn't autonomously click through tasks or perform destructive actions.

The browser microphone is optional and may use an online speech backend. The app uses only locally running Ollama for AI reasoning, but installation and first model download require an internet connection.

Automated tests and a browser smoke test passed on the build machine. Native Windows UI and your local Ollama model have **not** been tested on your laptop. Do not claim that they have been.
