"""
Table (workbook) creation inside an already-open Clay folder.

`create_workbook_with_csv()` is ported unchanged from clay-icp-pipeline's
automation/clay_sync/clay_ui.create_workbook_with_csvs — proven live across
~90 workbooks in that repo.

`create_workbook_blank()` is new. The source repo's automation never drove
a blank-table create flow from the empty-workbook screen (it only ever
imported a CSV there) — but it DID capture a working "create a blank table,
then rename it" mechanic elsewhere: automation/build_automation/
column_config.py's dest_create_table(), used inside a formula column's
"Send table data" destination picker. That function's core steps (click
"Create" -> menuitem "Table" -> an input pre-filled "New table..." appears
-> select-all, type the real name, Tab to commit) are ported into
_rename_blank_table() below and wired into the empty-workbook screen. The
entry point used to reach a blank table from THAT screen (as opposed to the
destination picker) is a guess — see create_workbook_blank()'s docstring.
"""
import os
import re

from playwright.sync_api import Page

from clay_nav import ClayUIError


def _add_table_button(page: Page):
    """The bottom-bar add-table button. Its accessible name is "Add" and it
    is type="button"; the grid's separate "Add row" button (also named
    "Add") is type="submit", so filtering on type uniquely targets this
    one."""
    return page.get_by_role("button", name="Add", exact=True).and_(
        page.locator('button[type="button"]'))


def _click_footer_commit(page: Page, timeout: int) -> None:
    """Click the commit control in the import dialog's footer."""
    page.get_by_test_id("stage-display-footer").click(timeout=timeout)


def _import_csv(page: Page, csv_path: str, has_continue: bool) -> None:
    """From an open CSV import dialog: browse to the file, set it, and
    commit. The Add-table modal has an extra 'Continue' step before the
    commit footer; the first-import flow goes straight to the footer."""
    page.wait_for_timeout(150)
    with page.expect_file_chooser(timeout=15000) as fc:
        page.get_by_text("Browse files").click()
    fc.value.set_files(os.path.abspath(csv_path))
    page.wait_for_timeout(500)

    if has_continue:
        page.get_by_role("button", name="Continue").click(timeout=15000)
        page.wait_for_timeout(150)
        try:
            _click_footer_commit(page, timeout=10000)
        except Exception:
            pass
    else:
        _click_footer_commit(page, timeout=30000)


def _wait_for_table_data(page: Page, timeout: int = 300000) -> None:
    """Block until the imported table shows at least one data cell."""
    try:
        page.get_by_test_id(re.compile(r"^cell-r\d+-c0$")).first.wait_for(
            state="visible", timeout=timeout)
    except Exception as e:
        raise ClayUIError(
            f"Import committed but no table data appeared within "
            f"{timeout // 1000}s: {e}")
    page.wait_for_timeout(300)


def _rename_blank_table(page: Page, name: str, retries: int = 3) -> None:
    """Rename a freshly-created blank table. Clay pre-fills an editable
    input with a default name ("New table...", sometimes "Table..."); select
    all and type over it, commit with Tab.

    Ported from column_config.dest_create_table's rename step (proven live,
    but in the destination-picker modal, not necessarily this screen).
    """
    last = None
    for _ in range(retries):
        try:
            inp = page.locator('input[value^="New table"]')
            if not inp.count():
                inp = page.locator('input[value^="Table"]')
            if not inp.count():
                raise ClayUIError("new-table name input not found")
            inp.first.click(timeout=8000)
            page.keyboard.press("Control+a")
            page.keyboard.type(name, delay=25)
            page.keyboard.press("Tab")
            page.wait_for_timeout(1200)
            return
        except Exception as e:
            last = e
            page.wait_for_timeout(2000)
    raise ClayUIError(f"could not rename blank table to {name!r}: {last}")


def create_workbook_with_csv(page: Page, workbook_name: str, csv_path: str) -> None:
    """Create workbook `workbook_name` in the open folder and import
    `csv_path` as its first table. Clay names the table after the CSV
    filename (Exhibitors.csv -> "Exhibitors") — no rename needed.

    Proven flow, ported unchanged from clay_ui.create_workbook_with_csvs.
    Assumes a folder is already open (see clay_nav.open_path /
    open_or_create_folder).
    """
    try:
        page.get_by_test_id("create-new").click(timeout=15000)
        page.wait_for_timeout(150)
        page.get_by_test_id("new-workbook").click(timeout=15000)
        page.wait_for_timeout(500)

        page.get_by_label("title").fill(workbook_name)
        page.keyboard.press("Enter")
        page.wait_for_timeout(150)

        page.get_by_role("button", name="Import from CSV").click(timeout=20000)
        _import_csv(page, csv_path, has_continue=False)
        _wait_for_table_data(page)
    except Exception as e:
        raise ClayUIError(f"Failed to create workbook {workbook_name!r} with CSV: {e}")


def create_workbook_blank(page: Page, workbook_name: str, table_name: str = None) -> None:
    """Create workbook `workbook_name` in the open folder with one blank
    table, optionally renamed to `table_name` (else Clay's default name is
    left as-is).

    UNVERIFIED ENTRY POINT: after naming the workbook, this looks for a
    "Start from scratch" / "Blank table" / "Table" button as the empty-
    workbook screen's non-CSV option (by analogy with "Import from CSV",
    which IS the confirmed option on that screen). Run this once with
    --show, watch what actually renders, and adjust _BLANK_ENTRY_TEXT (or
    swap in the exact selector) if none of these match.
    """
    _BLANK_ENTRY_TEXT = ["Start from scratch", "Blank table", "Table"]
    try:
        page.get_by_test_id("create-new").click(timeout=15000)
        page.wait_for_timeout(150)
        page.get_by_test_id("new-workbook").click(timeout=15000)
        page.wait_for_timeout(500)

        page.get_by_label("title").fill(workbook_name)
        page.keyboard.press("Enter")
        page.wait_for_timeout(150)

        clicked = False
        for text in _BLANK_ENTRY_TEXT:
            try:
                page.get_by_role("button", name=text, exact=True).click(timeout=4000)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            raise ClayUIError(
                "no blank-table entry point found on the empty-workbook "
                f"screen (tried {_BLANK_ENTRY_TEXT}) — rerun with --show, "
                "see what's actually offered, and update _BLANK_ENTRY_TEXT")
        page.wait_for_timeout(1000)

        if table_name:
            _rename_blank_table(page, table_name)
    except Exception as e:
        raise ClayUIError(f"Failed to create blank workbook {workbook_name!r}: {e}")


def add_csv_table(page: Page, csv_path: str) -> None:
    """Add another CSV-backed table to the already-open workbook, via the
    bottom-bar 'Add' button. Ported unchanged from clay_ui.add_csv_table."""
    add_table = _add_table_button(page)
    add_table.wait_for(state="visible", timeout=20000)
    add_table.click(timeout=15000)
    page.wait_for_timeout(150)
    search = page.get_by_placeholder("Search")
    search.wait_for(state="visible", timeout=10000)
    search.fill("Import from CSV")
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Import from CSV", exact=True).first.click(
        timeout=10000)
    _import_csv(page, csv_path, has_continue=True)

    table_name = os.path.splitext(os.path.basename(csv_path))[0]
    tab = page.get_by_role("button", name=table_name, exact=True).first
    try:
        tab.wait_for(state="visible", timeout=60000)
    except Exception as e:
        raise ClayUIError(
            f"Added-table import committed but no {table_name!r} tab appeared: {e}")
    tab.click(timeout=10000)
    page.wait_for_timeout(600)
    _wait_for_table_data(page)


def existing_tables(page: Page, candidates: list) -> set:
    """Which of `candidates` (table names) already exist as tabs in the
    open workbook. Raises rather than reporting absence on a failed check —
    callers branch on this to decide whether to create a duplicate."""
    found = set()
    for name in candidates:
        try:
            if page.get_by_role("button", name=name, exact=True).count() > 0:
                found.add(name)
        except Exception as e:
            raise ClayUIError(
                f"could not determine whether table {name!r} exists "
                f"({type(e).__name__}: {str(e)[:120]})")
    return found
