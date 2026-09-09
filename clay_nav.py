"""
Generalized Clay folder navigation.

Ported from clay-icp-pipeline's automation/clay_sync/clay_ui.py, where the
destination was hardcoded to Home -> "Labs [2026 - Qasim]" -> "Competitive
Events". Here `open_path()` takes an arbitrary list of folder names, so any
depth works: e.g. open_path(page, ["Clients", "Acme Corp"]).

Selectors carried over as-is (is_logged_in, _open_cell, open_path,
list_contents) are the ones proven live against a real Clay account in the
source repo. `create_folder()` is new — see its docstring for what's
unverified there.
"""
import os
import re

from playwright.sync_api import Page, TimeoutError as PWTimeout

CLAY_URL = "https://app.clay.com"


class ClayUIError(Exception):
    """Any failure interacting with the Clay UI."""


# --------------------------------------------------------------------------
# session
# --------------------------------------------------------------------------

def is_logged_in(page: Page) -> bool:
    """Navigate to Clay and report whether we have an authenticated session.

    A URL check alone is not enough: when Clay bot-blocks an automated
    browser it serves the logged-out marketing page ON app.clay.com, whose
    URL contains no "login". So we also require a signed-in affordance to
    be present."""
    try:
        page.goto(CLAY_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)
    except PWTimeout:
        pass
    url = page.url.lower()
    if any(x in url for x in ("login", "signin", "sign-in")):
        return False
    for probe in (lambda: page.get_by_test_id("create-new"),
                  lambda: page.locator('a[href*="/workbooks/"]'),
                  lambda: page.locator('a[href*="/workspaces/"]')):
        try:
            probe().first.wait_for(timeout=10000)
            return True
        except Exception:
            continue
    return False


# --------------------------------------------------------------------------
# navigation
# --------------------------------------------------------------------------

def _open_cell(page: Page, name: str) -> None:
    """Click into a folder that shows as a table cell with a link. Raises on
    failure so the caller can retry."""
    cell = page.get_by_role("cell", name=name).get_by_role("link").first
    cell.wait_for(state="visible", timeout=30000)
    cell.scroll_into_view_if_needed(timeout=10000)
    cell.click(timeout=20000)
    page.wait_for_load_state("networkidle", timeout=20000)


def open_path(page: Page, parts: list) -> None:
    """Navigate Home -> parts[0] -> parts[1] -> ... and assert we land
    somewhere a table/workbook can be created. Raises (never falls back
    elsewhere) if it can't be reached.

    Clay's folder views load unevenly under load, so retry the whole hop a
    few times (reloading each attempt) before giving up — same approach as
    the source repo's open_target_location().
    """
    last_err = None
    for attempt in range(3):
        try:
            try:
                page.goto(CLAY_URL, wait_until="domcontentloaded", timeout=30000)
            except PWTimeout:
                pass
            for part in parts:
                _open_cell(page, part)
            page.get_by_test_id("create-new").wait_for(timeout=15000)
            return
        except Exception as e:
            last_err = e
            page.wait_for_timeout(1500)
    raise ClayUIError(
        f"Could not navigate to {' / '.join(parts)!r} after 3 attempts: {last_err}")


# --------------------------------------------------------------------------
# listing — scoped to whatever folder is currently open
# --------------------------------------------------------------------------

# Every cell in a listing row is wrapped in a link to that item's URL. A
# workbook link contains "/workbooks/<id>" (confirmed live). A folder link
# looks like ".../home/f_<id>?..." (also confirmed live, via debug_list.py
# against a real account — the earlier "/folders/<id>" guess was wrong).
_COLLECT_ROWS_JS = """() => {
    const out = {};
    for (const a of document.querySelectorAll('a[href]')) {
        const href = a.href;
        let kind = null, id = null;
        let m = href.match(/\\/workbooks\\/([^/?]+)/);
        if (m) {
            kind = 'workbook'; id = m[1];
        } else {
            m = href.match(/\\/home\\/(f_[^/?]+)/);
            if (m) { kind = 'folder'; id = m[1]; }
        }
        if (!kind) continue;
        const cell = a.closest('td, [role="cell"], [role="gridcell"]');
        const text = (cell ? cell.textContent : a.textContent).trim();
        if (!(id in out) && text) out[id] = {name: text, kind: kind};
    }
    return out;
}"""


def list_contents(page: Page) -> dict:
    """{id: {"name": ..., "kind": "workbook"|"folder"}} for every item in
    the open folder. Scrolls the (possibly virtualized) listing until no new
    rows appear for a few consecutive attempts — same pattern as the source
    repo's list_workbooks(), which found ~90 rows this way."""
    try:
        page.get_by_role("cell").first.wait_for(state="visible", timeout=45000)
    except Exception as e:
        raise ClayUIError(
            f"Listing never hydrated — cannot tell what exists, refusing to "
            f"risk creating a duplicate: {e}")
    page.wait_for_timeout(1000)
    page.wait_for_timeout(3000)  # let the first screen of rows hydrate

    first_cell = page.get_by_role("cell").first
    box = first_cell.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    items = {}
    stable = 0
    while stable < 3:
        before = len(items)
        items.update(page.evaluate(_COLLECT_ROWS_JS))
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(1200)
        items.update(page.evaluate(_COLLECT_ROWS_JS))
        stable = stable + 1 if len(items) == before else 0
    return items


def list_folder_names(page: Page) -> list:
    """Just the folder names visible in the currently open location."""
    return sorted({v["name"] for v in list_contents(page).values()
                   if v["kind"] == "folder"})


def folder_exists(page: Page, name: str) -> bool:
    return name in set(list_folder_names(page))


# --------------------------------------------------------------------------
# folder creation
# --------------------------------------------------------------------------

def create_folder(page: Page, name: str) -> None:
    """Create a new folder named `name` inside the currently open location.

    UNVERIFIED: the source repo's automation never captured a folder-
    creation flow — it only ever created workbooks, via
    get_by_test_id("new-workbook") behind the same "create-new" button. This
    assumes a sibling "new-folder" test-id, falling back to a "Folder" menu
    item text search, and assumes the name field shares the "title"
    accessible label the workbook-naming step uses. Confirm/fix with
    `playwright codegen https://app.clay.com` against a real account before
    relying on this unattended — click "create-new" and see what's actually
    there.
    """
    page.get_by_test_id("create-new").click(timeout=15000)
    page.wait_for_timeout(150)
    try:
        page.get_by_test_id("new-folder").click(timeout=5000)
    except Exception:
        page.get_by_role("menuitem", name=re.compile("folder", re.I)).first.click(
            timeout=10000)
    page.wait_for_timeout(300)
    try:
        page.get_by_label("title").fill(name)
    except Exception:
        page.get_by_role("textbox").first.fill(name)
    page.keyboard.press("Enter")
    page.wait_for_timeout(500)


def open_or_create_folder(page: Page, parent_parts: list, name: str) -> None:
    """Open parent_parts, create `name` inside it if missing, then open it."""
    open_path(page, parent_parts)
    if not folder_exists(page, name):
        create_folder(page, name)
    _open_cell(page, name)
