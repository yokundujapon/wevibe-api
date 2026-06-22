#!/bin/bash
# WeVibe Backend — Script de lancement rapide
# Usage: bash start.sh

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       WeVibe Backend — MVP           ║"
echo "╚══════════════════════════════════════╝"
echo ""

# Activer le venv
if [ -f "$DIR/venv/bin/activate" ]; then
  source "$DIR/venv/bin/activate"
  echo "✓ venv activé"
else
  echo "✗ venv introuvable. Lance: python3 -m venv venv && pip install -r requirements.txt"
  exit 1
fi

# Vérifier les clés API
if [ -f "$DIR/.env" ]; then
  export $(grep -v '^#' "$DIR/.env" | xargs) 2>/dev/null || true
  echo "✓ .env chargé"
else
  echo "✗ Fichier .env manquant"
  exit 1
fi

if [ -z "$ASSEMBLYAI_API_KEY" ] || [ "$ASSEMBLYAI_API_KEY" = "your_assemblyai_key_here" ]; then
  echo "✗ ASSEMBLYAI_API_KEY non configurée dans .env"
  exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "your_anthropic_key_here" ]; then
  echo "✗ ANTHROPIC_API_KEY non configurée dans .env"
  exit 1
fi

echo "✓ Clés API vérifiées"

# Afficher l'IP locale pour l'app mobile
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📱 Adresse à utiliser dans l'app mobile:"
IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$IP" ]; then
  echo "   http://$IP:8000"
else
  echo "   http://localhost:8000  (vérifie ton IP avec: ifconfig en0)"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 Démarrage du serveur sur port 8000..."
echo "   (Ctrl+C pour arrêter)"
echo ""

# Lancer uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
