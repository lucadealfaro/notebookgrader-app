import csv
import datetime
import io
import nbformat
import requests

from py4web import action, request, abort, redirect, URL, Flash
from pydal import Field
from yatl.helpers import A, BUTTON, SPAN
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated, flash
from py4web.utils.form import Form, FormStyleBulma
from .models import get_user_email, build_drive_service, can_access_assignment
from .settings import APP_FOLDER, COLAB_BASE, GCS_BUCKET, ADMIN_EMAIL

from .common import flash, url_signer, gcs
from .util import random_id, long_random_id, upload_to_drive, grading_request

from .api_admin_assignment_grid import AdminAssignmentGrid


admin_assignment_grid = AdminAssignmentGrid('api-admin-assignment-grid')

@action('admin-home')
@action.uses('admin_home.html', db, auth.user, admin_assignment_grid)
def teacher_home():
    return dict(grid=admin_assignment_grid())
