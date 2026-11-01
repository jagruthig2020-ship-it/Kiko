# KIKO direct-action fix — November 1, 2026

Fixed previously advertised requests that weren't implemented:

- “Find a downloaded file” -> File Explorer opens and selects the newest completed download, without opening it.
- “Open a new browser tab” -> Default browser opens a Google tab.

English, తెలుగు, हिन्दी phrase recognition. No API key, screenshots, or Ollama used for these two commands. The browser microphone may still use the browser vendor's speech service.

This does NOT add arbitrary app control. Native Windows effects have not been tested on the user's machine; portable tests exercise the logic, HTTP handler, and browser UI.

Install the update over your existing latest KIKO-Interactive folder (the one containing server.py and START_KIKO.bat), then close old KIKO terminals and start again.
