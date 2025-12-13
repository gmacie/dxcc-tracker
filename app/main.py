from __future__ import annotations

from datetime import datetime, UTC
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
from app import dxcc_prefixes


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
ALL_BANDS = [
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
    "2m",
]


# ------------------------------------------------------------
# Global state
# ------------------------------------------------------------
current_user: dict | None = None


# ------------------------------------------------------------
# App entry
# ------------------------------------------------------------
def main(page: ft.Page):
    global current_user

    page.title = "DXCC Need List Tracker"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    init_db()
    dxcc_prefixes.load_dxcc_data()

    # =========================================================
    # LOGIN VIEW
    # =========================================================
    callsign = ft.TextField(label="Callsign", width=240)
    password = ft.TextField(
        label="Password", password=True, can_reveal_password=True, width=240
    )
    status = ft.Text(color=ft.Colors.RED)

    def do_login(e):
        global current_user
        ok, msg = authenticate(callsign.value, password.value)
        if not ok:
            status.value = msg
            page.update()
            return
        current_user = {"callsign": callsign.value.upper()}
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
    # MAIN APPLICATION
    # =========================================================
    def show_app():
        page.controls.clear()
        user = current_user["callsign"]

        track_all, bands, include_deleted = get_user_profile(user)

        # -----------------------------
        # Dashboard
        # -----------------------------
        worked_txt = ft.Text(size=22, weight="bold")
        confirmed_txt = ft.Text(size=22, weight="bold")
        remaining_txt = ft.Text(size=22, weight="bold")

        def stat_box(label, value, color):
            return ft.Container(
                content=ft.Column(
                    [ft.Text(label), value],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=14,
                bgcolor=color,
                border_radius=8,
            )

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
                ft.DataColumn(ft.Text("Entity")),
                ft.DataColumn(ft.Text("Country")),
                ft.DataColumn(ft.Text("Call Worked")),
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("QSL Status")),
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

        band_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Band")),
                ft.DataColumn(ft.Text("Worked")),
                ft.DataColumn(ft.Text("Confirmed")),
            ],
            rows=[],
        )

        # -----------------------------
        # ADIF Import
        # -----------------------------
        picker = ft.FilePicker()
        page.overlay.append(picker)

        def on_adif_selected(e: ft.FilePickerResultEvent):
            if not e.files:
                return
            import_adif(e.files[0].path, user)
            refresh()

        picker.on_result = on_adif_selected

        import_btn = ft.ElevatedButton(
            "Import ADIF",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: picker.pick_files(
                allow_multiple=False, allowed_extensions=["adi", "adif"]
            ),
        )

        # -----------------------------
        # Admin Panel
        # -----------------------------
        def admin_panel():
            active, total, prefixes = get_dxcc_stats()

            stats = ft.Text(
                f"DXCC Entities\n"
                f"Active: {active}\n"
                f"Total: {total}\n"
                f"Prefixes: {prefixes}",
                selectable=True,
            )

            def reload_dxcc(e):
                dxcc_prefixes.reload_dxcc_cache()
                a, t, p = get_dxcc_stats()
                stats.value = (
                    f"DXCC Entities\n"
                    f"Active: {a}\n"
                    f"Total: {t}\n"
                    f"Prefixes: {p}"
                )
                page.update()

            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Admin Panel", size=18, weight="bold"),
                        stats,
                        ft.ElevatedButton(
                            "Reload DXCC Cache",
                            icon=ft.Icons.REFRESH,
                            on_click=reload_dxcc,
                        ),
                    ],
                    spacing=10,
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
            band_table.rows.clear()

            qsos = get_qsos_for_user(user)

            band_worked = defaultdict(set)
            band_confirmed = defaultdict(set)
            grouped = defaultdict(list)

            for prefix, country, call, date, status, band in qsos:
                
                eid, name, active = dxcc_prefixes.entity_for_callsign(call)
                prefix = dxcc_prefixes.prefix_for_callsign(call)

                if not eid:
                    continue
                if not include_deleted and not active:
                    continue

                eid, name, active = dxcc_prefixes.entity_for_callsign(call)
                prefix = dxcc_prefixes.prefix_for_callsign(call)

                band_worked[band].add(eid)
                if status in ("Confirmed", "LoTW", "QSL"):
                    band_confirmed[band].add(eid)

                grouped[(eid, band)].append(
                    (eid, name, prefix, call, date, status, band)
                )


            # QSO table
            for (eid, band), rows in grouped.items():
                confirmed_rows = [r for r in rows if r[5] in ("Confirmed", "LoTW", "QSL")]
                display = confirmed_rows[:1] if confirmed_rows else rows

                for eid, name, prefix, call, date, status, band in display:
                    qso_table.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(prefix or eid)),
                                ft.DataCell(ft.Text(name)),
                                ft.DataCell(ft.Text(call)),
                                ft.DataCell(ft.Text(date)),
                                ft.DataCell(ft.Text(status)),
                                ft.DataCell(ft.Text(band)),
                                ft.DataCell(
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE,
                                        on_click=lambda e, r=(name, call, date, status, band): (
                                            delete_qso(user, *r),
                                            refresh(),
                                        ),
                                    )
                                ),
                            ]
                        )
                    )

            # Per-band summary
            for band in sorted(band_worked):
                w = len(band_worked[band])
                c = min(len(band_confirmed.get(band, set())), w)
                band_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(band)),
                            ft.DataCell(ft.Text(str(w))),
                            ft.DataCell(ft.Text(str(c))),
                        ]
                    )
                )

            # Need List
            need_bands = bands if not track_all else ALL_BANDS
            needs = get_dxcc_need_list(user, need_bands, include_deleted)

            for eid, country, band in sorted(needs):
                need_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(eid)),
                            ft.DataCell(ft.Text(country)),
                            ft.DataCell(ft.Text(band)),
                        ]
                    )
                )

            # Dashboard
            worked, confirmed, total_active = get_dxcc_dashboard(
                user, None if track_all else bands, include_deleted
            )

            worked_txt.value = str(len(worked))
            confirmed_txt.value = str(min(len(confirmed), len(worked)))
            remaining_txt.value = str(max(total_active - len(worked), 0))

            page.update()

        # -----------------------------
        # Add QSO
        # -----------------------------
        call_in = ft.TextField(label="Call Worked", width=150)
        date_in = ft.TextField(
            label="Date",
            value=datetime.now(UTC).strftime("%Y-%m-%d"),
            width=120,
        )
        band_in = ft.TextField(label="Band", width=80)
        status_in = ft.Dropdown(
            label="QSL Status",
            width=150,
            options=[
                ft.dropdown.Option("Worked"),
                ft.dropdown.Option("Requested"),
                ft.dropdown.Option("Confirmed"),
                ft.dropdown.Option("LoTW"),
                ft.dropdown.Option("QSL"),
            ],
        )

        def add_clicked(e):
            if not call_in.value:
                return
            add_qso(
                user=user,
                country="",
                call_worked=call_in.value.upper(),
                date=date_in.value,
                status=status_in.value or "Worked",
                band=band_in.value,
            )
            call_in.value = ""
            refresh()

        add_row = ft.Row(
            [
                call_in,
                date_in,
                band_in,
                status_in,
                ft.ElevatedButton("Add QSO", on_click=add_clicked),
            ],
            wrap=True,
        )

        # -----------------------------
        # Tabs
        # -----------------------------
        tabs = ft.Tabs(
            tabs=[
                ft.Tab("QSOs", ft.Column([qso_table], scroll=ft.ScrollMode.AUTO)),
                ft.Tab(
                    "DXCC Need List",
                    ft.Column(
                        [
                            ft.Text(
                                "DXCC Needed (per band)",
                                size=18,
                                weight="bold",
                            ),
                            need_table,
                        ],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                ),
            ]
        )

        # -----------------------------
        # Layout
        # -----------------------------
        controls = [ft.Text(f"Logged in as {user}", size=18)]

        if is_admin_user(user):
            controls.append(admin_panel())

        controls.extend(
            [
                dashboard,
                ft.Divider(),
                import_btn,
                band_table,
                ft.Divider(),
                add_row,
                ft.Divider(),
                tabs,
            ]
        )

        page.add(ft.Column(controls, spacing=20))
        refresh()

    page.update()


if __name__ == "__main__":
    ft.app(target=main)
