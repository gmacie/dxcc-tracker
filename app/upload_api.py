from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import tempfile
import os

from app.adif_import import import_adif

api = FastAPI()

# Mount static files from root /static directory
api.mount("/static", StaticFiles(directory="static"), name="static")


@api.post("/upload-adif")
async def upload_adif(
    file: UploadFile = File(...),
    user: str = Form(...)
):
    suffix = os.path.splitext(file.filename)[1] or ".adi"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # ✅ Run importer and CAPTURE results
    result = import_adif(tmp_path, user)

    return JSONResponse(
        {
            "status": "ok",
            "user": user,
            "added": result["added"],
            "skipped": result["skipped"],
            "total": result["total"],
        }
    )