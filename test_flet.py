import flet as ft

def main(page: ft.Page):
    page.title = "Flet Test"
    page.add(ft.Text("If you can see this, Flet is working!"))

ft.app(target=main)
