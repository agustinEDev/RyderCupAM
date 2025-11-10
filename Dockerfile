# 1. Imagen base: Usamos una imagen oficial de Python ligera
FROM python:3.11-slim

# 2. Instalar dependencias del sistema necesarias
# netcat-openbsd: Para verificar conexión con PostgreSQL
# postgresql-client: Para herramientas de postgres si es necesario
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 3. Directorio de trabajo: Establecemos el directorio donde se ejecutará la app
WORKDIR /app

# 4. Copiar e instalar dependencias:
# Copiamos primero el fichero de requisitos para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar el código de la aplicación y el script de inicio
COPY . .
COPY entrypoint.sh /entrypoint.sh

# 6. Dar permisos de ejecución al script
RUN chmod +x /entrypoint.sh

# 7. Exponer el puerto (por defecto 8000, pero configurable con ENV PORT)
EXPOSE 8000

# 8. Comando de ejecución:
# Ejecuta el script que espera a la BD y ejecuta migraciones antes de iniciar
ENTRYPOINT ["/entrypoint.sh"]