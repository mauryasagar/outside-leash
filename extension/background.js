// Outside Leash - background script.
// Counts time you spend on the sites below. Once you pass the limit and you
// haven't completed a quest recently, the tab is sent to the local quest page.

const SITES = ["youtube.com", "reddit.com", "instagram.com", "facebook.com", "x.com", "twitter.com"];
const LIMIT_SECONDS = 20 * 60; // TESTING value. Change to 20 * 60 for real use.
const TICK_SECONDS = 30;  // how often we check (matches the alarm below)
const SERVER = "http://localhost:8000";

chrome.alarms.create("tick", { periodInMinutes: TICK_SECONDS / 60 });

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== "tick") return;

  // only count time when you are actually looking at a blocked site
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab || !tab.url) return;
  let host;
  try { host = new URL(tab.url).hostname; } catch (e) { return; }
  if (!SITES.some((s) => host === s || host.endsWith("." + s))) return;

  const today = new Date().toDateString();
  const saved = await chrome.storage.local.get(["used", "day"]);
  let used = saved.day === today ? (saved.used || 0) : 0;
  used += TICK_SECONDS;
  await chrome.storage.local.set({ used, day: today });
  if (used < LIMIT_SECONDS) return;

  // over the limit: ask the local server whether a quest was completed recently
  try {
    const res = await fetch(SERVER + "/status");
    const status = await res.json();
    if (status.unlocked) {
      await chrome.storage.local.set({ used: 0 }); // fresh allowance after a quest
      return;
    }
  } catch (e) {
    return; // server not running: do nothing (the lock only works while it is on)
  }

  chrome.tabs.update(tab.id, { url: SERVER + "/?back=" + encodeURIComponent(tab.url) });
});
