import flet as ft
from app.dxcc_list import DXCC_COUNTRIES
from app.ui_components import build_login_controls
from app.data_manager import get_user_file, save_to_excel, load_from_excel
from app.auth import authenticate, register_user
from app.adif_import import parse_adif_file


def main(page: ft.Page):
    page.title = "DXCC Need List Tracker"
    page.padding = 20
    page.scroll = "auto"

    current_user = {"callsign": None}

    # This will hold ALL rows for the current user:
    # [country, call, date, status]
    all_rows: list[list[str]] = []

    # Filter / sort state (strings updated by dropdowns)
    status_filter_state = {"value": "All"}      # "All", "Needed", "Requested", "Confirmed"
    sort_state = {"value": "None"}             # "None", "Country", "Callsign", "QSO Date", "QSL Status"

    # Shared DataTable instance
    table = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Country")),
            ft.DataColumn(ft.Text("Callsign")),
            ft.DataColumn(ft.Text("QSO Date")),
            ft.DataColumn(ft.Text("QSL Status")),
            ft.DataColumn(ft.Text("Actions")),
        ],
        rows=[],
    )

    # Dashboard row (cards added dynamically)
    dashboard = ft.Row(spacing=10, wrap=True)

    # For edit dialog
    edit_dialog = ft.AlertDialog(modal=True)

    # File picker for ADIF import
    adif_picker = ft.FilePicker()
    page.overlay.append(adif_picker)

    # -----------------------
    # Utility helpers
    # -----------------------

    def show_message(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg), open=True)
        page.update()

    def clear_page():
        page.controls.clear()

    # -----------------------
    # Row helpers
    # -----------------------

    def create_row(country, call, date, status):
        """Create a DataRow with Edit/Delete buttons (with safe bound callbacks)."""
        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(country)),
                ft.DataCell(ft.Text(call)),
                ft.DataCell(ft.Text(date)),
                ft.DataCell(ft.Text(status)),
                ft.DataCell(
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                tooltip="Edit",
                                on_click=lambda e, c=country, ca=call, d=date, s=status: edit_entry(
                                    c, ca, d, s
                                ),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                tooltip="Delete",
                                on_click=lambda e, c=country, ca=call, d=date, s=status: delete_entry(
                                    c, ca, d, s
                                ),
                            ),
                        ],
                        spacing=5,
                    )
                ),
            ]
        )

    def export_rows():
        """Return ALL data rows (for saving to Excel)."""
        return list(all_rows)

    # -----------------------
    # Dashboard logic
    # -----------------------

    def compute_stats():
        rows = all_rows
        total_qsos = len(rows)
        unique_countries = {r[0] for r in rows if r[0]}
        worked = len(unique_countries)
        needed = sum(1 for r in rows if r[3] == "Needed")
        requested = sum(1 for r in rows if r[3] == "Requested")
        confirmed = sum(1 for r in rows if r[3] == "Confirmed")
        total_dxcc = len(DXCC_COUNTRIES)
        remaining = max(total_dxcc - worked, 0)

        return {
            "total": total_qsos,
            "worked": worked,
            "needed": needed,
            "requested": requested,
            "confirmed": confirmed,
            "remaining": remaining,
            "total_dxcc": total_dxcc,
        }

    def update_dashboard():
        stats = compute_stats()

        def card(title, value, subtitle=""):
            items = [
                ft.Text(title, size=12, weight="bold"),
                ft.Text(str(value), size=20, weight="bold"),
            ]
            if subtitle:
                items.append(
                    ft.Text(subtitle, size=11, color=ft.Colors.GREY_600)
                )

            return ft.Container(
                content=ft.Column(items, spacing=2),
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.BLUE_50,
            )

        dashboard.controls = [
            card("Total QSOs", stats["total"]),
            card("DXCC Worked", stats["worked"], f"of {stats['total_dxcc']}"),
            card("Needed", stats["needed"]),
            card("Requested", stats["requested"]),
            card("Confirmed", stats["confirmed"]),
            card("Remaining DXCC", stats["remaining"]),
        ]

        page.update()

    # -----------------------
    # Persistence
    # -----------------------

    def save_user_table():
        if not current_user["callsign"]:
            return
        user_file = get_user_file(current_user["callsign"])
        save_to_excel(export_rows(), user_file)

    # -----------------------
    # View (filter + sort) helper
    # -----------------------

    def apply_view():
        """
        Build table.rows from all_rows, applying current
        filter (status_filter_state) and sort (sort_state).
        """
        # Start from all_rows
        rows = list(all_rows)

        # Filter by status
        sf = status_filter_state["value"]
        if sf != "All":
            rows = [r for r in rows if r[3] == sf]

        # Sort
        sb = sort_state["value"]
        key = None
        if sb == "Country":
            key = lambda r: (r[0] or "")
        elif sb == "Callsign":
            key = lambda r: (r[1] or "")
        elif sb == "QSO Date":
            key = lambda r: (r[2] or "")
        elif sb == "QSL Status":
            key = lambda r: (r[3] or "")

        if key:
            rows.sort(key=key)

        # Rebuild visible table
        table.rows.clear()
        for c, ca, d, s in rows:
            table.rows.append(create_row(c, ca, d, s))

        # Dashboard is based on ALL data, not just filtered subset
        update_dashboard()
        page.update()

    # -----------------------
    # Row operations (modify all_rows, then apply_view)
    # -----------------------

    def add_entry(country, call, date, status):
        if not country:
            show_message("Select a country first.")
            return
        all_rows.append([country, call, date, status])
        save_user_table()
        apply_view()

    def delete_entry(country, call, date, status):
        removed = False
        new_all = []
        for r in all_rows:
            if (
                not removed
                and r[0] == country
                and r[1] == call
                and r[2] == date
                and r[3] == status
            ):
                removed = True
                continue
            new_all.append(r)
        all_rows.clear()
        all_rows.extend(new_all)
        save_user_table()
        apply_view()

    def edit_entry(country, call, date, status):
        """
        Open dialog, update entry in all_rows, refresh view.
        """
        country_dd = ft.Dropdown(
            label="Country",
            width=250,
            options=[ft.dropdown.Option(c) for c in DXCC_COUNTRIES],
            value=country,
        )
        call_tf = ft.TextField(label="Callsign", width=200, value=call)
        date_tf = ft.TextField(label="QSO Date YYYY-MM-DD", width=200, value=date)
        status_dd = ft.Dropdown(
            label="QSL Status",
            width=200,
            value=status,
            options=[
                ft.dropdown.Option("Needed"),
                ft.dropdown.Option("Requested"),
                ft.dropdown.Option("Confirmed"),
            ],
        )

        def save_changes(e):
            # Remove old first
            delete_entry(country, call, date, status)
            # Then add updated values
            all_rows.append(
                [
                    country_dd.value,
                    call_tf.value,
                    date_tf.value,
                    status_dd.value,
                ]
            )
            save_user_table()
            page.close(edit_dialog)
            apply_view()

        edit_dialog.title = ft.Text("Edit Entry")
        edit_dialog.content = ft.Column(
            [
                country_dd,
                call_tf,
                date_tf,
                status_dd,
                ft.Row(
                    [
                        ft.ElevatedButton("Save", on_click=save_changes),
                        ft.OutlinedButton(
                            "Cancel", on_click=lambda e: page.close(edit_dialog)
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            tight=True,
        )

        page.open(edit_dialog)

    # -----------------------
    # ADIF import
    # -----------------------

    def import_adif(path: str):
        """Import QSOs from an ADIF file and add them to all_rows."""
        try:
            new_rows = parse_adif_file(path)
        except Exception as ex:
            show_message(f"ADIF parse error: {ex}")
            return

        if not new_rows:
            show_message("No QSO records found in ADIF file.")
            return

        for country, call, date, status in new_rows:
            all_rows.append([country, call, date, status])

        save_user_table()
        apply_view()
        show_message(f"Imported {len(new_rows)} QSOs from log.")

    def on_adif_pick(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        path = e.files[0].path
        if not path:
            show_message("No file path available (web mode may not support direct file paths).")
            return
        import_adif(path)

    adif_picker.on_result = on_adif_pick

    # -----------------------
    # Load from Excel for current user
    # -----------------------

    def reload_from_excel(e=None):
        all_rows.clear()
        user_file = get_user_file(current_user["callsign"])
        for c, ca, d, s in load_from_excel(user_file):
            all_rows.append([c, ca, d, s])
        apply_view()
        if e:
            show_message("Reloaded from Excel")

    # -----------------------
    # Main app UI (after login)
    # -----------------------

    def show_app():
        clear_page()

        # Header
        page.add(
            ft.Row(
                [
                    ft.Text(
                        f"DXCC Need List Tracker — {current_user['callsign']}",
                        size=24,
                        weight="bold",
                    ),
                    ft.Container(expand=True),
                    ft.ElevatedButton("Logout", on_click=lambda e: show_login()),
                ]
            )
        )

        # Dashboard
        page.add(dashboard)

        # Entry controls
        country_dd = ft.Dropdown(
            label="Country",
            width=250,
            options=[ft.dropdown.Option(c) for c in DXCC_COUNTRIES],
        )
        call_tf = ft.TextField(label="Callsign", width=200)
        date_tf = ft.TextField(label="QSO Date YYYY-MM-DD", width=200)
        status_dd = ft.Dropdown(
            label="QSL Status",
            width=200,
            value="Needed",
            options=[
                ft.dropdown.Option("Needed"),
                ft.dropdown.Option("Requested"),
                ft.dropdown.Option("Confirmed"),
            ],
        )

        def on_add(e):
            add_entry(country_dd.value, call_tf.value, date_tf.value, status_dd.value)
            call_tf.value = ""
            date_tf.value = ""
            status_dd.value = "Needed"
            country_dd.value = None
            page.update()

        add_btn = ft.ElevatedButton("Add Entry", on_click=on_add)

        # Filter + Sort controls
        status_filter_dd = ft.Dropdown(
            label="Filter QSL",
            width=150,
            value=status_filter_state["value"],
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("Needed"),
                ft.dropdown.Option("Requested"),
                ft.dropdown.Option("Confirmed"),
            ],
        )

        sort_dd = ft.Dropdown(
            label="Sort by",
            width=150,
            value=sort_state["value"],
            options=[
                ft.dropdown.Option("None"),
                ft.dropdown.Option("Country"),
                ft.dropdown.Option("Callsign"),
                ft.dropdown.Option("QSO Date"),
                ft.dropdown.Option("QSL Status"),
            ],
        )

        def on_filter_change(e):
            status_filter_state["value"] = status_filter_dd.value or "All"
            apply_view()

        def on_sort_change(e):
            sort_state["value"] = sort_dd.value or "None"
            apply_view()

        status_filter_dd.on_change = on_filter_change
        sort_dd.on_change = on_sort_change

        def save_click(e):
            save_user_table()
            show_message("Saved to Excel")

        # Initial load from Excel
        reload_from_excel(e=None)

        # Layout
        page.add(
            ft.Container(
                ft.Row(
                    [
                        country_dd,
                        call_tf,
                        date_tf,
                        status_dd,
                        add_btn,
                    ],
                    spacing=10,
                    wrap=True,
                ),
                padding=10,
            ),
            ft.Row(
                [
                    status_filter_dd,
                    sort_dd,
                    ft.ElevatedButton("Save to Excel", on_click=save_click),
                    ft.ElevatedButton(
                        "Reload from Excel", on_click=reload_from_excel
                    ),
                    ft.ElevatedButton(
                        "Import ADIF",
                        on_click=lambda e: adif_picker.pick_files(
                            allow_multiple=False,
                            file_type=ft.FilePickerFileType.CUSTOM,
                            allowed_extensions=["adi", "adif", "log"],
                        ),
                    ),
                ],
                spacing=10,
                wrap=True,
            ),
            ft.Divider(),
            table,
        )

        page.update()

    # -----------------------
    # Login UI
    # -----------------------

    def show_login():
        clear_page()

        def do_login(callsign, password):
            ok, msg = authenticate(callsign, password)
            if not ok:
                show_message(msg)
                return
            current_user["callsign"] = callsign.upper()
            show_app()

        def do_register(callsign, password):
            ok, msg = register_user(callsign, password)
            show_message(msg)
            if ok:
                do_login(callsign, password)

        login_controls, _ = build_login_controls(do_login, do_register)

        page.add(
            ft.Container(
                login_controls,
                padding=20,
                alignment=ft.alignment.center,
            )
        )
        page.update()

    # start at login
    show_login()


if __name__ == "__main__":
    ft.app(target=main)
