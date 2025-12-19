from __future__ import annotations

import warnings
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
)

APP_VERSION = "0.9.0-stable"
BUILD_DATE = "2025-12-13"

from datetime import datetime, UTC, timedelta
from collections import defaultdict

import flet as ft

import os
import tempfile
import sqlite3

IS_WEB = os.environ.get("FLET_PLATFORM") == "web"

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
    get_dxcc_counts,
)

from app.adif_import import import_adif

from app.lotw_cache import refresh_lotw_cache, get_lotw_last_upload

from app import dxcc_prefixes

from app.config import DB_PATH


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
ALL_BANDS = [
    "160m", "80m", "60m", "40m", "30m",
    "20m", "17m", "15m", "12m", "10m",
    "6m",
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

    # -------------------------
    # LOGIN VIEW
    # -------------------------
    def show_login():
        page.controls.clear()

        callsign_input = ft.TextField(label="Callsign", autofocus=True, width=300)
        password_input = ft.TextField(label="Password", password=True, width=300)
        status = ft.Text(color=ft.Colors.RED)

        def on_login(e):
            ok, msg = authenticate(callsign_input.value, password_input.value)
            if not ok:
                status.value = msg
                page.update()
                return

            current_user["callsign"] = callsign_input.value.upper()
            show_app()

        page.add(
            ft.Column(
                [
                    ft.Text("DXCC Tracker", size=24, weight="bold"),
                    callsign_input,
                    password_input,
                    ft.ElevatedButton("Login", on_click=on_login),
                    status,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        page.update()

    # -------------------------
    # LOGOUT
    # -------------------------
    def do_logout(e=None):
        current_user["callsign"] = None
        show_login()

    # -------------------------
    # MAIN APP
    # -------------------------
    def show_app():
        page.controls.clear()

        user = current_user["callsign"]
        if not user:
            show_login()
            return
            
        track_all, bands, include_deleted = get_user_profile(user)
        
        qso_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Prefix")),
                ft.DataColumn(ft.Text("Country")),
                ft.DataColumn(ft.Text("Call")),
                ft.DataColumn(ft.Text("Date")),
                ft.DataColumn(ft.Text("QSL")),
                ft.DataColumn(ft.Text("LoTW")),
                ft.DataColumn(ft.Text("Band")),
            ],
            rows=[],
        )
        
        need_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Prefix")),
                ft.DataColumn(ft.Text("Country")),
                ft.DataColumn(ft.Text("Band")),
            ],
            rows=[],
        )
               
        qso_tabs = ft.Tabs(
            tabs=[
                ft.Tab(
                    "QSOs",
                    ft.Column(
                        [qso_table],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                ),
               ft.Tab(
                    "DXCC Need List",
                    ft.Column(
                        [need_table],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                ),
            ],
            expand=True,
        )
        
        # -----------------------------
        # Admin Panel
        # -----------------------------
        def admin_panel():
            active, total, prefixes = get_dxcc_stats()

            stats_txt = ft.Text(
                f"DXCC Entities\n"
                f"Active: {active}\n"
                f"Total: {total}\n"
                f"Prefixes: {prefixes}",
                selectable=True,
            )

            def reload_dxcc(e):
                dxcc_prefixes.reload_dxcc_cache()
                a, t, p = get_dxcc_stats()
                stats_txt.value = (
                    f"DXCC Entities\n"
                    f"Active: {a}\n"
                    f"Total: {t}\n"
                    f"Prefixes: {p}"
                )
                page.snack_bar = ft.SnackBar(
                    ft.Text("DXCC cache reloaded"),
                    open=True,
                )
                page.update()

            def refresh_lotw(e):
                refresh_lotw_cache(force=True)
                page.snack_bar = ft.SnackBar(
                    ft.Text("LoTW cache refreshed"),
                    open=True,
                )
                page.update()

            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Admin Tools", size=18, weight="bold"),
                        stats_txt,
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Reload DXCC Cache",
                                    icon=ft.Icons.REFRESH,
                                    on_click=reload_dxcc,
                                ),
                                ft.ElevatedButton(
                                    "Refresh LoTW Cache",
                                    icon=ft.Icons.CLOUD_SYNC,
                                    on_click=refresh_lotw,
                                ),
                            ],
                            wrap=True,
                        ),
                    ],
                    spacing=10,
                ),
                padding=14,
                bgcolor=ft.Colors.BLUE_GREY_900,
                border_radius=10,
            )

        def stat_box(label, value_control, color):
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text(label, size=14),
                        value_control,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=16,
                bgcolor=color,
                border_radius=10,
                width=180,
            )

        worked_txt = ft.Text(size=26, weight="bold")
        confirmed_txt = ft.Text(size=26, weight="bold")
        remaining_txt = ft.Text(size=26, weight="bold")


        dashboard = ft.Row(
            [
                stat_box("Worked DXCC", worked_txt, ft.Colors.BLUE_GREY_800),
                stat_box("Confirmed DXCC", confirmed_txt, ft.Colors.GREEN_800),
                stat_box("Remaining DXCC", remaining_txt, ft.Colors.ORANGE_800),
            ],
            spacing=20,
        )
        
        def on_done(result=None):
            import_progress.visible = False
            cancel_btn.visible = False

            if result:
                import_status.value = (
                    f"ADIF import complete: "
                    f"{result['added']} added, "
                    f"{result['skipped']} skipped"
                )
            else:
                import_status.value = "ADIF import complete"

            refresh_qso_table()
            refresh_dashboard()
            page.update()

        def refresh_qso_table():
            con = sqlite3.connect(DB_PATH)
            cur = con.cursor()

            # Query the qsos table
            cur.execute(
                """
                SELECT call_worked, qso_date, qsl_status, band
                FROM qsos
                WHERE callsign=?
                ORDER BY qso_date DESC
                """,
                (user,),
            )

            rows = cur.fetchall()

            qso_table.rows.clear()

            for call, qso_date, qsl_status, band in rows:
                eid, country, active = dxcc_prefixes.entity_for_callsign(call)
                prefix = dxcc_prefixes.prefix_for_callsign(call) or ""
                
                # Look up LoTW last upload date for this callsign
                lotw_date = get_lotw_last_upload(call)

                qso_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(prefix)),
                            ft.DataCell(ft.Text(country or "—")),
                            ft.DataCell(ft.Text(call)),
                            ft.DataCell(ft.Text(qso_date)),
                            ft.DataCell(ft.Text(qsl_status or "—")),
                            ft.DataCell(ft.Text(lotw_date or "—")),
                            ft.DataCell(ft.Text(band or "—")),
                        ]
                    )
                )
            
            con.close()
            page.update()
        
        # ============================================================
        # DASHBOARD (STABLE)
        # Relies on:
        #   - get_user_profile()
        #   - get_dxcc_dashboard()
        #   - dxcc_prefixes.entity_for_callsign()
        # DO NOT MODIFY without checking counts carefully
        # ============================================================

        def refresh_dashboard():
            worked, confirmed, total_active = get_dxcc_dashboard(
                user,
                None if track_all else bands,
                include_deleted,
            )

            worked_txt.value = str(len(worked))
            confirmed_txt.value = str(min(len(confirmed), len(worked)))
            remaining_txt.value = str(max(total_active - len(worked), 0))

            page.update()


        page.update()
    
        logout_btn = ft.ElevatedButton(
            "Logout",
            icon=ft.Icons.LOGOUT,
            on_click=do_logout,
        )

        # -----------------------------
        # Web ADIF upload launcher
        # -----------------------------
        def upload_adif_web(e):
            page.launch_url(
                f"http://localhost:8551/static/upload.html?user={user}"
            )

        # -----------------------------
        # Import buttons
        # -----------------------------
        import_btn = ft.ElevatedButton(
            "Import ADIF",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: picker.pick_files(
                allow_multiple=False,
                allowed_extensions=["adi", "adif"],
            ),
        )

        import_web_btn = ft.ElevatedButton(
            "Import ADIF (Web)",
            icon=ft.Icons.CLOUD_UPLOAD,
            on_click=upload_adif_web,
        )

        # -----------------------------
        # Footer
        # -----------------------------
        footer = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        f"DXCC Need List Tracker • v{APP_VERSION} • Build {BUILD_DATE}",
                        size=12,
                        color=ft.Colors.GREY_500,
                    ),
                    ft.Text(
                        "© N4LR",
                        size=12,
                        color=ft.Colors.GREY_500,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
            padding=10,
)

        
        page.add(
            ft.Column(
                [
                    # Header row
                    ft.Row(
                        [
                            ft.Text(f"Logged in as {user}", size=18),
                            logout_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    
                    # Admin tools (conditional)
                    admin_panel() if is_admin_user else ft.Container(),
                    
                    ft.Divider(),
                    dashboard,
                    
                    ft.Divider(),
                    import_btn,
                    import_web_btn,

                    ft.Divider(),
                    qso_tabs,

                    # 👇 FOOTER GOES HERE
                    ft.Divider(),
                    footer,
                    
                ],
                spacing=16,
            )
        )

        refresh_dashboard()
        refresh_qso_table()
        page.update()
    
    # -------------------------
    # START APP
    # -------------------------
    show_login()



if __name__ == "__main__":
    ft.app(
        target=main,
        view=ft.AppView.WEB_BROWSER,
        host="0.0.0.0",
        port=8550,
    )

