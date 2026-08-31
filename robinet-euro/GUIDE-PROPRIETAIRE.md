# 💧 Robinet € — Guide du propriétaire

## 🔑 Identifiants et accès

### Compte Administrateur
| Champ | Valeur |
|-------|--------|
| Nom d'utilisateur | `admin` |
| Mot de passe | `admin123` |
| Accès | Onglet « ⚙️ Admin » après connexion |

> ⚠️ **À FAIRE EN PREMIER** : change ce mot de passe ! Sinon n'importe qui peut administrer le site.

### Comment changer le mot de passe admin ?
Le plus simple : connecte-toi en admin, puis envoie-moi « change le mot de passe admin en XXXXX » et je le modifie dans la base. (Il n'y a pas encore de page « mon compte » dans l'interface.)

---

## ⚙️ Ce que peut faire l'admin

Depuis l'onglet **⚙️ Admin** :

1. **Voir les statistiques** : nombre d'utilisateurs, retraits en attente, total payé, total gagné.
2. **Traiter les retraits** : bouton ✓ « Payer » ou ✗ « Refuser ».
   - Si tu refuses, l'argent est **automatiquement remboursé** sur le compte de l'utilisateur.
3. **Gérer les utilisateurs** : bannir / débannir, ajouter manuellement +0,50 € à quelqu'un.
4. **Créer des offres** : titre, type (vidéo / clic / sondage), récompense (en centimes), durée.
5. **Activer / désactiver** les offres existantes.

---

## 💰 Règles du site (réglages actuels)

| Paramètre | Valeur actuelle |
|-----------|-----------------|
| Retrait minimum | **2,00 €** |
| Plafond de gain par jour | 5,00 € |
| Bonus quotidien | 0,05 € |
| Bonus de bienvenue | 0,10 € |
| Cooldown entre 2 vidéos | 45 secondes |
| Tours de roue / jour | 5 |

Ces valeurs sont modifiables dans `server.py` (section « Paramètres » en haut du fichier).

---

## 📁 Structure du projet

```
robinet-euro/
├── server.py          → tout le backend (API + serveur web + base de données)
├── data.db            → base de données SQLite (utilisateurs, offres, retraits…)
└── static/
    ├── index.html     → l'interface
    ├── style.css      → le design
    └── app.js         → la logique côté navigateur
```

### Lancer le site en local
```bash
cd robinet-euro
python3 server.py
```
Puis ouvre http://localhost:8000

---

## 🌍 Comment PUBLIER réellement le site

⚠️ **Point important et honnête** : l'aperçu que tu vois ici est **temporaire** (il n'existe que pendant notre session). Pour que ton site soit visible par tout le monde **24h/24**, il faut le déployer sur un vrai hébergeur. Voici comment :

### Option 1 — Hébergement Python simple (recommandé)
Services compatibles : **Railway**, **Render**, **Fly.io**, **PythonAnywhere**, ou un VPS (OVH, OVHcloud, DigitalOcean, Hostinger…).
- Ils détectent automatiquement un projet Python.
- Point de démarrage : `python3 server.py`
- Définis la variable d'environnement `PORT` sur celle fournie par l'hébergeur (le script la lit automatiquement).

### Option 2 — VPS (plus de contrôle)
```bash
# sur ton serveur
git clone <ton projet>
cd robinet-euro
nohup python3 server.py &
```

### Ce qu'il faudra ajouter pour un site « pro »
1. **Vraies publicités** : les pubs actuelles sont *simulées*. Pour gagner de l'argent réel, il faut intégrer un vrai réseau publicitaire (Google AdSense, etc.). Ces réseaux ont des conditions strictes et souvent des minimums de trafic.
2. **Paiements automatiques** : actuellement l'admin valide les retraits à la main. Pour payer automatiquement, il faut brancher une API PayPal / Stripe.
3. **Vrai domaine** : acheter un nom de domaine (ex: robinet-euro.fr) et un certificat SSL (HTTPS).
4. **Sécurité** : les mots de passe sont déjà hachés (sha256 + sel), mais pour la production il faudra du HTTPS obligatoire et idéalement une base de données plus robuste (PostgreSQL).
5. **Mentions légales / CGU / RGPD** : obligatoires en France si tu touches de l'argent réel.

---

## ⚠️ Avertissement important

Ce site est une **démonstration fonctionnelle**. Il ne verse **pas d'argent réel** tant que :
- tu n'as pas branché de vrais revenus publicitaires, et
- tu n'as pas branché un vrai système de paiement.

Faire croire à des utilisateurs qu'ils vont être payés sans en avoir les moyens est interdit et illégal (escroquerie). Utilise-le comme base de projet, jamais pour tromper des gens.
