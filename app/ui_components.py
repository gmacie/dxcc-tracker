import flet as ft


def build_login_controls(on_login, on_register):
    callsign = ft.TextField(label="Callsign", width=250)
    password = ft.TextField(
        label="Password",
        password=True,
        can_reveal_password=True,
        width=250,
    )

    def login_click(e):
        on_login(callsign.value, password.value)

    def register_click(e):
        on_register(callsign.value, password.value)

    col = ft.Column(
        [
            ft.Text("DXCC Tracker Login", size=24, weight="bold"),
            callsign,
            password,
            ft.Row(
                [
                    ft.ElevatedButton("Login", on_click=login_click),
                    ft.OutlinedButton("Register", on_click=register_click),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )

    return col, (callsign, password)
