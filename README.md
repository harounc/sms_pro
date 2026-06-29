# SMS Pro

Application Django de gestion SMS multi-entreprises : comptes, contacts,
groupes, campagnes, expéditeurs, historique et facturation.

## Lancement local

```bash
source venv/bin/activate
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Puis ouvrir :

```text
http://127.0.0.1:8000/
```

## Configuration

Les paramètres sensibles sont lus depuis `.env`, qui ne doit pas être commité.

Variables principales :

- `DJANGO_SECRET_KEY` : clé secrète Django.
- `DJANGO_DEBUG` : `True` en local, `False` en production.
- `DJANGO_ALLOWED_HOSTS` : hôtes autorisés, séparés par des virgules.
- `DB_ENGINE` : `sqlite` en local, `mysql` en production.
- `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST`, `MYSQL_PORT` : accès MySQL production.
- `CELERY_BROKER_URL` : broker Redis pour les envois SMS asynchrones.
- `CELERY_TASK_ALWAYS_EAGER` : `True` en local sans Redis, `False` en production.
- `DJANGO_LOG_LEVEL`, `SMS_LOG_LEVEL` : niveau des journaux applicatifs.
- `SMS_API_BASE_URL` : URL de la gateway SMS.
- `SMS_API_KEY_BASE64` : credential Basic encodé en base64.
- `SMS_API_FROM` : expéditeur par défaut.

## Vérifications utiles

```bash
python manage.py check
python manage.py test
```

## Préparation production

Configurer au minimum :

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=une-cle-longue-et-secrete
DJANGO_ALLOWED_HOSTS=sms.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://sms.example.com
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_SSL_REDIRECT=True
DB_ENGINE=mysql
MYSQL_DATABASE=sms_pro
MYSQL_USER=sms_pro_user
MYSQL_PASSWORD=mot-de-passe-fort
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
CELERY_TASK_ALWAYS_EAGER=False
```

Collecter les fichiers statiques :

```bash
python manage.py collectstatic
```

Vérification déploiement :

```bash
python manage.py check --deploy
```

Vérification de cohérence des données :

```bash
python manage.py check_data_integrity
python manage.py check_data_integrity --fail-on-issues
```

Les envois immédiats et campagnes sont mis en file Celery. En production,
lancer au minimum :

```bash
celery -A sms_platform worker --loglevel=INFO
celery -A sms_platform beat --loglevel=INFO
```

La commande `process_scheduled_sms` reste disponible comme outil de secours,
mais ne doit pas tourner en même temps que Celery Beat pour éviter les doublons.

## Déploiement Linode avec MySQL

Voir aussi [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) pour la checklist
operationnelle a suivre le jour du deploiement.

Installer les paquets système :

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential pkg-config \
  default-libmysqlclient-dev mysql-server redis-server nginx git
```

Créer la base MySQL :

```sql
CREATE DATABASE sms_pro CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sms_pro_user'@'localhost' IDENTIFIED BY 'mot-de-passe-fort';
GRANT ALL PRIVILEGES ON sms_pro.* TO 'sms_pro_user'@'localhost';
FLUSH PRIVILEGES;
```

Déployer le code :

```bash
cd /var/www
sudo git clone <url-github-du-projet> sms_pro
sudo chown -R $USER:www-data sms_pro
cd sms_pro
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.production.example .env
```

Modifier `.env` sur le serveur avec le domaine, les accès MySQL et les clés SMS,
puis exécuter :

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
python manage.py check_data_integrity --fail-on-issues
```

Service systemd Gunicorn :

```ini
[Unit]
Description=SMS Pro Gunicorn
After=network.target mysql.service
Requires=mysql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/sms_pro
EnvironmentFile=/var/www/sms_pro/.env
RuntimeDirectory=sms_pro
RuntimeDirectoryMode=0755
ExecStart=/var/www/sms_pro/venv/bin/gunicorn sms_platform.wsgi:application \
  --workers 3 --bind unix:/run/sms_pro/sms_pro.sock
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Services systemd Celery :

```bash
sudo cp deploy/sms_pro_celery_worker.service.example /etc/systemd/system/sms_pro_celery_worker.service
sudo cp deploy/sms_pro_celery_beat.service.example /etc/systemd/system/sms_pro_celery_beat.service
sudo systemctl enable --now sms_pro_celery_worker sms_pro_celery_beat
```

Nginx :

```nginx
server {
    server_name sms.example.com;

    location /static/ {
        alias /var/www/sms_pro/staticfiles/;
    }

    location / {
        proxy_pass http://unix:/run/sms_pro/sms_pro.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activer le service :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sms_pro
sudo nginx -t
sudo systemctl reload nginx
```
