"""
Errores del módulo golf_course que la API traduce a su código HTTP en un solo sitio.

La respuesta es la que daba cada ruta con su `except X: raise HTTPException(código, str(e))`:
el código de aquí y {"detail": str(e)}. Lo registra la composition root
(`src/config/codigos_de_error.py`). Un error que en alguna ruta da otro código, como el
país que no existe (404 al editar, 400 al crear), se sigue traduciendo en esa ruta.
"""

from fastapi import status

from src.modules.golf_course.application.exceptions import (
    GolfCourseEditForbiddenError,
    GolfCourseMissingError,
    GolfCourseViewForbiddenError,
)

CODIGOS: dict[type[Exception], int] = {
    # 403: quien pide no puede hacerlo
    GolfCourseEditForbiddenError: status.HTTP_403_FORBIDDEN,
    GolfCourseViewForbiddenError: status.HTTP_403_FORBIDDEN,
    # 404: no existe
    GolfCourseMissingError: status.HTTP_404_NOT_FOUND,
}
