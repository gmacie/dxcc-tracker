import threading
import uvicorn

from app.upload_api import api
from app.main import main
import flet as ft


def run_api():
    uvicorn.run(api, host="0.0.0.0", port=8551)


threading.Thread(target=run_api, daemon=True).start()

ft.app(target=main, view=ft.WEB_BROWSER, port=8550)
