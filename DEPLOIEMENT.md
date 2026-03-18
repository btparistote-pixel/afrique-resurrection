# Guide de Déploiement - Afrique Résurrection

## Étape 1: Créer un compte GitHub

1. Allez sur https://github.com
2. Créez un compte si vous n'en avez pas
3. Créez un nouveau dépôt nommé `afrique-resurrection`

## Étape 2: Uploader le code

Dans votre terminal:
```bash
cd C:\Users\Claud\Downloads\code_export\code_export
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/VOTRE_USERNAME/afrique-resurrection.git
git push -u origin main
```

## Étape 3: Déployer le Backend sur Render

1. Allez sur https://render.com et connectez-vous avec GitHub
2. Cliquez sur "New +" → "Web Service"
3. Sélectionnez votre dépôt `afrique-resurrection`
4. Configurez:
   - Name: `afrique-backend`
   - Environment: `Python`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
5. Cliquez sur "Create Web Service"
6. Attendez le déploiement (5-10 min)

## Étape 4: Déployer le Frontend sur Vercel

1. Allez sur https://vercel.com et connectez-vous avec GitHub
2. Cliquez sur "Add New..." → "Project"
3. Sélectionnez votre dépôt
4. Configurez:
   - Framework Preset: `Create React App`
   - Build Command: `npm run build` (ou `yarn build`)
   - Output Directory: `build`
5. Cliquez sur "Deploy"

## Étape 5: Variable d'environnement Backend

Dans Render, allez dans "Environment Variables" et ajoutez:
- `MONGO_URL`: URL de MongoDB Atlas (voir ci-dessous)
- `DB_NAME`: afrique_resurrection

## Étape 6: MongoDB Atlas (Gratuit)

1. Allez sur https://www.mongodb.com/cloud/atlas
2. Créez un compte gratuit
3. Créez un cluster gratuit
4. Créez un utilisateur avec mot de passe
5. Dans "Network Access", cliquez "Add IP Address" et sélectionnez "Allow Access from Anywhere (0.0.0.0/0)"
6. Cliquez sur "Connect" → "Connect your application"
7. Copiez la chaîne de connexion et remplacer `<password>` par votre mot de passe
8. Collez cette URL dans la variable `MONGO_URL` de Render

## URL Finale

- Frontend: https://afrique-resurrection.vercel.app
- Backend: https://afrique-backend.onrender.com

## Notes importantes

- FFmpeg est automatiquement installé sur Render
- Le premier déploiement peut prendre 5-10 minutes
- Le tier gratuit de Render suspend après 15 min d'inactivité (se réveille en 30s)