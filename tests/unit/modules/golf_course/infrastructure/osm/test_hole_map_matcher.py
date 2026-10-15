"""
Tests del emparejado de un recorrido con lo que hay en OpenStreetMap (BE #532).

Del contorno al green: qué campo de OSM es el nuestro, qué hoyos suyos entran
(contra nuestra tarjeta) y dónde quedan delante, centro y fondo del green.
"""

import math

import pytest
from shapely import (
    Point as ShapelyPoint,
    Polygon,
)

from src.modules.golf_course.application.ports.osm_hole_map_source import (
    CardHole,
    DiscardReason,
)
from src.modules.golf_course.domain.value_objects.position_source import PositionSource
from src.modules.golf_course.infrastructure.osm.hole_map_matcher import match_hole_map
from src.modules.golf_course.infrastructure.osm.overpass_client import OsmRelation, OsmWay

from .geometria import campo, circulo, cuadrado, green, hoyo, metros, pt, zona

# Nuestra tarjeta: par 4 y hándicap = número en todos los hoyos salvo el 3 (par 5)
TARJETA = tuple(CardHole(number=n, par=5 if n == 3 else 4, stroke_index=n) for n in range(1, 19))
DENTRO = pt(500, 500)


def _match(area, punto=DENTRO, physical_holes=18, card=TARJETA):
    return match_hole_map(
        area, latitude=punto[0], longitude=punto[1], card=card, physical_holes=physical_holes
    )


def _hoyo_recto(way_id=10, ref="1", par=None, handicap=None, x=500):
    """Hoyo de 300 m de sur a norte, con su green al final."""
    return hoyo(way_id, ref, (x, 100), (x, 400), par=par, handicap=handicap)


def _cerca(a, b, tolerancia=0.6):
    """Dos puntos (lat, lon) a menos de `tolerancia` metros."""
    ax, ay = metros(*a)
    bx, by = metros(*b)
    return math.hypot(ax - bx, ay - by) <= tolerancia


def _xy(point):
    return metros(point.latitude, point.longitude)


# ============================================================================
# C — Contorno del campo
# ============================================================================


def test_c1_point_inside_outline_picks_it():
    """
    GIVEN: Nuestra coordenada dentro de un contorno de campo
    WHEN: Se empareja
    THEN: Se elige ese contorno
    """
    candidate = _match(zona(cursos=[campo(1)], hoyos=[_hoyo_recto()], greens=[green(20, 500, 400)]))

    assert candidate is not None
    assert candidate.osm_reference == "way/1"


def test_c2_point_outside_picks_nearest_within_1_km():
    """
    GIVEN: Nuestra coordenada fuera de dos contornos, a 300 y 700 m
    WHEN: Se empareja
    THEN: Se elige el más cercano
    """
    cerca = campo(1, cuadrado(0, 0, 1000, 1000))
    lejos = campo(2, cuadrado(2000, 0, 3000, 1000))

    candidate = _match(zona(cursos=[lejos, cerca]), punto=pt(1300, 500))

    assert candidate is not None
    assert candidate.osm_reference == "way/1"


def test_c3_no_outline_within_1_km_returns_none():
    """
    GIVEN: El contorno más cercano a 1,2 km
    WHEN: Se empareja
    THEN: No hay candidato
    """
    assert _match(zona(cursos=[campo(1)]), punto=pt(2200, 500)) is None


def test_c3_no_outline_at_all_returns_none():
    """
    GIVEN: Ningún contorno
    WHEN: Se empareja
    THEN: No hay candidato
    """
    assert _match(zona(hoyos=[_hoyo_recto()])) is None


def test_c4_relation_outline_made_of_pieces():
    """
    GIVEN: El contorno es una relación cuyo anillo exterior viene en dos trozos
    WHEN: Se empareja
    THEN: Se monta el polígono, se elige y sus hoyos entran
    """
    anillo = cuadrado(0, 0, 1000, 1000)
    relacion = OsmRelation(
        id=7,
        tags={"leisure": "golf_course"},
        outer=(anillo[:3], anillo[2:]),
        inner=(),
    )

    candidate = _match(
        zona(relaciones=[relacion], hoyos=[_hoyo_recto()], greens=[green(20, 500, 400)])
    )

    assert candidate is not None
    assert candidate.osm_reference == "relation/7"
    assert [h.number for h in candidate.holes] == [1]


def test_c5_only_holes_inside_the_chosen_outline():
    """
    GIVEN: Dos campos vecinos con un hoyo 1 cada uno (caso Valderrama)
    WHEN: Se empareja con la coordenada del primero
    THEN: Solo entra el hoyo 1 de dentro de su contorno
    """
    vecino = campo(2, cuadrado(1000, 0, 2000, 1000))
    nuestro = _hoyo_recto(way_id=10, x=500)
    del_vecino = _hoyo_recto(way_id=11, x=1500)

    candidate = _match(
        zona(
            cursos=[campo(1), vecino],
            hoyos=[nuestro, del_vecino],
            greens=[green(20, 500, 400), green(21, 1500, 400)],
        )
    )

    assert candidate is not None
    assert len(candidate.holes) == 1
    assert _cerca((candidate.holes[0].tee.latitude, candidate.holes[0].tee.longitude), pt(500, 100))


def test_c1_nested_outlines_pick_the_tightest():
    """
    GIVEN: El contorno del club entero y, dentro, el de nuestro recorrido
    WHEN: Se empareja con una coordenada dentro de los dos
    THEN: Se elige el del recorrido, el más ajustado
    """
    club = campo(1, cuadrado(-1000, -1000, 2000, 2000))
    recorrido = campo(2, cuadrado(0, 0, 1000, 1000))

    candidate = _match(zona(cursos=[club, recorrido]))

    assert candidate is not None
    assert candidate.osm_reference == "way/2"


def test_c4_relation_inner_ring_is_left_out():
    """
    GIVEN: Una relación con un hueco (un lago fuera del campo) y nuestra
           coordenada en mitad de ese hueco, a más de 1 km de cualquier borde
    WHEN: Se empareja
    THEN: El hueco no cuenta como campo: no se elige
    """
    relacion = OsmRelation(
        id=7,
        tags={"leisure": "golf_course"},
        outer=(cuadrado(-3000, -3000, 4000, 4000),),
        inner=(cuadrado(-1500, -1500, 2500, 2500),),
    )

    assert _match(zona(relaciones=[relacion])) is None


def test_c6_unclosed_way_is_not_an_outline():
    """
    GIVEN: Un contorno de campo mal dibujado, sin cerrar
    WHEN: Se empareja
    THEN: No se toma como contorno
    """
    abierto = campo(1, cuadrado(0, 0, 1000, 1000)[:-1])

    assert _match(zona(cursos=[abierto])) is None


def test_h1b_hole_just_outside_the_outline_still_counts():
    """
    GIVEN: Un hoyo cuyo punto medio cae 10 m fuera del contorno (el tee más
           atrasado se sale del dibujo), y otro a 40 m
    WHEN: Se empareja
    THEN: Entra el de 10 m; el de 40 m no es de este campo
    """
    cerca = hoyo(10, "1", (1010, 100), (1010, 400))
    lejos = hoyo(11, "2", (1040, 100), (1040, 400))

    candidate = _match(zona(cursos=[campo()], hoyos=[cerca, lejos]))

    assert candidate is not None
    assert [h.number for h in candidate.holes] == [1]
    assert candidate.discarded == {}


def test_g1b_unclosed_green_is_ignored():
    """
    GIVEN: El único green, mal dibujado, sin cerrar
    WHEN: Se empareja
    THEN: El hoyo entra sin green
    """
    abierto = OsmWay(id=20, tags={"golf": "green"}, points=green(20, 500, 400).points[:-1])

    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[abierto]))

    assert candidate is not None
    assert candidate.holes[0].green is None


# ============================================================================
# H — Hoyos
# ============================================================================


def test_h1_hole_inside_enters_with_number_and_line():
    """
    GIVEN: Un hoyo con ref 1 dentro del contorno
    WHEN: Se empareja
    THEN: Entra como hoyo 1, con su línea de la salida al final
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[green(20, 500, 400)]))

    assert candidate is not None
    (hole,) = candidate.holes
    assert hole.number == 1
    assert len(hole.play_line) == 2
    assert _cerca((hole.tee.latitude, hole.tee.longitude), pt(500, 100))


@pytest.mark.parametrize("ref", [None, "1a", "0", "19", "", "4.0"])
def test_h2_hole_without_valid_number_is_discarded(ref):
    """
    GIVEN: Un hoyo sin ref, o con un ref que no es un número de 1 a 18
    WHEN: Se empareja
    THEN: No entra, y se cuenta como sin número
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto(ref=ref)]))

    assert candidate is not None
    assert candidate.holes == ()
    assert candidate.discarded == {DiscardReason.NO_NUMBER: 1}


def test_h3_hole_beyond_the_course_is_discarded():
    """
    GIVEN: Un campo de 9 hoyos y un hoyo 14 en OSM
    WHEN: Se empareja
    THEN: No entra, y se cuenta como fuera del campo
    """
    candidate = _match(
        zona(cursos=[campo()], hoyos=[_hoyo_recto(ref="14"), _hoyo_recto(way_id=11, ref="9")]),
        physical_holes=9,
    )

    assert candidate is not None
    assert [h.number for h in candidate.holes] == [9]
    assert candidate.discarded == {DiscardReason.BEYOND_COURSE: 1}


def test_h3_first_hole_beyond_the_course_is_discarded():
    """
    GIVEN: Un campo de 9 hoyos y un hoyo 10 en OSM (el límite justo)
    WHEN: Se empareja
    THEN: No entra
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto(ref="10")]), physical_holes=9)

    assert candidate is not None
    assert candidate.holes == ()
    assert candidate.discarded == {DiscardReason.BEYOND_COURSE: 1}


def test_h4_par_mismatch_is_discarded():
    """
    GIVEN: El hoyo 1 de OSM es par 5 y en nuestra tarjeta es par 4
    WHEN: Se empareja
    THEN: No entra, y se cuenta como par distinto
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto(par="5")]))

    assert candidate is not None
    assert candidate.holes == ()
    assert candidate.discarded == {DiscardReason.PAR_MISMATCH: 1}


@pytest.mark.parametrize("par", [None, "4"])
def test_h4_matching_or_missing_par_enters(par):
    """
    GIVEN: El hoyo 1 sin par en OSM, o con el mismo par que el nuestro
    WHEN: Se empareja
    THEN: Entra
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto(par=par)]))

    assert candidate is not None
    assert [h.number for h in candidate.holes] == [1]
    assert candidate.discarded == {}


def test_h5_duplicate_number_resolved_by_handicap():
    """
    GIVEN: Dos hoyos 3 (dos recorridos del club), par 5 los dos, hándicap 3 y 12
    WHEN: Se empareja con nuestra tarjeta (hoyo 3: par 5, hándicap 3)
    THEN: Entra el de hándicap 3
    """
    bueno = _hoyo_recto(way_id=10, ref="3", par="5", handicap="3", x=300)
    otro = _hoyo_recto(way_id=11, ref="3", par="5", handicap="12", x=700)

    candidate = _match(zona(cursos=[campo()], hoyos=[otro, bueno]))

    assert candidate is not None
    (hole,) = candidate.holes
    assert _cerca((hole.tee.latitude, hole.tee.longitude), pt(300, 100))
    assert candidate.discarded == {}


def test_h5_duplicate_number_resolved_by_par():
    """
    GIVEN: Dos hoyos 3, uno par 5 y otro par 3
    WHEN: Se empareja (nuestro 3 es par 5)
    THEN: Entra el par 5; el otro se cuenta como par distinto
    """
    bueno = _hoyo_recto(way_id=10, ref="3", par="5", x=300)
    otro = _hoyo_recto(way_id=11, ref="3", par="3", x=700)

    candidate = _match(zona(cursos=[campo()], hoyos=[otro, bueno]))

    assert candidate is not None
    (hole,) = candidate.holes
    assert _cerca((hole.tee.latitude, hole.tee.longitude), pt(300, 100))
    assert candidate.discarded == {DiscardReason.PAR_MISMATCH: 1}


@pytest.mark.parametrize(
    ("handicap_a", "handicap_b"),
    [(None, None), ("3", "3"), ("7", "12")],
    ids=["sin", "iguales", "ninguno"],
)
def test_h5_duplicate_number_not_distinguishable_is_discarded(handicap_a, handicap_b):
    """
    GIVEN: Dos hoyos 3 que no se distinguen por par y hándicap
    WHEN: Se empareja
    THEN: No entra ninguno, y se cuenta una vez como ambiguo
    """
    a = _hoyo_recto(way_id=10, ref="3", handicap=handicap_a, x=300)
    b = _hoyo_recto(way_id=11, ref="3", handicap=handicap_b, x=700)

    candidate = _match(zona(cursos=[campo()], hoyos=[a, b]))

    assert candidate is not None
    assert candidate.holes == ()
    assert candidate.discarded == {DiscardReason.AMBIGUOUS: 1}


def test_h6_reversed_line_is_turned_around():
    """
    GIVEN: Una línea dibujada del green a la salida (el green junto a su primer punto)
    WHEN: Se empareja
    THEN: Se le da la vuelta: la salida es el extremo lejos del green
    """
    al_reves = hoyo(10, "1", (500, 400), (500, 100))

    candidate = _match(zona(cursos=[campo()], hoyos=[al_reves], greens=[green(20, 500, 400)]))

    assert candidate is not None
    (hole,) = candidate.holes
    assert _cerca((hole.tee.latitude, hole.tee.longitude), pt(500, 100))
    assert hole.green is not None


def test_h7_coordinates_have_seven_decimals():
    """
    GIVEN: Puntos de OSM con muchos decimales
    WHEN: Se empareja
    THEN: Las coordenadas guardadas tienen como mucho 7 (1 cm)
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[green(20, 500, 400)]))

    assert candidate is not None
    hole = candidate.holes[0]
    assert hole.green is not None
    points = [*hole.play_line, hole.green.front, hole.green.center, *hole.green.outline]
    for point in points:
        assert round(point.latitude, 7) == point.latitude
        assert round(point.longitude, 7) == point.longitude


# ============================================================================
# G — Green
# ============================================================================


def test_g1_green_within_60_m_is_assigned():
    """
    GIVEN: Un green a 50 m del final de la línea
    WHEN: Se empareja
    THEN: Se le asigna
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[green(20, 500, 460)]))

    assert candidate is not None
    assert candidate.holes[0].green is not None


def test_g1_green_beyond_60_m_leaves_hole_pending():
    """
    GIVEN: El único green a 80 m del final de la línea
    WHEN: Se empareja
    THEN: El hoyo entra sin green (pendiente de marcar)
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[green(20, 500, 490)]))

    assert candidate is not None
    assert candidate.holes[0].green is None


def test_g1_nearest_green_wins():
    """
    GIVEN: Dos greens cerca del final, a 5 y a 40 m
    WHEN: Se empareja
    THEN: Se asigna el más cercano
    """
    candidate = _match(
        zona(
            cursos=[campo()],
            hoyos=[_hoyo_recto()],
            greens=[green(21, 500, 450), green(20, 500, 415)],
        )
    )

    assert candidate is not None
    green_ = candidate.holes[0].green
    assert green_ is not None
    assert _cerca((green_.center.latitude, green_.center.longitude), pt(500, 415))


def test_g2_front_center_back_along_the_approach():
    """
    GIVEN: Un hoyo de sur a norte y un green cuadrado de 20 m centrado en su final
    WHEN: Se empareja
    THEN: Centro en el centro; delante en el borde sur y fondo en el norte
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[green(20, 500, 400)]))

    assert candidate is not None
    green_ = candidate.holes[0].green
    assert green_ is not None
    assert _cerca((green_.center.latitude, green_.center.longitude), pt(500, 400))
    assert _cerca((green_.front.latitude, green_.front.longitude), pt(500, 390))
    assert _cerca((green_.back.latitude, green_.back.longitude), pt(500, 410))


def test_g2_center_is_the_centroid():
    """
    GIVEN: Un green triangular (su centro de masas no es el de su caja)
    WHEN: Se empareja
    THEN: El centro es el centro de masas del triángulo
    """
    triangulo = OsmWay(
        id=20,
        tags={"golf": "green"},
        points=(pt(490, 395), pt(520, 395), pt(490, 425), pt(490, 395)),
    )

    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[triangulo]))

    assert candidate is not None
    green_ = candidate.holes[0].green
    assert green_ is not None
    assert _cerca((green_.center.latitude, green_.center.longitude), pt(500, 405))


def test_g2_center_falls_inside_a_horseshoe_green():
    """
    GIVEN: Un green en herradura, cuyo centro de masas cae fuera del green
    WHEN: Se empareja
    THEN: El centro se pone dentro del green
    """
    herradura = OsmWay(
        id=20,
        tags={"golf": "green"},
        points=tuple(
            pt(x, y)
            for x, y in [
                (480, 395),
                (520, 395),
                (520, 425),
                (510, 425),
                (510, 405),
                (490, 405),
                (490, 425),
                (480, 425),
                (480, 395),
            ]
        ),
    )

    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[herradura]))

    assert candidate is not None
    green_ = candidate.holes[0].green
    assert green_ is not None
    forma = Polygon([metros(lat, lon) for lat, lon in herradura.points])
    assert forma.contains(ShapelyPoint(_xy(green_.center)))


def test_g3_dogleg_uses_the_last_segment():
    """
    GIVEN: Un dogleg: 300 m al norte y luego 200 m al este hasta el green
    WHEN: Se empareja
    THEN: Delante y fondo van de oeste a este (último tramo), no en diagonal
    """
    dogleg = hoyo(10, "1", (300, 100), (300, 400), (500, 400))

    candidate = _match(zona(cursos=[campo()], hoyos=[dogleg], greens=[green(20, 500, 400)]))

    assert candidate is not None
    hole = candidate.holes[0]
    assert len(hole.play_line) == 3
    assert hole.green is not None
    assert _cerca((hole.green.front.latitude, hole.green.front.longitude), pt(490, 400))
    assert _cerca((hole.green.back.latitude, hole.green.back.longitude), pt(510, 400))


def test_g4_double_green_is_shared():
    """
    GIVEN: Dos hoyos que terminan en el mismo green (green doble)
    WHEN: Se empareja
    THEN: Los dos lo usan
    """
    a = hoyo(10, "1", (400, 100), (495, 400))
    b = hoyo(11, "2", (600, 100), (505, 400))

    candidate = _match(zona(cursos=[campo()], hoyos=[a, b], greens=[green(20, 500, 400, lado=40)]))

    assert candidate is not None
    assert all(h.green is not None for h in candidate.holes)
    assert candidate.holes[0].green.center == candidate.holes[1].green.center


def test_g5_outline_simplified_to_64_points_within_half_a_metre():
    """
    GIVEN: Un green circular de 15 m de radio dibujado con 400 puntos
    WHEN: Se empareja
    THEN: El contorno guardado tiene como mucho 64 puntos y no se aparta más de
         0,5 m del dibujado (ningún punto del original queda más lejos)
    """
    redondo = circulo(500, 400, 15, 400)

    candidate = _match(
        zona(
            cursos=[campo()],
            hoyos=[_hoyo_recto()],
            greens=[OsmWay(id=20, tags={"golf": "green"}, points=redondo)],
        )
    )

    assert candidate is not None
    outline = candidate.holes[0].green.outline
    assert 3 <= len(outline) <= 64
    guardado = Polygon([_xy(p) for p in outline])
    for lat, lon in redondo:
        assert guardado.exterior.distance(ShapelyPoint(metros(lat, lon))) <= 0.5 + 0.01


def test_g5_huge_outline_is_capped_at_64_points():
    """
    GIVEN: Un green enorme (círculo de 1 km de radio, 2000 puntos) que a 0,5 m
           no baja de 64 puntos
    WHEN: Se empareja
    THEN: Se afloja la tolerancia hasta guardarlo con 64 puntos como mucho
    """
    enorme = circulo(500, 1450, 1000, 2000)

    candidate = _match(
        zona(
            cursos=[campo()],
            hoyos=[_hoyo_recto()],
            greens=[OsmWay(id=20, tags={"golf": "green"}, points=enorme)],
        )
    )

    assert candidate is not None
    assert candidate.holes[0].green is not None
    assert 3 <= len(candidate.holes[0].green.outline) <= 64


def test_g5_outline_has_no_repeated_closing_point():
    """
    GIVEN: Un green cuadrado (OSM repite el primer punto al final)
    WHEN: Se empareja
    THEN: El contorno guardado no repite el punto de cierre
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[green(20, 500, 400)]))

    assert candidate is not None
    outline = candidate.holes[0].green.outline
    assert len(outline) == 4
    assert outline[0] != outline[-1]


def test_g6_every_position_comes_from_osm():
    """
    GIVEN: Un hoyo con green
    WHEN: Se empareja
    THEN: La línea y el green tienen origen OSM
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto()], greens=[green(20, 500, 400)]))

    assert candidate is not None
    hole = candidate.holes[0]
    assert hole.line_source is PositionSource.OSM
    assert hole.green is not None
    assert hole.green.source is PositionSource.OSM


def test_holes_come_sorted_by_number():
    """
    GIVEN: Hoyos 2 y 1, en ese orden
    WHEN: Se empareja
    THEN: Salen ordenados
    """
    candidate = _match(
        zona(cursos=[campo()], hoyos=[_hoyo_recto(way_id=11, ref="2", x=700), _hoyo_recto()])
    )

    assert candidate is not None
    assert [h.number for h in candidate.holes] == [1, 2]


# ============================================================================
# Revisión — casos de datos reales
# ============================================================================


def test_h6_tee_next_to_the_previous_green_is_not_turned():
    """
    GIVEN: Un hoyo bien dibujado cuya salida está a 2 m del green del hoyo
           anterior y cuya línea acaba 6 m antes de su propio green
    WHEN: Se empareja
    THEN: No se gira: la salida sigue primero y el green es el suyo
    """
    anterior = green(20, 500, 88)  # su borde norte en y=98
    propio = green(21, 500, 416)  # su borde sur en y=406
    linea = hoyo(10, "1", (500, 100), (500, 400))

    candidate = _match(zona(cursos=[campo()], hoyos=[linea], greens=[anterior, propio]))

    assert candidate is not None
    hole = candidate.holes[0]
    assert _cerca((hole.tee.latitude, hole.tee.longitude), pt(500, 100))
    assert hole.green is not None
    assert _cerca((hole.green.center.latitude, hole.green.center.longitude), pt(500, 416))


@pytest.mark.parametrize("ref", ["²", "\u0661", "³"])
def test_h2_exotic_digits_are_no_number(ref):
    """
    GIVEN: Un ref con un carácter que Python considera dígito pero no es un número
    WHEN: Se empareja
    THEN: Se descarta como sin número, sin reventar el campo entero
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto(ref=ref)]))

    assert candidate is not None
    assert candidate.discarded == {DiscardReason.NO_NUMBER: 1}


def test_h4_exotic_par_is_taken_as_missing():
    """
    GIVEN: Un par «⁴» en OSM
    WHEN: Se empareja
    THEN: Se toma como sin par y el hoyo entra
    """
    candidate = _match(zona(cursos=[campo()], hoyos=[_hoyo_recto(par="⁴")]))

    assert candidate is not None
    assert [h.number for h in candidate.holes] == [1]


def test_h3_hole_beyond_a_short_card_is_beyond_course():
    """
    GIVEN: Una tarjeta de solo 9 hoyos y un hoyo 12 en OSM
    WHEN: Se empareja
    THEN: Se cuenta como fuera del campo, no como sin número
    """
    corta = TARJETA[:9]

    candidate = _match(
        zona(cursos=[campo()], hoyos=[_hoyo_recto(ref="12")]), card=corta, physical_holes=9
    )

    assert candidate is not None
    assert candidate.discarded == {DiscardReason.BEYOND_COURSE: 1}


def test_c7_self_crossing_outline_keeps_both_halves():
    """
    GIVEN: Un contorno dibujado en ocho (se corta a sí mismo) con un hoyo en
           cada mitad
    WHEN: Se empareja con la coordenada en una mitad
    THEN: Entran los dos hoyos: no se pierde media figura al repararla
    """
    ocho = (pt(0, 0), pt(2000, 1000), pt(2000, 0), pt(0, 1000), pt(0, 0))
    izquierda = hoyo(10, "1", (300, 300), (300, 700))
    derecha = hoyo(11, "2", (1700, 300), (1700, 700))

    candidate = _match(
        zona(cursos=[campo(1, ocho)], hoyos=[izquierda, derecha]), punto=pt(300, 500)
    )

    assert candidate is not None
    assert [h.number for h in candidate.holes] == [1, 2]
