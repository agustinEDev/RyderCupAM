# 1. Imagen base: Usamos una imagen oficial de Python ligera
FROM python:3.11-slim

# 2. Directorio de trabajo: Establecemos el directorio donde se ejecutará la app
WORKDIR /app

# 3. Copiar e instalar dependencias:
# Copiamos primero el fichero de requisitos para aprovechar el cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar el código de la aplicación
COPY . .

# 5. Comando de ejecución:
# Le decimos a Docker cómo iniciar nuestra aplicación con Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]