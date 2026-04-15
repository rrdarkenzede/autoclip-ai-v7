# 🌌 Tutoriel : Configuration Manuelle AutoClipAI v7.0 (Cloud)

Ce guide vous explique comment migrer votre pipeline vers GitHub Actions et Google Colab sans avoir besoin de scripts d'aspiration complexes.

---

## 🛠️ Étape 1 : Extraire vos Cookies (30 sec)

Puisque les cookies sont chiffrés par votre système, nous allons les copier directement depuis votre navigateur.

1. Installez l'extension **[Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkbbadnoamhpnmmadjmge)** sur Chrome ou Edge.
2. Allez sur **TikTok.com** et assurez-vous d'être connecté.
3. Cliquez sur l'icône de l'extension -> Cliquez sur **Export** -> Choisissez **JSON**.
4. **Enregistrez ce texte** (nous en aurons besoin à l'étape 2).
5. Faites la **même chose** pour **YouTube.com**.

---

## 🔐 Étape 2 : Configurer vos GitHub Secrets

GitHub Actions a besoin de ces "clés" pour fonctionner chaque nuit.

1. Allez sur votre dépôt GitHub.
2. Cliquez sur **Settings** -> **Secrets and variables** -> **Actions**.
3. Cliquez sur **New repository secret** pour chaque valeur ci-dessous :

| Nom du Secret | Valeur à coller |
| :--- | :--- |
| `GEMINI_API_KEY` | Votre clé API Gemini (trouvée dans votre `.env`) |
| `TIKTOK_COOKIES` | Le JSON copié depuis TikTok (Etape 1) |
| `YOUTUBE_COOKIES` | Le JSON copié depuis YouTube (Etape 1) |
| `GOOGLE_DRIVE_FOLDER_ID` | L'ID de votre dossier Google Drive |
| `GOOGLE_DRIVE_CREDENTIALS` | Le contenu de votre fichier JSON Service Account |

---

## 🚀 Étape 3 : Activer l'Automatisation

1. Allez dans l'onglet **Actions** de votre GitHub.
2. Dans la barre latérale gauche, cliquez sur **"AutoClipAI Nightly Pipeline"**.
3. Cliquez sur le bouton **Run workflow** (en haut à droite) pour faire un premier test immédiat.

---

## 📺 Surveillance
- Le script tournera automatiquement chaque nuit à **3h00 du matin**.
- Vous pouvez voir l'avancement en cliquant sur le "Workflow Run" dans l'onglet **Actions**.
- Les clips finaux apparaîtront directement dans votre **Google Drive** !

---

> [!TIP]
> **Pourquoi faire ça manuellement ?**
> C'est 100% sécurisé (vos cookies ne quittent pas votre environnement GitHub) et cela évite les erreurs dues aux mises à jour de sécurité des navigateurs.
