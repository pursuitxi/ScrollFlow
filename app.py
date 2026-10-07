from __future__ import annotations

import ipaddress
import os
import socket
import tempfile
import time
import uuid
import webbrowser
from pathlib import Path
from threading import Timer
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request, send_from_directory
from PIL import Image
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("请输入网页地址。")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("仅支持 http / https 网页地址。")
    return raw


def is_private_host(hostname: str | None) -> bool:
    """Small guard against accidental local-file/service probing.

    Localhost is allowed because it is useful for previewing the user's own pages.
    Other private/reserved IPs are rejected by default.
    """
    if not hostname:
        return True
    if hostname in {"localhost", "127.0.0.1", "::1"}:
        return False
    try:
        infos = socket.getaddrinfo(hostname, None)
        for info in infos:
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
    except Exception:
        # Let Playwright produce the clearer navigation error.
        return False
    return False


def clamp(value, low, high):
    return max(low, min(high, value))


def capture_scroll_gif(
    url: str,
    output_path: Path,
    viewport_width: int,
    viewport_height: int,
    output_width: int,
    fps: int,
    scroll_speed: int,
    top_pause: float,
    bottom_pause: float,
    page_wait: float,
    max_duration: float,
) -> dict:
    frame_delay_ms = max(40, round(1000 / fps))
    frames: list[Image.Image] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height},
            device_scale_factor=1,
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(20_000)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightTimeoutError:
            # Some pages keep connections/resources alive indefinitely. Continue with
            # the explicit readiness checks below instead of failing immediately.
            pass

        # ------------------------------------------------------------------
        # PRELOAD / SETTLE PHASE
        # Nothing is recorded before this phase finishes. This deliberately does
        # more than waiting for `load`: it also triggers lazy-loaded content by
        # sweeping through the page once, waits for fonts/images/network activity,
        # then waits until the document height stops changing.
        # ------------------------------------------------------------------
        preload_started = time.perf_counter()

        try:
            page.wait_for_load_state("load", timeout=20_000)
        except PlaywrightTimeoutError:
            pass

        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PlaywrightTimeoutError:
            pass

        # Web fonts can visibly reflow text after load/networkidle.
        try:
            page.evaluate(
                """
                async () => {
                  if (document.fonts && document.fonts.ready) {
                    try { await document.fonts.ready; } catch (_) {}
                  }
                }
                """
            )
        except Exception:
            pass

        # Disable browser smooth scrolling so preload and capture positions are
        # deterministic. This does not start recording.
        page.add_style_tag(content="html { scroll-behavior: auto !important; }")

        def document_height() -> int:
            return int(page.evaluate(
                """
                () => Math.max(
                  document.body ? document.body.scrollHeight : 0,
                  document.documentElement ? document.documentElement.scrollHeight : 0,
                  document.body ? document.body.offsetHeight : 0,
                  document.documentElement ? document.documentElement.offsetHeight : 0
                )
                """
            ))

        # First pass through the whole document to trigger IntersectionObserver /
        # loading=lazy assets. The height is re-read every step because lazy content
        # may append sections while we move down the page.
        y = 0
        preload_steps = 0
        max_preload_steps = 220
        step_px = max(320, int(viewport_height * 0.80))
        while preload_steps < max_preload_steps:
            height_now = max(document_height(), viewport_height)
            bottom = max(0, height_now - viewport_height)
            if y >= bottom:
                page.evaluate("y => window.scrollTo(0, y)", bottom)
                page.wait_for_timeout(450)
                # Re-check after reaching the apparent bottom in case infinite/lazy
                # sections expanded the document.
                height_after = max(document_height(), viewport_height)
                new_bottom = max(0, height_after - viewport_height)
                if new_bottom <= bottom + 4:
                    break
                y = bottom
            else:
                y = min(bottom, y + step_px)
                page.evaluate("y => window.scrollTo(0, y)", y)
                page.wait_for_timeout(140)
            preload_steps += 1

        # Give lazy requests a chance to finish after the sweep.
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except PlaywrightTimeoutError:
            pass

        # Wait for all currently-created <img> elements. Each image has its own
        # timeout so one broken remote asset cannot block the whole job forever.
        try:
            page.evaluate(
                """
                async () => {
                  const sleep = ms => new Promise(r => setTimeout(r, ms));
                  const waitOne = async (img) => {
                    if (img.complete) {
                      try { await img.decode(); } catch (_) {}
                      return;
                    }
                    await Promise.race([
                      new Promise(resolve => {
                        const done = () => resolve();
                        img.addEventListener('load', done, { once: true });
                        img.addEventListener('error', done, { once: true });
                      }),
                      sleep(5000)
                    ]);
                    try { await img.decode(); } catch (_) {}
                  };
                  await Promise.all(Array.from(document.images).map(waitOne));
                  if (document.fonts && document.fonts.ready) {
                    try { await document.fonts.ready; } catch (_) {}
                  }
                }
                """
            )
        except Exception:
            pass

        # Wait for the page height to be stable for several consecutive samples.
        # This catches late image sizing, injected project sections, font reflow, etc.
        stable_samples = 0
        previous_height = -1
        settle_deadline = time.perf_counter() + 10.0
        while time.perf_counter() < settle_deadline and stable_samples < 4:
            current_height = document_height()
            if abs(current_height - previous_height) <= 2:
                stable_samples += 1
            else:
                stable_samples = 0
                previous_height = current_height
            page.wait_for_timeout(350)

        # Return to the true recording start only after the full preload phase.
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(max(300, int(page_wait * 1000)))
        preload_seconds = round(time.perf_counter() - preload_started, 2)

        dims = page.evaluate(
            """
            () => ({
              scrollHeight: Math.max(
                document.body ? document.body.scrollHeight : 0,
                document.documentElement ? document.documentElement.scrollHeight : 0,
                document.body ? document.body.offsetHeight : 0,
                document.documentElement ? document.documentElement.offsetHeight : 0
              ),
              innerHeight: window.innerHeight
            })
            """
        )
        scroll_height = max(int(dims["scrollHeight"]), viewport_height)
        max_scroll = max(0, scroll_height - int(dims["innerHeight"]))

        # Distance-based duration with a user-set hard cap for very long pages.
        natural_duration = max_scroll / max(scroll_speed, 1)
        scroll_duration = min(max_duration, max(0.8, natural_duration)) if max_scroll else 0
        moving_frames = max(1, round(scroll_duration * fps)) if max_scroll else 1
        top_hold = max(0, round(top_pause * fps))
        bottom_hold = max(0, round(bottom_pause * fps))

        def snap(y: int) -> Image.Image:
            page.evaluate("y => window.scrollTo(0, y)", y)
            page.wait_for_timeout(35)
            png = page.screenshot(type="png", full_page=False, animations="disabled")
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(png)
                tmp_path = Path(tmp.name)
            try:
                img = Image.open(tmp_path).convert("RGB")
                if output_width < img.width:
                    new_height = max(1, round(img.height * output_width / img.width))
                    img = img.resize((output_width, new_height), Image.Resampling.LANCZOS)
                return img.copy()
            finally:
                tmp_path.unlink(missing_ok=True)

        first = snap(0)
        frames.extend([first.copy() for _ in range(max(1, top_hold))])

        if max_scroll:
            # Include both endpoints while avoiding a duplicated first frame.
            for i in range(1, moving_frames + 1):
                ratio = i / moving_frames
                # Smoothstep gives a more natural start/stop than linear motion.
                eased = ratio * ratio * (3 - 2 * ratio)
                y = round(max_scroll * eased)
                frames.append(snap(y))

        last = frames[-1].copy()
        frames.extend([last.copy() for _ in range(bottom_hold)])

        browser.close()

    # Pillow performs palette conversion during GIF encoding.
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=frame_delay_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )

    return {
        "scroll_height": scroll_height,
        "max_scroll": max_scroll,
        "frame_count": len(frames),
        "duration": round(len(frames) / fps, 2),
        "width": frames[0].width,
        "height": frames[0].height,
        "size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
        "preload_seconds": preload_seconds,
        "preload_steps": preload_steps,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/generate")
def generate():
    data = request.get_json(silent=True) or {}
    try:
        url = normalize_url(str(data.get("url", "")))
        host = urlparse(url).hostname
        if is_private_host(host):
            raise ValueError("出于安全考虑，默认不访问私有网段地址；localhost 可以使用。")

        viewport_width = int(clamp(int(data.get("viewportWidth", 1440)), 800, 1920))
        viewport_height = int(clamp(int(data.get("viewportHeight", 900)), 600, 1200))
        output_width = int(clamp(int(data.get("outputWidth", 960)), 480, viewport_width))
        fps = int(clamp(int(data.get("fps", 5)), 2, 10))
        scroll_speed = int(clamp(int(data.get("scrollSpeed", 760)), 200, 2200))
        top_pause = float(clamp(float(data.get("topPause", 1.2)), 0, 5))
        bottom_pause = float(clamp(float(data.get("bottomPause", 1.0)), 0, 5))
        page_wait = float(clamp(float(data.get("pageWait", 1.5)), 0.2, 8))
        max_duration = float(clamp(float(data.get("maxDuration", 24)), 5, 90))

        filename = f"scrollflow_{int(time.time())}_{uuid.uuid4().hex[:6]}.gif"
        output_path = OUTPUT_DIR / filename

        meta = capture_scroll_gif(
            url=url,
            output_path=output_path,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            output_width=output_width,
            fps=fps,
            scroll_speed=scroll_speed,
            top_pause=top_pause,
            bottom_pause=bottom_pause,
            page_wait=page_wait,
            max_duration=max_duration,
        )
        return jsonify(
            {
                "ok": True,
                "url": url,
                "gifUrl": f"/outputs/{filename}",
                "downloadUrl": f"/outputs/{filename}?download=1",
                "filename": filename,
                "meta": meta,
            }
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify(
            {
                "ok": False,
                "error": "生成失败。请确认该网址可公开访问，且已安装 Playwright Chromium。",
                "detail": str(exc),
            }
        ), 500


@app.get("/outputs/<path:filename>")
def outputs(filename: str):
    as_attachment = request.args.get("download") == "1"
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=as_attachment)


def open_browser():
    webbrowser.open_new("http://127.0.0.1:5178")


if __name__ == "__main__":
    if os.environ.get("SCROLLFLOW_NO_BROWSER") != "1":
        Timer(0.7, open_browser).start()
    app.run(host="127.0.0.1", port=5178, debug=False, threaded=True)
