#!/usr/bin/env python3
"""
One-off diagnostic: dump every link (href + visible cell text) in a Clay
folder view, so we can see the real URL pattern Clay uses for sub-folders
(vs. the confirmed "/workbooks/<id>" pattern for workbooks).

Usage:
  python debug_list.py                     # opens Home -> Clients and dumps
  python debug_list.py --path Clients SomeClient   # dumps a deeper path
"""
import argparse
import json

import clay_nav
from clay_auth import clay_page

DUMP_JS = """() => {
    const out = [];
    for (const a of document.querySelectorAll('a[href]')) {
        const cell = a.closest('td, [role="cell"], [role="gridcell"]');
        const text = (cell ? cell.textContent : a.textContent).trim();
        if (text) out.push({href: a.href, text: text});
    }
    return out;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", nargs="+", default=["Clients"],
                     help="Folder path to open before dumping, e.g. Clients or "
                          "Clients SomeClient")
    args = ap.parse_args()

    with clay_page(headless=False) as page:
        if not clay_nav.is_logged_in(page):
            raise SystemExit("Not logged in — run: python clay_login.py")
        clay_nav.open_path(page, args.path)
        page.wait_for_timeout(2000)
        rows = page.evaluate(DUMP_JS)
        print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
