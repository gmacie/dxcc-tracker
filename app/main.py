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
import threading

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

from app.cty_import import update_cty_data, get_last_cty_update


# ------------------------------------------------------------
# Constants
# ------------------------------------------------------------
ALL_BANDS = [
    "160m", "80m", "60m", "40m", "30m",
    "20m", "17m", "15m", "12m", "10m",
    "6m",
]

LOTW_GREEN_DAYS = 90

COUNTRY_ABBREVIATIONS = {
    "International Telecommunication Union Headquarters": "ITU HQ",
    "United States of America": "USA",
    "United Kingdom": "UK",
    # Add more as you encounter them
}

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
        
        # Sort handler function
        def on_sort_prefix(e):
            sort_column["ascending"] = not sort_column["ascending"] if sort_column["name"] == "prefix" else True
            sort_column["name"] = "prefix"
            refresh_qso_table()
        
        # File picker for ADIF import
        def on_file_picked(e: ft.FilePickerResultEvent):
            if not e.files:
                return
            
            file_path = e.files[0].path
            import_status.value = f"Importing {e.files[0].name}..."
            import_progress.visible = True
            import_progress.value = None  # Indeterminate progress
            page.update()
            
            # Run import in background
            #import threading
            def do_import():
                try:
                    result = import_adif(file_path, user)
                    page.run_task(lambda: on_done(result))
                except Exception as ex:
                    import_status.value = f"Import failed: {str(ex)}"
                    import_progress.visible = False
                    page.update()
            
            threading.Thread(target=do_import, daemon=True).start()
        
        picker = ft.FilePicker(on_result=on_file_picked)
        page.overlay.append(picker)
        
        # Progress indicator controls
        import_progress = ft.ProgressBar(visible=False, width=400)
        import_status = ft.Text("")
        
        # Create band filter dropdown
        band_filter = ft.Dropdown(
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("160m"),
                ft.dropdown.Option("80m"),
                ft.dropdown.Option("60m"),
                ft.dropdown.Option("40m"),
                ft.dropdown.Option("30m"),
                ft.dropdown.Option("20m"),
                ft.dropdown.Option("17m"),
                ft.dropdown.Option("15m"),
                ft.dropdown.Option("12m"),
                ft.dropdown.Option("10m"),
                ft.dropdown.Option("6m"),
            ],
            value="All",
            width=100,
            #height=40,
            text_size=12,
            on_change=lambda e: (refresh_qso_table(), refresh_dashboard()), # add refresh_dashboard 12/19/2025
        )
        
        # Callsign search field
        callsign_search = ft.TextField(
            label="Search Callsign",
            hint_text="Type to filter...",
            width=200,
            on_change=lambda e: refresh_qso_table(),
        )
        
        qso_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Prefix"), on_sort=on_sort_prefix),
                ft.DataColumn(
                    ft.Text(
                        "Country",
                        text_align=ft.TextAlign.CENTER,
                    )
                ),
                ft.DataColumn(ft.Text("Call")),
                ft.DataColumn(
                    ft.Text(
                        "QSO\nDate",  # Line break for two rows
                    )
                ),
                ft.DataColumn(
                    ft.Text(
                        "QSL\nStatus",  # Could also make this two rows for consistency
                    )
                ),
                ft.DataColumn(
                    ft.Text(
                        "LoTW\nDate",  # Makes it explicit
                        text_align=ft.TextAlign.CENTER,
                    )
                ),
                #Column(ft.Text("Band")),
                ft.DataColumn(
                    ft.Column(
                        [
                            ft.Text("Band", size=12),
                            band_filter,
                        ],
                        spacing=2,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                ),
            ],
            rows=[],
            column_spacing=10,
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_800),
            heading_row_height=80,  # Taller header to accommodate two lines
            sort_column_index=None,
            sort_ascending=True,
        )
        
        sort_column = {"name": None, "ascending": True}
        
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
            cty_last_update = get_last_cty_update()

            stats_txt = ft.Text(
                f"DXCC Entities\n"
                f"Active: {active}\n"
                f"Total: {total}\n"
                f"Prefixes: {prefixes}\n\n"
                f"CTY.DAT Last Update:\n{cty_last_update}",
                selectable=True,
            )

            def reload_dxcc(e):
                dxcc_prefixes.reload_dxcc_cache()
                a, t, p = get_dxcc_stats()
                cty_update = get_last_cty_update()
                stats_txt.value = (
                    f"DXCC Entities\n"
                    f"Active: {a}\n"
                    f"Total: {t}\n"
                    f"Prefixes: {p}\n\n"
                    f"CTY_DAT Last Update:\n{cty_update}"
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

            def update_cty(e):
                page.snack_bar = ft.SnackBar(
                    ft.Text("Downloading CTY.DAT..."),
                    open=True,
                )
                page.update()
        
                result = update_cty_data()
        
                if result['success']:
                    # Reload the cache to pick up new data
                    dxcc_prefixes.reload_dxcc_cache()
            
                    a, t, p = get_dxcc_stats()    # <-- ADD THIS LINE
                    cty_update = get_last_cty_update()
                    stats_txt.value = (
                        f"DXCC Entities\n"
                        f"Active: {a}\n"
                        f"Total: {t}\n"
                        f"Prefixes: {p}\n\n"
                        f"CTY.DAT Last Update:\n{cty_update}"
                    )
            
                    page.snack_bar = ft.SnackBar(
                        ft.Text(f"CTY.DAT updated! {result['entities']} entities, {result['prefixes']} prefixes"),
                        open=True,
                    )
                else:
                    page.snack_bar = ft.SnackBar(
                        ft.Text(f"CTY.DAT update failed: {result['error']}"),
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
                                ft.ElevatedButton(
                                    "Update CTY.DAT",
                                    icon=ft.Icons.DOWNLOAD,
                                    on_click=update_cty,
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
                stat_box("Worked", worked_txt, ft.Colors.BLUE_GREY_800),
                stat_box("Confirmed", confirmed_txt, ft.Colors.GREEN_800),
                stat_box("Unconfirmed", remaining_txt, ft.Colors.ORANGE_800),
            ],
            spacing=20,
        )
        
        def on_done(result=None):
            import_progress.visible = False

            if result:
                import_status.value = (
                    f"✓ Import complete: "
                    f"{result['added']} added, "
                    f"{result['skipped']} skipped, "
                    f"{result['total']} total"
                )
            else:
                import_status.value = "✓ Import complete"

            refresh_qso_table()
            refresh_dashboard()
            page.update()

        def refresh_qso_table():
            con = sqlite3.connect(DB_PATH)
            cur = con.cursor()

            # Build WHERE clause with QSL filter
            where_clause = "WHERE callsign=?"
            params = [user]
    
            # Add QSL status filter if not "All"
            if qsl_filter_dropdown.value != "All":
                where_clause += " AND qsl_status=?"
                params.append(qsl_filter_dropdown.value)
                
            # Add Band filter if not "All"
            if band_filter.value != "All":
                where_clause += " AND band=?"
                params.append(band_filter.value)
                
            # Add callsign search filter
            if callsign_search.value and callsign_search.value.strip():
                where_clause += " AND UPPER(call_worked) LIKE ?"
                params.append(f"%{callsign_search.value.strip().upper()}%")

            # Build ORDER BY clause based on sort state
            order_by = "qso_date DESC"  # Default
            if sort_column["name"] == "prefix":
                order_by = f"call_worked {'ASC' if sort_column['ascending'] else 'DESC'}"
    
            cur.execute(
                f"""
                SELECT call_worked, qso_date, qsl_status, band
                FROM qsos
                {where_clause}
                 ORDER BY {order_by}
                """,
                tuple(params),
             )

            rows = cur.fetchall()
            qso_table.rows.clear()
            page.update()

            # Sort in Python by prefix if needed (since prefix isn't in DB)
            data_rows = []
            for call, qso_date, qsl_status, band in rows:
                eid, country, active = dxcc_prefixes.entity_for_callsign(call)
                
                prefix = eid if eid else ""
                    
                lotw_date = get_lotw_last_upload(call)
        
                # Check if LoTW date is over 90 days old
                lotw_color = ft.Colors.WHITE
                if lotw_date:
                    try:
                        lotw_dt = datetime.fromisoformat(lotw_date)
                        days_ago = (datetime.now() - lotw_dt).days
                        if days_ago > 90:
                            lotw_color = ft.Colors.RED_300
                    except:
                        pass
        
                display_country = COUNTRY_ABBREVIATIONS.get(country, country) if country else "—"
                full_country = country or "Unknown"
        
                data_rows.append((prefix, display_country, full_country, call, qso_date, qsl_status, lotw_date, lotw_color, band))
    
            # Sort by prefix if that's selected
            if sort_column["name"] == "prefix":
                data_rows.sort(key=lambda x: x[0], reverse=not sort_column["ascending"])
                qso_table.sort_column_index = 0
                qso_table.sort_ascending = sort_column["ascending"]
            else:
                qso_table.sort_column_index = None
    
            # Build rows
            for prefix, display_country, full_country, call, qso_date, qsl_status, lotw_date, lotw_color, band in data_rows:
                qso_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(prefix)),
                            ft.DataCell(
                                ft.Text(
                                    display_country,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    width=150,
                                    tooltip=full_country,
                                )
                            ),
                            ft.DataCell(ft.Text(call)),
                            ft.DataCell(ft.Text(qso_date)),
                            ft.DataCell(ft.Text(qsl_status or "—")),
                            ft.DataCell(
                                 ft.Text(
                                    lotw_date or "—",
                                    color=lotw_color,
                                )
                            ),
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
            
            # Get the selected band filter
            selected_band = band_filter.value if band_filter.value != "All" else None
    
            # Pass the band filter to get_dxcc_dashboard
            worked, confirmed, total_active = get_dxcc_dashboard(
                user,
                None if track_all else bands,
                include_deleted,
            )
    
            # If band filter is active, filter the worked/confirmed sets
            if selected_band:
                # Filter worked entities by band
                worked_filtered = set()
                confirmed_filtered = set()
        
                con = sqlite3.connect(DB_PATH)
                cur = con.cursor()
        
                # Get entities for selected band
                cur.execute(
                   """
                   SELECT DISTINCT call_worked, qsl_status
                   FROM qsos
                   WHERE callsign=? AND band=?
                   """,
                   (user, selected_band),
                )
        
                for call, qsl_status in cur.fetchall():
                    eid, country, active = dxcc_prefixes.entity_for_callsign(call)
                    if eid:
                        worked_filtered.add(eid)
                        if qsl_status == "Confirmed":
                            confirmed_filtered.add(eid)
        
                con.close()
        
                worked = worked_filtered
                confirmed = confirmed_filtered

            worked_txt.value = str(len(worked))
            confirmed_txt.value = str(len(confirmed))
            remaining_txt.value = str(len(worked) - len(confirmed))
            
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

        # After import_web_btn definition, add:

        # QSL Status filter dropdown
        qsl_filter_dropdown = ft.Dropdown(
            label="Filter by QSL Status",
            options=[
                ft.dropdown.Option("All"),
                ft.dropdown.Option("Confirmed"),
                ft.dropdown.Option("Requested"),
                ft.dropdown.Option("Not Requested"),
            ],
            value="All",
            width=200,
            on_change=lambda e: refresh_qso_table(),
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
                    
                    import_progress,
                    import_status,
                    
                    ft.Divider(),
                    qsl_filter_dropdown,
                    callsign_search,

                    ft.Divider(),
                    qso_tabs,

                    # 👇 FOOTER
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

