# src/config/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargar las variables de entorno del fichero .env
# Es útil para desarrollo local sin Docker
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("No se ha definido la variable de entorno DATABASE_URL")

# El engine es el punto de entrada a la base de datos.
# Gestiona las conexiones y la comunicación.
engine = create_engine(DATABASE_URL)

# La sessionmaker es una "fábrica" de sesiones.
# Cada sesión que crea es una conversación individual con la base de datos.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)