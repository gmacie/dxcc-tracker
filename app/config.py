# app/config.py

import os

# Central database path for the application
DB_PATH = os.environ.get(
    "DXCC_DB_PATH",
    os.path.join(os.path.dirname(__file__), "dxcc.db"),
)
