# -*- coding: utf-8 -*-
"""
Base SQLAlchemy Configuration - Centralized Registry and Metadata.

Este módulo proporciona el registry y metadata centralizados que deben usar
todos los módulos de la aplicación para definir sus tablas y mappers.

Esto es necesario porque SQLAlchemy requiere que todas las tablas con
Foreign Keys entre sí estén en el mismo metadata para poder resolver
las referencias correctamente.

Uso:
    from src.shared.infrastructure.persistence.sqlalchemy.base import (
        mapper_registry,
        metadata
    )

    # Definir tabla
    my_table = Table('my_table', metadata, ...)

    # Registrar mapper
    mapper_registry.map_imperatively(MyEntity, my_table)
"""

from sqlalchemy.orm import registry


# Registry centralizado para toda la aplicación
# Todos los módulos deben usar este registry para registrar sus mappers
mapper_registry = registry()

# Metadata centralizado donde se definen todas las tablas
# Esto permite que los Foreign Keys se resuelvan correctamente entre módulos
metadata = mapper_registry.metadata
