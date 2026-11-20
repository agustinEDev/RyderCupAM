"""
Caracterización de los decoradores de persistencia de ids y de país.

Fija, para cada uno de los 38 que había el 20 nov 2026, qué guarda en la BD con
cada entrada (el id, un texto, None, un uuid.UUID, un valor raro) y qué
devuelve al leer. Se sacó de develop ANTES de unificarlos en una sola fábrica
(`tipos_de_id`): lo que cambia por decisión (Agustín, 20 nov 2026) se cambia
aquí a propósito y se dice en el commit; lo demás tiene que seguir igual.

  #   | decisión                                                   | casos
  ----|------------------------------------------------------------|---------------
  2a  | el id, un texto o un uuid.UUID se guardan; None, NULL;     | bind
      | cualquier otra cosa, TypeError                             |
  3   | al leer, siempre el id con su valor de siempre (UUID; el   | result
      | país, su texto)                                            |
"""

import importlib
import uuid

import pytest
import sqlalchemy

from src.shared.domain.value_objects.country_code import CountryCode

UN_UUID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

# (módulo, decorador, value object): todos los que había el 20 nov 2026
DECORADORES = [
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "CompetitionIdDecorator",
        "CompetitionId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "EnrollmentIdDecorator",
        "EnrollmentId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "InvitationIdDecorator",
        "InvitationId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "UserIdDecorator",
        "UserId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "CountryCodeDecorator",
        "CountryCode",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "HoleScoreIdDecorator",
        "HoleScoreId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "CompetitionGolfCourseIdDecorator",
        "CompetitionGolfCourseId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "GolfCourseIdDecorator",
        "GolfCourseId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "RoundIdDecorator",
        "RoundId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "DraftIdDecorator",
        "DraftId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "EnvelopeIdDecorator",
        "EnvelopeId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "MatchIdDecorator",
        "MatchId",
    ),
    (
        "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers",
        "TeamAssignmentIdDecorator",
        "TeamAssignmentId",
    ),
    (
        "src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper",
        "GolfCourseIdType",
        "GolfCourseId",
    ),
    (
        "src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper",
        "CountryCodeType",
        "CountryCode",
    ),
    (
        "src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper",
        "UserIdType",
        "UserId",
    ),
    (
        "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper",
        "QuickMatchIdType",
        "QuickMatchId",
    ),
    (
        "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper",
        "QuickMatchHoleScoreIdType",
        "QuickMatchHoleScoreId",
    ),
    (
        "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper",
        "ParticipantIdType",
        "ParticipantId",
    ),
    (
        "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper",
        "QuickMatchUserIdType",
        "UserId",
    ),
    (
        "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper",
        "QuickMatchGolfCourseIdType",
        "GolfCourseId",
    ),
    (
        "src.modules.social.infrastructure.persistence.mappers.friendship_mapper",
        "FriendshipIdType",
        "FriendshipId",
    ),
    (
        "src.modules.social.infrastructure.persistence.mappers.friendship_mapper",
        "SocialUserIdType",
        "UserId",
    ),
    (
        "src.modules.social.infrastructure.persistence.mappers.profile_photo_mapper",
        "ProfilePhotoIdType",
        "ProfilePhotoId",
    ),
    ("src.modules.user.infrastructure.persistence.sqlalchemy.mappers", "UserIdDecorator", "UserId"),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.mappers",
        "ActiveAvatarUploadIdDecorator",
        "UserAvatarUploadId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.password_history_mapper",
        "PasswordHistoryIdDecorator",
        "PasswordHistoryId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.password_history_mapper",
        "UserIdDecorator",
        "UserId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_mapper",
        "RefreshTokenIdDecorator",
        "RefreshTokenId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_mapper",
        "UserDeviceIdDecorator",
        "UserDeviceId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.terms_acceptance_mapper",
        "TermsAcceptanceIdDecorator",
        "TermsAcceptanceId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.user_avatar_upload_mapper",
        "UserAvatarUploadIdDecorator",
        "UserAvatarUploadId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.user_avatar_upload_mapper",
        "_AvatarUploadUserIdDecorator",
        "UserId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.user_device_mapper",
        "UserDeviceIdDecorator",
        "UserDeviceId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.user_device_mapper",
        "UserIdDecorator",
        "UserId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.user_oauth_account_mapper",
        "OAuthAccountIdDecorator",
        "OAuthAccountId",
    ),
    (
        "src.modules.user.infrastructure.persistence.sqlalchemy.user_oauth_account_mapper",
        "UserIdDecorator",
        "UserId",
    ),
    (
        "src.shared.infrastructure.persistence.sqlalchemy.country_mappers",
        "CountryCodeDecorator",
        "CountryCode",
    ),
]


def _describe(valor):
    if valor is None:
        return None
    if isinstance(valor, uuid.UUID):
        return f"UUID:{valor}"
    if isinstance(valor, str):
        return f"str:{valor}"
    interno = getattr(valor, "value", valor)
    return f"{type(valor).__name__}({type(interno).__name__}:{interno})"


def _prueba(funcion, entrada):
    try:
        return _describe(funcion(entrada, None))
    except Exception as e:  # se caracteriza también el fallo
        return f"!{type(e).__name__}"


def _vo_de_ejemplo(clase):
    if clase.__name__ == "CountryCode":
        return clase("ES")
    try:
        return clase(UN_UUID)
    except TypeError:
        return clase(value=UN_UUID)


def sondea(modulo, nombre, vo):
    """Lo que hace hoy el decorador con cada entrada."""
    mod = importlib.import_module(modulo)
    decorador = getattr(mod, nombre)()
    # El país se busca en su dominio: un mapper que ya no lo nombra no lo importa
    clase = CountryCode if vo == "CountryCode" else getattr(mod, vo)
    es_pais = vo == "CountryCode"
    texto = "ES" if es_pais else str(UN_UUID)
    en_bd = UN_UUID if isinstance(decorador.impl, sqlalchemy.types.Uuid) and not es_pais else texto
    return {
        "bind_vo": _prueba(decorador.process_bind_param, _vo_de_ejemplo(clase)),
        "bind_texto": _prueba(decorador.process_bind_param, texto),
        "bind_none": _prueba(decorador.process_bind_param, None),
        "bind_uuid": _prueba(decorador.process_bind_param, UN_UUID),
        "bind_raro": _prueba(decorador.process_bind_param, 123),
        "result_none": _prueba(decorador.process_result_value, None),
        "result_valor": _prueba(decorador.process_result_value, en_bd),
    }


ESPERADO = {
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.CompetitionIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "CompetitionId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.EnrollmentIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "EnrollmentId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.InvitationIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "InvitationId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.UserIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.CountryCodeDecorator": {
        "bind_vo": "str:ES",
        "bind_texto": "str:ES",
        "bind_none": None,
        "bind_uuid": "!TypeError",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "CountryCode(str:ES)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.HoleScoreIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "HoleScoreId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.CompetitionGolfCourseIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "CompetitionGolfCourseId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.GolfCourseIdDecorator": {
        "bind_vo": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "GolfCourseId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.RoundIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "RoundId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.DraftIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "DraftId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.EnvelopeIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "EnvelopeId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.MatchIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "MatchId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.competition.infrastructure.persistence.sqlalchemy.mappers.TeamAssignmentIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "TeamAssignmentId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper.GolfCourseIdType": {
        "bind_vo": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "GolfCourseId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper.CountryCodeType": {
        "bind_vo": "str:ES",
        "bind_texto": "str:ES",
        "bind_none": None,
        "bind_uuid": "!TypeError",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "CountryCode(str:ES)",
    },
    "src.modules.golf_course.infrastructure.persistence.mappers.golf_course_mapper.UserIdType": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper.QuickMatchIdType": {
        "bind_vo": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "QuickMatchId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper.QuickMatchHoleScoreIdType": {
        "bind_vo": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "QuickMatchHoleScoreId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper.ParticipantIdType": {
        "bind_vo": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "ParticipantId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper.QuickMatchUserIdType": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.quick_match.infrastructure.persistence.mappers.quick_match_mapper.QuickMatchGolfCourseIdType": {
        "bind_vo": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "GolfCourseId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.social.infrastructure.persistence.mappers.friendship_mapper.FriendshipIdType": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "FriendshipId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.social.infrastructure.persistence.mappers.friendship_mapper.SocialUserIdType": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.social.infrastructure.persistence.mappers.profile_photo_mapper.ProfilePhotoIdType": {
        "bind_vo": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "UUID:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "ProfilePhotoId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.mappers.UserIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.mappers.ActiveAvatarUploadIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserAvatarUploadId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.password_history_mapper.PasswordHistoryIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "PasswordHistoryId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.password_history_mapper.UserIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_mapper.RefreshTokenIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "RefreshTokenId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.refresh_token_mapper.UserDeviceIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserDeviceId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.terms_acceptance_mapper.TermsAcceptanceIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "TermsAcceptanceId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.user_avatar_upload_mapper.UserAvatarUploadIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserAvatarUploadId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.user_avatar_upload_mapper._AvatarUploadUserIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.user_device_mapper.UserDeviceIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserDeviceId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.user_device_mapper.UserIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.user_oauth_account_mapper.OAuthAccountIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "OAuthAccountId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.modules.user.infrastructure.persistence.sqlalchemy.user_oauth_account_mapper.UserIdDecorator": {
        "bind_vo": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_texto": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_none": None,
        "bind_uuid": "str:550e8400-e29b-41d4-a716-446655440000",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "UserId(UUID:550e8400-e29b-41d4-a716-446655440000)",
    },
    "src.shared.infrastructure.persistence.sqlalchemy.country_mappers.CountryCodeDecorator": {
        "bind_vo": "str:ES",
        "bind_texto": "str:ES",
        "bind_none": None,
        "bind_uuid": "!TypeError",
        "bind_raro": "!TypeError",
        "result_none": None,
        "result_valor": "CountryCode(str:ES)",
    },
}


@pytest.mark.parametrize(("modulo", "nombre", "vo"), DECORADORES)
def test_el_decorador_hace_lo_fijado(modulo, nombre, vo):
    assert sondea(modulo, nombre, vo) == ESPERADO[f"{modulo}.{nombre}"]


def test_estan_todos():
    assert len(DECORADORES) == 38
    assert set(ESPERADO) == {f"{m}.{n}" for m, n, _ in DECORADORES}
