# iPad Lobby Kiosk — Setup Guide

How to turn an iPad into a locked-down, full-screen display for the
dedication board in the building lobby. Follow these once and you're set.

**The page lives at:** `https://mendel-ctrl.github.io/dedication/`
_(This works after the project branch is merged and GitHub Pages is on.)_

---

## Step 1 — Add the page to the iPad Home Screen

This makes it open **full-screen** with no Safari address bar.

1. Open **Safari** on the iPad and go to `https://mendel-ctrl.github.io/dedication/`
2. Let it finish loading once **while on WiFi** — this saves an offline copy so
   the screen never goes blank if the WiFi hiccups later.
3. Tap the **Share** button (the square with an up-arrow, top of the screen).
4. Tap **Add to Home Screen** → **Add**.
5. Close Safari. Tap the new gold **Dedications** icon on the Home Screen.
   It now opens full-screen.

---

## Step 2 — Keep the screen awake (don't let it sleep)

1. Open **Settings → Display & Brightness → Auto-Lock**
2. Set it to **Never**.
3. (Keep the iPad plugged into power in the lobby.)

---

## Step 3 — Lock it to this one app (Guided Access)

Guided Access is Apple's built-in "kiosk mode." It stops a visitor from
leaving the page, opening other apps, or closing it.

**Turn the feature on first:**
1. **Settings → Accessibility → Guided Access** → toggle **ON**.
2. Tap **Passcode Settings → Set Guided Access Passcode** and choose a code
   only staff know (so only you can exit). Write it down somewhere safe.

**Start it each time the iPad goes on display:**
1. Open the **Dedications** app from the Home Screen.
2. **Triple-click** the top button (or Home button on older iPads).
3. Tap **Start** (top-right).

The iPad is now locked to the dedication board. To exit, triple-click again
and enter your passcode.

> Tip: While starting Guided Access you can tap **Options** to also turn the
> **volume buttons** and **motion** off, so nothing is disturbed on display.

---

## Step 4 — (Optional) Hide the touch dots / keep it tidy

- In Guided Access **Options**, you can disable **Touch** in specific corners
  if you want to block certain areas — usually not needed here.
- Turn on **Settings → Accessibility → Guided Access → Mirror Display
  Auto-Lock: Off** so the screen stays lit inside Guided Access.

---

## Updating the board later

You (or whoever edits the site) just change the content in
`dedication/index.html` and it goes live automatically. The iPad will pick up
the new version the next time it's online — **no need to reinstall anything.**

If a big change doesn't appear, on the iPad: exit Guided Access, open Safari
once to `https://mendel-ctrl.github.io/dedication/` while on WiFi to refresh
the saved copy, then relaunch the Home Screen app.

---

## Quick troubleshooting

| Problem | Fix |
|---|---|
| Screen went to sleep | Auto-Lock must be **Never** (Step 2), and keep it plugged in |
| A visitor closed/left the app | Make sure **Guided Access is started** (Step 3) |
| Page looks blank on first ever load | It needs internet the **first** time to save its offline copy |
| Edits aren't showing | Open it in Safari once on WiFi to refresh (see "Updating" above) |
| Want a different exit code | Settings → Accessibility → Guided Access → Passcode Settings |
