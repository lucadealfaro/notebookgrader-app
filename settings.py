"""
This is an optional file that defined app level settings such as:
- database settings
- session settings
- i18n settings
This file is provided as an example:
"""
import os
from py4web.core import required_folder, URL

# Is this a testing or prod instance?
IS_TEST = os.getcwd().startswith("/Users/")

# db settings
APP_FOLDER = os.path.dirname(__file__)
APP_NAME = os.path.split(APP_FOLDER)[-1]
# DB_FOLDER:    Sets the place where migration files will be created
#               and is the store location for SQLite databases
DB_FOLDER = required_folder(APP_FOLDER, "databases")
DB_URI = "sqlite://storage.db"
DB_POOL_SIZE = 1
DB_MIGRATE = True
DB_FAKE_MIGRATE = False  # maybe?

MAX_GRADES_24H = 100 if IS_TEST else 5

# location where static files are stored:
STATIC_FOLDER = required_folder(APP_FOLDER, "static")

# location where to store uploaded files:
# UPLOAD_FOLDER = required_folder(APP_FOLDER, "uploads")

# send email on registration
VERIFY_EMAIL = False

# account requires to be approved ?
REQUIRES_APPROVAL = False

# ALLOWED_ACTIONS:
# ["all"]
# ["login", "logout", "request_reset_password", "reset_password", "change_password", "change_email", "update_profile"]
# if you add "login", add also "logout"
ALLOWED_ACTIONS = ["all"]


# email settings
SMTP_SSL = False
SMTP_SERVER = None
SMTP_SENDER = "you@example.com"
SMTP_LOGIN = "username:password"
SMTP_TLS = False

# session settings
SESSION_TYPE = "database"
SESSION_SECRET_KEY = "<session-secret-key>" # replace this with a uuid
MEMCACHE_CLIENTS = ["127.0.0.1:11211"]
REDIS_SERVER = "localhost:6379"

# logger settings
LOGGERS = [
    "warning:stdout"
]  # syntax "severity:filename" filename can be stderr or stdout

# single sign on Google (will be used if provided)
OAUTH2GOOGLE_CLIENT_ID = None
OAUTH2GOOGLE_CLIENT_SECRET = None

# Our sign in on Google, with credentials
GOOGLE_SCOPED_CLIENT_SECRETS = os.path.join(APP_FOLDER, "private/client_secret.apps.googleusercontent.com.json")

# single sign on Okta (will be used if provided. Please also add your tenant
# name to py4web/utils/auth_plugins/oauth2okta.py. You can replace the XXX
# instances with your tenant name.)
OAUTH2OKTA_CLIENT_ID = None
OAUTH2OKTA_CLIENT_SECRET = None

# single sign on Google (will be used if provided)
OAUTH2FACEBOOK_CLIENT_ID = None
OAUTH2FACEBOOK_CLIENT_SECRET = None

# enable PAM
USE_PAM = False

# enable LDAP
USE_LDAP = False
LDAP_SETTINGS = {
    "mode": "ad",
    "server": "my.domain.controller",
    "base_dn": "ou=Users,dc=domain,dc=com",
}

# i18n settings
T_FOLDER = required_folder(APP_FOLDER, "translations")

# Celery settings
USE_CELERY = False
CELERY_BROKER = "redis://localhost:6379/0"

COLAB_BASE = "https://colab.research.google.com/drive/"

# You need to provide your own private settings :-)
from .private.private_settings import (
    # These are the DB parameters.
    DB_USER, DB_PASSWORD, DB_CONNECTION, DB_NAME,
    # Email of admin.
    ADMIN_EMAIL,
    # GCS buckets
    GCS_TEST_BUCKET, GCS_PROD_BUCKET, GCS_SUBMISSIONS_BUCKET,
    # Queue info.
    STUDENT_GRADING_QUEUE_NAME, STUDENT_GRADING_QUEUE_PROJECT, STUDENT_GRADING_QUEUE_LOCATION,
    FEEDBACK_QUEUE_NAME, FEEDBACK_QUEUE_LOCATION, FEEDBACK_QUEUE_PROJECT,
    QUEUE_SERVICE_ACCOUNT, GRADING_FUNCTION_URL, FEEDBACK_FUNCTION_URL
)

if IS_TEST:
    IS_CLOUD = False
    GCS_BUCKET = GCS_TEST_BUCKET
    GRADING_URL = "http://localhost:8080"
    FEEDBACK_URL = "http://localhost:8088"
else:
    IS_CLOUD = True
    GCS_BUCKET = GCS_PROD_BUCKET
    GRADING_URL = GRADING_FUNCTION_URL
    FEEDBACK_URL = FEEDBACK_FUNCTION_URL

MIN_TIME_BETWEEN_GRADE_REQUESTS = 12 # Seconds
MAX_AGE_AI_PENDING_REQUEST = 60 * 60 # Seconds
STUDENT_GRADING_USES_QUEUE = IS_CLOUD


# Google Cloud Database
CLOUD_DB_URI = "google:MySQLdb://{DB_USER}:{DB_PASSWORD}@/{DB_NAME}?unix_socket=/cloudsql/{DB_CONNECTION}".format(
    DB_USER=DB_USER,
    DB_NAME=DB_NAME,
    DB_PASSWORD=DB_PASSWORD,
    DB_CONNECTION=DB_CONNECTION
)
CLOUD_DB_POOL_SIZE = 1
CLOUD_DB_MIGRATE = False # IMPORTANT!
CLOUD_DB_FAKE_MIGRATE = False

from .private.private_settings import ADMIN_EMAIL
