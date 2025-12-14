from __future__ import annotations

APP_VERSION = "0.9.0-stable"
BUILD_DATE = "2025-12-13"

from datetime import datetime, UTC, timedelta
from collections import defaultdict

import flet as ft

from app.auth import authenticate, register_user
from app.database import (
    init_db,
    add_qso,
    delete_qso,
    get_qsos_for_user,
    get_user_profile,
    get_dxcc_dashboard,
    get_dxcc_need_list,
    is_admin_user,
    get_dxcc_stats,
)
from app.adif_import import import_adif
from app.lotw_cache import refresh_lotw_cache, get_lotw_last_upload
from app import dxcc_prefixes


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
ALL_BANDS = [
    "160m", "80m", "60m", "40m", "30m",
    "20m", "17m", "15m", "12m", "10m",
    "6m", "2m",
]

LOTW_GREEN_DAYS = 90


# ------------------------------------------------------------
# App entry
# ------------------------------------------------------------
def main(page: ft.Page):
    page.title = "DXCC Need List Tracker"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    init_db()
    dxcc_prefixes.load_dxcc_data()

    current_user = {"callsign": None}

    # =========================================================
    # LOGIN VIEW
    # =========================================================
    #callsign = ft.TextField(label="Callsign", width=240)
    callsign = ft.TextField(
        label="Callsign",
        width=240,
        autofocus=True,   # ✅ ADD THIS
)

    
    password = ft.TextField(label="Password", password=True, width=240)
    status = ft.Text(color=ft.Colors.RED)

    def do_login(e):
        ok, msg = authenticate(callsign.value, password.value)
        if not ok:
            status.value = msg
            page.update()
            return
        current_user["callsign"] = callsign.value.upper()
        show_app()

    def do_register(e):
        ok, msg = register_user(callsign.value, password.value)
        status.value = msg
        page.update()

    page.add(
        ft.Column(
            [
                ft.Text("DXCC Need List Tracker", size=28, weight="bold"),
                callsign,
                password,
                ft.Row(
                    [
                        ft.ElevatedButton("Login", on_click=do_login),
                        ft.OutlinedButton("Register", on_click=do_register),
                    ]
                ),
                status,
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )
    )

    # =========================================================
    # MAIN APP
    # =========================================================
    def show_app():
        page.controls.clear()
        user = current_user["callsign"]
        
        # -----------------------------
        # ADIF File Picker (REQUIRED)
        # -----------------------------
        picker = ft.FilePicker()
        page.overlay.append(picker)
        
        def on_adif_selected(e: ft.FilePickerResultEvent):
            if not e.files:
                return
            import_adif(e.files[0].path, user)
            refresh()

        picker.on_result = on_adif_selected

        track_all, bands, include_deleted = get_user_profile(user)
        
        import_btn = ft.ElevatedButton(
            "Import ADIF",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["adi", "adif"],
            ),
        )

        # -----------------------------
        # Dashboard helpers
        # -----------------------------
        def stat_box(label, value, color):
            return ft.Container(
                content=ft.Column(
                    [ft.Text(label), value],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=14,
                bgcolor=color,
                border_radius=8,
                width=180,
            )

        worked_txt = ft.Text(size=22, weight="bold")
        confirmed_txt = ft.Text(size=22, weight="bold")
        remaining_txt = ft.Text(size=22, weight="bold")

        dashboard = ft.Row(
            [
                stat_box("Worked DXCC", worked_txt, ft.Colors.BLUE_GREY_800),
                stat_box("Confirmed DXCC", confirmed_txt, ft.Colors.GREEN_800),
                stat_box("Remaining DXCC", remaining_txt, ft.Colors.ORANGE_800),
            ],
            spacing=20,
        )

        # -----------------------------
        # Tables
        # -----------------------------
        qso_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Prefix")),
                ft.DataColumn(ft.Text("Country")),
                ft.DataColumn(ft.Text("Call")),
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("QSL")),
                ft.DataColumn(ft.Text("LoTW Upload")),
                ft.DataColumn(ft.Text("Band")),
                ft.DataColumn(ft.Text("")),
            ],
            rows=[],
        )

        need_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Entity")),
                ft.DataColumn(ft.Text("Country")),
                ft.DataColumn(ft.Text("Band")),
            ],
            rows=[],
        )

        # -----------------------------
        # Admin Panel
        # -----------------------------
        def admin_panel():
            active, total, prefixes = get_dxcc_stats()

            stats = ft.Text(
                f"DXCC Entities\nActive: {active}\nTotal: {total}\nPrefixes: {prefixes}"
            )

            def reload_dxcc(e):
                dxcc_prefixes.reload_dxcc_cache()
                a, t, p = get_dxcc_stats()
                stats.value = f"DXCC Entities\nActive: {a}\nTotal: {t}\nPrefixes: {p}"
                page.update()

            def refresh_lotw(e):
                refresh_lotw_cache(force=True)
                page.snack_bar = ft.SnackBar(ft.Text("LoTW cache refreshed"))
                page.snack_bar.open = True
                page.update()

            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Admin Panel", size=18, weight="bold"),
                        stats,
                        ft.Row(
                            [
                                ft.ElevatedButton("Reload DXCC Cache", on_click=reload_dxcc),
                                ft.ElevatedButton("Refresh LoTW Cache", on_click=refresh_lotw),
                            ]
                        ),
                    ]
                ),
                padding=14,
                bgcolor=ft.Colors.BLUE_GREY_900,
                border_radius=8,
            )

        # -----------------------------
        # Refresh
        # -----------------------------
        def refresh():
            qso_table.rows.clear()
            need_table.rows.clear()

            qsos = get_qsos_for_user(user)

            grouped = defaultdict(list)
            

            #for prefix, country, call, date, status, band in qsos:   12/13/2025 12:27 pm
            for _db_prefix, country, call, date, status, band in qsos:
                
                prefix = dxcc_prefixes.prefix_for_callsign(call)
                missing_prefix = not prefix
                
                #eid, name, active = dxcc_prefixes.entity_for_callsign(call)
                eid, dxcc_name, active = dxcc_prefixes.entity_for_callsign(call)
                display_country = dxcc_name if dxcc_name != "Unknown" else country

                
                if not eid:
                    continue
                if not include_deleted and not active:
                    continue
                
                display_prefix = prefix if isinstance(prefix, str) else ""

                grouped[(eid, band)].append(
                    (
                        display_prefix,        # Prefix (display)
                        display_country,       # Country
                        call,
                        date,
                        status,
                        band,
                        missing_prefix,        # flag, not displayed
                    )
                )


            for (eid, band), rows in grouped.items():
                confirmed = [r for r in rows if r[4] in ("Confirmed", "LoTW", "QSL")]
                display = confirmed[:1] if confirmed else rows

                for prefix, country, call, date, status, band, missing_prefix in display:
                    lotw_date = get_lotw_last_upload(call)
                    lotw_cell = ft.Text(lotw_date or "")
                    
                    # Highlight ONLY if not confirmed
                    if lotw_date and status not in ("Confirmed", "LoTW", "QSL"):
                        try:
                            dt = datetime.fromisoformat(lotw_date)
                            if datetime.now(UTC) - dt < timedelta(days=LOTW_GREEN_DAYS):
                                lotw_cell.color = ft.Colors.GREEN
                        except Exception:
                            pass

                    qso_table.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(
                                    ft.Text(
                                        prefix or "⚠️",
                                        color=ft.Colors.RED if missing_prefix else None,
                                        weight="bold" if missing_prefix else None,
                                    )
                                ),
                                ft.DataCell(ft.Text(country)),
                                ft.DataCell(ft.Text(call)),
                                ft.DataCell(ft.Text(date)),
                                ft.DataCell(ft.Text(status)),
                                ft.DataCell(lotw_cell),
                                ft.DataCell(ft.Text(band)),
                                ft.DataCell(
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE,
                                        on_click=lambda e, r=(country, call, date, status, band): (
                                            delete_qso(user, *r),
                                            refresh(),
                                        ),
                                    )
                                ),
                            ],
                            color=ft.Colors.RED_900 if missing_prefix else None,
                        )
                    )
   

            need_bands = bands if not track_all else ALL_BANDS
            needs = get_dxcc_need_list(user, need_bands, include_deleted)

            for eid, country, band in sorted(needs):
                need_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(prefix)),
                            ft.DataCell(ft.Text(country)),
                            ft.DataCell(ft.Text(band)),
                        ]
                    )
                )

            worked, confirmed, total_active = get_dxcc_dashboard(
                user, None if track_all else bands, include_deleted
            )

            worked_txt.value = str(len(worked))
            confirmed_txt.value = str(min(len(confirmed), len(worked)))
            remaining_txt.value = str(max(total_active - len(worked), 0))

            page.update()

        # -----------------------------
        # Layout
        # -----------------------------
        controls = [ft.Text(f"Logged in as {user}", size=18)]

        if is_admin_user(user):
            controls.append(admin_panel())

        assert import_btn is not None, "Import ADIF button missing from layout"
        
        controls.extend(
            [
                dashboard,
                ft.Divider(),
                import_btn,
                ft.Divider(),
                ft.Tabs(
                    tabs=[
                        ft.Tab("QSOs", ft.Column([qso_table], scroll=ft.ScrollMode.AUTO)),
                        ft.Tab("DXCC Need List", ft.Column([need_table], scroll=ft.ScrollMode.AUTO)),
                    ]
                ),
            ]
        )

        footer = ft.Container(
            content=ft.Text(
                f"DXCC Need List Tracker  •  v{APP_VERSION}  •  Build {BUILD_DATE}",
                size=12,
                color=ft.Colors.GREY_500,
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.only(top=10),
        )

        page.add(
            ft.Column(
                controls + [footer],
                spacing=20,
            )
        )

        #page.add(ft.Column(controls, spacing=20))
        refresh()

    page.update()


if __name__ == "__main__":
    ft.app(target=main)
