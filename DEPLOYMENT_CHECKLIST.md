# Checklist de deploiement SMS Pro

Cette checklist sert pour le deploiement Linode. Les valeurs sensibles doivent
rester dans le fichier `.env` du serveur, jamais dans GitHub.

## 1. Avant le push GitHub

- Verifier que `.env` est ignore par Git.
- Verifier que les fichiers `staticfiles/` ne sont pas commites.
- Lancer les tests :

```bash
source venv/bin/activate
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

- Lancer une verification production simulee :

```bash
DJANGO_DEBUG=False \
DJANGO_SECRET_KEY=change-me-for-check-only \
DJANGO_ALLOWED_HOSTS=sms.example.com \
DJANGO_CSRF_TRUSTED_ORIGINS=https://sms.example.com \
DJANGO_SESSION_COOKIE_SECURE=True \
DJANGO_CSRF_COOKIE_SECURE=True \
DJANGO_SECURE_SSL_REDIRECT=True \
DB_ENGINE=mysql \
MYSQL_DATABASE=sms_pro \
MYSQL_USER=sms_pro_user \
MYSQL_PASSWORD=change-me \
MYSQL_HOST=127.0.0.1 \
MYSQL_PORT=3306 \
CELERY_BROKER_URL=redis://127.0.0.1:6379/0 \
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0 \
CELERY_TASK_ALWAYS_EAGER=False \
python manage.py check --deploy
```

## 2. Sur Linode

- Installer les paquets systeme : Python, MySQL, Redis, Nginx, Git.
- Cloner le projet dans `/var/www/sms_pro`.
- Creer l'environnement virtuel Python.
- Installer `requirements.txt`.
- Creer la base MySQL en `utf8mb4`.
- Copier `.env.production.example` vers `.env`.
- Renseigner dans `.env` :
  - domaine et securite Django ;
  - acces MySQL ;
  - URLs Redis/Celery ;
  - identifiants API SMS ;
  - configuration email si la recuperation de mot de passe doit envoyer des emails.

## 3. Initialisation application

```bash
source /var/www/sms_pro/venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py check_data_integrity --fail-on-issues
```

## 4. Services a activer

- `sms_pro` : Gunicorn/Django.
- `sms_pro_celery_worker` : envoi reel des SMS en arriere-plan.
- `sms_pro_celery_beat` : declenchement des SMS programmes.
- `nginx` : proxy HTTP/HTTPS.
- `mysql` : base de donnees.
- `redis-server` : file d'attente Celery.

Commandes utiles :

```bash
sudo systemctl status sms_pro
sudo systemctl status sms_pro_celery_worker
sudo systemctl status sms_pro_celery_beat
sudo systemctl status nginx
sudo systemctl status mysql
sudo systemctl status redis-server
```

Logs utiles :

```bash
sudo journalctl -u sms_pro -f
sudo journalctl -u sms_pro_celery_worker -f
sudo journalctl -u sms_pro_celery_beat -f
sudo tail -f /var/log/nginx/error.log
```

## 5. Verification fonctionnelle apres mise en ligne

- Connexion administrateur.
- Creation ou verification d'une entreprise.
- Verification du solde SMS.
- Envoi d'un SMS simple vers un numero de test.
- Verification que le message passe de `pending` a `sent` ou `failed`.
- Test d'une campagne de petit volume.
- Test d'un SMS programme avec quelques minutes de decalage.
- Verification des logs Celery worker si un SMS reste en attente.

## 6. Points de vigilance

- Ne pas lancer `process_scheduled_sms` en meme temps que Celery Beat.
- Ne pas mettre les vraies cles SMS dans GitHub.
- Ne pas utiliser SQLite en production.
- Ne pas laisser `DJANGO_DEBUG=True` en production.
- Ne pas oublier HTTPS avant d'activer HSTS avec preload.
