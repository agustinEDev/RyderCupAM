"""
Reglas puras del dominio de competiciones: no conocen ninguna entidad.

Las usan las entidades y los servicios del dominio. Están por debajo de las entidades para que
ninguna entidad tenga que importar `domain/services`, que sí importa entidades (B10, fase 5).
"""
