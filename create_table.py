#!/usr/bin/env python3
"""
Create a new Clay table for a client.

Flow:  Home -> Clients -> {pick or create a client folder} -> new table

The client folder list is read live from Clay every run (not a hardcoded
list) — whatever's under the "Clients" folder shows up in the picker, plus
a "+ Create new client..." option that prompts for a name and creates it.

Usage:
  python create_table.py                          # interactive: pick client,
                                                    # enter table name, blank table
  python create_table.py --client "Acme Corp" --name "Q3 Prospects"
  python create_table.py --client "Acme Corp" --name "Raw Import" --csv data.csv
  python create_table.py --show                    # headed browser, for debugging

Requires a saved session first: python clay_login.py
"""
import argparse
import os
import sys

import clay_nav
import clay_tables
from clay_auth import clay_page

TOP_FOLDER = os.environ.get("CLAY_TOP_FOLDER", "Clients")

NEW_CLIENT_CHOICE = "+ Create new client..."


def pick_client(page) -> str:
    """List existing client folders live from Clay and let the user pick one
    via a numbered prompt, or create a new one.

    Plain input() only — NOT questionary/prompt_toolkit. Playwright's sync
    API keeps an event loop active in this thread (via greenlets, to fake
    synchronous calls); prompt_toolkit's Application.run() then tries
    asyncio.run() on top of that and raises "cannot be called from a running
    event loop". Keep this picker dependency-free rather than reintroducing
    that clash.
    """
    clay_nav.open_path(page, [TOP_FOLDER])
    clients = clay_nav.list_folder_names(page)
    choices = clients + [NEW_CLIENT_CHOICE]

    print("\nClients:")
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    raw = input("Pick a number: ").strip()
    pick = choices[int(raw) - 1] if raw.isdigit() and 1 <= int(raw) <= len(choices) else None

    if pick is None:
        sys.exit("Cancelled.")

    if pick == NEW_CLIENT_CHOICE:
        new_name = input("New client folder name: ").strip()
        if not new_name:
            sys.exit("No name given.")
        clay_nav.create_folder(page, new_name)
        return new_name

    return pick


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--client", help="Client folder name (skips the interactive picker; "
                                      "created if it doesn't exist)")
    ap.add_argument("--name", help="Table/workbook name (prompted if omitted)")
    ap.add_argument("--csv", help="Optional CSV to import as the table's data "
                                   "(default: blank table)")
    ap.add_argument("--show", action="store_true",
                     help="Run with a visible browser window (debugging)")
    args = ap.parse_args()

    table_name = args.name or input("Table name: ").strip()
    if not table_name:
        sys.exit("No table name given.")
    if args.csv and not os.path.exists(args.csv):
        sys.exit(f"CSV not found: {args.csv}")

    with clay_page(headless=not args.show) as page:
        if not clay_nav.is_logged_in(page):
            sys.exit("Clay session expired or missing — run: python clay_login.py")

        if args.client:
            client = args.client
            clay_nav.open_or_create_folder(page, [TOP_FOLDER], client)
        else:
            client = pick_client(page)
            clay_nav.open_path(page, [TOP_FOLDER, client])

        if args.csv:
            clay_tables.create_workbook_with_csv(page, table_name, args.csv)
        else:
            clay_tables.create_workbook_blank(page, table_name)

    print(f"\nCreated '{table_name}' under {TOP_FOLDER} / {client}.")


if __name__ == "__main__":
    main()
