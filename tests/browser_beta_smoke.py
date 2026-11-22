"""Exercise the built extension against local forms in headless Brave.

Requires a local Brave browser and the optional `websockets` Python package.
The copied test extension gains localhost host access only inside a temp folder;
the release manifest remains unchanged. No form is submitted.
"""

import argparse
import base64
import functools
import http.server
import json
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]
PROFILE = {
    "fullName": "Ada Example", "firstName": "Ada", "lastName": "Example", "email": "ada@example.test",
    "phone": "+1 555 0100", "city": "Edmonton", "country": "Canada", "linkedin": "", "github": "",
    "university": "", "degree": "", "graduationYear": "",
}
FIXTURES = (("greenhouse.html", "Greenhouse"), ("lever.html", "Lever"),
            ("application.html", "Generic HTML"), ("dynamic.html", "Generic HTML"))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def wait_for(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise TimeoutError("Browser did not reach the expected state")


class CDP:
    def __init__(self, socket):
        self.socket = socket
        self.number = 0

    def call(self, method, params=None):
        self.number += 1
        identifier = self.number
        self.socket.send(json.dumps({"id": identifier, "method": method, "params": params or {}}))
        while True:
            data = json.loads(self.socket.recv(timeout=8))
            if data.get("id") == identifier:
                if "error" in data:
                    raise RuntimeError(data["error"])
                return data.get("result", {})

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        return result.get("result", {}).get("value")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", default="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--privacy-screenshot", type=Path)
    args = parser.parse_args()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as folder:
            temporary = Path(folder)
            extension = temporary / "extension"
            shutil.copytree(ROOT / "apps/extension/dist", extension)
            manifest_file = extension / "manifest.json"
            manifest = json.loads(manifest_file.read_text())
            manifest["host_permissions"] = [*manifest.get("host_permissions", []), "http://127.0.0.1/*"]
            manifest_file.write_text(json.dumps(manifest))
            browser = subprocess.Popen([
                args.browser, "--headless=new", "--no-first-run", "--no-default-browser-check", "--disable-gpu",
                "--remote-allow-origins=*", f"--user-data-dir={temporary / 'profile'}", "--remote-debugging-port=0",
                f"--load-extension={extension}", f"--disable-extensions-except={extension}", "about:blank",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                active = temporary / "profile/DevToolsActivePort"
                wait_for(active.exists)
                port = active.read_text().splitlines()[0]

                def browser_json(path, method="GET"):
                    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
                    return json.load(urllib.request.urlopen(request, timeout=3))

                worker = wait_for(lambda: next((item for item in browser_json("/json")
                    if item["url"].endswith("/background/index.js")), None))
                extension_id = worker["url"].split("/")[2]
                panel_url = f"chrome-extension://{extension_id}/sidepanel.html"
                panel = browser_json(f"/json/new?{urllib.parse.quote(panel_url, safe='')}", "PUT")
                with connect(panel["webSocketDebuggerUrl"], open_timeout=4) as panel_socket:
                    sidepanel = CDP(panel_socket)
                    wait_for(lambda: sidepanel.evaluate("document.body?.innerText.includes('Your data, your choice') ?? false"))
                    assert sidepanel.evaluate("!document.body.innerText.includes('OpenAI') && !document.body.innerText.includes('AI draft')") is True
                    if args.privacy_screenshot:
                        sidepanel.call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False})
                        image = sidepanel.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
                        args.privacy_screenshot.parent.mkdir(parents=True, exist_ok=True)
                        args.privacy_screenshot.write_bytes(base64.b64decode(image))
                    assert sidepanel.evaluate("document.querySelector('.privacy-intro button').disabled") is True
                    sidepanel.evaluate("document.querySelector('.privacy-intro input[type=checkbox]').click()")
                    wait_for(lambda: sidepanel.evaluate("document.querySelector('.privacy-intro button').disabled === false"))
                    sidepanel.evaluate("document.querySelector('.privacy-intro button').click()")
                    wait_for(lambda: sidepanel.evaluate("document.body.innerText.includes('Review before fill')"))
                    assert sidepanel.evaluate("[...document.querySelectorAll('nav.tabs button')].map(button => button.textContent.trim()).join('|')") == "Autofill|Profile|Resumes|Tracker|Account"
                    sidepanel.evaluate("chrome.storage.local.set(" + json.dumps({
                        "auto-fill.profile.v1": PROFILE,
                    }) + ").then(() => location.reload())")
                    wait_for(lambda: sidepanel.evaluate("document.body.innerText.includes('Profile ready')"))
                    for filename, adapter in FIXTURES:
                        url = f"http://127.0.0.1:{server.server_port}/tests/fixtures/{filename}"
                        page = browser_json(f"/json/new?{urllib.parse.quote(url, safe='')}", "PUT")
                        with connect(page["webSocketDebuggerUrl"], open_timeout=4) as page_socket:
                            form = CDP(page_socket)
                            wait_for(lambda: form.evaluate(
                                f"location.pathname.endsWith({json.dumps(filename)}) && document.readyState === 'complete'"
                            ))
                            form.evaluate("window.__submitCount = 0; document.querySelectorAll('form').forEach(f => f.addEventListener('submit', () => window.__submitCount++))")
                            sidepanel.evaluate("[...document.querySelectorAll('button')].find(b => /Scan (current page|again)/.test(b.innerText)).click()")
                            wait_for(lambda: sidepanel.evaluate(f"document.body.innerText.includes('Detected form: {adapter}')"))
                            if filename == "dynamic.html":
                                form.evaluate("document.getElementById('conditional').innerHTML = '<label for=first>First Name</label><input id=first name=first_name>'")
                                wait_for(lambda: sidepanel.evaluate("document.body.innerText.includes('The form changed. Review its current fields')"))
                                wait_for(lambda: sidepanel.evaluate("document.body.innerText.includes('First Name')"))
                            if args.screenshot and filename == "greenhouse.html":
                                sidepanel.call("Emulation.setDeviceMetricsOverride", {"width": 1280, "height": 800, "deviceScaleFactor": 1, "mobile": False})
                                image = sidepanel.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
                                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                                args.screenshot.write_bytes(base64.b64decode(image))
                            sidepanel.evaluate("[...document.querySelectorAll('button')].find(b => /^Fill [0-9]+ reviewed/.test(b.innerText)).click()")
                            wait_for(lambda: sidepanel.evaluate("document.body.innerText.includes('proposed fields read back successfully')"))
                            result = form.evaluate("({email:document.querySelector('form:not(#newsletter) input[type=email]').value, submits:window.__submitCount, files:document.querySelector('input[type=file]')?.files.length ?? 0})")
                            assert result["email"] == PROFILE["email"] and result["submits"] == 0 and result["files"] == 0, (filename, result)
                            print(f"{filename}: scanned, filled email, left upload and submit untouched")
            finally:
                browser.terminate()
                try:
                    browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    browser.kill()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
