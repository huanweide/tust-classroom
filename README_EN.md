**中文** · [README.md](./README.md)

<p align="center">
  <img src="assets/banner.svg" alt="CampusFreeRoom">
</p>

[![License](https://img.shields.io/github/license/huanweide/tust-classroom)](LICENSE)
[![CI](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml/badge.svg)](https://github.com/huanweide/tust-classroom/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/unit%20tests-102%20passed-brightgreen)](#quality-assurance)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Zero-backend](https://img.shields.io/badge/deploy-pure%20static%20Pages-blue?logo=github)](https://huanweide.github.io/tust-classroom/)
[![Live](https://img.shields.io/badge/open%20on%20phone-a%20certain%20university-success)](https://huanweide.github.io/tust-classroom/)

# CampusFreeRoom · a framework for querying free classrooms at any university

> Academic portals already know "which classrooms are free right now" — but that data is trapped behind a login, only reachable on the campus network, and unreadable on a phone. This framework pulls that data out into an offline-capable, zero-backend static PWA you can open on a phone anytime.
>
> A framework that turns "which classrooms are free right now" out of login-walled campus portals into an offline, zero-backend static PWA.
>
> **Pipeline**: reuse your logged-in browser → by campus → by building → by period → deduplicate into SQLite → export daily-sharded JSON → publish to Pages
> `collect → deduplicate → export → publish`

**Live example (a certain university, two campuses)**: <https://huanweide.github.io/tust-classroom/>

[30-Second Overview](#30-second-overview) · [What It Solves](#what-it-solves) · [Features](#features) · [Quick Start](#quick-start) · [CLI Reference](#cli-reference) · [Architecture](#architecture) · [Supported Schools](#supported-schools) · [Connect Your Own School](#connect-your-own-school) · [Roadmap](#roadmap) · [Quality Assurance](#quality-assurance) · [Contributing](#contributing) · [License](#license)

---

## Who Should Use This

- **Students** at schools where free-classroom info is buried behind a login, only on the campus network, with no mobile view — who want it on their phone, offline, no VPN, no login.
- **Student developers** who want to add their own school without reinventing the wheel — wiring up a new school means writing one adapter file.
- **Anyone who wants a reusable framework**, not another one-off scrape script that breaks the moment the portal changes.

## Who Should NOT

- **People expecting a hosted global database of every school** — this is a self-hosted framework. You connect your own school's adapter; today there is exactly one official adapter (a certain university).
- **People who won't log into their school portal in a browser at least once** — login-state reuse (CDP) needs a locally logged-in browser session; the tool never asks for your password.
- **The general public with no school-portal access** — without a portal to read, there is nothing to extract.

---

## 30-Second Overview

**The status quo (students at most schools)**:

```text
$ Me (want a free room to study)
  → walk to the building, peek through every door            # legwork, and you still miss rooms
  → or go back to the dorm, boot a PC, log into the portal    # needs campus network / VPN
  → click "teaching resources → free classrooms", pick campus, building, period  # 4–5 clicks for a result
  → want to check on your phone at the building?              # page isn't mobile-friendly, basically unreadable
```

**Using a site exported by this framework**:

```text
$ Open huanweide.github.io/tust-classroom/ in a phone browser
  → pick campus: Campus A / Campus B
  → pick period: periods 1–13
  → instantly see which rooms are free; "Add to Home Screen" to use it like an app
  → no campus network, no VPN, no login; works offline too (Service Worker cache)
```

The one-line difference: **it is not "one school's free-room page" but a pipeline that turns any school's portal data into an offline site** — the cost of adding a new school is **one adapter file (about 150 lines)**.

---

## What It Solves

| Role | Pain | What this project does |
|------|------|------------|
| University student | Wants a free room to study; can only peek door by door, or log into the portal and click for ages on a PC | Open a web page on your phone, pick a period → instantly see which rooms are free |
| Student developer | Every school has someone who built "our-school free-room query", but they're all **one-off scripts**; a new school means building from scratch | Provides a general pipeline; **connecting a new school = write one adapter (4 methods, ~30 minutes)** |

### How it differs from similar projects

Searching GitHub for "free classroom query" returns almost entirely **single-school, single-implementation** projects:

| | Single-school script (most others) | This framework |
|---|---|---|
| Coverage | 1 school | Any school (add a file) |
| Cost to switch schools | Rewrite from zero | Write one adapter (~150 lines) |
| Data pipeline | Each their own, uneven quality | Unified crawl → store → export → publish |
| Front end | Usually none, or crude | A ready PWA: installable, offline, mobile-optimized |
| Tests | Essentially none | 102 unit tests + real-browser end-to-end |
| Contract checks | None | `check` command catches what the adapter missed early |

The first supported school is **a certain university**, two campuses, 13 periods, already live.

---

## Features

- **🔌 Adapter Contract** — one school = one adapter; implement only `profile` + 4 methods (`list_campuses` / `list_buildings` / `select_building` / `list_free_rooms`). Paging buildings, paging periods, deduplicating into the DB, and exporting the static site are all handled by the framework. `campusfree/adapter.py`
- **🔑 Login-state reuse (CDP Reuse)** — connects via Chrome DevTools Protocol to a browser window you've **already logged into**; **never touches your password, never saves a Cookie file**. CAPTCHA, CAS redirects, device binding — none of it matters. `campusfree/cdp.py`
- **🛡️ Export Gate** — if local data has fewer days than what's already live, `export` is blocked, preventing "the crawl broke but you overwrote 130 days of live data with 3". That is the most dangerous silent data loss. `campusfree/exporter.py`
- **🧪 Contract Check** — the `check` command **needs no network, opens no browser**; a pure static check of whether the adapter is written correctly, turning "crawled for ages before discovering a missing method" into a 3-second check. `campusfree/adapter.py` · `validate_adapter()`
- **📦 Daily Sharding** — one JSON file per day; the front end fetches only today's, so first paint is tens of KB instead of a multi-MB full dump. `campusfree/exporter.py`
- **🔁 Resumable Runner** — the crawl scheduler has resume-from-checkpoint and failure isolation; one day failing doesn't affect the others. `campusfree/runner.py`
- **🧭 Scaffold Generator** — `new-school` generates an adapter skeleton with TODOs in one command; just fill it in. `campusfree/scaffold.py`
- **🔒 Read-Only Dry Run** — `refresh_crawl.py --dry-run` opens the DB with `mode=ro`, so it is **physically unable to write**; you can health-check before deciding whether to touch data. `refresh_crawl.py`

---

## Quick Start

### Route A: I just want to find a free room (students at the supported school)

Just use this URL — install nothing:

**📱 <https://huanweide.github.io/tust-classroom/>**

- Open in a phone browser and use immediately; "Add to Home Screen" to use like an app
- No campus network, no VPN, no login required
- Data refreshes automatically every hour

### Route B: I want my own school supported (developers)

> Note: in the commands below, `your-school` is an **example adapter ID**. Use the actual ID from `python -m campusfree schools` (docs are de-identified and not tied to any specific school).

```bash
# 1. Install dependencies
pip install -r requirements-dev.txt
playwright install chromium

# 2. See which schools are supported now
python -m campusfree schools

# 3. Health-check an adapter (no network, pure static check)
python -m campusfree check --school your-school

# 4. Generate your school's adapter skeleton
python -m campusfree new-school your-school --name "Your School"
#    → generates adapters/your-school.py; fill in the TODOs inside

# 5. Self-check after filling in
python -m campusfree check --school your-school

# 6. Start crawling (auto-launches a browser; log into the portal once inside)
python -m campusfree run --school your-school --range 0-6

# 7. Export the static site
python -m campusfree export --school your-school
```

Full illustrated tutorial: **[docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md)**

**`schools` sample output (de-identified)**:

```text
$ python -m campusfree schools
1 school registered:

ID           SCHOOL                PERIODS  DEFAULT CAMPUS   PORTAL
------------------------------------------------------------------------------------------
your-school  a certain university  13       Campus A         http://jwxt.example.edu.cn:46110
```

**`check` sample output (de-identified)**:

```text
$ python -m campusfree check --school your-school
Target: a certain university
   Portal: http://jwxt.example.edu.cn:46110/student/teachingResources/freeClassroom/index
   Periods: 13
   Default campus: Campus A
   Browser: Microsoft Edge | exe=...\msedge.exe | profile=...\tust-classroom\edge-cdp-profile | port=9222

[PASS] Adapter contract check passed; safe to crawl.
```

---

## CLI Reference

| Command | Purpose | Needs browser? |
|------|------|------------|
| `python -m campusfree schools` | List all registered schools | No |
| `python -m campusfree check --school your-school` | Health-check whether an adapter is correctly written | No |
| `python -m campusfree run --school your-school --range 0-6` | Crawl the next 7 days | Yes |
| `python -m campusfree run --school your-school --auto` | Auto-detect term boundaries, crawl straight through to break | Yes |
| `python -m campusfree export --school your-school` | Export static JSON | No |
| `python -m campusfree new-school <id>` | Generate a new-school adapter skeleton | No |

Crawl a single day: `run --school your-school --dayoffset 1` (1 = tomorrow)

### Fixed refresh crawl (overwrite old data)

`INSERT OR IGNORE` has a trap: on a UNIQUE hit it skips, so **re-crawling the same day won't update data** — if the portal changed the timetable, you won't see it. Use `refresh_crawl.py` for periodic refresh; it DELETEs then re-inserts:

```bash
python refresh_crawl.py --dry-run    # read-only health check: no DB write, no portal request
python refresh_crawl.py              # refresh today + next 7 days, overwrite old values
python refresh_crawl.py --repast 7   # also re-crawl the past 7 days (fix historical data)
```

Three protections: ① `--dry-run` opens the DB with `mode=ro`, physically unwritable ② by default it does not purge history (`--prune-days N` to prune) — the 130 live days are an asset ③ after crawling it self-verifies; any day with rows below a threshold raises an alert immediately. When the login expires, the portal returns an empty list — **the crawler errors out silently but the DB gets cleared without new rows inserted**, the most dangerous silent data loss.

### Rebuild metadata only (when local data is incomplete)

When local DB days are fewer than live, `export` is blocked by the safety gate (which is correct). But when you've only changed normalization logic and want to update `buildingMeta` in `index.json` and the normalized fields in `search.json` without touching the 130 daily files:

```bash
python meta_only.py --dry-run   # preview
python meta_only.py             # write to disk (daily JSON left untouched)
```

---

## Architecture

The default engine is a **layered pipeline where "the adapter only answers 5 questions, the framework does the rest"** — not a one-shot crawler script. Adapters must not import playwright; the framework passes in the already-logged-in page object (duck typing — it only needs `.evaluate` / `.url` / `.goto`), so adapters can be unit-tested without a browser.

### Core concepts

| Concept | Meaning |
|------|------|
| Adapter | One school's implementation; answers 5 questions: URL / campus / building / how to select a building / which rooms are free |
| Login-state reuse (CDP reuse) | Connects to a locally logged-in browser window; no password, no Cookie file on disk |
| Contract check | Static health-check without opening a browser; catches missing adapter methods early |
| Daily shard | One JSON per day; the front end fetches only today's, first paint tens of KB |
| Export gate | Refuses to export when local day count is insufficient, preventing overwrite of live assets |
| Read-only mode (`mode=ro`) | Opens the DB read-only, physically unwritable |

### Data pipeline

```text
┌──────────────┐   CDP reuse  ┌───────────────┐   request  ┌──────────────┐
│ Local browser │ ──────────▶ │ campusfree    │ ───────▶  │ Portal        │
│ (logged in)   │  login state│ scheduler     │ free rooms │ (varies)      │
└──────────────┘             └───────┬───────┘           └──────────────┘
                                     │ ask
                             ┌───────▼───────┐
                             │ SchoolAdapter │ ← one per school, only 4 methods
                             └───────┬───────┘
                                     ↓ normalize
┌──────────────┐   export   ┌───────────────┐   store    ┌──────────────┐
│ GitHub Pages │ ◀────────  │ static/data/  │ ◀────────  │ SQLite dedup  │
│ PWA offline  │  static    │ *.json daily  │            └──────────────┘
└──────────────┘            └───────────────┘
```

- **Collect**: connect to your already-logged-in browser window, page by campus → building → period, write into SQLite (auto-dedup)
- **Export**: compress into date-sharded JSON (one file per day; front end fetches only today's, first paint tens of KB)
- **Publish**: drop onto GitHub Pages — zero backend, instant load, offline after Service Worker cache

> Detailed layering and the reasoning behind each design decision: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

### Core modules

| Module | File | Responsibility |
|------|------|------|
| Data model | `campusfree/model.py` | `Campus` / `Building` / `Room` / `Period` / `SchoolProfile` |
| Adapter protocol | `campusfree/adapter.py` | `SchoolAdapter` abstract base + `validate_adapter()` contract check |
| Login-state reuse | `campusfree/cdp.py` | Reuse local browser session; `BrowserSpec` manages exe/profile/port |
| Crawl scheduler | `campusfree/runner.py` | Resume-from-checkpoint, failure isolation |
| Storage | `campusfree/store.py` | SQLite deduplicated storage |
| Export | `campusfree/exporter.py` | → static JSON, includes export safety gate |
| Scaffold | `campusfree/scaffold.py` | New-school skeleton generator |
| Registry | `campusfree/registry.py` | Adapter auto-discovery |
| CLI | `campusfree/cli.py` | `schools` / `check` / `run` / `export` / `new-school` |

### Why not log in with a username and password

Portal login usually has CAPTCHA, CAS redirects, and device binding; a script simulating login is both fragile and forces you to put your password in a config file. This framework instead **reuses the browser window you've already logged into** (Chrome DevTools Protocol), and **never touches your password or saves a Cookie file**.

---

## Supported Schools

| ID | School | Campuses | Periods | Status |
|----|------|------|------|------|
| `your-school` | a certain university | Campus A + Campus B | 13 | ✅ Official adapter, live [online query](https://huanweide.github.io/tust-classroom/) |

**Your school isn't here?** See below — about 30 minutes, and pull requests are welcome.

---

## Connect Your Own School

One school = one adapter, 4 methods:

```python
from campusfree.adapter import SchoolAdapter
from campusfree.model import Building, Campus, Room, SchoolProfile

class YourSchoolAdapter(SchoolAdapter):
    @property
    def profile(self) -> SchoolProfile:
        return SchoolProfile(school_id="your-school", school_name="Your School",
                             base_url="https://jwxt.example.edu.cn", period_count=13)

    def list_campuses(self, page):        return [Campus(name="Campus A")]
    def list_buildings(self, page, campus): return [Building(name="Main Building")]
    def select_building(self, page, campus, building) -> bool: ...
    def list_free_rooms(self, page, period, day_offset): return [Room(...)]
```

> Iron rule: **adapters must not import playwright**. The framework passes in the logged-in page object; you only send requests in the page and parse results — that's what lets adapters be unit-tested without a browser.

The generator gets you started: `python -m campusfree new-school your-school --name "Your School"`

---

## Roadmap

- [x] Extract the general framework (`campusfree/`, 9 modules)
- [x] First official adapter: a certain university (two campuses / 13 periods / live)
- [x] 102 unit tests (the original project had zero)
- [x] CI: Python 3.11 + 3.12 matrix, ruff + pytest + CLI smoke + front-end asset checks
- [x] Export safety gate + read-only health-check mode
- [ ] Recruit 3 off-campus adapter PRs (currently only `your-school`)
- [ ] Front end supports switching between multiple schools
- [ ] Templatize `static/`, so a new school's export yields its own page
- [ ] Data-freshness alert (auto-open an Issue when `generated_at` expires)

---

## Quality Assurance

| Type | Count | How to run |
|------|------|--------|
| Unit tests | 102, all green | `pytest` |
| Static checks | ruff, all green | `ruff check .` |
| Syntax compile | all green | `python -m compileall -q .` |
| Adapter contract | each command self-checks | `python -m campusfree check --school your-school` |
| Front-end E2E | 11 real-browser clicks | `npm install && npm run e2e` |
| **Normalization regression** | 35 | `python test_normalize.py` |
| **Crawl ops** | 10 | `python test_refresh_crawl.py` |
| **Room-selection E2E** | 65 real-browser | `node test_e2e_browse.mjs` |
| **Full end-to-end** | 47 | `python verify_all.py` |

`verify_all.py` runs all nine layers in one command: data-layer regression → export contract → daily-data consistency → front/back field alignment → real-browser E2E → export safety gate → crawl ops → credential scan. **Iron rule: any single FAIL means the deliverable is not done.**

**CI runs the first four types** (Python 3.11 / 3.12 dual-version matrix + front-end asset checks); the last four depend on a local DB or a real browser and run locally only.

Tests drive the whole pipeline with a "fake portal page" object (`tests/conftest.py`), so **no browser, no campus network, no login state** is needed — CI runs it all.

```text
102 passed in 7.29s
```

---

## Data and Privacy

- **Collects, stores, and transmits no account passwords.** There are no hardcoded credentials in the code.
- Only reuses your local browser session via CDP; **does not save a Cookie file**.
- Data is written only to local SQLite (`data/classrooms.db`, already ignored by `.gitignore`); the published static files contain no account information.
- If your school adapter needs account info, use environment variables only — **never commit it to the repo**.

### Credential security

- Committing any credential file is forbidden. `.gitignore` already ignores `.env`, `data/cookies.txt`, `*.key`, etc.
- Before every commit, scan the staged content for credential signatures (key prefixes, private-key headers, session cookies).
- If leaked: change your portal password immediately; the old session token becomes invalid with it.

---

## Upgrading From v1 (existing users)

Upgrading from v1, **your local scheduled tasks need no change**:

```bash
python crawler_playwright.py --range 0-6   # still works
python export_static.py                    # still works
python keepalive.py --once                 # still works
```

The DB schema is unchanged; your local `data/classrooms.db` is reused directly, no re-crawl needed. Full changes: [CHANGELOG.md](CHANGELOG.md).

---

## Directory Structure

```
.
├── campusfree/            # general framework (unchanged when switching schools)
│   ├── model.py           #   Campus/Building/Room/Period/SchoolProfile
│   ├── adapter.py         #   SchoolAdapter protocol + contract check
│   ├── cdp.py             #   reuse browser login state
│   ├── runner.py          #   crawl scheduler (resume, failure isolation)
│   ├── store.py           #   SQLite storage
│   ├── exporter.py        #   → static JSON
│   ├── scaffold.py        #   new-school skeleton generator
│   ├── registry.py        #   adapter auto-discovery
│   └── cli.py             #   command line
├── adapters/              # per-school adapters (only this dir changes for a new school)
│   └── tust.py            #   a certain university
├── tests/                 # 102 unit tests
├── docs/
│   ├── ADAPTER_GUIDE.md   #   30-minute onboarding guide
│   └── ARCHITECTURE.md    #   architecture notes
├── static/                # PWA front end + exported static data
├── crawler_playwright.py  # compatibility entry (old usage unchanged)
├── export_static.py       # compatibility entry
└── app.py                 # local query API (127.0.0.1:5000)
```

---

## Contributing

The most welcome contribution: **write an adapter for your own school**.

1. `python -m campusfree new-school <school-abbr>`
2. Fill in the 4 methods following [docs/ADAPTER_GUIDE.md](docs/ADAPTER_GUIDE.md)
3. `python -m campusfree check --school <abbr>` to self-check
4. Add a row to the "Supported Schools" table in the README and open a PR

---

## Disclaimer

This is an unofficial tool; data comes from each school's academic portal. Schedules can change without notice — defer to official announcements from the registrar's office. Do not use it for any violation of rules.

---

## License

[MIT](LICENSE) · by [huanweide](https://github.com/huanweide)

---

## Star

If you're also tired of "walking building to building peeking through doors" or "wanting a version for your school but having to build from scratch", give a Star so more schools' students can find this framework — the most welcome contribution is **writing an adapter for your own school**.

[![Star](https://img.shields.io/github/stars/huanweide/tust-classroom?style=social)](https://github.com/huanweide/tust-classroom)

← [More open-source tools · huanweide](https://github.com/huanweide)
