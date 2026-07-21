"""Paste endpoints.

Reads by slug are public (unlisted-link model); create/edit/delete require auth and are
owner-checked. Persistence lives in :mod:`pastry_api.repository`.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pastry_shared.models import Paste, PasteCreate, PasteUpdate

from pastry_api import repository
from pastry_api.deps import CurrentUserId

router = APIRouter(tags=["pastes"])


@router.post("/pastes", status_code=status.HTTP_201_CREATED)
def create_paste(body: PasteCreate, user_id: CurrentUserId) -> Paste:
    """Create a paste owned by the caller; returns it (including its public slug)."""
    try:
        return repository.create_paste(user_id, body.content, body.expires_in)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc  # Unprocessable Content


@router.get("/pastes")
def list_pastes(user_id: CurrentUserId) -> list[Paste]:
    """List the caller's own pastes, newest first (KSUID range query on their partition)."""
    return repository.list_pastes(user_id)


@router.get("/p/{slug}")
def get_paste(slug: str) -> Paste:
    """Public read by slug. No auth. 404 if missing/expired/deleted."""
    try:
        return repository.get_paste(slug)
    except repository.PasteNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paste not found") from exc


@router.get("/p/{slug}/raw", response_class=Response)
def get_paste_raw(slug: str) -> Response:
    """Public raw read for the CLI: paste content as text/plain, pipeable."""
    try:
        paste = repository.get_paste(slug)
    except repository.PasteNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paste not found") from exc
    return Response(content=paste.content, media_type="text/plain; charset=utf-8")


@router.patch("/p/{slug}")
def edit_paste(slug: str, body: PasteUpdate, user_id: CurrentUserId) -> Paste:
    """Edit a paste's content. Owner only (403 otherwise)."""
    try:
        return repository.update_paste(user_id, slug, body.content)
    except repository.PasteNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paste not found") from exc
    except repository.PasteForbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your paste") from exc


@router.delete("/p/{slug}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paste(slug: str, user_id: CurrentUserId) -> None:
    """Delete a paste. Owner only (403 otherwise)."""
    try:
        repository.delete_paste(user_id, slug)
    except repository.PasteNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paste not found") from exc
    except repository.PasteForbidden as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your paste") from exc
