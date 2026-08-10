"""
Profile Photo Routes - API REST Layer (Infrastructure).

Galeria de fotos del perfil (BE #177).
"""

import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)

from src.config.dependencies import (
    get_current_user,
    get_delete_profile_photo_use_case,
    get_profile_gallery_use_case,
    get_profile_photo_image_use_case,
    get_upload_profile_photo_use_case,
)
from src.config.rate_limit import limiter
from src.modules.social.application.dto.profile_photo_dto import (
    ProfileGalleryResponseDTO,
    ProfilePhotoDTO,
)
from src.modules.social.application.exceptions import (
    ActivityNotVisibleError,
    PhotoNotFoundError,
    ProfileGalleryFullError,
    ProfileNotVisibleError,
)
from src.modules.social.application.use_cases.delete_profile_photo_use_case import (
    DeleteProfilePhotoUseCase,
)
from src.modules.social.application.use_cases.get_profile_gallery_use_case import (
    GetProfileGalleryUseCase,
)
from src.modules.social.application.use_cases.get_profile_photo_image_use_case import (
    GetProfilePhotoImageUseCase,
)
from src.modules.social.application.use_cases.upload_profile_photo_use_case import (
    UploadProfilePhotoUseCase,
)
from src.modules.user.application.dto.user_dto import UserResponseDTO
from src.modules.user.domain.errors.user_errors import (
    AvatarUploadTooLargeError,
    InvalidAvatarImageError,
    UserNotFoundError,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# Un año, que es el maximo que recomienda la norma. Se puede ser tan agresivo
# porque la imagen es inmutable: no se edita una foto, se borra y se sube otra
# con otro id, asi que estos bytes bajo este id no van a cambiar nunca.
# `private` porque las fotos son solo para amigos: una cache compartida no debe
# quedarselas y servirselas a otro.
PHOTO_CACHE_CONTROL = "private, max-age=31536000, immutable"


@router.post(
    "/users/me/photos",
    response_model=ProfilePhotoDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a photo to my gallery",
    description=(
        "Adds a photo to your profile gallery. Resized to 1080px on its longest side and "
        "recompressed, keeping its original proportions — no square crop. Rejected with "
        "409 when the gallery is full rather than silently dropping your oldest photo."
    ),
)
@limiter.limit("30/hour")
async def upload_my_photo(
    request: Request,  # noqa: ARG001 - Required by SlowAPI for rate limiting
    file: UploadFile = File(..., description="Image file (JPEG, PNG or WEBP)"),
    caption: str | None = Form(None, max_length=280),
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: UploadProfilePhotoUseCase = Depends(get_upload_profile_photo_use_case),
):
    raw = await file.read()
    try:
        return await use_case.execute(str(current_user.id), raw, caption=caption)
    except ProfileGalleryFullError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except AvatarUploadTooLargeError as e:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e)
        ) from e
    except InvalidAvatarImageError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except UserNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get(
    "/users/{user_id}/photos",
    response_model=ProfileGalleryResponseDTO,
    summary="Get a player's photo gallery",
    description=(
        "The photos a friend has on their profile, newest first. Friends only: 403 "
        "otherwise. Returns where to fetch each image, not the images themselves — ten "
        "photos are nearly four megabytes, and the browser fetches and caches them "
        "separately."
    ),
)
async def get_player_gallery(
    user_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetProfileGalleryUseCase = Depends(get_profile_gallery_use_case),
):
    try:
        return await use_case.execute(str(current_user.id), str(user_id))
    except ProfileNotVisibleError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found"
        ) from e
    except ActivityNotVisibleError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e


@router.get(
    "/users/{user_id}/photos/{photo_id}/image",
    summary="Get a photo's image",
    description=(
        "The image bytes. Cached for a year with an ETag, because a photo never changes: "
        "editing one means deleting it and uploading another with a different id. Sends "
        "304 when the client already has it."
    ),
    responses={
        200: {"content": {"image/jpeg": {}}, "description": "The image"},
        304: {"description": "The client's cached copy is still good"},
    },
)
async def get_photo_image(
    user_id: UUID,
    photo_id: UUID,
    request: Request,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: GetProfilePhotoImageUseCase = Depends(get_profile_photo_image_use_case),
):
    try:
        imagen = await use_case.execute(str(current_user.id), str(user_id), str(photo_id))
    except ActivityNotVisibleError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except PhotoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    # Si el cliente ya la tiene, no se reenvian los bytes. Es lo que evita que
    # abrir un perfil diez veces mueva setenta megas
    if request.headers.get("if-none-match") == imagen.etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"ETag": imagen.etag, "Cache-Control": PHOTO_CACHE_CONTROL},
        )

    return Response(
        content=imagen.data,
        media_type=imagen.content_type,
        headers={"ETag": imagen.etag, "Cache-Control": PHOTO_CACHE_CONTROL},
    )


@router.delete(
    "/users/me/photos/{photo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of my photos",
    description=(
        "Permanently deletes a photo from your gallery. Someone else's photo gives the "
        "same 404 as one that does not exist."
    ),
)
async def delete_my_photo(
    photo_id: UUID,
    current_user: UserResponseDTO = Depends(get_current_user),
    use_case: DeleteProfilePhotoUseCase = Depends(get_delete_profile_photo_use_case),
):
    try:
        await use_case.execute(str(current_user.id), str(photo_id))
    except PhotoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
