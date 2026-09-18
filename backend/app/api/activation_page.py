from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates


router = APIRouter(
    tags=["activation-page"],
)

templates = Jinja2Templates(
    directory=str(
        Path(__file__).resolve().parent.parent
        / "templates"
    )
)

STATIC_DIRECTORY = (
    Path(__file__).resolve().parent.parent
    / "static"
)


@router.get(
    "/activate/assets/device-activation.css",
    include_in_schema=False,
)
def get_device_activation_styles() -> FileResponse:
    return FileResponse(
        path=STATIC_DIRECTORY / "device_activation.css",
        media_type="text/css",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/activate/assets/device-activation.js",
    include_in_schema=False,
)
def get_device_activation_script() -> FileResponse:
    return FileResponse(
        path=STATIC_DIRECTORY / "device_activation.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/activate/{token}",
    response_class=HTMLResponse,
)
def activation_page(
    request: Request,
    token: str,
):
    return templates.TemplateResponse(
        request=request,
        name="activate.html",
        context={
            "token": token,
        },
    )
