# Guide de Configuration Déploiement Automatique

## Résumé

Le code est sur GitHub. Les workflows GitHub Actions sont configurés pour déployer automatiquement vers Render (backend) et Vercel (frontend).

## Ce qui est déjà fait ✅

- [x] Code sur GitHub
- [x] Workflows GitHub Actions créés
- [x] Fichiers de configuration Render et Vercel

## Ce que vous devez faire

### 1. Créer un compte MongoDB Atlas (gratuit)

1. Allez sur https://www.mongodb.com/cloud/atlas
2. Créez un compte gratuit
3. Créez un cluster gratuit
4. Créez un utilisateur (nom: `admin`, mot de passe: `votre_mot_de_passe`)
5. Network Access: Add IP Address → `0.0.0.0/0`
6. Connect → Connect your application
7. Copiez l'URL: `mongodb+srv://admin:votre_mot_de_passe@clusterxxx.mongodb.net/?retryWrites=true&w=majority`

### 2..Configurer Render

1. Allez sur https://dashboard.render.com
2. Connectez-vous avec GitHub
3. Settings → API Keys → Create API Key
4. Copiez la clé (nommez-la `render-api-key`)

### 3. Configurer Vercel

1. Allez sur https://vercel.com
2. Connectez-vous avec GitHub
3. Importez le projet `btparistote-pixel/afrique-resurrection`
4. Dans Project Settings:
   - Copiez `Project ID`
   - Copiez `Org ID`
5. Account Settings → Tokens → Create Token (nommez-le `vercel-deploy`)

### 4. Ajouter les secrets GitHub

1. Allez sur https://github.com/btparistote-pixel/afrique-resurrection/settings/secrets/actions
2. Ajoutez ces secrets:

| Nom | Valeur |
|-----|--------|
| `RENDER_API_KEY` | Votre clé API Render |
| `VERCEL_TOKEN` | Votre token Vercel |
| `VERCEL_ORG_ID` | Votre Organization ID |
| `VERCEL_PROJECT_ID` | Votre Project ID |
| `REACT_APP_BACKEND_URL` | URL du backend (ex: https://afrique-backend.onrender.com) |

### 5. Premier déploiement

1. Dans Render: Créez manually un web service:
   - Name: `afrique-backend`
   - Repo: `btparistote-pixel/afrique-resurrection`
   - Branch: `main`
   - Build Command: `pip install -r backend/requirements.txt`
   - Start Command: `uvicorn backend.server:app --host 0.0.0.0 --port $PORT`
   - Environment: `Python`
   - Après création, allez dans Environment Variables et ajoutez:
     - `MONGO_URL`: Votre URL MongoDB Atlas
     - `DB_NAME`: `afrique_resurrection`

2. Dans Vercel:
   - Attendez que le déploiement se fasse automatiquement
   - OU cliquez "Deploy" manuellement

### 6. URL finales

- Frontend: `https://afrique-resurrection.vercel.app`
- Backend: `https://afrique-backend.onrender.com`

## Problèmes courants

### Le déploiement Render échoue
- Vérifiez que `MONGO_URL` est correct
- Vérifiez que le cluster MongoDB est actif

### Le frontend ne peut pas communiquer avec le backend
- Vérifiez que `REACT_APP_BACKEND_URL` pointe vers le bon URL Render
- Dans Render, vérifiez que `CORS_ORIGINS=*` est configuré
