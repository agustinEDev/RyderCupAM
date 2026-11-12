"""
Los errores de dominio se traducen a su código HTTP en un solo sitio (fase 5).

Antes, cada ruta repetía `except X as e: raise HTTPException(código, str(e))`: 292
cláusulas para 123 excepciones. Ahora cada módulo declara su mapa y la app los registra.
La respuesta no cambia: mismo código y el mismo `{"detail": str(e)}`.
"""

import ast
import importlib
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from main import app
from src.config.codigos_de_error import todos_los_codigos
from src.shared.infrastructure.http.codigos_de_error import registra_los_codigos

RAIZ = Path(__file__).resolve().parents[5]

# El código que daba cada excepción en develop (12 nov 2026, tras la #809): en sus rutas o,
# las dos de los torneos sin equipos (#251), en exception_handlers.py de competición
CODIGOS_DE_DEVELOP = {
    "src.modules.competition.domain.entities.competition.TournamentTypeError": 400,
    "src.modules.competition.domain.value_objects.stroke_play_setup.StrokePlaySettingsError": 400,
    "src.modules.competition.application.exceptions.AgendaNotEditableError": 400,
    "src.modules.competition.application.exceptions.CompetitionAlreadyExistsError": 409,
    "src.modules.competition.application.exceptions.CompetitionFullError": 400,
    "src.modules.competition.application.exceptions.CompetitionNotClosedError": 400,
    "src.modules.competition.application.exceptions.CompetitionNotDraftError": 400,
    "src.modules.competition.application.exceptions.CompetitionNotFoundError": 404,
    "src.modules.competition.application.exceptions.DateOutOfRangeError": 400,
    "src.modules.competition.application.exceptions.EnrollmentNotFoundError": 404,
    "src.modules.competition.application.exceptions.FranjaInvalidaError": 400,
    "src.modules.competition.application.exceptions.GolfCourseHasRoundsError": 400,
    "src.modules.competition.application.exceptions.HandicapEditNotAllowedError": 400,
    "src.modules.competition.application.exceptions.InvalidHoleNumberError": 400,
    "src.modules.competition.application.exceptions.InvalidTeeColorError": 400,
    "src.modules.competition.application.exceptions.InvitationNotFoundError": 404,
    "src.modules.competition.application.exceptions.InviteeNotFoundError": 404,
    "src.modules.competition.application.exceptions.MatchNotFoundError": 404,
    "src.modules.competition.application.exceptions.MatchNotScoringError": 409,
    "src.modules.competition.application.exceptions.NotCompetitionCreatorError": 403,
    "src.modules.competition.application.exceptions.NotCompetitionParticipantError": 403,
    "src.modules.competition.application.exceptions.NotCreatorError": 403,
    "src.modules.competition.application.exceptions.NotInviteeError": 403,
    "src.modules.competition.application.exceptions.NotMatchPlayerError": 403,
    "src.modules.competition.application.exceptions.PartidaNotFoundError": 404,
    "src.modules.competition.application.exceptions.PlazaEnFranjaError": 400,
    "src.modules.competition.application.exceptions.RoundNotFoundError": 404,
    "src.modules.competition.application.exceptions.RoundNotModifiableError": 400,
    "src.modules.competition.application.exceptions.ScheduleAlreadyInPlayError": 400,
    "src.modules.competition.application.exceptions.ScorecardAlreadySubmittedError": 400,
    "src.modules.competition.application.exceptions.ScorecardNotReadyError": 400,
    "src.modules.competition.application.services.envelope_pairings.EnvelopesDecideThePairingsError": 400,
    "src.modules.competition.application.services.envelope_pairings.EnvelopesNotRevealedError": 400,
    "src.modules.competition.application.services.genero_obligatorio.PerfilIncompletoError": 400,
    "src.modules.competition.application.services.jugadores_del_partido.PlayerNotEnrolledError": 400,
    "src.modules.competition.application.services.match_players_builder.TeeColorNotFoundError": 400,
    "src.modules.competition.application.use_cases.add_golf_course_use_case.GolfCourseNotFoundError": 404,
    "src.modules.competition.application.use_cases.cancel_enrollment_use_case.NotOwnerError": 403,
    "src.modules.competition.application.use_cases.configure_schedule_use_case.NoGolfCoursesError": 400,
    "src.modules.competition.application.use_cases.create_round_use_case.DuplicateSessionError": 400,
    "src.modules.competition.application.use_cases.create_round_use_case.GolfCourseNotInCompetitionError": 400,
    "src.modules.competition.application.use_cases.declare_walkover_use_case.CompetitionNotInProgressError": 400,
    "src.modules.competition.application.use_cases.declare_walkover_use_case.InvalidWalkoverError": 400,
    "src.modules.competition.application.use_cases.direct_enroll_player_use_case.AlreadyEnrolledError": 409,
    "src.modules.competition.application.use_cases.direct_enroll_player_use_case.CompetitionNotActiveError": 400,
    "src.modules.competition.application.use_cases.generate_matches_use_case.RoundNotPendingMatchesError": 400,
    "src.modules.competition.application.use_cases.name_vice_captain_use_case.NotCaptainOrCreatorError": 403,
    "src.modules.competition.application.use_cases.reassign_match_players_use_case.MatchNotScheduledError": 400,
    "src.modules.competition.application.use_cases.reassign_match_players_use_case.NoTeamAssignmentError": 400,
    "src.modules.competition.application.use_cases.reassign_match_players_use_case.PlayerNotInTeamError": 400,
    "src.modules.competition.application.use_cases.reassign_match_players_use_case.WrongNumberOfPlayersError": 400,
    "src.modules.competition.application.use_cases.remove_golf_course_use_case.GolfCourseNotAssignedError": 400,
    "src.modules.competition.application.use_cases.reorder_golf_courses_use_case.InvalidReorderError": 400,
    "src.modules.competition.application.use_cases.request_enrollment_use_case.AlreadyEnrolledError": 409,
    "src.modules.competition.application.use_cases.request_enrollment_use_case.CompetitionIsPrivateError": 403,
    "src.modules.competition.application.use_cases.request_enrollment_use_case.CompetitionNotActiveError": 400,
    "src.modules.competition.application.use_cases.request_enrollment_use_case.EnrollmentClosedError": 400,
    "src.modules.competition.application.use_cases.request_enrollment_use_case.TooManyEnrollmentsError": 400,
    "src.modules.competition.application.use_cases.reset_envelopes_use_case.NothingToResetError": 400,
    "src.modules.competition.application.use_cases.reset_envelopes_use_case.SessionAlreadyPlayedError": 400,
    "src.modules.competition.application.use_cases.reveal_envelopes_use_case.EarlyRevealNeedsBothCaptainsError": 409,
    "src.modules.competition.application.use_cases.set_name_preference_use_case.NotOwnerError": 403,
    "src.modules.competition.application.use_cases.submit_envelope_use_case.NotATeamCaptainError": 403,
    "src.modules.competition.application.use_cases.update_match_status_use_case.CompetitionNotInProgressError": 400,
    "src.modules.competition.application.use_cases.update_match_status_use_case.InvalidActionError": 400,
    "src.modules.competition.application.use_cases.update_round_use_case.DuplicateSessionError": 400,
    "src.modules.competition.application.use_cases.update_round_use_case.GolfCourseNotInCompetitionError": 400,
    "src.modules.competition.application.use_cases.withdraw_enrollment_use_case.NotOwnerError": 403,
    "src.modules.competition.domain.entities.draft.NotYourTurnError": 409,
    "src.modules.competition.domain.entities.enrollment.EnrollmentStateError": 400,
    "src.modules.competition.domain.exceptions.competition_violations.AlreadyEnrolledInvitationViolation": 409,
    "src.modules.competition.domain.exceptions.competition_violations.CompetitionFullViolation": 422,
    "src.modules.competition.domain.exceptions.competition_violations.DuplicateInvitationViolation": 409,
    "src.modules.competition.domain.exceptions.competition_violations.InvalidInvitationStatusViolation": 409,
    "src.modules.competition.domain.exceptions.competition_violations.InvitationCompetitionStatusViolation": 422,
    "src.modules.competition.domain.exceptions.competition_violations.InvitationExpiredViolation": 409,
    "src.modules.competition.domain.exceptions.competition_violations.SelfInvitationViolation": 400,
    "src.modules.competition.domain.services.location_builder.InvalidCountryError": 400,
    "src.modules.competition.domain.value_objects.location.InvalidLocationError": 400,
    "src.modules.quick_match.application.exceptions.FriendUserNotFoundError": 404,
    "src.modules.quick_match.application.exceptions.GolfCourseNotFoundError": 404,
    "src.modules.quick_match.application.exceptions.InvalidParticipantError": 422,
    "src.modules.quick_match.application.exceptions.InvalidTeeSelectionError": 422,
    "src.modules.quick_match.application.exceptions.NotAScorerError": 403,
    "src.modules.quick_match.application.exceptions.NotAuthorizedToRemoveError": 403,
    "src.modules.quick_match.application.exceptions.NotFriendsError": 403,
    "src.modules.quick_match.application.exceptions.NotQuickMatchCreatorError": 403,
    "src.modules.quick_match.application.exceptions.NotQuickMatchParticipantError": 403,
    "src.modules.quick_match.application.exceptions.QuickMatchIdTakenError": 409,
    "src.modules.quick_match.application.exceptions.QuickMatchNotFoundError": 404,
    "src.modules.quick_match.application.exceptions.QuickMatchNotSharedError": 403,
    "src.modules.quick_match.application.exceptions.TargetParticipantNotFoundError": 404,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.CreatorCannotBeRemovedViolation": 400,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.DuplicateParticipantViolation": 409,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.IncompleteRosterViolation": 422,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.InvalidAllowanceViolation": 422,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.InvalidHoleScoreViolation": 400,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.InvalidQuickMatchStatusViolation": 409,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.InvalidScorerConfigurationViolation": 422,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.InvalidTeamAssignmentViolation": 422,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.NotAssignedScorerViolation": 403,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.NotQuickMatchParticipantViolation": 404,
    "src.modules.quick_match.domain.exceptions.quick_match_violations.QuickMatchFullViolation": 422,
    "src.modules.social.application.exceptions.ActivityNotVisibleError": 403,
    "src.modules.social.application.exceptions.AddresseeNotFoundError": 404,
    "src.modules.social.application.exceptions.FriendshipNotFoundError": 404,
    "src.modules.social.application.exceptions.GamesTogetherNotVisibleError": 403,
    "src.modules.social.application.exceptions.NotAddresseeError": 403,
    "src.modules.social.application.exceptions.NotFriendshipParticipantError": 403,
    "src.modules.social.application.exceptions.PhotoNotFoundError": 404,
    "src.modules.social.application.exceptions.ProfileGalleryFullError": 409,
    "src.modules.social.domain.exceptions.social_violations.BlockedUserViolation": 403,
    "src.modules.social.domain.exceptions.social_violations.DuplicateFriendRequestViolation": 409,
    "src.modules.social.domain.exceptions.social_violations.InvalidFriendshipStatusViolation": 409,
    "src.modules.social.domain.exceptions.social_violations.SelfFriendRequestViolation": 400,
    "src.modules.user.domain.errors.handicap_errors.HandicapNotFoundError": 404,
    "src.modules.user.domain.errors.user_errors.AliasAlreadyTakenError": 409,
    "src.modules.user.domain.errors.user_errors.AvatarUploadNotFoundError": 404,
    "src.modules.user.domain.errors.user_errors.AvatarUploadTooLargeError": 413,
    "src.modules.user.domain.errors.user_errors.InvalidAvatarImageError": 400,
    "src.modules.user.domain.errors.user_errors.TermsAcceptanceRequiredError": 422,
    "src.modules.user.domain.errors.user_errors.UserNotFoundError": 404,
    "src.modules.user.domain.exceptions.user_has_activity_exception.UserHasActivityException": 409,
    "src.shared.domain.value_objects.country_code.InvalidCountryCodeError": 400,
    "src.shared.infrastructure.http.upload_reader.UploadTooLargeError": 413,
}

# Las que dan códigos distintos según la ruta: siguen traduciéndose en cada ruta
CONFLICTOS = {"GolfCourseNotApprovedError", "InvalidAvatarPresetError"}

# Except triviales que se quedan a propósito, por fichero y función: en
# reassign_match_players los sigue un `except Exception` que, sin ellos, convertiría
# esos errores en un 500
SE_QUEDAN_A_PROPOSITO = {("round_match_routes.py", "reassign_match_players")}


def _nombre(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def test_the_central_map_gives_each_error_the_code_it_had_in_the_routes():
    """
    Given: El código que daba cada error de dominio en las rutas de develop
    When: Se lee el mapa central de todos los módulos
    Then: Están todos, con el mismo código, y ninguno más
    """
    assert {_nombre(c): s for c, s in todos_los_codigos().items()} == CODIGOS_DE_DEVELOP


def test_registering_the_central_map_gives_every_error_its_handler():
    """
    Given: El mapa central
    When: Se mira qué manejadores tiene la app
    Then: Cada error del mapa tiene el suyo
    """
    sin_manejador = [_nombre(c) for c in todos_los_codigos() if c not in app.exception_handlers]

    assert sin_manejador == []


def test_reading_the_map_with_conflicting_errors_leaves_them_to_their_routes():
    """
    Given: Los dos errores que dan códigos distintos según la ruta
    When: Se mira el mapa central
    Then: No están: cada ruta sigue dando el suyo
    """
    assert not {c.__name__ for c in todos_los_codigos()} & CONFLICTOS


class _PadreError(Exception):
    pass


class _HijaError(_PadreError):
    pass


class _NietaError(_HijaError):
    pass


class _HermanaError(_PadreError):
    pass


@pytest.fixture
def cliente():
    mini = FastAPI()
    registra_los_codigos(mini, {_PadreError: 400, _HijaError: 404})

    @mini.get("/lanza/{cual}")
    async def lanza(cual: str):
        raise {
            "padre": _PadreError,
            "hija": _HijaError,
            "nieta": _NietaError,
            "hermana": _HermanaError,
        }[cual](f"motivo de {cual}")

    @mini.get("/como-antes")
    async def como_antes():
        raise HTTPException(status_code=404, detail="motivo de hija")

    return TestClient(mini)


def test_a_mapped_error_answers_its_code_with_its_message_as_detail(cliente):
    """
    Given: Un error registrado con 404
    When: Una ruta lo lanza sin capturarlo
    Then: 404 con {"detail": str(e)}, igual que el HTTPException de antes
    """
    nueva = cliente.get("/lanza/hija")
    antes = cliente.get("/como-antes")

    assert nueva.status_code == antes.status_code == 404
    assert nueva.json() == antes.json() == {"detail": "motivo de hija"}
    assert nueva.headers["content-type"] == antes.headers["content-type"]


@pytest.mark.parametrize(
    ("cual", "codigo"), [("padre", 400), ("hija", 404), ("nieta", 404), ("hermana", 400)]
)
def test_a_subclass_gets_the_code_of_its_closest_mapped_class(cliente, cual, codigo):
    """
    Given: Padre con 400 e Hija con 404
    When: Se lanza cada una, y también una nieta y una hermana sin código propio
    Then: Cada una recibe el de su clase registrada más cercana
    """
    assert cliente.get(f"/lanza/{cual}").status_code == codigo


def _except_triviales():
    """
    Los `except X as e: raise HTTPException(status_code=..., detail=str(e))` de las rutas,
    con cada X resuelta a su clase (las rutas importan algunas con otro nombre).
    """
    for ruta in sorted((RAIZ / "src" / "modules").glob("*/infrastructure/api/v1/*.py")):
        modulo = vars(
            importlib.import_module(".".join(ruta.relative_to(RAIZ).with_suffix("").parts))
        )
        funciones = [
            f
            for f in ast.walk(ast.parse(ruta.read_text(encoding="utf-8")))
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for funcion, nodo in ((f, n) for f in funciones for n in ast.walk(f)):
            if not (isinstance(nodo, ast.ExceptHandler) and nodo.type is not None and nodo.name):
                continue
            cuerpo = nodo.body
            if not (
                len(cuerpo) == 1
                and isinstance(cuerpo[0], ast.Raise)
                and isinstance(cuerpo[0].exc, ast.Call)
                and ast.unparse(cuerpo[0].exc.func) == "HTTPException"
            ):
                continue
            argumentos = {k.arg: ast.unparse(k.value) for k in cuerpo[0].exc.keywords}
            if argumentos != {
                "status_code": argumentos.get("status_code"),
                "detail": f"str({nodo.name})",
            }:
                continue
            clases = []
            for tipo in nodo.type.elts if isinstance(nodo.type, ast.Tuple) else [nodo.type]:
                valor = eval(compile(ast.Expression(tipo), ruta.name, "eval"), modulo)
                clases.extend(valor if isinstance(valor, tuple) else [valor])
            codigo = next(k.value for k in cuerpo[0].exc.keywords if k.arg == "status_code")
            yield (
                ruta.name,
                funcion.name,
                clases,
                eval(compile(ast.Expression(codigo), ruta.name, "eval"), modulo),
            )


def test_no_route_translates_by_hand_an_error_the_central_map_already_translates():
    """
    Given: Las rutas y el mapa central
    When: Se busca, clase a clase (también dentro de una tupla), un except trivial que le
          da el mismo código que el mapa, contando el que hereda de su clase registrada
    Then: No queda ninguno, salvo los que se quedan a propósito (una ruta que quiera
          otro código para un error del mapa sí puede traducirlo ella)
    """
    mapa = todos_los_codigos()

    def codigo_del_mapa(clase: type) -> int | None:
        # El que le daría la app: el de su clase registrada más cercana
        return next((mapa[c] for c in clase.__mro__ if c in mapa), None)

    repetidos = [
        (fichero, funcion, clase.__name__)
        for fichero, funcion, clases, codigo in _except_triviales()
        for clase in clases
        if codigo_del_mapa(clase) == codigo and (fichero, funcion) not in SE_QUEDAN_A_PROPOSITO
    ]

    assert repetidos == []
