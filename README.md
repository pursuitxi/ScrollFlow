<div align="center">

# ScrollFlow

**Turn any webpage into a smooth, presentation-ready scrolling GIF.**

Paste a URL, let the page fully load, and ScrollFlow automatically captures a top-to-bottom browsing animation as a looping GIF.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-Chromium-2EAD33?logo=playwright&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-6C63FF)

</div>

---

## Overview

ScrollFlow is a lightweight local tool for converting long webpages into animated GIFs that look like someone is naturally reading the page from top to bottom.

It is especially useful for:

- project pages and research websites;
- product landing pages and portfolios;
- GitHub README previews;
- presentation and demo assets;
- sharing long webpages in a compact visual format.

Unlike iframe-based or browser-only solutions, ScrollFlow uses a real Chromium instance through Playwright, so it can reliably render and capture public webpages before creating the GIF locally.

## Features

- **URL → GIF in one step** — paste a webpage URL and start generating.
- **Full-page preload before recording** — loading states are not recorded into the final GIF.
- **Lazy-load aware** — ScrollFlow performs a preload sweep to trigger images and sections that only appear during scrolling.
- **Font and image readiness checks** — waits for web fonts and currently created images to settle before capture.
- **Stable-page detection** — waits until the document height stops changing before recording begins.
- **Smooth top-to-bottom motion** — uses eased scrolling for a more natural presentation.
- **Custom capture settings** — viewport, GIF width, FPS, scroll speed, pauses, and maximum duration are configurable.
- **Local output** — generated GIFs are saved to `outputs/` on your machine.
- **No browser extension required** — everything runs from a small local web interface.

## How It Works

ScrollFlow deliberately separates **page preparation** from **recording**:

```text
Open URL
   ↓
Wait for page load
   ↓
Wait for network to become mostly idle
   ↓
Wait for web fonts
   ↓
Pre-scroll through the page
   ↓
Trigger lazy-loaded content
   ↓
Wait for images to load / decode
   ↓
Wait for document height to stabilize
   ↓
Return to the top
   ↓
Start recording
   ↓
Smoothly scroll to the bottom
   ↓
Encode frames as a looping GIF
```

This is important because many modern webpages continue changing after the initial `load` event. ScrollFlow tries to make sure the first GIF frame represents the finished page rather than an unfinished loading state.

## Requirements

- Python **3.10+**
- Internet access for loading the target webpage and installing Chromium on first setup
- macOS, Windows, or Linux

The Python dependencies are intentionally small:

```text
Flask
Pillow
Playwright
```

## Quick Start

### macOS

For the first run:

```bash
cd scrollflow_gif_tool
chmod +x install_and_run.command
./install_and_run.command
```

You can also double-click `install_and_run.command` in Finder.

After the initial installation, launch ScrollFlow with:

```bash
./run.command
```

### Windows

For the first run, double-click:

```text
install_and_run.bat
```

After installation, launch with:

```text
run.bat
```

### Linux

The macOS launcher is a regular shell script, so it can also be run from a Linux terminal:

```bash
chmod +x install_and_run.command run.command
./install_and_run.command
```

After the initial installation:

```bash
./run.command
```

## Manual Installation

If you prefer to set everything up manually:

```bash
python3 -m venv .venv
```

Activate the environment.

macOS / Linux:

```bash
source .venv/bin/activate
```

Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies and Chromium:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Then start the application:

```bash
python app.py
```

ScrollFlow will open automatically at:

```text
http://127.0.0.1:5178
```

To prevent the application from opening a browser window automatically:

```bash
SCROLLFLOW_NO_BROWSER=1 python app.py
```

## Usage

1. Start ScrollFlow.
2. Paste a public `http://` or `https://` webpage URL.
3. Optionally expand the advanced settings.
4. Click **Generate GIF**.
5. ScrollFlow prepares the full page before recording begins.
6. Preview the generated animation in the browser.
7. Save the GIF, or find it directly inside `outputs/`.

## Capture Settings

| Setting | Default | Supported range | Description |
| --- | ---: | ---: | --- |
| Viewport width | `1440 px` | `800–1920` | Chromium browser width used during capture |
| Viewport height | `900 px` | `600–1200` | Chromium browser height used during capture |
| GIF width | `960 px` | `480–viewport width` | Final output width; aspect ratio is preserved |
| FPS | `5` | `2–10` | Frames per second in the final GIF |
| Scroll speed | `760 px/s` | `200–2200` | Target scrolling speed |
| Top pause | `1.2 s` | `0–5 s` | Hold time before scrolling starts |
| Bottom pause | `1.0 s` | `0–5 s` | Hold time after reaching the bottom |
| Final page wait | `1.5 s` | `0.2–8 s` | Extra wait after returning to the top |
| Max scroll duration | `24 s` | `5–90 s` | Hard cap for very long webpages |

Higher resolution, higher FPS, and longer durations will increase GIF file size and memory usage.

## Project Structure

```text
scrollflow_gif_tool/
├── app.py                  # Flask server, Playwright capture, GIF encoding
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html          # ScrollFlow web interface
├── outputs/                # Generated GIF files
├── install_and_run.command # First-run installer for macOS / Linux shell
├── run.command             # Launcher for macOS / Linux shell
├── install_and_run.bat     # First-run installer for Windows
└── run.bat                 # Launcher for Windows
```

## Technical Notes

### Why not pure HTML / JavaScript?

A normal webpage cannot reliably capture arbitrary third-party websites because of browser security boundaries such as:

- Same-Origin Policy;
- CORS;
- `X-Frame-Options`;
- Content Security Policy (CSP).

ScrollFlow avoids these limitations by opening the target page in a separate Playwright-controlled Chromium process and capturing the rendered viewport directly.

### GIF generation

Each viewport frame is captured as PNG, resized when necessary, and then encoded as an animated GIF with Pillow. Scrolling positions use a smoothstep easing curve so that the motion starts and ends more naturally than a constant linear movement.

### Localhost and private networks

`localhost`, `127.0.0.1`, and `::1` are allowed so you can preview your own local project pages.

Other private, loopback, link-local, and reserved network addresses are rejected by default to reduce accidental access to local services.

## Limitations

ScrollFlow works best with ordinary publicly accessible webpages. Some cases may need additional work:

- **Authenticated pages** — login/session reuse is not currently implemented.
- **Cloudflare / CAPTCHA / anti-bot pages** — automated Chromium may be challenged or blocked.
- **Infinite-scroll websites** — ScrollFlow uses a bounded preload sweep and will not crawl an endless feed forever.
- **Live dashboards** — continuously changing content may never become perfectly stable.
- **Video / WebGL / hardware-accelerated effects** — headless Chromium rendering may differ slightly from an interactive browser session.
- **Very long pages** — high FPS and large output dimensions can create very large GIF files.
- **Cookie banners / popups** — the current version does not automatically dismiss site-specific overlays.

## Privacy

ScrollFlow runs locally. The generated screenshots and GIFs are written to your local `outputs/` directory and are not uploaded by ScrollFlow itself.

The target webpage is still loaded normally by Chromium, so that webpage and any third-party resources it includes may receive the usual browser requests.

## API

The local frontend calls:

```http
POST /api/generate
Content-Type: application/json
```

Example payload:

```json
{
  "url": "https://example.com",
  "viewportWidth": 1440,
  "viewportHeight": 900,
  "outputWidth": 960,
  "fps": 5,
  "scrollSpeed": 760,
  "topPause": 1.2,
  "bottomPause": 1.0,
  "pageWait": 1.5,
  "maxDuration": 24
}
```

A successful response includes the generated filename, preview/download URLs, and metadata such as frame count, duration, output size, page height, and preload time.

## Roadmap

Potential future improvements include:

- reusable authenticated browser sessions;
- MP4 / WebM export;
- custom start and end positions;
- automatic cookie-banner dismissal;
- element-specific recording;
- mouse cursor and click animations;
- per-section pauses;
- presets for GitHub, project pages, and product demos;
- smarter compression for large outputs.

## Contributing

Contributions are welcome. If you have an idea or find a bug, feel free to open an issue or submit a pull request.

For larger changes, opening an issue first is recommended so the behavior and implementation can be discussed before development.

---

<div align="center">

**From web pages to moving stories.**

</div>
