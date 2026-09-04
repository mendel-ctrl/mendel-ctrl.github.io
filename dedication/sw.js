/* ============================================================================
   SERVICE WORKER  ·  the "offline safety net" for the dedication board
   ----------------------------------------------------------------------------
   Plain-English version of what this file does:

   A service worker is a tiny helper the browser keeps running in the
   background. The FIRST time the tablet loads the page online, this helper
   saves a copy of the page (and its fonts) onto the tablet. After that, if
   the building's WiFi drops or gets slow, the tablet shows the saved copy
   instead of a blank screen. When the internet is back, it quietly grabs the
   latest version again so your edits still show up.

   YOU DO NOT NEED TO EDIT THIS FILE. The one thing to know:
   whenever you make a BIG change and want to force every tablet to refresh,
   change the version number on the next line (e.g. "v1" -> "v2").
   ========================================================================== */

const CACHE = "dedication-v1";

// The core files to save for offline use (the "app shell").
const CORE = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-180.png",
  "./icon-192.png",
  "./icon-512.png",
];

// 1) INSTALL — save the core files the first time.
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(CORE)).then(() => self.skipWaiting())
  );
});

// 2) ACTIVATE — delete any older saved versions so we don't pile them up.
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// 3) FETCH — decide, for each request, whether to use the internet or the
//    saved copy.
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // only handle simple page/asset loads

  const isPage = req.mode === "navigate" ||
                 (req.headers.get("accept") || "").includes("text/html");

  if (isPage) {
    // For the page itself: try the internet first (so fresh edits show),
    // but fall back to the saved copy if we're offline.
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put("./index.html", copy));
          return res;
        })
        .catch(() => caches.match("./index.html").then((r) => r || caches.match("./")))
    );
    return;
  }

  // For everything else (fonts, icons): use the saved copy first (fast),
  // and quietly save anything new we successfully download.
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
