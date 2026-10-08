"""
Outside Leash - local server (standard library only, no pip installs).

Run:   python outside_leash_server.py
Needs: Ollama running, with the model pulled:  ollama pull gemma4:e2b

Open on your laptop:   http://localhost:8000
Open on your phone:    the http://<laptop-ip>:8000 address printed at startup
                       (phone and laptop must be on the same Wi-Fi)
"""
import base64
import json
import os
import random
import socket
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request as urlrequest

MODEL = "gemma4:e2b"
OLLAMA = "http://localhost:11434/api/generate"
PORT = 8000
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

# The model only words the quest. The check question is written by hand, so the
# model can never make the check stricter or looser than the quest.
THEMES = [
    ("something with a repeating pattern",
     "Is the main subject of the photo a repeating pattern, such as tiles, bricks, a fence, windows or bark?"),
    ("something much older than you",
     "Is the main subject of the photo something that looks old or weathered, such as a wall, tree, stone or building? A plant or surface that is only in the background does not count."),
    ("something that is a different colour from everything around it",
     "Is the main subject of the photo one object that clearly stands out in colour from everything around it?"),
    ("a living thing that is not a person",
     "Is the main subject of the photo a plant, a bird, an insect or an animal?"),
    ("the sky",
     "Is at least half of the photo sky or clouds?"),
    ("a clear shadow",
     "Is a clear shadow the main subject of the photo?"),
]
STYLES = ["find", "notice", "photograph"]

UNLOCK_MINUTES = 30  # how long a passed quest keeps the sites unlocked

QUESTS = {}  # quest id -> {"quest": ..., "check": ...}
STATE = {"current": None, "unlocked_until": 0}


def ask_ollama(prompt, images=None, max_tokens=80):
    body = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {"num_predict": max_tokens},
    }
    if images:
        body["images"] = images
    req = urlrequest.Request(OLLAMA, data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
    with urlrequest.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())["response"].strip()


def make_quest():
    theme, check = random.choice(THEMES)
    style = random.choice(STYLES)
    prompt = (
        "You write short text quests for a person who will go outside and take a photo "
        "themselves. You never take photos. Write one quest, at most 15 words, in a casual "
        f"tone like a friend texting. The quest is to {style} {theme}. "
        "Silently follow these rules without mentioning them: doable in 10 minutes on foot "
        "near home, daylight, no roads or traffic, no water edges, no private property, "
        "nothing risky, no parks or special places needed. "
        "Do not mention leaves, time, distance or safety. "
        "Output exactly one line starting with QUEST: and nothing else."
    )
    try:
        text = ask_ollama(prompt)
        line = next((l for l in text.splitlines() if l.strip().upper().startswith("QUEST:")), "")
        quest = line.split(":", 1)[1].strip() if line else ""
    except Exception as e:
        print("quest generation failed:", e)
        quest = ""
    if not quest:
        quest = f"Go outside and {style} {theme}, then take one photo of it."
    qid = uuid.uuid4().hex[:8]
    QUESTS[qid] = {"quest": quest, "check": check}
    print(f"[quest {qid}] {quest}")
    return qid, QUESTS[qid]


def check_photo(qid, data):
    q = QUESTS.get(qid)
    if not q:
        return {"error": "Unknown quest. Reload the page to get a new one."}
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # random file name so a name like "tree.jpg" can never hint the model
    path = os.path.join(UPLOAD_DIR, uuid.uuid4().hex + ".jpg")
    with open(path, "wb") as f:
        f.write(data)
    prompt = q["check"] + " Answer yes or no."
    answer = ask_ollama(prompt, images=[base64.b64encode(data).decode()], max_tokens=10)
    passed = answer.strip().lower().startswith("yes")
    print(f"[check {qid}] answer={answer!r} passed={passed}")
    if passed:
        STATE["unlocked_until"] = time.time() + UNLOCK_MINUTES * 60
        STATE["current"] = None  # next visit gets a fresh quest
    return {"passed": passed, "answer": answer}


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Outside Leash</title>
<style>
:root{--bg:#0f1a14;--card:#16251c;--text:#eef5ef;--muted:#9bb3a2;--accent:#6fcf8e;--bad:#e8806f}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;padding:1rem}
.card{width:100%;max-width:460px;background:var(--card);border-radius:20px;padding:2rem 1.5rem;text-align:center;box-shadow:0 10px 40px rgba(0,0,0,.35)}
.brand{color:var(--accent);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:.8rem}
.label{color:var(--muted);font-size:.9rem;margin-top:1.5rem}
#quest{font-size:1.5rem;line-height:1.35;font-weight:600;margin:.5rem 0 1.5rem}
.btn{display:block;width:100%;padding:1rem;border-radius:14px;font-size:1.05rem;font-weight:600;cursor:pointer;margin-top:.75rem;border:0}
.primary{background:var(--accent);color:#0b1a11}
.secondary{background:transparent;color:var(--muted);border:1px solid #2f4a39}
.btn input{display:none}
#res{min-height:1.5rem;margin-top:1.25rem;font-weight:600}
.ok{color:var(--accent)}
.bad{color:var(--bad)}
.addr{margin-top:.5rem;padding:.75rem;border-radius:12px;background:#0f1a14;font-family:ui-monospace,monospace;color:var(--accent);word-break:break-all}
.hint{color:var(--muted);font-size:.85rem;margin-top:1rem}
</style></head><body>
<div class="card">
  <div class="brand">Outside Leash</div>
  <div class="label">Your quest</div>
  <div id="quest">Loading your quest...</div>
  <div id="laptop" style="display:none">
    <div class="label">Open this on your phone</div>
    <div class="addr">__PHONE__</div>
    <div class="hint">Same Wi-Fi as this laptop. This page unlocks by itself once you pass.</div>
  </div>
  <div id="phone" style="display:none">
    <label class="btn primary">Take a photo<input id="f" type="file" accept="image/*" capture="environment"></label>
    <label class="btn secondary">Pick from gallery<input id="g" type="file" accept="image/*"></label>
  </div>
  <div id="res"></div>
</div>
<script>
let qid = null;
const back = new URLSearchParams(location.search).get('back');
setInterval(async () => {
  try {
    const s = await (await fetch('/status')).json();
    if (s.unlocked && back) location.href = back;
  } catch (e) {}
}, 3000);
fetch('/quest').then(r => r.json()).then(d => {
  qid = d.id;
  document.getElementById('quest').textContent = d.quest;
  const onLaptop = ['localhost', '127.0.0.1'].includes(location.hostname);
  document.getElementById(onLaptop ? 'laptop' : 'phone').style.display = 'block';
});
async function handle(e) {
  const file = e.target.files[0];
  if (!file) return;
  const res = document.getElementById('res');
  res.className = '';
  res.textContent = 'Checking your photo...';
  try {
    let body = file;
    try {
      // shrink big phone photos before upload (saves phone memory and time)
      const bmp = await createImageBitmap(file, {resizeWidth: 800, resizeQuality: 'medium'});
      const c = document.createElement('canvas');
      c.width = bmp.width; c.height = bmp.height;
      c.getContext('2d').drawImage(bmp, 0, 0);
      body = await new Promise(ok => c.toBlob(ok, 'image/jpeg', 0.85));
    } catch (err) { console.log('resize failed, sending original', err); }
    const r = await fetch('/check?id=' + qid, {method: 'POST', body: body});
    const d = await r.json();
    if (d.error) { res.className = 'bad'; res.textContent = d.error; }
    else if (d.passed) { res.className = 'ok'; res.textContent = 'Passed. You can go back to your laptop.'; }
    else { res.className = 'bad'; res.textContent = 'Not quite. Try another photo.'; }
  } catch (err) {
    res.className = 'bad';
    res.textContent = 'Upload failed: ' + err;
  }
  e.target.value = '';
}
document.getElementById('f').addEventListener('change', handle);
document.getElementById('g').addEventListener('change', handle);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        raw = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            page = PAGE.replace("__PHONE__", f"http://{lan_ip()}:{PORT}")
            self._send(200, page, "text/html; charset=utf-8")
        elif path == "/quest":
            if STATE["current"] is None:
                STATE["current"] = make_quest()
            qid, q = STATE["current"]
            self._send(200, json.dumps({"id": qid, "quest": q["quest"]}))
        elif path == "/status":
            left = int(STATE["unlocked_until"] - time.time())
            self._send(200, json.dumps({"unlocked": left > 0, "seconds_left": max(left, 0)}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        if not self.path.startswith("/check"):
            return self._send(404, json.dumps({"error": "not found"}))
        ip = self.client_address[0]
        if ip in ("127.0.0.1", "::1") or ip == lan_ip():
            return self._send(403, json.dumps({"error": "Finish the quest from your phone, not this laptop."}))
        qid = self.path.split("id=")[-1] if "id=" in self.path else ""
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        try:
            self._send(200, json.dumps(check_photo(qid, data)))
        except Exception as e:
            print("check failed:", e)
            self._send(500, json.dumps({"error": "Could not check the photo. Is Ollama running?"}))

    def log_message(self, *a):
        pass


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "localhost"
    finally:
        s.close()


if __name__ == "__main__":
    print(f"Outside Leash server running.\n  Laptop: http://localhost:{PORT}\n  Phone:  http://{lan_ip()}:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
