"""
Los números del freno del login por correo y origen (BE #732, ADR-043).

Viven en el dominio para que los compartan el adaptador que los aplica y el correo
que se los cuenta al dueño. El respaldo de la cuenta (50 en una hora) está en la
entidad User.
"""

# 10 fallos de un origen (una red, o un dispositivo fiable) en 30 minutos lo
# bloquean 30 minutos para ese correo. La ventana y el bloqueo son cosas distintas,
# aunque hoy duren lo mismo
FALLOS_POR_ORIGEN = 10
MINUTOS_DE_LA_VENTANA_POR_ORIGEN = 30
MINUTOS_DE_BLOQUEO_POR_ORIGEN = 30
