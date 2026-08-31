# 🚀 Publier le site sur un hébergeur (guide pas-à-pas)

Ton projet est **prêt à déployer** : j'ai ajouté les fichiers que les hébergeurs attendent
(`Procfile`, `Dockerfile`, `render.yaml`, `requirements.txt`).

Tu dois juste **choisir un hébergeur** et **créer ton compte gratuit**, puis suivre les étapes ci-dessous.

---

## ✅ Option 1 — Render.com (le plus simple, gratuit)

1. Va sur **https://render.com** → clique **« Get Started »** → crée un compte (email ou Google/GitHub).
2. Connecte ton compte **GitHub** (ou téléverse le dossier).
3. Clique **« New » → « Web Service »**.
4. Choisis **« Deploy from public Git repository »** ou connecte ton dépôt.
   - Astuce : tu peux aussi glisser-déposer le dossier via l'option « Upload ».
5. Render détecte automatiquement le fichier `render.yaml`.
6. Clique **« Create Web Service »**. C'est tout ! 🎉

- Render fournit une URL gratuite du type `https://robinet-euro.onrender.com`
- Le site met ~2 minutes à démarrer la première fois.

> ⚠️ Sur le plan gratuit, le serveur **s'endort après 15 min d'inactivité** (il se réveille à la première visite, ~30 s). Pour un site toujours actif, prends le plan payant (~7 $/mois).

---

## ✅ Option 2 — Railway.app (gratuit avec crédits)

1. Va sur **https://railway.app** → crée un compte avec GitHub.
2. Clique **« New Project » → « Deploy from GitHub repo »**.
3. Sélectionne ton dossier `robinet-euro`.
4. Railway détecte le `Procfile` et lance `python3 server.py` automatiquement.
5. Va dans **Settings → Networking → Generate Domain** pour obtenir ton URL publique.

---

## ✅ Option 3 — VPS (OVH, DigitalOcean, Hostinger…) — contrôle total

Sur ton serveur (Ubuntu/Debian) :
```bash
# 1. Envoie le dossier robinet-euro sur le serveur (via Git, SFTP ou scp)
# 2. Connecte-toi en SSH puis :
sudo apt update && sudo apt install -y python3
cd robinet-euro
nohup python3 server.py > server.log 2>&1 &
```
Ton site sera sur `http://IP-du-serveur:8000`.

Pour un domaine + HTTPS, installe **Caddy** (très simple) :
```bash
sudo apt install -y caddy
# dans /etc/caddy/Caddyfile :
#   ton-domaine.fr {
#       reverse_proxy localhost:8000
#   }
```

---

## 📋 Récapitulatif des fichiers ajoutés

| Fichier | Rôle |
|---------|------|
| `Procfile` | Indique la commande de démarrage (Heroku/Railway) |
| `Dockerfile` | Pour déployer en conteneur Docker |
| `render.yaml` | Config automatique pour Render |
| `requirements.txt` | Déclare les dépendances (aucune, stdlib uniquement) |
| `.gitignore` | Évite de publier la base de données |

---

## ⚠️ Choses à savoir AVANT de publier

1. **Base de données** : le site utilise un fichier `data.db`. Sur les hébergeurs gratuits (Render/Railway),
   ce fichier est **effacé à chaque redéploiement**. Pour garder les données, il faudra passer à
   PostgreSQL (je peux t'aider à adapter le code).

2. **Vraies pubs & paiements** : les publicités et les retraits sont encore **simulés**.
   Pour un vrai business, il faudra intégrer un réseau publicitaire + PayPal/Stripe (je peux t'aider).

3. **Mentions légales** : obligatoires si tu touches de l'argent réel.

---

👉 Dis-moi **quel hébergeur tu choisis**, et je te guide étape par étape (et j'adapte le code si besoin).
