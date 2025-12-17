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

        page.add(
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(f"Logged in as {user}", size=18),
                            logout_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Divider(),
                    dashboard,
                ]
            )
        )

        refresh_dashboard()
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

