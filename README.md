# Afrique Résurrection - Générateur de Vidéos HD

## Structure du projet
```
code_export/
├── backend/
│   ├── server.py          # API FastAPI complète
│   ├── requirements.txt   # Dépendances Python
│   └── .env.example       # Variables d'environnement
├── frontend/
│   ├── src/
│   │   ├── App.js         # Composant React principal
│   │   ├── App.css        # Styles complets
│   │   └── index.js       # Point d'entrée React
│   ├── public/
│   │   └── index.html     # HTML template
│   ├── package.json       # Dépendances Node.js
│   └── .env.example       # Variables d'environnement
└── README.md
```

## Assets requis (à placer dans backend/assets/)
- `logo.png` - Logo Afrique Résurrection
- `whoosh.mp3` - Effet sonore transition
- `afrique_resurrection.mp3` - Musique de fond option 1
- `breaking_news.mp3` - Musique de fond option 2

## Installation

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env avec vos valeurs
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd frontend
yarn install
cp .env.example .env
# Éditer .env avec l'URL du backend
yarn start
```

## Configuration .env

### Backend (.env)
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=afrique_resurrection
CORS_ORIGINS=*
RESEND_API_KEY=re_votre_cle  # Optionnel pour emails
SENDER_EMAIL=onboarding@resend.dev
```

### Frontend (.env)
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

## Fonctionnalités
- Upload jusqu'à 20 images (drag & drop)
- Sous-titres personnalisés par image
- 3 modes: Ultra Rapide ⚡, Normal 🎬, HD 💎
- Voix off Edge TTS (homme/femme)
- Musique de fond (2 options)
- Transitions (Zoom + Whoosh, Fondu)
- Effet Ken Burns sur tous les modes
- Format vertical 1080x1920
- Email de notification (optionnel)

© Afrique Résurrection 2026
