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
body{font-family:system-ui,sans-serif;max-width:520px;margin:2rem auto;padding:0 1rem;line-height:1.5}
button,input{font-size:1.1rem;margin-top:1rem}
#res{margin-top:1rem;font-weight:600}
</style></head><body>
<h2>Outside Leash</h2>
<p id="quest">Loading your quest...</p>
<p><small>On your phone open: <b>__PHONE__</b></small></p>
<input id="f" type="file" accept="image/*" capture="environment" disabled><br>
<input id="g" type="file" accept="image/*" disabled> <small>(or pick from gallery)</small>
<p id="res"></p>
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
  if (onLaptop) {
    document.getElementById('res').textContent = 'Do this one on your phone. Open the address above.';
    document.getElementById('f').style.display = 'none';
    document.getElementById('g').style.display = 'none';
  } else {
    document.getElementById('f').disabled = false;
    document.getElementById('g').disabled = false;
  }
});
async function handle(e) {
  const file = e.target.files[0];
  if (!file) return;
  const res = document.getElementById('res');
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
    res.textContent = d.error ? d.error : (d.passed ? 'Passed. You can go back to your laptop.' : 'Not quite. Try another photo.');
  } catch (err) {
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
