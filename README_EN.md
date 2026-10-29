<p align="center">
  <img src="assets/banner.svg" alt="CampusFreeRoom">
</p>

<!-- badges -->
[![License](https://img.shields.io/github/license/huanweide/tust-classroom)](LICENSE)
[![CI](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-102%20passed-brightgreen)](#-quality)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Zero backend](https://img.shields.io/badge/deploy-static%20Pages-blue?logo=github)](https://huanweide.github.io/tust-classroom/)
<!-- /badges -->

# 🏫 CampusFreeRoom · Free-Classroom Finder Framework for Universities

> **Your campus portal already knows which classrooms are free right now — it just keeps that data behind a login, inside the campus network, on a page your phone can't render.** This framework moves that data out and turns it into a zero-backend static PWA you can open anywhere, even offline.
>
> **Auto-flow**: reuse a logged-in browser → walk campus → building → period → dedupe into SQLite → export per-day JSON shards → publish to Pages
> `crawl → dedupe → export → publish`

**Live demo (Tianjin University of Science & Technology, Taida + Hexi campuses)**: <https://huanweide.github.io/tust-classroom/>

[30-Second Demo](#-30-second-demo) · [Problem](#-the-problem) · [Features](#-features) · [Quick Start](#-quick-start) · [CLI](#-cli-reference) · [Architecture](#-architecture) · [Add Your School](#-add-your-own-school) · [Roadmap](#-roadmap) · [Quality](#-quality) · [License](#-license)

---

## 🏫 30-Second Demo

**Today (for most students anywhere):**

```
$ me (trying to find a free classroom to study in)
  → walk to the teaching building and peek through door windows   # exhausting, still incomplete
  → or go back to the dorm, boot a laptop, log into the portal    # needs campus network / VPN
  → click Teaching Resources → Free Classrooms → campus → bldg    # 4-5 clicks before any result
  → want to check it on your phone, standing in the hallway?      # no mobile layout — unusable
```

**With a site exported by this framework:**

```
$ open huanweide.github.io/tust-classroom/ on your phone
  → pick campus: Taida / Hexi
  → pick period: 1-13
  → instantly see which rooms are free; "Add to Home Screen" to use it as an app
  → no campus network, no VPN, no login — works offline (Service Worker cache)
```

One-sentence difference: **this is not "a free-classroom page for one university" — it is a pipeline that turns any university's portal data into an offline site.** Switching schools costs **one adapter file (~150 lines)**.

---

## 🏫 The Problem

| Role | Pain | How this helps |
|---|---|---|
| Student | Finding an empty room means physically walking the building, or logging into the portal at a desk | Open a URL on your phone, pick a period, see free rooms instantly |
| Student developer | Every university has someone's one-off "free classroom" script; changing schools means rebuilding from scratch | A generic pipeline: **one new school = one adapter (4 methods, ~30 min)** |

### How it differs from similar projects

Search GitHub for "free classroom finder" and nearly every result is a **single-school, single-implementation** script:

| | Single-school script (most of them) | This framework |
|---|---|---|
| Scope | 1 university | any university (add a file) |
| Cost to switch schools | rewrite from zero | write one adapter (~150 lines) |
| Data pipeline | ad hoc, uneven quality | unified crawl → store → export → publish |
| Frontend | usually none, or crude | ready-made PWA: installable, offline, mobile-optimized |
| Tests | basically none | 102 unit tests + real-browser E2E |
| Contract check | none | `check` catches what your adapter forgot to implement |

The first supported school is **Tianjin University of Science & Technology (TUST)** — 2 campuses, 13 periods, live in production.

---

## 🏫 Features

- **🔌 Adapter Contract** — one school = one adapter: implement `profile` + 4 methods (`list_campuses` / `list_buildings` / `select_building` / `list_free_rooms`). Walking dates, buildings and periods, dedupe-insert, and static export are all handled by the framework. `campusfree/adapter.py`
- **🔑 CDP Session Reuse** — connects over the Chrome DevTools Protocol to a browser window **you already logged into**. **Never touches your password, never saves a cookie file** — so captchas, CAS redirects and device binding are non-issues. `campusfree/cdp.py`
- **🛡️ Export Gate** — refuses to export when your local data covers fewer days than production, preventing "the crawl broke and 130 days of live data got overwritten by 3". This is the most dangerous form of silent data loss. `campusfree/exporter.py`
- **🧪 Contract Check** — `check` runs **without network and without a browser**: a purely static inspection of your adapter, turning "crawled for an hour then discovered a missing method" into a 3-second check. `campusfree/adapter.py` · `validate_adapter()`
- **📦 Daily Sharding** — one JSON file per day; the frontend fetches only today, so first paint is tens of KB instead of a multi-MB blob. `campusfree/exporter.py`
- **🔁 Resumable Runner** — crawl scheduling with resume and failure isolation: one broken day doesn't poison the rest. `campusfree/runner.py`
- **🧭 Scaffold Generator** — `new-school` emits an adapter skeleton with TODOs; just fill it in. `campusfree/scaffold.py`
- **🔒 Read-Only Dry Run** — `refresh_crawl.py --dry-run` opens the database with `mode=ro`, so it **physically cannot write** — inspect first, decide later. `refresh_crawl.py`

---

## 🏫 Quick Start

### Route A — I just want to find a free classroom (TUST students)

Just open this URL; install nothing:

**📱 <https://huanweide.github.io/tust-classroom/>**

- Open in any mobile browser; "Add to Home Screen" to use it as an app
- No campus network, no VPN, no login required
- Data refreshes automatically every hour

### Route B — I want my own school supported (developers)

```bash
# 1. install deps
pip install -r requirements-dev.txt
playwright install chromium

# 2. see which schools are registered
python -m campusfree schools

# 3. health-check an adapter (no network, purely static)
python -m campusfree check --school tust

# 4. scaffold an adapter for your own school
python -m campusfree new-school nku --name "Nankai University"
#    → generates adapters/nku.py; fill in the TODOs

# 5. self-check after filling it in
python -m campusfree check --school nku

# 6. crawl (launches a browser; log into the portal once inside it)
python -m campusfree run --school nku --range 0-6

# 7. export the static site
python -m campusfree export --school nku
```

Full guide: **[docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md)**

**Real output of `schools`:**

```
$ python -m campusfree schools
1 school registered:

ID          School                Periods  Default campus  Portal
------------------------------------------------------------------------------------------
tust        Tianjin Univ. of S&T      13   Taida           http://jwxtxs.tust.edu.cn:46110
```

**Real output of `check`:**

```
$ python -m campusfree check --school tust
Target: Tianjin University of Science and Technology (tust)
  Portal : http://jwxtxs.tust.edu.cn:46110/student/teachingResources/freeClassroom/index
  Periods: 13
  Campus : Taida
  Browser: Microsoft Edge | exe=...\msedge.exe | profile=...\tust-classroom\edge-cdp-profile | port=9222

[OK] Adapter contract checks all passed. Ready to crawl.
```

---

## 🏫 CLI Reference

| Command | Purpose | Needs browser? |
|---|---|---|
| `python -m campusfree schools` | list all registered schools | no |
| `python -m campusfree check --school tust` | health-check an adapter | no |
| `python -m campusfree run --school tust --range 0-6` | crawl the next 7 days | yes |
| `python -m campusfree run --school tust --auto` | auto-detect term bounds, crawl to the break | yes |
| `python -m campusfree export --school tust` | export static JSON | no |
| `python -m campusfree new-school <id>` | scaffold a new school adapter | no |

Crawl a single day: `run --school tust --dayoffset 1` (1 = tomorrow)

### Scheduled refresh (overwrite stale data)

`INSERT OR IGNORE` has a trap: it skips on UNIQUE conflicts, so **re-crawling the same day never updates anything** and you won't notice when the registrar changes the schedule. `refresh_crawl.py` does DELETE-then-INSERT instead:

```bash
python refresh_crawl.py --dry-run    # read-only checkup: no writes, no portal requests
python refresh_crawl.py              # refresh 7 days from today, overwriting old values
python refresh_crawl.py --repast 7   # also re-crawl the past 7 days (fix history)
```

Three safeguards: ① `--dry-run` opens the DB with `mode=ro`, so it physically cannot write ② history is not pruned by default (only with `--prune-days N`) — 130 days online is an asset ③ a post-crawl self-check alarms if any day falls below the row threshold. When the login session expires the portal returns an empty list, so **the crawler reports no error while the DB gets emptied and nothing is re-inserted** — the most dangerous silent data loss there is.

---

## 🏫 Architecture

The default engine is **a layered pipeline where "the adapter answers 5 questions and the framework does everything else"** — not a monolithic scraper. Adapters may not import playwright: the framework passes in an already-logged-in page object (duck-typed — anything with `.evaluate` / `.url` / `.goto`), which is exactly why adapters are unit-testable without a browser.

### Core concepts

| Concept | Meaning |
|---|---|
| adapter | one school's implementation; answers "URL / campuses / buildings / how to select a building / which rooms are free" |
| CDP reuse | attach to a locally logged-in browser; no password touched, no cookie file written |
| contract check | browser-free static inspection that catches missing adapter methods early |
| daily shard | one JSON per day; the frontend fetches only today, tens of KB first paint |
| export gate | refuses to export when local day coverage is short, protecting live data |
| `mode=ro` | opens the DB read-only so it physically cannot be written |

### Data pipeline

```
┌──────────────┐   CDP reuse  ┌───────────────┐  request  ┌──────────────┐
│ local browser│ ───────────▶ │ campusfree    │ ────────▶ │  campus      │
│ (logged in)  │   session    │ runner        │ free rooms│  portal      │
└──────────────┘              └───────┬───────┘           └──────────────┘
                                      │ ask
                              ┌───────▼───────┐
                              │ SchoolAdapter │ ← one per school, 4 methods
                              └───────┬───────┘
                                      ↓ normalize
┌──────────────┐  export   ┌───────────────┐  store   ┌──────────────┐
│ GitHub Pages │ ◀──────── │ static/data/  │ ◀─────── │ SQLite dedupe│
│ offline PWA  │ static JSON│ *.json daily  │          └──────────────┘
└──────────────┘           └───────────────┘
```

- **Crawl** — attach to your logged-in browser, walk campus → building → period, write into SQLite with automatic dedupe.
- **Export** — compress into per-day JSON shards (one file per day); the frontend fetches only today.
- **Publish** — drop it on GitHub Pages: zero backend, instant load, offline once the Service Worker caches it.

> Full layering and the reasoning behind each decision: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

### Core modules

| Module | File | Responsibility |
|---|---|---|
| Data model | `campusfree/model.py` | `Campus` / `Building` / `Room` / `Period` / `SchoolProfile` |
| Adapter protocol | `campusfree/adapter.py` | `SchoolAdapter` base class + `validate_adapter()` |
| Session reuse | `campusfree/cdp.py` | reuse local browser session; `BrowserSpec` holds exe/profile/port |
| Crawl scheduling | `campusfree/runner.py` | resume + failure isolation |
| Storage | `campusfree/store.py` | SQLite dedupe insert |
| Export | `campusfree/exporter.py` | → static JSON, includes the export gate |
| Scaffold | `campusfree/scaffold.py` | new-school skeleton generator |
| Registry | `campusfree/registry.py` | adapter auto-discovery |
| CLI | `campusfree/cli.py` | `schools` / `check` / `run` / `export` / `new-school` |

### Why no username/password login

Portal logins usually involve captchas, CAS redirects and device binding; simulating them is fragile *and* forces you to put your password into a config file. This framework instead **reuses a browser window you already logged into** (Chrome DevTools Protocol) — **no password handling, no cookie file saved**.

---

## 🏫 Supported Schools

| ID | School | Campuses | Periods | Status |
|---|---|---|---|---|
| `tust` | Tianjin University of Science & Technology | Taida + Hexi | 13 | ✅ official adapter, [live](https://huanweide.github.io/tust-classroom/) |

**Your school isn't here?** See below — about 30 minutes; PRs welcome.

---

## 🏫 Add Your Own School

One school = one adapter with 4 methods:

```python
from campusfree.adapter import SchoolAdapter
from campusfree.model import Building, Campus, Room, SchoolProfile

class NkuAdapter(SchoolAdapter):
    @property
    def profile(self) -> SchoolProfile:
        return SchoolProfile(school_id="nku", school_name="Nankai University",
                             base_url="https://jwxt.nku.edu.cn", period_count=13)

    def list_campuses(self, page):        return [Campus(name="Balitai")]
    def list_buildings(self, page, campus): return [Building(name="Main Building")]
    def select_building(self, page, campus, building) -> bool: ...
    def list_free_rooms(self, page, period, day_offset): return [Room(...)]
```

> Hard rule: **never import playwright inside an adapter.** The framework hands you an already-logged-in page object; you only issue requests and parse results inside that page — which is what makes adapters unit-testable without a browser.

Start from a skeleton: `python -m campusfree new-school nku --name "Nankai University"`

---

## 🏫 Roadmap

- [x] Generic framework extracted (`campusfree/`, 9 modules)
- [x] First official adapter: TUST (2 campuses / 13 periods / live)
- [x] 102 unit tests (the project previously had zero)
- [x] CI: Python 3.11 + 3.12 matrix, ruff + pytest + CLI smoke + frontend asset checks
- [x] Export gate + read-only dry-run mode
- [ ] Recruit 3 outside-school adapter PRs (currently only `tust`)
- [ ] Multi-school switching in the frontend
- [ ] Template `static/` so a new school gets its own page on export
- [ ] Data-freshness alarm (auto-open an Issue when `generated_at` goes stale)

---

## 🏫 Quality

| Type | Count | How to run |
|---|---|---|
| Unit tests | 102 passed | `pytest` |
| Lint | ruff clean | `ruff check .` |
| Compile check | clean | `python -m compileall -q .` |
| Adapter contract | self-checkable | `python -m campusfree check --school tust` |
| Frontend E2E | 11 real-browser clicks | `npm install && npm run e2e` |
| Normalization regression | 35 | `python test_normalize.py` |
| Crawl ops | 10 | `python test_refresh_crawl.py` |
| Room-browsing E2E | 65 real-browser | `node test_e2e_browse.mjs` |
| Full-chain | 47 | `python verify_all.py` |

`verify_all.py` runs nine layers in one command: data regression → export contract → per-day consistency → frontend/backend field alignment → real-browser E2E → export gate → crawl ops → credential scan. **Hard rule: a single FAIL means it is not delivered.**

**CI runs the first four** (Python 3.11 / 3.12 matrix + frontend asset checks); the last four need a local database or a real browser and are run locally.

Tests drive the whole pipeline through a **fake portal page** object (`tests/conftest.py`), so they need **no browser, no campus network, no login** — everything runs in CI.

```
102 passed in 7.29s
```

---

## 🏫 Data & Privacy

- **No account passwords are collected, stored, or transmitted.** No hardcoded credentials exist in the code.
- The session is reused from your local browser via CDP only; **no cookie file is saved**.
- Data is written only to a local SQLite file (`data/classrooms.db`, already git-ignored); published static files contain no account information.
- If your adapter needs account info, use environment variables only — **never commit it**.

### Credential safety

- Never commit credential files. `.gitignore` already excludes `.env`, `data/cookies.txt`, `*.key`, etc.
- Scan staged content for key-like patterns (key prefixes, private-key headers, session cookies) before every commit.
- If a leak happens: change your portal password immediately; old session tokens become invalid.

---

## 🏫 Directory Layout

```
.
├── campusfree/            # generic framework (don't touch when adding a school)
│   ├── model.py           #   Campus/Building/Room/Period/SchoolProfile
│   ├── adapter.py         #   SchoolAdapter protocol + contract validation
│   ├── cdp.py             #   reuse browser session
│   ├── runner.py          #   crawl scheduling (resume, failure isolation)
│   ├── store.py           #   SQLite storage
│   ├── exporter.py        #   → static JSON
│   ├── scaffold.py        #   new-school skeleton generator
│   ├── registry.py        #   adapter auto-discovery
│   └── cli.py             #   CLI
├── adapters/              # per-school adapters (adding a school touches only this)
│   └── tust.py            #   Tianjin University of Science & Technology
├── tests/                 # 102 unit tests
├── docs/
│   ├── ADAPTER_GUIDE.md   #   30-minute onboarding guide
│   └── ARCHITECTURE.md    #   architecture notes
├── static/                # PWA frontend + exported static data
├── crawler_playwright.py  # compatibility entry (old usage unchanged)
├── export_static.py       # compatibility entry
└── app.py                 # local query API (127.0.0.1:5000)
```

---

## 🏫 Contributing

The most welcome contribution: **write an adapter for your own school**.

1. `python -m campusfree new-school <school-id>`
2. Follow [docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md) and fill in the 4 methods
3. `python -m campusfree check --school <id>` to self-check
4. Add a row to the Supported Schools table and open a PR

---

## 🏫 Disclaimer

Unofficial tool; data comes from each university's portal. Schedules may change at short notice — always defer to your registrar's official announcements. Do not use it for any prohibited purpose.

## 🧰 More Tools by the Same Author

> The author maintains a series of open-source productivity tools — a Star is always appreciated:

- 📚 Long-form writing — AI novel workshop, local rule engine, zero dependencies: [visit](https://github.com/huanweide/novel-smith)
- 🎓 Course assistant — Zhihuishu autoplay / resume / AI answering: [visit](https://github.com/huanweide/zhihuishu-helper)
- 🎬 Subtitles — one-click Bilibili subtitle extraction (no API key): [visit](https://github.com/huanweide/bili-subtitle-universal)
- 📺 Live captions — real-time subtitles for streams and meetings: [visit](https://github.com/huanweide/live-subtitle)
- ✂️ Video summary — one-click summarization of long videos: [visit](https://github.com/huanweide/video-brief)
- 🖥️ Overview — hub of all the author's open-source projects: [visit](https://github.com/huanweide/family-showcase)
- 🩺 Code health — zero-dependency multi-axis static checkup: [visit](https://github.com/huanweide/doctors)

## 🏫 License

[MIT](LICENSE) · by [ReTri · huanweide](https://github.com/huanweide)

---

## ⭐ Star

If you're tired of walking the building looking for an empty room — or of rebuilding the whole thing from scratch for your own school — a Star helps more students find this framework. The most welcome contribution is **an adapter for your own school**.

[![Star](https://img.shields.io/github/stars/huanweide/tust-classroom?style=social)](https://github.com/huanweide/tust-classroom)
