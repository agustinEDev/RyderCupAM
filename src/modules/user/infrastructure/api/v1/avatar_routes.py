"""
Avatar Routes - API REST Layer (Infrastructure).

Endpoints FastAPI para gestión del avatar de usuario: presets fijos (fotos de
golf empaquetadas con el backend) y fotos subidas por el propio usuario
(guardadas en BD, historial acotado a 5, redimensionadas/comprimidas con Pillow).

Diseño: cualquier avatar (propio o de otro usuario, preset o subido) se sirve
por una única ruta `GET /users/{user_id}/avatar`, para que el frontend nunca
necesite saber el origen — solo conoce el user_id.
"""

import hashlib
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status

from src.config.dependencies import (
    get_activate_uploaded_avatar_use_case,
    get_avatar_image_use_case,
    get_avatar_preset_image_use_case,
    get_current_user,
    get_list_avatar_presets_use_case,
    get_list_my_avatar_uploads_use_case,
    get_my_avatar_upload_image_use_case,
    get_remove_avatar_use_case,
    get_set_avatar_preset_use_case,
    get_upload_avatar_use_case,
)
from src.config.rate_limit import limiter
from src.modules.user.application.dto.avatar_dto import SetAvatarPresetRequestDTO
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.application.use_cases.activate_uploaded_avatar_use_case import (
    ActivateUploadedAvatarUseCase,
)
from src.modules.user.application.use_cases.get_avatar_image_use_case import (
    GetAvatarImageUseCase,
)
from src.modules.user.application.use_cases.get_avatar_preset_image_use_case import (
    GetAvatarPresetImageUseCase,
)
from src.modules.user.application.use_cases.get_my_avatar_upload_image_use_case import (
    GetMyAvatarUploadImageUseCase,
)
from src.modules.user.application.use_cases.list_avatar_presets_use_case import (
    ListAvatarPresetsUseCase,
)
from src.modules.user.application.use_cases.list_my_avatar_uploads_use_case import (
    ListMyAvatarUploadsUseCase,
)
from src.modules.user.application.use_cases.remove_avatar_use_case import RemoveAvatarUseCase
from src.modules.user.application.use_cases.set_avatar_preset_use_case import (
    SetAvatarPresetUseCase,
)
from src.modules.user.application.use_cases.upload_avatar_use_case import (
    MAX_UPLOAD_BYTES,
    UploadAvatarUseCase,
)
from src.modules.user.domain.errors.user_errors import (
    AvatarNotFoundError,
    AvatarUploadNotFoundError,
    AvatarUploadTooLargeError,
    InvalidAvatarImageError,
    InvalidAvatarPresetError,
    UserNotFoundError,
)

router = APIRouter()

_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024  # 1 MB


async def _read_upload_within_limit(file: UploadFile, max_bytes: int) -> bytes:
    """
    Lee un UploadFile por trozos, cortando en cuanto se supera `max_bytes`.

    A diferencia de `await file.read()` (que carga el cuerpo entero en memoria
    antes de que nadie pueda comprobar su tamaño), esto evita que un archivo
    absurdamente grande llegue a bufferizarse por completo — el rechazo por
    tamaño ocurre tan pronto como se cruza el límite, no después.
    """
    buffer = bytearray()
    while True:
        chunk = await file.read(_UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > max_bytes:
            raise AvatarUploadTooLargeError(
                f"El archivo supera el tamaño máximo permitido "
                f"({max_bytes // (1024 * 1024)}MB)"
            )
    return bytes(buffer)


# ======================================================================================
# PRESETS (catálogo fijo, sin autenticación: son assets públicos empaquetados)
# ======================================================================================


@router.get(
    "/avatar-presets",
    summary="List avatar presets",
    description="Lists the 10 available preset avatars (golf photos).",
)
async def list_avatar_presets(
    use_case: ListAvatarPresetsUseCase = Depends(get_list_avatar_presets_use_case),
):
    return await use_case.execute()


@router.get(
    "/avatar-presets/{preset_id}/image",
    summary="Get avatar preset image",
    description="Returns the raw image bytes of a preset avatar.",
)
async def get_avatar_preset_image(
    preset_id: int,
    use_case: GetAvatarPresetImageUseCase = Depends(get_avatar_preset_image_use_case),
):
    try:
        image_bytes, content_type = await use_case.execute(preset_id)
        # Los presets son assets estáticos empaquetados con el backend: nunca
        # cambian para un preset_id dado, así que se pueden cachear "para
        # siempre" (un cambio real de la foto pasaría por un despliegue nuevo,
        # lo que ya invalida cualquier caché de CDN/navegador vía nuevo deploy).
        etag = hashlib.sha256(image_bytes).hexdigest()
        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "ETag": f'"{etag}"',
            },
        )
    except InvalidAvatarPresetError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ======================================================================================
# AVATAR ACTIVO DE UN USUARIO (propio o ajeno) — una única ruta para toda la app
# ======================================================================================


@router.get(
    "/users/{user_id}/avatar",
    summary="Get user's active avatar image",
    description="Returns the raw image bytes of a user's active avatar (preset or upload).",
)
async def get_user_avatar_image(
    user_id: UUID,
    _current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetAvatarImageUseCase = Depends(get_avatar_image_use_case),
):
    try:
        image_bytes, content_type = await use_case.execute(str(user_id))
        return Response(content=image_bytes, media_type=content_type)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except AvatarNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# ======================================================================================
# GESTIÓN DEL PROPIO AVATAR (usuario autenticado)
# ======================================================================================


@router.post(
    "/users/me/avatar/preset",
    response_model=UserResponseDTO,
    summary="Set a preset as active avatar",
    description="Activates one of the 10 preset avatars for the authenticated user.",
)
async def set_avatar_preset(
    body: SetAvatarPresetRequestDTO,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: SetAvatarPresetUseCase = Depends(get_set_avatar_preset_use_case),
):
    try:
        return await use_case.execute(str(current_user.id), body)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InvalidAvatarPresetError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/users/me/avatar/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new avatar photo",
    description=(
        "Uploads a new photo to use as avatar (max 10MB, JPEG/PNG/WEBP). "
        "The server resizes/compresses it to 512x512 JPEG before storing. "
        "Rate limited to 10 per hour. Keeps a history of up to 5 uploads per user "
        "(oldest is pruned automatically)."
    ),
)
@limiter.limit("10/hour")
async def upload_avatar(
    request: Request,  # noqa: ARG001 - Required by SlowAPI for rate limiting
    current_user: UserResponseDTO = Depends(get_current_user),
    file: UploadFile = File(...),
    use_case: UploadAvatarUseCase = Depends(get_upload_avatar_use_case),
):
    try:
        raw_bytes = await _read_upload_within_limit(file, MAX_UPLOAD_BYTES)
        return await use_case.execute(str(current_user.id), raw_bytes)
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except AvatarUploadTooLargeError as e:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(e)) from e
    except InvalidAvatarImageError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/users/me/avatar/uploads",
    summary="List my avatar upload history",
    description="Lists the authenticated user's uploaded avatar photos (up to 5, most recent first).",
)
async def list_my_avatar_uploads(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ListMyAvatarUploadsUseCase = Depends(get_list_my_avatar_uploads_use_case),
):
    try:
        return await use_case.execute(str(current_user.id))
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/users/me/avatar/uploads/{upload_id}/image",
    summary="Get one of my uploaded avatar photos",
    description="Returns the raw image bytes of one of the authenticated user's uploaded photos.",
)
async def get_my_avatar_upload_image(
    upload_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetMyAvatarUploadImageUseCase = Depends(get_my_avatar_upload_image_use_case),
):
    try:
        image_bytes, content_type = await use_case.execute(str(current_user.id), str(upload_id))
        return Response(content=image_bytes, media_type=content_type)
    except AvatarUploadNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post(
    "/users/me/avatar/uploads/{upload_id}/activate",
    response_model=UserResponseDTO,
    summary="Reactivate a previously uploaded photo",
    description="Sets one of the authenticated user's already-uploaded photos as active avatar, without re-uploading.",
)
async def activate_uploaded_avatar(
    upload_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: ActivateUploadedAvatarUseCase = Depends(get_activate_uploaded_avatar_use_case),
):
    try:
        return await use_case.execute(str(current_user.id), str(upload_id))
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except AvatarUploadNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.delete(
    "/users/me/avatar",
    response_model=UserResponseDTO,
    summary="Remove active avatar",
    description="Clears the authenticated user's active avatar (falls back to default placeholder). Does not delete upload history.",
)
async def remove_avatar(
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: RemoveAvatarUseCase = Depends(get_remove_avatar_use_case),
):
    try:
        return await use_case.execute(str(current_user.id))
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
