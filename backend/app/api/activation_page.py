from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
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