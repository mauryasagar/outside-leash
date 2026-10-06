# Outside Leash build log

## Day 1 (Oct 6)

Picked the idea: a Chrome extension that sends me to a quest page after too long on YouTube or Reddit, and only lets me back once I send a photo that matches the quest. Everything runs on my laptop (16 GB RAM, no GPU).

**Picking the vision model**
- Qwen3-VL 2B took about 47 seconds per photo. Almost all of that was the model reading the image (about 1100 tokens), and shrinking the photo changed nothing.
- Gemma 4 E2B took about 31 seconds at first, because it writes out its reasoning before answering. With thinking turned off it took about 3.4 seconds. Using that.
- On my first three test photos it was right every time: pink flowers (no tree), a real tree (yes), a wooden table (no). Those were pictures from Google, not mine, so I'm not counting them as results.

**Quests**
- Asking the model for both the quest and the check question went badly. It kept giving leaf quests, and some check questions were useless, like "is the photo clear?"
- Now the code picks a theme at random, the model only words the quest, and I wrote the check question for each theme by hand.
- First quests sounded like a form ("within a 10-minute walk during daylight"). Rewrote the prompt and now they read like a text from a friend.

**Things that broke**
- My phone's camera gave a "low memory" error when the page opened it, so I added a pick-from-gallery button. Downside: that button lets me upload any old photo, so it's a way to cheat.
- The phone couldn't reach the laptop at first. Fixed it by checking the network settings.
- The pink flower photo passed an "old thing" quest. The check was too loose, so I rewrote the checks to ask about the main subject of the photo. Haven't tested the new wording yet.
- A YouTube screenshot was rejected, which is what I wanted.

**The lock**
- YouTube jumped to the quest page, I sent a photo from my phone, and the laptop went back to YouTube by itself. It took a few seconds to load back.
- It locked sooner than I expected because my earlier test time was still counted for the day.
- Laptop can't upload photos anymore, only the phone can.
- Limit is now 20 minutes.

**Known weak spots**
- Turn off the extension and the lock is gone.
- The lock only works while the server is running.
- A photo of a screen showing a tree probably passes. Haven't tested it properly yet.

## Day 2 onward

Template for each lockout:

- **Time and site:**
- **Quest:**
- **What I did:**
- **Did the check get it right:**
- **What annoyed me:**
