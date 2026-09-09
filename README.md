# table-creator

Small, standalone tool: give it a client name and a table name, it creates
the table in Clay under `Home > Clients > {ClientName}`, creating the client
folder first if it doesn't exist yet. No CSV required by default — tables
are blank unless you pass one.

Extracted and generalized from the table/workbook-creation half of
[clay-icp-pipeline](https://github.com/qasimovski/clay-icp-pipeline), which
also does a much larger config-driven ICP scoring pipeline this repo doesn't
need. Only the Clay-navigation and table-creation primitives came over.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
python clay_login.py     # one-time: log in by hand, saves .clay_session.json
```

`.clay_session.json` holds live login cookies — it's gitignored, never
commit it.

If Clay bot-blocks the automated browser (it does this to some Playwright-
launched sessions even with valid cookies), drive a real Chrome instead:

```bash
chrome.exe --remote-debugging-port=9222 --user-data-dir=C:\clay-debug --window-size=1720,1000
# log into Clay in that window, then:
set CLAY_USE_CDP=1        # (Windows)  |  export CLAY_USE_CDP=1  (mac/Linux)
```

## Usage

```bash
python create_table.py
```

Prompts for a client (arrow-key picker listing whatever folders already
exist under "Clients" in Clay, live — plus a "+ Create new client..."
option) and a table name, then creates a blank table there.

Non-interactive:

```bash
python create_table.py --client "Acme Corp" --name "Q3 Prospects"
python create_table.py --client "Acme Corp" --name "Raw Import" --csv data.csv
python create_table.py --show     # visible browser, for debugging
```

If `--client` names a folder that doesn't exist yet, it's created
automatically — same as picking "+ Create new client..." interactively.

## Files

| File | What it does |
|---|---|
| `clay_auth.py` | Playwright session/connection handling (CDP or saved cookies) |
| `clay_login.py` | One-time interactive login, saves the session |
| `clay_nav.py` | Folder navigation: open an arbitrary path, list what's inside, create a folder |
| `clay_tables.py` | Table/workbook creation: blank or from CSV |
| `create_table.py` | CLI entry point — client picker + table creation |

## What's proven vs. what needs a smoke test

Ported unchanged from the source repo, live-tested there across ~90
workbooks:
- `clay_nav.is_logged_in`, `clay_nav.open_path` (folder-by-folder, arbitrary
  depth), `clay_nav.list_contents` (workbook side confirmed via
  `/workbooks/<id>` hrefs)
- `clay_tables.create_workbook_with_csv`, `add_csv_table`, `existing_tables`

New in this repo, **not yet run against a live account** — run once with
`--show` and watch what happens before leaving this unattended:
- `clay_nav.create_folder` — the source repo never automated folder
  creation, only workbook creation. This guesses a sibling `new-folder`
  test-id / "Folder" menu item behind the same "create-new" button. If it
  fails, open devtools, click "create-new" yourself, and see what's really
  there.
- `clay_nav.list_contents`'s folder branch — the `/folders/<id>` href
  pattern is inferred by analogy with the confirmed `/workbooks/<id>`
  pattern, not confirmed live.
- `clay_tables.create_workbook_blank` — the source repo only ever imported
  a CSV from the empty-workbook screen. This tries a few likely button
  labels ("Start from scratch" / "Blank table" / "Table") for the
  non-CSV option on that same screen; the actual rename mechanic
  (`_rename_blank_table`) IS proven live, just in a different modal (a
  formula column's "Send table data" destination picker in the source
  repo's `column_config.dest_create_table`).

If any of these need fixing: `playwright codegen https://app.clay.com`
against a real logged-in account, click through the flow by hand, and copy
the selector Playwright records for the failing step.
