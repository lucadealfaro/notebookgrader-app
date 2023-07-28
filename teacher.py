import json
import os

from py4web import action, request, abort, redirect, URL, Flash
from pydal import Field
from yatl.helpers import A, BUTTON, SPAN
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated, flash
from py4web.utils.url_signer import URLSigner
from py4web.utils.form import Form, FormStyleBulma
from .models import get_user_email
from .settings import APP_FOLDER, COLAB_BASE

# Google imports
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import google.oauth2.credentials

from .controllers import flash, url_signer

from .api_assignment_form import AssignmentFormCreate, AssignmentFormEdit, AssignmentFormView

# The ID is the ID of the course for which the assignment is created.
form_assignment_create = AssignmentFormCreate('api-assignment-create',
                                              redirect_url='teacher-home',
                                              signer=url_signer)
# The ID is the ID of the assignment.  This form is used for instructors.
form_assignment_view = AssignmentFormView('api-assignment-view',
                                          signer=url_signer)
# The ID is the ID of the assignment.  This form is used for instructors.
form_assignment_edit = AssignmentFormEdit('api-assignment-edit',
                                          redirect_url='teacher-home',
                                          signer=url_signer)

@action('teacher-home')
@action.uses('teacher_home.html', db, auth.user)
def teacher_home():
    return dict()

@action('create-assignment')
@action.uses('create_assignment.html', db, auth.user, form_assignment_create)
def create_assignment():
    form = form_assignment_create()
    return dict(form=form)
