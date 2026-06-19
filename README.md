# BrightBank — AI-Assisted Account Opening Form (eKYC)

A Flask-based bank account opening application that uses a self-hosted **Qwen2.5-VL**
vision-language model (served via **Ollama** on a remote GPU server) to automatically
read identity documents — Aadhaar, PAN, or Driving License — and pre-fill the
applicant's details, instead of requiring manual typing.

No cloud AI APIs (OpenAI, Anthropic, etc.) are used anywhere in this project. The only
model call this app makes is to your own self-hosted Ollama instance.

---

## How it works

```
Applicant                          Flask App                      Remote GPU Server
   |                                   |                                  |
   | 1. Uploads ID photo               |                                  |
   |---------------------------------->|                                  |
   |                                   | 2. Sends image + prompt          |
   |                                   |---------------------------------->|
   |                                   |                          Ollama runs Qwen2.5-VL
   |                                   | 3. Returns extracted JSON         |
   |                                   |<----------------------------------|
   | 4. Reviews/corrects pre-filled    |                                  |
   |    form, fills account details    |                                  |
   |---------------------------------->|                                  |
   | 5. Submits application            |                                  |
   |---------------------------------->|  Saved to database.db            |
```

If the remote server can't be reached, times out, or returns something that isn't
valid JSON, the app **does not crash** — it falls back to an empty manual-entry form
and clearly flags the application as `Manual` in the admin dashboard, so nothing
silently fails.

---

## Features

- **4-step application wizard**: Upload ID → Review extracted details → Account
  preferences → Final review & submit
- **AI document scanning** for Aadhaar, PAN, and Driving License via Qwen2.5-VL
- **Graceful manual fallback** if the AI scan fails for any reason
- **Aadhaar number masking** — only the last 4 digits are ever stored or displayed,
  anywhere in the app (see *Compliance* below)
- **Audit trail** — the model's raw JSON response is stored per application, useful
  for debugging extraction issues later
- **Admin dashboard** — view all applications, see whether each was Auto-scanned or
  Manually entered, update application status (Submitted → Under Review → Approved/Rejected)
- **Auto-generated reference numbers** (`AOF<date><random>`) for tracking

---

## Project structure

```
aof_kyc/
├── app.py              # Routes: wizard steps, confirmation, admin
├── config.py            # DB, upload, and Ollama connection settings
├── extensions.py        # Shared SQLAlchemy db object
├── models.py             # AccountApplication table
├── ocr_extract.py        # Talks to Qwen2.5-VL via Ollama; parsing + error handling
├── requirements.txt
├── templates/             # Jinja2 templates for every page
├── static/css/style.css
└── uploads/                # Saved ID document images (auto-created)
```

---

## Setup

### 1. On the remote GPU server (where Qwen2.5-VL runs)

```bash
ollama pull qwen2.5vl:7b        # or qwen2.5vl:3b on lower-memory machines
OLLAMA_HOST=0.0.0.0 ollama serve
```

By default Ollama only listens on `127.0.0.1`, so the `OLLAMA_HOST=0.0.0.0` part is
required for this app — running on a different machine — to reach it at all.

**Security note:** Ollama has no built-in authentication. Don't expose port `11434`
to the open internet. Restrict it with a firewall/security group to known IPs, or
tunnel over SSH instead of opening the port publicly:

```bash
ssh -L 11434:localhost:11434 user@remote-gpu-server
```

(If you tunnel, set `OLLAMA_HOST = "http://localhost:11434"` in `config.py` instead
of the server's real IP.)

### 2. On the machine running this Flask app

```bash
cd aof_kyc
pip install -r requirements.txt
```

Edit `config.py` and set `OLLAMA_HOST` to your remote server's actual address:

```python
OLLAMA_HOST = "http://203.0.113.10:11434"   # your server's real IP
```

### 3. Run it

```bash
python app.py
```

Open `http://localhost:5001`.

---

## Using the app

1. **Home page** → "Start Application"
2. **Step 1** → choose document type (Aadhaar / PAN / Driving License), upload a clear photo
3. **Step 2** → review the auto-filled fields (or fill them manually if the scan failed) — a
   badge at the top tells you honestly which case you're in
4. **Step 3** → account type, initial deposit, nominee details
5. **Step 4** → final review, then submit — you'll get a reference number (e.g. `AOF2606190001`)
6. **`/admin`** → view all submitted applications, change status, see the Auto/Manual
   scan-method badge per row

---

## Compliance note: Aadhaar handling

Per UIDAI guidance, full Aadhaar numbers should not be stored or displayed
unnecessarily. This app masks the Aadhaar number **immediately at extraction time**,
inside `ocr_extract.py` — by the time the number reaches the form, the database, or
the admin dashboard, only the last 4 digits (`XXXX XXXX 1234`) are ever present. The
full number is never written to disk or to the session.

---

## What's been tested vs. what to verify yourself

Everything in this project was built and tested **except the live call to your actual
remote Qwen2.5-VL server**, since that server isn't reachable from the environment
this was built in. Specifically tested (with mocked Ollama responses):

- ✅ Clean JSON extraction response → fields pre-fill correctly
- ✅ Markdown-fenced JSON (` ```json ... ``` `) → still parses correctly
- ✅ Garbled/non-JSON response → falls back to manual entry, doesn't crash
- ✅ Connection refused / server unreachable → falls back to manual entry
- ✅ Aadhaar masking → only last 4 digits ever stored
- ✅ Full wizard flow (all 4 steps), database persistence, admin dashboard, status updates

**Worth testing yourself, with real documents against your real server:**
- Actual extraction accuracy of `qwen2.5vl:7b` on real Aadhaar/PAN/DL photos (lighting,
  angle, and image quality will all affect this)
- Network latency from your Flask app to the remote GPU server — the timeout is set to
  60 seconds in `config.py`, adjust `OLLAMA_TIMEOUT_SECONDS` if needed
- Whether `qwen2.5vl:3b` (lighter, faster) gives acceptable accuracy if `7b` is too
  slow on your hardware

---

## Possible future extensions

- Candidate-facing "track my application" lookup by reference number
- Login-protecting the `/admin` section
- Email/SMS notification on status change
- Side-by-side display of the uploaded document image next to the extracted fields
  in the admin dashboard, for manual verification
- Confidence scoring — re-prompting the model to flag fields it's unsure about
