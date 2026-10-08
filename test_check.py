import base64, glob, os, time
from outside_leash_server import THEMES, ask_ollama

question = THEMES[1][1] + " If the photo shows a screen, a monitor, a phone display, or is a picture of a picture, answer no."
print("Question:", question, "\n")

for path in sorted(glob.glob("testphotos/*.*")):
    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    start = time.time()
    answer = ask_ollama(question + " Answer yes or no.", images=[img], max_tokens=10)
    passed = answer.strip().lower().startswith("yes")
    expected = os.path.basename(path).startswith("yes")
    verdict = "OK " if passed == expected else "WRONG"
    print(f"{verdict} {os.path.basename(path)}: said {answer!r} ({time.time()-start:.1f}s)")