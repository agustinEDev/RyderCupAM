"""Tests para TypeDecorators y JSONB serialization del Block 5."""

import uuid

from src.modules.competition.domain.value_objects.handicap_mode import HandicapMode
from src.modules.competition.domain.value_objects.match_format import MatchFormat
from src.modules.competition.domain.value_objects.match_id import MatchId
from src.modules.competition.domain.value_objects.match_player import MatchPlayer
from src.modules.competition.domain.value_objects.match_status import MatchStatus
from src.modules.competition.domain.value_objects.round_id import RoundId
from src.modules.competition.domain.value_objects.round_status import RoundStatus
from src.modules.competition.domain.value_objects.session_type import SessionType
from src.modules.competition.domain.value_objects.team_assignment_id import (
    TeamAssignmentId,
)
from src.modules.competition.domain.value_objects.team_assignment_mode import (
    TeamAssignmentMode,
)
from src.modules.competition.infrastructure.persistence.sqlalchemy.mappers import (
    MatchIdDecorator,
    MatchPlayersJsonType,
    MatchResultJsonType,
    RoundIdDecorator,
    TeamAssignmentIdDecorator,
    UserIdsJsonType,
    _create_enum_decorator,
)
from src.modules.golf_course.domain.value_objects.tee_category import TeeCategory
from src.modules.user.domain.value_objects.user_id import UserId

# ==================== ID TypeDecorators ====================


class TestRoundIdDecorator:
    """Tests para RoundIdDecorator TypeDecorator."""

    def setup_method(self):
        self.decorator = RoundIdDecorator()

    def test_process_bind_param_with_round_id(self):
        """Serializa RoundId a string UUID."""
        round_id = RoundId.generate()
        result = self.decorator.process_bind_param(round_id, None)
        assert result == str(round_id.value)

    def test_process_bind_param_with_string(self):
        """Acepta string directamente."""
        uid = str(uuid.uuid4())
        result = self.decorator.process_bind_param(uid, None)
        assert result == uid

    def test_process_bind_param_with_none(self):
        """Retorna None para None."""
        assert self.decorator.process_bind_param(None, None) is None

    def test_process_result_value_to_round_id(self):
        """Deserializa string a RoundId."""
        uid = str(uuid.uuid4())
        result = self.decorator.process_result_value(uid, None)
        assert isinstance(result, RoundId)
        assert str(result.value) == uid

    def test_process_result_value_none(self):
        """Retorna None para None."""
        assert self.decorator.process_result_value(None, None) is None


class TestMatchIdDecorator:
    """Tests para MatchIdDecorator TypeDecorator."""

    def setup_method(self):
        self.decorator = MatchIdDecorator()

    def test_roundtrip(self):
        """Serializa y deserializa MatchId correctamente."""
        match_id = MatchId.generate()
        serialized = self.decorator.process_bind_param(match_id, None)
        deserialized = self.decorator.process_result_value(serialized, None)
        assert isinstance(deserialized, MatchId)
        assert deserialized == match_id


class TestTeamAssignmentIdDecorator:
    """Tests para TeamAssignmentIdDecorator TypeDecorator."""

    def setup_method(self):
        self.decorator = TeamAssignmentIdDecorator()

    def test_roundtrip(self):
        """Serializa y deserializa TeamAssignmentId correctamente."""
        ta_id = TeamAssignmentId.generate()
        serialized = self.decorator.process_bind_param(ta_id, None)
        deserialized = self.decorator.process_result_value(serialized, None)
        assert isinstance(deserialized, TeamAssignmentId)
        assert deserialized == ta_id


# ==================== Enum TypeDecorators ====================


class TestEnumDecorators:
    """Tests para la factory _create_enum_decorator y los decorators generados."""

    def test_factory_creates_named_class(self):
        """La factory genera una clase con nombre descriptivo."""
        DecoratorClass = _create_enum_decorator(SessionType)
        assert DecoratorClass.__name__ == "SessionTypeDecorator"

    def test_session_type_roundtrip(self):
        """SessionType se serializa/deserializa correctamente."""
        DecoratorClass = _create_enum_decorator(SessionType)
        decorator = DecoratorClass()
        for session_type in SessionType:
            serialized = decorator.process_bind_param(session_type, None)
            assert serialized == session_type.value
            deserialized = decorator.process_result_value(serialized, None)
            assert deserialized == session_type

    def test_match_format_roundtrip(self):
        """MatchFormat se serializa/deserializa correctamente."""
        DecoratorClass = _create_enum_decorator(MatchFormat)
        decorator = DecoratorClass()
        for fmt in MatchFormat:
            serialized = decorator.process_bind_param(fmt, None)
            deserialized = decorator.process_result_value(serialized, None)
            assert deserialized == fmt

    def test_round_status_roundtrip(self):
        """RoundStatus se serializa/deserializa correctamente."""
        DecoratorClass = _create_enum_decorator(RoundStatus)
        decorator = DecoratorClass()
        for status in RoundStatus:
            serialized = decorator.process_bind_param(status, None)
            deserialized = decorator.process_result_value(serialized, None)
            assert deserialized == status

    def test_handicap_mode_roundtrip(self):
        """HandicapMode se serializa/deserializa correctamente."""
        DecoratorClass = _create_enum_decorator(HandicapMode)
        decorator = DecoratorClass()
        for mode in HandicapMode:
            serialized = decorator.process_bind_param(mode, None)
            deserialized = decorator.process_result_value(serialized, None)
            assert deserialized == mode

    def test_match_status_roundtrip(self):
        """MatchStatus se serializa/deserializa correctamente."""
        DecoratorClass = _create_enum_decorator(MatchStatus)
        decorator = DecoratorClass()
        for status in MatchStatus:
            serialized = decorator.process_bind_param(status, None)
            deserialized = decorator.process_result_value(serialized, None)
            assert deserialized == status

    def test_team_assignment_mode_roundtrip(self):
        """TeamAssignmentMode se serializa/deserializa correctamente."""
        DecoratorClass = _create_enum_decorator(TeamAssignmentMode)
        decorator = DecoratorClass()
        for mode in TeamAssignmentMode:
            serialized = decorator.process_bind_param(mode, None)
            deserialized = decorator.process_result_value(serialized, None)
            assert deserialized == mode

    def test_tee_category_roundtrip(self):
        """TeeCategory se serializa/deserializa correctamente."""
        DecoratorClass = _create_enum_decorator(TeeCategory)
        decorator = DecoratorClass()
        for cat in TeeCategory:
            serialized = decorator.process_bind_param(cat, None)
            deserialized = decorator.process_result_value(serialized, None)
            assert deserialized == cat

    def test_none_handling(self):
        """None pasa sin cambio en ambas direcciones."""
        DecoratorClass = _create_enum_decorator(SessionType)
        decorator = DecoratorClass()
        assert decorator.process_bind_param(None, None) is None
        assert decorator.process_result_value(None, None) is None

    def test_string_passthrough_bind(self):
        """Un string ya formateado pasa sin cambio al serializar."""
        DecoratorClass = _create_enum_decorator(SessionType)
        decorator = DecoratorClass()
        result = decorator.process_bind_param("MORNING", None)
        assert result == "MORNING"


# ==================== JSONB TypeDecorators ====================


class TestMatchPlayersJsonType:
    """Tests para serialización JSONB de MatchPlayer tuples."""

    def setup_method(self):
        self.decorator = MatchPlayersJsonType()
        self.user_id_1 = UserId.generate()
        self.user_id_2 = UserId.generate()
        self.player_1 = MatchPlayer(
            user_id=self.user_id_1,
            playing_handicap=12,
            tee_category=TeeCategory.AMATEUR_MALE,
            strokes_received=(1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6),
        )
        self.player_2 = MatchPlayer(
            user_id=self.user_id_2,
            playing_handicap=8,
            tee_category=TeeCategory.CHAMPIONSHIP_FEMALE,
            strokes_received=(1, 3, 5, 7, 9, 11, 13, 15),
        )

    def test_serialize_match_players(self):
        """Serializa tuple de MatchPlayer a lista de dicts."""
        players = (self.player_1, self.player_2)
        result = self.decorator.process_bind_param(players, None)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["user_id"] == str(self.user_id_1.value)
        assert result[0]["playing_handicap"] == 12
        assert result[0]["tee_category"] == "AMATEUR_MALE"
        assert result[0]["strokes_received"] == [1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6]

    def test_deserialize_match_players(self):
        """Deserializa lista de dicts a tuple de MatchPlayer."""
        json_data = [
            {
                "user_id": str(self.user_id_1.value),
                "playing_handicap": 12,
                "tee_category": "AMATEUR_MALE",
                "strokes_received": [1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6],
            },
        ]
        result = self.decorator.process_result_value(json_data, None)

        assert isinstance(result, tuple)
        assert len(result) == 1
        player = result[0]
        assert isinstance(player, MatchPlayer)
        assert player.user_id == self.user_id_1
        assert player.playing_handicap == 12
        assert player.tee_category == TeeCategory.AMATEUR_MALE
        assert player.strokes_received == (1, 3, 5, 7, 9, 11, 13, 15, 17, 2, 4, 6)

    def test_roundtrip(self):
        """Serializa y deserializa sin pérdida de datos."""
        players = (self.player_1, self.player_2)
        serialized = self.decorator.process_bind_param(players, None)
        deserialized = self.decorator.process_result_value(serialized, None)
        assert deserialized == players

    def test_none_handling(self):
        """None pasa sin cambio."""
        assert self.decorator.process_bind_param(None, None) is None
        assert self.decorator.process_result_value(None, None) is None

    def test_empty_tuple(self):
        """Serializa tuple vacía a lista vacía."""
        result = self.decorator.process_bind_param((), None)
        assert result == []
        deserialized = self.decorator.process_result_value(result, None)
        assert deserialized == ()


class TestUserIdsJsonType:
    """Tests para serialización JSONB de UserId tuples."""

    def setup_method(self):
        self.decorator = UserIdsJsonType()
        self.uid_1 = UserId.generate()
        self.uid_2 = UserId.generate()
        self.uid_3 = UserId.generate()

    def test_serialize_user_ids(self):
        """Serializa tuple de UserId a lista de strings."""
        ids = (self.uid_1, self.uid_2, self.uid_3)
        result = self.decorator.process_bind_param(ids, None)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == str(self.uid_1.value)
        assert result[1] == str(self.uid_2.value)
        assert result[2] == str(self.uid_3.value)

    def test_deserialize_user_ids(self):
        """Deserializa lista de strings a tuple de UserId."""
        json_data = [str(self.uid_1.value), str(self.uid_2.value)]
        result = self.decorator.process_result_value(json_data, None)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] == self.uid_1
        assert result[1] == self.uid_2

    def test_roundtrip(self):
        """Serializa y deserializa sin pérdida de datos."""
        ids = (self.uid_1, self.uid_2, self.uid_3)
        serialized = self.decorator.process_bind_param(ids, None)
        deserialized = self.decorator.process_result_value(serialized, None)
        assert deserialized == ids

    def test_none_handling(self):
        """None pasa sin cambio."""
        assert self.decorator.process_bind_param(None, None) is None
        assert self.decorator.process_result_value(None, None) is None


class TestMatchResultJsonType:
    """Tests para serialización JSONB de match result."""

    def setup_method(self):
        self.decorator = MatchResultJsonType()

    def test_passthrough_dict(self):
        """Dict pasa sin cambio en ambas direcciones."""
        result_data = {"winner": "A", "score": "3&2"}
        assert self.decorator.process_bind_param(result_data, None) == result_data
        assert self.decorator.process_result_value(result_data, None) == result_data

    def test_none_handling(self):
        """None pasa sin cambio."""
        assert self.decorator.process_bind_param(None, None) is None
        assert self.decorator.process_result_value(None, None) is None

    def test_walkover_result(self):
        """Resultado de walkover se serializa correctamente."""
        walkover = {"winner": "B", "score": "W/O", "reason": "No show"}
        assert self.decorator.process_bind_param(walkover, None) == walkover
