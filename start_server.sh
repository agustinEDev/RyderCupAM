#!/bin/bash

echo "=== Iniciando Servidor Ryder Cup AM ==="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "main.py" ]; then
    echo "❌ Error: No se encuentra main.py"
    echo "   Ejecuta este script desde el directorio raíz del proyecto"
    exit 1
fi

# Activar entorno virtual
echo "🔧 Activando entorno virtual..."
source .venv/bin/activate

# Verificar que requests está instalado
echo "🔍 Verificando dependencias..."
python -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Instalando requests..."
    pip install requests==2.32.3
fi

# Mostrar configuración
echo ""
echo "📧 Configuración de Email:"
python -c "from src.config.settings import settings; print(f'   Mailgun Domain: {settings.MAILGUN_DOMAIN}'); print(f'   Frontend URL: {settings.FRONTEND_URL}')"

echo ""
echo "🚀 Iniciando servidor en http://localhost:8000"
echo "   Documentación: http://localhost:8000/docs"
echo ""
echo "⚠️  IMPORTANTE: Observa los logs para ver el envío de emails"
echo "   Deberías ver: 'Email enviado correctamente a...'"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Iniciar servidor
uvicorn main:app --reload --log-level info
