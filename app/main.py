import sqlite3
import flet as ft

from app.ui_components import build_login_controls
from app.database import (
    init_db,
    get_qsos_for_user,
    add_qso,
    delete_qso,
    update_qso,
    get_user_profile,
    set_user_profile,
    DB_PATH,
)
from app.auth import authenticate, register_user
from app.adif_import import parse_adif_file
from app.dxcc_prefixes import (
    DXCC_ENTITIES,
    lookup_entity_from_call,
    load_extended_data,
)

# Bands supported in the app
BAND_OPTIONS = [
    "160m",
    "80m",
    "60m",
    "40m",
    "30m",
    "20m",
    "17m",
    "15m",
    "12m",
    "10m",
    "6m",
]


def main(page: ft.Page):
    page.title = "DXCC Need List Tracker"
    page.padding = 20
    page.scroll = "auto"

    # Load DB + DXCC data
    init_db()
    load_extended_data()  # safe if no JSON files yet

    current_user = {"callsign": None}

    # In-memory table rows: [country, call, date, status, band]
    all_rows: list[list[str]] = []

    # Filter / sort state
    status_filter_state = {"value": "All"}
    sort_state = {"value": "None"}
    band_filter_state = {"value": "All"}

    # User profile settings
    user_track_all = {"value": True}
    user_bands = {"value": []}
    include_deleted_state = {"value": False}

    # UI components
    table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text("Loading..."))],
        rows=[],
    )
    dashboard = ft.Row(spacing=10, wrap=True)

    edit_dialog = ft.AlertDialog(modal=True)
    clear_dialog = ft.AlertDialog(modal=True)
    profile_dialog = ft.AlertDialog(modal=True)

    adif_picker = ft.FilePicker()
    page.overlay.append(adif_picker)

    # ------------------------------------------------------
    # Utility
    # ------------------------------------------------------

    def show_message(msg: str):
        page.snack_bar = ft.SnackBar(ft.Text(msg), open=True)
        page.update()

    def clear_page():
        page.controls.clear()

    # ------------------------------------------------------
    # Band tracking helpers
    # ------------------------------------------------------

    def band_is_tracked(band: str) -> bool:
        if user_track_all["value"]:
            return True
        if not band:
            return False
        return band in user_bands["value"]

    def should_show_band_column() -> bool:
        # Only show band column when user is tracking multiple bands
        return (not user_track_all["value"]) and len(user_bands["value"]) > 1

    # ------------------------------------------------------
    # DXCC helpers
    # ------------------------------------------------------

    def dxcc_from_call(call: str):
        """
        Returns (entity_id, entity_name, active_flag) or (None, None, None) if unknown.
        """
        info = lookup_entity_from_call(call)
        if not info:
            return None, None, None
        ent, name = info  # DXCCEntity, name
        return ent.id, name, ent.active

    # ------------------------------------------------------
    # Dashboard calculation (per DXCC entity, prefix-based)
    # ------------------------------------------------------

    def compute_stats():
        # Universe of DXCC entities (active vs all)
        if include_deleted_state["value"]:
            total_dxcc = len(DXCC_ENTITIES)
        else:
            total_dxcc = sum(1 for e in DXCC_ENTITIES.values() if e.active)

        # Only consider rows in tracked bands
        tracked_rows = [r for r in all_rows if band_is_tracked(r[4])]

        total_qsos = len(tracked_rows)

        worked_entities = set()
        requested_entities = set()
        confirmed_entities = set()

        for country, call, date, status, band in tracked_rows:
            dxcc_id, dxcc_name, is_active = dxcc_from_call(call)
            if not dxcc_id:
                # Unknown DXCC, skip for DXCC stats
                continue

            # If include_deleted is OFF, ignore deleted entities in stats
            if not include_deleted_state["value"] and not is_active:
                continue

            worked_entities.add(dxcc_id)

            if status == "Requested":
                requested_entities.add(dxcc_id)
            elif status == "Confirmed":
                confirmed_entities.add(dxcc_id)

        needed_entities = worked_entities - requested_entities - confirmed_entities

        worked = len(worked_entities)
        requested = len(requested_entities)
        confirmed = len(confirmed_entities)
        needed = len(needed_entities)
        remaining = total_dxcc - worked

        # Debug prints
        print("=== DXCC STATS DEBUG ===")
        print(f"Include deleted: {include_deleted_state['value']}")
        print(f"Total QSOs (tracked bands): {total_qsos}")
        print(f"Worked entities ({worked}): {sorted(worked_entities)}")
        print(f"Requested entities ({requested}): {sorted(requested_entities)}")
        print(f"Confirmed entities ({confirmed}): {sorted(confirmed_entities)}")
        print(f"Needed entities ({needed}): {sorted(needed_entities)}")
        print(f"Total DXCC universe: {total_dxcc}")
        print("========================")

        return {
            "total_qsos": total_qsos,
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
                items.append(ft.Text(subtitle, size=11, color=ft.Colors.GREY_600))
            return ft.Container(
                content=ft.Column(items, spacing=2),
                padding=10,
                border_radius=8,
                bgcolor=ft.Colors.BLUE_50,
            )

        tracking_text = (
            "All bands"
            if user_track_all["value"]
            else ", ".join(user_bands["value"]) or "No bands selected"
        )
        deleted_text = "All + Deleted" if include_deleted_state["value"] else "Active only"

        dashboard.controls = [
            card("Total QSOs", stats["total_qsos"], f"{tracking_text} / {deleted_text}"),
            card("Worked DXCC", stats["worked"], f"of {stats['total_dxcc']}"),
            card("Needed (DXCC)", stats["needed"]),
            card("Requested (DXCC)", stats["requested"]),
            card("Confirmed (DXCC)", stats["confirmed"]),
            card("Remaining DXCC", stats["remaining"]),
        ]
        page.update()

    # ------------------------------------------------------
    # Create DataRow
    # ------------------------------------------------------

    def create_row(country, call, date, status, band, show_band_col: bool):
        dxcc_id, dxcc_name, is_active = dxcc_from_call(call)
        is_deleted = (dxcc_id is not None and is_active is False)

        label = dxcc_name if dxcc_name else (country or "")
        if is_deleted:
            label = f"💀 {label}"
            color = ft.Colors.RED_400
        else:
            color = None

        cells = [
            ft.DataCell(ft.Text(label, color=color)),
            ft.DataCell(ft.Text(call)),
            ft.DataCell(ft.Text(date)),
            ft.DataCell(ft.Text(status)),
        ]

        if show_band_col:
            cells.append(ft.DataCell(ft.Text(band or "")))

        cells.append(
            ft.DataCell(
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.EDIT,
                            tooltip="Edit",
                            on_click=lambda e: edit_entry(
                                country, call, date, status, band
                            ),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE,
                            tooltip="Delete",
                            on_click=lambda e: delete_entry(
                                country, call, date, status, band
                            ),
                        ),
                    ],
                    spacing=5,
                )
            )
        )

        return ft.DataRow(cells=cells)

    # ------------------------------------------------------
    # View filter + sort
    # ------------------------------------------------------

    def apply_view():
        show_band_col = should_show_band_column()

        # Columns
        table.columns.clear()
        table.columns.append(ft.DataColumn(ft.Text("DXCC Entity")))
        table.columns.append(ft.DataColumn(ft.Text("Callsign")))
        table.columns.append(ft.DataColumn(ft.Text("QSO Date")))
        table.columns.append(ft.DataColumn(ft.Text("QSL Status")))
        if show_band_col:
            table.columns.append(ft.DataColumn(ft.Text("Band")))
        table.columns.append(ft.DataColumn(ft.Text("Actions")))

        # Base rows = all rows in tracked bands
        rows = [r for r in all_rows if band_is_tracked(r[4])]

        # Filter by QSL status
        fval = status_filter_state["value"]
        if fval != "All":
            rows = [r for r in rows if r[3] == fval]

        # Filter by band
        bf = band_filter_state["value"]
        if bf != "All":
            rows = [r for r in rows if r[4] == bf]

        # Sort
        sval = sort_state["value"]
        if sval != "None":
            if sval == "DXCC":
                rows.sort(key=lambda r: (dxcc_from_call(r[1])[1] or ""))
            elif sval == "Callsign":
                rows.sort(key=lambda r: r[1] or "")
            elif sval == "QSO Date":
                rows.sort(key=lambda r: r[2] or "")
            elif sval == "QSL Status":
                rows.sort(key=lambda r: r[3] or "")

        table.rows.clear()
        for country, call, date, status, band in rows:
            table.rows.append(
                create_row(country, call, date, status, band, show_band_col)
            )

        update_dashboard()
        page.update()

    # ------------------------------------------------------
    # Data operations
    # ------------------------------------------------------

    def add_entry(call, date, status, band):
        if not call:
            show_message("Enter a callsign.")
            return

        dxcc_id, dxcc_name, _active = dxcc_from_call(call)
        if dxcc_name:
            country = dxcc_name
        else:
            country = "Unknown"

        rec = [country, call, date, status, band]
        all_rows.append(rec)
        add_qso(current_user["callsign"], country, call, date, status, band)
        apply_view()

    def delete_entry(country, call, date, status, band):
        removed = False
        newlist = []
        for r in all_rows:
            if not removed and r == [country, call, date, status, band]:
                removed = True
                continue
            newlist.append(r)
        all_rows[:] = newlist
        delete_qso(current_user["callsign"], country, call, date, status, band)
        apply_view()

    def edit_entry(country, call, date, status, band):
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
        band_dd = ft.Dropdown(
            label="Band",
            width=150,
            value=band if band in BAND_OPTIONS else None,
            options=[ft.dropdown.Option(b) for b in BAND_OPTIONS],
        )

        # Live DXCC label
        dxcc_label = ft.Text()

        def update_dxcc_label():
            dxcc_id, dxcc_name, is_active = dxcc_from_call(call_tf.value)
            if dxcc_name:
                if is_active is False:
                    dxcc_label.value = f"DXCC: 💀 {dxcc_name} (deleted)"
                    dxcc_label.color = ft.Colors.RED_400
                else:
                    dxcc_label.value = f"DXCC: {dxcc_name}"
                    dxcc_label.color = None
            else:
                dxcc_label.value = "DXCC: Unknown"
                dxcc_label.color = ft.Colors.GREY_600

        def on_call_change(e):
            update_dxcc_label()
            edit_dialog.update()

        call_tf.on_change = on_call_change
        update_dxcc_label()

        def save_changes(e):
            old_row = [country, call, date, status, band]

            new_dxcc_id, new_dxcc_name, _is_active = dxcc_from_call(call_tf.value)
            if new_dxcc_name:
                new_country = new_dxcc_name
            else:
                new_country = "Unknown"

            new_row = [
                new_country,
                call_tf.value,
                date_tf.value,
                status_dd.value,
                band_dd.value,
            ]

            for i, r in enumerate(all_rows):
                if r == old_row:
                    all_rows[i] = new_row
                    break

            update_qso(current_user["callsign"], old_row, new_row)
            page.close(edit_dialog)
            apply_view()

        edit_dialog.title = ft.Text("Edit Entry")
        edit_dialog.content = ft.Column(
            [
                call_tf,
                dxcc_label,
                date_tf,
                status_dd,
                band_dd,
                ft.Row(
                    [
                        ft.ElevatedButton("Save", on_click=save_changes),
                        ft.OutlinedButton(
                            "Cancel",
                            on_click=lambda e: page.close(edit_dialog),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            tight=True,
        )
        page.open(edit_dialog)

    # ------------------------------------------------------
    # Clear All QSOs
    # ------------------------------------------------------

    def clear_all_qsos():
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute(
            "DELETE FROM qsos WHERE callsign=?",
            (current_user["callsign"],),
        )
        con.commit()
        con.close()

        all_rows.clear()
        apply_view()
        show_message("All QSOs deleted.")

    clear_dialog.title = ft.Text("Confirm Delete")
    clear_dialog.content = ft.Text(
        "Delete ALL QSOs for this user?\nThis cannot be undone!"
    )
    clear_dialog.actions = [
        ft.TextButton("Cancel", on_click=lambda e: page.close(clear_dialog)),
        ft.TextButton(
            "Delete All",
            on_click=lambda e: (page.close(clear_dialog), clear_all_qsos()),
        ),
    ]
    clear_dialog.actions_alignment = ft.MainAxisAlignment.END

    # ------------------------------------------------------
    # ADIF Import
    # ------------------------------------------------------

    def import_adif(path):
        try:
            rows = parse_adif_file(path)
        except Exception as e:
            show_message(f"ADIF error: {e}")
            return
        if not rows:
            show_message("No QSOs found in ADIF file.")
            return

        imported = 0
        for c, call, d, s, band in rows:
            call = (call or "").strip().upper()
            if not call:
                continue

            dxcc_id, dxcc_name, _is_active = dxcc_from_call(call)
            if dxcc_name:
                country = dxcc_name
            else:
                country = (c or "Unknown")

            rec = [country, call, d, s, band]
            all_rows.append(rec)
            add_qso(current_user["callsign"], country, call, d, s, band)
            imported += 1

        apply_view()
        show_message(f"Imported {imported} QSOs from ADIF.")

    def on_adif_pick(e):
        if not e.files:
            return
        file_path = e.files[0].path
        if file_path:
            import_adif(file_path)

    adif_picker.on_result = on_adif_pick

    # ------------------------------------------------------
    # Load user data + profile
    # ------------------------------------------------------

    def load_user_profile():
        track_all, bands, include_deleted = get_user_profile(current_user["callsign"])
        user_track_all["value"] = track_all
        user_bands["value"] = bands
        include_deleted_state["value"] = include_deleted

    def load_user_data():
        all_rows.clear()
        qsos = get_qsos_for_user(current_user["callsign"])
        for c, call, date, status, band in qsos:
            all_rows.append([c, call, date, status, band or ""])
        apply_view()

    # ------------------------------------------------------
    # User Profile dialog (bands + deleted toggle)
    # ------------------------------------------------------

    def open_profile_dialog(e=None):
        band_checks = []
        selected_set = set(user_bands["value"])

        def make_on_change(band_name):
            def _change(ev):
                if user_track_all["value"]:
                    return
                if ev.control.value:
                    if band_name not in user_bands["value"]:
                        user_bands["value"].append(band_name)
                else:
                    if band_name in user_bands["value"]:
                        user_bands["value"].remove(band_name)
            return _change

        track_all_cb = ft.Checkbox(
            label="Track all bands",
            value=user_track_all["value"],
        )

        for b in BAND_OPTIONS:
            cb = ft.Checkbox(
                label=b,
                value=(b in selected_set),
                disabled=user_track_all["value"],
            )
            cb.on_change = make_on_change(b)
            band_checks.append(cb)

        include_deleted_cb = ft.Checkbox(
            label="Include deleted DXCC entities in stats",
            value=include_deleted_state["value"],
        )

        def track_all_changed(ev):
            user_track_all["value"] = ev.control.value
            for c in band_checks:
                c.disabled = user_track_all["value"]
            page.update()

        track_all_cb.on_change = track_all_changed

        def save_profile(ev):
            include_deleted_state["value"] = include_deleted_cb.value
            set_user_profile(
                current_user["callsign"],
                user_track_all["value"],
                user_bands["value"],
                include_deleted_state["value"],
            )
            page.close(profile_dialog)
            apply_view()
            show_message("Profile saved.")

        profile_dialog.title = ft.Text("User Profile")
        profile_dialog.content = ft.Column(
            [
                ft.Text("Bands to track", size=16, weight="bold"),
                track_all_cb,
                ft.Text("Bands:", size=12),
                ft.Column(band_checks, spacing=2),
                ft.Divider(),
                include_deleted_cb,
                ft.Text(
                    "When OFF, deleted entities (💀) are shown in the table, "
                    "but do not count toward DXCC totals.",
                    size=11,
                    color=ft.Colors.GREY_700,
                ),
            ],
            tight=True,
        )
        profile_dialog.actions = [
            ft.TextButton("Cancel", on_click=lambda ev: page.close(profile_dialog)),
            ft.TextButton("Save", on_click=save_profile),
        ]
        profile_dialog.actions_alignment = ft.MainAxisAlignment.END

        page.open(profile_dialog)

    # ------------------------------------------------------
    # Main app UI
    # ------------------------------------------------------

    def show_app():
        clear_page()

        # top bar
        page.add(
            ft.Row(
                [
                    ft.Text(
                        f"DXCC Need List Tracker — {current_user['callsign']}",
                        size=24,
                        weight="bold",
                    ),
                    ft.Container(expand=True),
                    ft.ElevatedButton("Profile", on_click=open_profile_dialog),
                    ft.ElevatedButton("Logout", on_click=lambda e: show_login()),
                ]
            )
        )

        page.add(dashboard)

        # Entry fields (no country dropdown; DXCC is from callsign)
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
        band_dd = ft.Dropdown(
            label="Band",
            width=150,
            options=[ft.dropdown.Option(b) for b in BAND_OPTIONS],
        )

        dxcc_label = ft.Text()

        def update_dxcc_label_add():
            dxcc_id, dxcc_name, is_active = dxcc_from_call(call_tf.value)
            if dxcc_name:
                if is_active is False:
                    dxcc_label.value = f"DXCC: 💀 {dxcc_name} (deleted)"
                    dxcc_label.color = ft.Colors.RED_400
                else:
                    dxcc_label.value = f"DXCC: {dxcc_name}"
                    dxcc_label.color = None
            else:
                dxcc_label.value = "DXCC: Unknown"
                dxcc_label.color = ft.Colors.GREY_600

        def on_call_change_add(e):
            update_dxcc_label_add()
            page.update()

        call_tf.on_change = on_call_change_add
        update_dxcc_label_add()

        def add_click(e):
            add_entry(
                call_tf.value,
                date_tf.value,
                status_dd.value,
                band_dd.value,
            )
            call_tf.value = ""
            date_tf.value = ""
            status_dd.value = "Needed"
            band_dd.value = None
            update_dxcc_label_add()
            page.update()

        add_btn = ft.ElevatedButton("Add Entry", on_click=add_click)

        page.add(
            ft.Container(
                ft.Column(
                    [
                        ft.Row(
                            [call_tf, date_tf, status_dd, band_dd, add_btn],
                            spacing=10,
                            wrap=True,
                        ),
                        dxcc_label,
                    ],
                    spacing=5,
                ),
                padding=10,
            )
        )

        # Filters and actions
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

        band_filter_dd = ft.Dropdown(
            label="Filter Band",
            width=150,
            value=band_filter_state["value"],
            options=[ft.dropdown.Option("All")]
            + [ft.dropdown.Option(b) for b in BAND_OPTIONS],
        )

        sort_dd = ft.Dropdown(
            label="Sort By",
            width=150,
            value=sort_state["value"],
            options=[
                ft.dropdown.Option("None"),
                ft.dropdown.Option("DXCC"),
                ft.dropdown.Option("Callsign"),
                ft.dropdown.Option("QSO Date"),
                ft.dropdown.Option("QSL Status"),
            ],
        )

        include_deleted_switch = ft.Switch(
            label="Include deleted in stats",
            value=include_deleted_state["value"],
        )

        def on_status_filter_change(e):
            status_filter_state["value"] = status_filter_dd.value or "All"
            apply_view()

        def on_band_filter_change(e):
            band_filter_state["value"] = band_filter_dd.value or "All"
            apply_view()

        def on_sort_change(e):
            sort_state["value"] = sort_dd.value or "None"
            apply_view()

        def on_include_deleted_change(e):
            include_deleted_state["value"] = include_deleted_switch.value
            set_user_profile(
                current_user["callsign"],
                user_track_all["value"],
                user_bands["value"],
                include_deleted_state["value"],
            )
            apply_view()

        status_filter_dd.on_change = on_status_filter_change
        band_filter_dd.on_change = on_band_filter_change
        sort_dd.on_change = on_sort_change
        include_deleted_switch.on_change = on_include_deleted_change

        page.add(
            ft.Row(
                [
                    status_filter_dd,
                    band_filter_dd,
                    sort_dd,
                    include_deleted_switch,
                    ft.ElevatedButton(
                        "Import ADIF",
                        on_click=lambda e: adif_picker.pick_files(
                            allow_multiple=False,
                            allowed_extensions=["adi", "adif", "log"],
                            file_type=ft.FilePickerFileType.CUSTOM,
                        ),
                    ),
                    ft.ElevatedButton(
                        "Clear All",
                        bgcolor=ft.Colors.RED_300,
                        color=ft.Colors.WHITE,
                        on_click=lambda e: page.open(clear_dialog),
                    ),
                ],
                spacing=10,
                wrap=True,
            )
        )

        page.add(ft.Divider())
        page.add(table)

        # Load profile + data AFTER building UI
        load_user_profile()
        load_user_data()
        update_dxcc_label_add()
        page.update()

    # ------------------------------------------------------
    # Login screen
    # ------------------------------------------------------

    def show_login():
        clear_page()

        def handle_login(callsign, password):
            ok, msg = authenticate(callsign, password)
            if not ok:
                show_message(msg)
                return
            current_user["callsign"] = callsign.upper()
            show_app()

        def handle_register(callsign, password):
            ok, msg = register_user(callsign, password)
            show_message(msg)
            if ok:
                handle_login(callsign, password)

        login_controls, _ = build_login_controls(handle_login, handle_register)

        page.add(
            ft.Container(
                login_controls,
                alignment=ft.alignment.center,
                padding=20,
            )
        )

    show_login()


if __name__ == "__main__":
    ft.app(target=main)
