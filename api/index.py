# Punto de entrada para Vercel Serverless (Flask WSGI)
import os
import sys

# Añadir la raíz del proyecto al path para importar app.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: F401 — Vercel usa esta variable WSGI
