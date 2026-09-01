# Draft: API key request to Casambi Support

Send to **support@casambi.com**. Fill in the bracketed parts. Keep it short —
they mainly need to know the network exists, you're the admin, and what you want
to build.

---

**Subject:** API key request — Chabad Center Casambi network

Hello Casambi Support,

We operate a Casambi lighting network in our building and would like to request
developer **API access (an X-Casambi-Key)** so we can control our own lights
programmatically.

Details:

- **Organization:** Chabad Center
- **Casambi network name:** Chabad Center
- **Network admin email:** [the email you use to log into the Casambi app as admin]
- **Approximate size:** [e.g. ~30 luminaires across sanctuary, lobby, social hall]
- **Gateway:** we have a dedicated Casambi Cloud Gateway installed, wired via
  Ethernet, currently online.
- **Intended use:** internal, on-demand control and simple schedules for our own
  single network only — no third-party or multi-site product.
- **Access needed:** network-level API key + confirmation of the REST and
  WebSocket endpoints for our network.

Could you let us know how to obtain the key and any terms we should be aware of?

Thank you,
[Your name]
[Phone / role]

---

After they reply with the key, paste it into `casambi/.env` as `CASAMBI_API_KEY`
and continue with Step 4 in `README.md`.
