"""
MatchPlayersBuilder - Los jugadores de un partido con su reparto de golpes.

Cada formato reparte a su manera, con el método diferencial del WHS:
- individual: solo recibe el de mayor hándicap de juego, y la diferencia;
- fourball: cada uno, la diferencia con el menor Course Handicap de los cuatro;
- foursomes: el equipo, el allowance sobre la diferencia de medias.

Vivía dentro de `GenerateMatchesUseCase`, y reasignar jugadores tenía su propia
versión que daba a cada uno TODO su hándicap de juego como golpes, fuera cual
fuera el formato (BE #477). Ahora generar y reasignar usan esta.
"""

from decimal import Decimal

from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.golf_course.domain.services.stroke_context import holes_for_tee
from src.modules.golf_course.domain.value_objects.tee_color import TeeColor
from src.modules.user.domain.value_objects.user_id import UserId
from src.shared.domain.services.playing_handicap_calculator import TeeRating
from src.shared.domain.services.stroke_allocation import holes_receiving_strokes
from src.shared.domain.services.tee_lookup import tee_key_for
from src.shared.domain.value_objects.gender import Gender
from src.shared.domain.value_objects.match_format import MatchFormat


class TeeColorNotFoundError(Exception):
    """No se encontró el color de barras del jugador en el campo."""

    pass


class MatchPlayersBuilder:
    """Construye los MatchPlayers de un partido según su formato."""

    def build(
        self,
        match_format: MatchFormat,
        team_a_ids: list[UserId],
        team_b_ids: list[UserId],
        enrollment_map,
        tee_ratings,
        calculator,
        allowance,
        is_scratch,
        user_handicap_map,
        holes_by_stroke_index,
        user_gender_map,
        max_playing_handicap=None,
        holes_by_tee=None,
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]]:
        """Los jugadores de los dos equipos, con los golpes que da su formato."""
        args = (
            enrollment_map,
            tee_ratings,
            calculator,
            allowance,
            is_scratch,
            user_handicap_map,
            holes_by_stroke_index,
            user_gender_map,
            max_playing_handicap,
            holes_by_tee,
        )
        if match_format == MatchFormat.SINGLES:
            a_player, b_player = self._build_singles_match_players(
                team_a_ids[0], team_b_ids[0], *args
            )
            return [a_player], [b_player]
        if match_format == MatchFormat.FOURBALL:
            return self._build_fourball_match_players(team_a_ids, team_b_ids, *args)
        if match_format == MatchFormat.FOURSOMES:
            return self._build_foursomes_match_players(team_a_ids, team_b_ids, *args)
        raise ValueError(f"Formato de partido no soportado: {match_format.value}")

    def resolve_player_data(
        self,
        user_id,
        enrollment_map,
        tee_ratings,
        user_handicap_map,
        user_gender_map,
    ) -> tuple[TeeColor, Gender | None, TeeRating | None, Decimal]:
        """
        Resuelve datos de un jugador: tee colour, gender, tee rating e handicap index.

        Returns:
            (tee_color, tee_gender, tee_rating, handicap_index)
        """
        enrollment = enrollment_map.get(str(user_id.value))
        tee_color = enrollment.tee_color if enrollment and enrollment.tee_color else TeeColor.YELLOW
        user_gender = user_gender_map.get(str(user_id.value))

        # Auto-resolve tee: (colour, user_gender) → (colour, None) fallback
        tee_key = tee_key_for(
            tee_ratings, tee_color.value, user_gender.value if user_gender else None
        ) or (tee_color.value, None)
        tee_gender = user_gender if tee_key[1] is not None else None

        tee_rating = tee_ratings.get(tee_key)

        # Handicap fallback: custom_handicap > user.handicap > 0
        if enrollment and enrollment.custom_handicap is not None:
            handicap_index = enrollment.custom_handicap
        elif str(user_id.value) in user_handicap_map:
            handicap_index = user_handicap_map[str(user_id.value)]
        else:
            handicap_index = Decimal("0")

        return tee_color, tee_gender, tee_rating, handicap_index

    @staticmethod
    def _team_holes(team_ids, player_data, holes_by_tee, default):
        """
        Orden de dificultad de un equipo de FOURSOMES.

        Comparten bola, asi que el golpe es del equipo y no puede caer en dos
        hoyos segun quien golpee: hace falta UNA tarjeta. Si los dos juegan la
        misma barra, la suya; si no, la del campo, que es lo unico neutral.
        """
        tees = {
            (player_data[str(uid.value)][0], player_data[str(uid.value)][1])
            for uid in team_ids
            if str(uid.value) in player_data
        }
        if len(tees) != 1:
            return default
        tee_color, tee_gender = next(iter(tees))
        return holes_for_tee(holes_by_tee, tee_color, tee_gender, default)

    def _build_fourball_match_players(
        self,
        team_a_ids,
        team_b_ids,
        enrollment_map,
        tee_ratings,
        calculator,
        allowance,
        is_scratch,
        user_handicap_map,
        holes_by_stroke_index,
        user_gender_map,
        max_playing_handicap=None,
        holes_by_tee=None,
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]]:
        """
        Construye MatchPlayers para FOURBALL usando el método diferencial WHS.

        En lugar de aplicar allowance% al CH individual, calcula las diferencias
        respecto al menor CH de los 4 jugadores y aplica allowance% a esas diferencias.

        Returns:
            (team_a_match_players, team_b_match_players)
        """
        all_ids = list(team_a_ids) + list(team_b_ids)

        if is_scratch:
            # En modo SCRATCH, todos juegan off scratch
            team_a_players = []
            for uid in team_a_ids:
                tee_color, tee_gen, _, hi = self.resolve_player_data(
                    uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
                )
                team_a_players.append(
                    MatchPlayer.create(
                        user_id=uid,
                        playing_handicap=0,
                        tee_color=tee_color,
                        strokes_received=[],
                        tee_gender=tee_gen,
                        player_handicap=hi,
                    )
                )
            team_b_players = []
            for uid in team_b_ids:
                tee_color, tee_gen, _, hi = self.resolve_player_data(
                    uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
                )
                team_b_players.append(
                    MatchPlayer.create(
                        user_id=uid,
                        playing_handicap=0,
                        tee_color=tee_color,
                        strokes_received=[],
                        tee_gender=tee_gen,
                        player_handicap=hi,
                    )
                )
            return team_a_players, team_b_players

        # 1. Calcular Course Handicaps (100%, sin allowance) para los 4 jugadores
        player_data: dict[str, tuple[TeeColor, Gender | None, TeeRating, Decimal]] = {}
        course_handicaps: list[tuple[str, int]] = []

        for uid in all_ids:
            tee_color, tee_gen, tee_rating, hi = self.resolve_player_data(
                uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
            )
            if not tee_rating:
                raise TeeColorNotFoundError(
                    f"No se encontró tee rating para color '{tee_color.value}' "
                    f"(gender: {tee_gen}) en el campo de golf"
                )
            player_data[str(uid.value)] = (tee_color, tee_gen, tee_rating, hi)
            ch = calculator.calculate_course_handicap(hi, tee_rating)
            course_handicaps.append((str(uid.value), ch))

        # 2. Método diferencial: aplica allowance% a diferencias respecto al menor CH
        # (calculate_fourball_differential aplica el cap de max_playing_handicap internamente)
        differential_phs = calculator.calculate_fourball_differential(
            course_handicaps, allowance, max_playing_handicap
        )

        # 3. Construir MatchPlayers con PH diferencial
        def build_player(uid):
            uid_str = str(uid.value)
            tee_color, tee_gen, _, hi = player_data[uid_str]
            ph = differential_phs[uid_str]
            strokes = holes_receiving_strokes(
                ph, holes_for_tee(holes_by_tee, tee_color, tee_gen, holes_by_stroke_index)
            )
            return MatchPlayer.create(
                user_id=uid,
                playing_handicap=ph,
                tee_color=tee_color,
                strokes_received=strokes,
                tee_gender=tee_gen,
                player_handicap=hi,
            )

        team_a_players = [build_player(uid) for uid in team_a_ids]
        team_b_players = [build_player(uid) for uid in team_b_ids]
        return team_a_players, team_b_players

    def _build_singles_match_players(
        self,
        a_player_id,
        b_player_id,
        enrollment_map,
        tee_ratings,
        calculator,
        allowance,
        is_scratch,
        user_handicap_map,
        holes_by_stroke_index,
        user_gender_map,
        max_playing_handicap=None,
        holes_by_tee=None,
    ) -> tuple["MatchPlayer", "MatchPlayer"]:
        """
        Construye MatchPlayers para SINGLES usando el método diferencial WHS.

        WHS Match Play: solo el jugador con mayor Playing Handicap recibe golpes.
        Los golpes recibidos = (PH_alto - PH_bajo) en los hoyos más difíciles (menor SI).
        El jugador con menor PH juega off scratch (0 golpes recibidos).
        El PH individual de cada jugador se conserva en playing_handicap para display.

        Returns:
            (match_player_a, match_player_b)
        """
        tee_color_a, tee_gen_a, tee_rating_a, hi_a = self.resolve_player_data(
            a_player_id, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
        )
        tee_color_b, tee_gen_b, tee_rating_b, hi_b = self.resolve_player_data(
            b_player_id, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
        )

        if is_scratch:
            return (
                MatchPlayer.create(
                    user_id=a_player_id,
                    playing_handicap=0,
                    tee_color=tee_color_a,
                    strokes_received=[],
                    tee_gender=tee_gen_a,
                    player_handicap=hi_a,
                ),
                MatchPlayer.create(
                    user_id=b_player_id,
                    playing_handicap=0,
                    tee_color=tee_color_b,
                    strokes_received=[],
                    tee_gender=tee_gen_b,
                    player_handicap=hi_b,
                ),
            )

        if not tee_rating_a:
            raise TeeColorNotFoundError(
                f"No se encontró tee rating para color '{tee_color_a.value}' "
                f"(gender: {tee_gen_a}) en el campo de golf"
            )
        if not tee_rating_b:
            raise TeeColorNotFoundError(
                f"No se encontró tee rating para color '{tee_color_b.value}' "
                f"(gender: {tee_gen_b}) en el campo de golf"
            )

        ph_a = calculator.calculate(hi_a, tee_rating_a, allowance, max_playing_handicap)
        ph_b = calculator.calculate(hi_b, tee_rating_b, allowance, max_playing_handicap)

        # Cada uno recibe en los hoyos de SU barra: solo uno de los dos recibe,
        # asi que no hay conflicto entre dos ordenes distintos.
        holes_a = holes_for_tee(holes_by_tee, tee_color_a, tee_gen_a, holes_by_stroke_index)
        holes_b = holes_for_tee(holes_by_tee, tee_color_b, tee_gen_b, holes_by_stroke_index)
        strokes_a, _ = calculator.calculate_singles_differential(ph_a, ph_b, holes_a)
        _, strokes_b = calculator.calculate_singles_differential(ph_a, ph_b, holes_b)

        return (
            MatchPlayer.create(
                user_id=a_player_id,
                playing_handicap=ph_a,
                tee_color=tee_color_a,
                strokes_received=strokes_a,
                tee_gender=tee_gen_a,
                player_handicap=hi_a,
            ),
            MatchPlayer.create(
                user_id=b_player_id,
                playing_handicap=ph_b,
                tee_color=tee_color_b,
                strokes_received=strokes_b,
                tee_gender=tee_gen_b,
                player_handicap=hi_b,
            ),
        )

    def _build_foursomes_match_players(
        self,
        team_a_ids,
        team_b_ids,
        enrollment_map,
        tee_ratings,
        calculator,
        allowance,
        is_scratch,
        user_handicap_map,
        holes_by_stroke_index,
        user_gender_map,
        max_playing_handicap=None,
        holes_by_tee=None,
    ) -> tuple[list[MatchPlayer], list[MatchPlayer]]:
        """
        Construye MatchPlayers para FOURSOMES usando el método diferencial WHS.

        En FOURSOMES (golpe alterno) los strokes se calculan a nivel de EQUIPO:
        1. Se calcula el CH individual de cada jugador (100%, sin allowance)
        2. Se promedian los CH por equipo
        3. Se aplica el allowance% a la diferencia entre promedios
        4. Solo el equipo con mayor CH promedio recibe strokes
        5. Ambos jugadores del equipo comparten los mismos strokes (una bola)

        Returns:
            (team_a_match_players, team_b_match_players)
        """
        all_ids = list(team_a_ids) + list(team_b_ids)

        if is_scratch:
            team_a_players = []
            for uid in team_a_ids:
                tee_color, tee_gen, _, hi = self.resolve_player_data(
                    uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
                )
                team_a_players.append(
                    MatchPlayer.create(
                        user_id=uid,
                        playing_handicap=0,
                        tee_color=tee_color,
                        strokes_received=[],
                        tee_gender=tee_gen,
                        player_handicap=hi,
                    )
                )
            team_b_players = []
            for uid in team_b_ids:
                tee_color, tee_gen, _, hi = self.resolve_player_data(
                    uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
                )
                team_b_players.append(
                    MatchPlayer.create(
                        user_id=uid,
                        playing_handicap=0,
                        tee_color=tee_color,
                        strokes_received=[],
                        tee_gender=tee_gen,
                        player_handicap=hi,
                    )
                )
            return team_a_players, team_b_players

        # 1. Calcular Course Handicaps individuales (100%, sin allowance)
        player_data: dict[str, tuple[TeeColor, Gender | None, Decimal]] = {}
        team_a_chs: list[int] = []
        team_b_chs: list[int] = []

        for uid in all_ids:
            tee_color, tee_gen, tee_rating, hi = self.resolve_player_data(
                uid, enrollment_map, tee_ratings, user_handicap_map, user_gender_map
            )
            if not tee_rating:
                raise TeeColorNotFoundError(
                    f"No se encontró tee rating para color '{tee_color.value}' "
                    f"(gender: {tee_gen}) en el campo de golf"
                )
            player_data[str(uid.value)] = (tee_color, tee_gen, hi)
            ch = calculator.calculate_course_handicap(hi, tee_rating)
            if uid in team_a_ids:
                team_a_chs.append(ch)
            else:
                team_b_chs.append(ch)

        # 2. Método diferencial por equipos: allowance% se aplica a la diferencia de promedios
        # (calculate_foursomes_differential aplica el cap de max_playing_handicap internamente)
        team_a_ph, team_b_ph = calculator.calculate_foursomes_differential(
            team_a_chs, team_b_chs, allowance, max_playing_handicap
        )

        # 3. Ambos jugadores del equipo comparten los mismos strokes (una bola),
        #    y por tanto un solo orden de dificultad. Se usa el de la barra del
        #    equipo cuando los dos juegan la misma; si juegan barras distintas no
        #    hay una tarjeta que sea "la del equipo" y se cae a la del campo.
        team_a_strokes = holes_receiving_strokes(
            team_a_ph,
            self._team_holes(team_a_ids, player_data, holes_by_tee, holes_by_stroke_index),
        )
        team_b_strokes = holes_receiving_strokes(
            team_b_ph,
            self._team_holes(team_b_ids, player_data, holes_by_tee, holes_by_stroke_index),
        )

        team_a_players = []
        for uid in team_a_ids:
            tee_color, tee_gen, hi = player_data[str(uid.value)]
            team_a_players.append(
                MatchPlayer.create(
                    user_id=uid,
                    playing_handicap=team_a_ph,
                    tee_color=tee_color,
                    strokes_received=team_a_strokes,
                    tee_gender=tee_gen,
                    player_handicap=hi,
                )
            )

        team_b_players = []
        for uid in team_b_ids:
            tee_color, tee_gen, hi = player_data[str(uid.value)]
            team_b_players.append(
                MatchPlayer.create(
                    user_id=uid,
                    playing_handicap=team_b_ph,
                    tee_color=tee_color,
                    strokes_received=team_b_strokes,
                    tee_gender=tee_gen,
                    player_handicap=hi,
                )
            )

        return team_a_players, team_b_players
