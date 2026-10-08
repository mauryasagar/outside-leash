import base64, glob, os
from outside_leash_server import ask_ollama

q = "Is this a photo of a screen, such as a monitor, laptop or phone display showing an image? Answer yes or no."

for path in sorted(glob.glob("testphotos/*.*")):
    with open(path, "rb") as f:
        img = base64.b64encode(f.read()).decode()
    answer = ask_ollama(q, images=[img], max_tokens=10)
    said_yes = answer.strip().lower().startswith("yes")
    should_be_yes = os.path.basename(path).startswith("no_screen")
    print("OK   " if said_yes == should_be_yes else "WRONG", os.path.basename(path), answer)