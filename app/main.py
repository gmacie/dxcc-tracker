import flet as ft
from app.dxcc_list import DXCC_COUNTRIES
from app.ui_components import build_login_controls
from app.database import init_db, get_qsos_for_user, add_qso, delete_qso, update_qso
from app.auth import authenticate, register_user
from app.adif_import import parse_adif_file


def main(page: ft.Page):
    page.title = "DXCC Need List Tracker"
    page.padding = 20
    page.scroll = "auto"

    # Ensure database and tables exist
    init_db()

    current_user = {"callsign": None}

    # In-memory model: list of [country, call, date, status]
    all_rows: list[list[str]] = []

    # Filter / sort state
    status_filter_state = {"value": "All"}  # "All", "Needed", "Requested", "Confirmed"
    sort_state = {"value": "None"}         # "None", "Country", "Callsign", "QSO Date", "QSL Status"

    # Shared DataTable
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

    # Dashboard row
    dashboard = ft.Row(spacing=10, wrap=True)

    # Edit dialog
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
    # Row + dashboard helpers
    # -----------------------

    def create_row(country, call, date, status):
        """Create a DataRow with Edit/Delete buttons (safe bound callbacks)."""
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
    # View (filter + sort)
    # -----------------------

    def apply_view():
        """
        Rebuild table.rows from all_rows using current filter/sort.
        """
        rows = list(all_rows)

        # Filter
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

        table.rows.clear()
        for c, ca, d, s in rows:
            table.rows.append(create_row(c, ca, d, s))

        update_dashboard()
        page.update()

    # -----------------------
    # Row operations (update all_rows + DB)
    # -----------------------

    def add_entry(country, call, date, status):
        if not country:
            show_message("Select a country first.")
            return
        rec = [country, call, date, status]
        all_rows.append(rec)
        add_qso(current_user["callsign"], country, call, date, status)
        apply_view()

    def delete_entry(country, call, date, status):
        # Update in-memory list
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

        # Update DB
        delete_qso(current_user["callsign"], country, call, date, status)
        apply_view()

    def edit_entry(country, call, date, status):
        """
        Open dialog, update entry in all_rows and DB, refresh view.
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
            old_row = [country, call, date, status]
            new_row = [
                country_dd.value,
                call_tf.value,
                date_tf.value,
                status_dd.value,
            ]

            # Update in-memory list
            for i, r in enumerate(all_rows):
                if r == old_row:
                    all_rows[i] = new_row
                    break

            # Update DB
            update_qso(current_user["callsign"], old_row, new_row)

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
        """Import QSOs from an ADIF file and add them to all_rows + DB."""
        try:
            new_rows = parse_adif_file(path)
        except Exception as ex:
            show_message(f"ADIF parse error: {ex}")
            return

        if not new_rows:
            show_message("No QSO records found in ADIF file.")
            return

        for country, call, date, status in new_rows:
            rec = [country, call, date, status]
            all_rows.append(rec)
            add_qso(current_user["callsign"], country, call, date, status)

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
    # Load data for current user from DB
    # -----------------------

    def load_user_data():
        all_rows.clear()
        if not current_user["callsign"]:
            return
        qsos = get_qsos_for_user(current_user["callsign"])
        for country, worked_call, qso_date, qsl_status in qsos:
            all_rows.append([country, worked_call, qso_date, qsl_status])
        apply_view()

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
            add_entry(
                country_dd.value,
                call_tf.value,
                date_tf.value,
                status_dd.value,
            )
            call_tf.value = ""
            date_tf.value = ""
            status_dd.value = "Needed"
            country_dd.value = None
            page.update()

        add_btn = ft.ElevatedButton("Add Entry", on_click=on_add)

        # Filter / sort controls
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

        # Layout (no Excel buttons anymore)
        page.add(
            ft.Container(
                ft.Row(
                    [country_dd, call_tf, date_tf, status_dd, add_btn],
                    spacing=10,
                    wrap=True,
                ),
                padding=10,
            ),
            ft.Row(
                [
                    status_filter_dd,
                    sort_dd,
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

        # Load user's data from DB
        load_user_data()

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
