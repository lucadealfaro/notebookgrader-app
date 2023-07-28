import json
import os
import uuid

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
from .util import random_id

from .api_assignment_form import AssignmentFormCreate, AssignmentFormEdit, AssignmentFormView

# The ID is the ID of the course for which the assignment is created.
form_assignment_create = AssignmentFormCreate('api-assignment-create',
                                              redirect_url='teacher-view-assignment',
                                              signer=url_signer,
                                              )
# The ID is the ID of the assignment.  This form is used for instructors.
form_assignment_view = AssignmentFormView('api-assignment-view',
                                          signer=url_signer)
# The ID is the ID of the assignment.  This form is used for instructors.
form_assignment_edit = AssignmentFormEdit('api-assignment-edit',
                                          redirect_url='teacher-view-assignment',
                                          signer=url_signer)

@action('teacher-home')
@action.uses('teacher_home.html', db, auth.user)
def teacher_home():
    return dict()

@action('create-assignment')
@action.uses('create_assignment.html', db, auth.user, form_assignment_create)
def create_assignment():
    form = form_assignment_create(cancel_url=URL('teacher-home'))
    return dict(form=form)


@action('teacher-view-assignment/<id>')
@action.uses('teacher_view_assignment.html', db, auth.user, form_assignment_view)
def teacher_view_assignment(id=None):
    # Checks permissions.
    assignment = db.assignment[id]
    print("Assignment owner:", assignment.owner)
    if assignment is None or assignment.owner != get_user_email():
        redirect(URL('teacher-home'))
    # Displays the assignment.
    form = form_assignment_view(id=id)
    return dict(
        form=form,
        assignment_id=assignment.id,
        change_access_url=URL('change-access-url', id, signer=url_signer),
    )

@action('change-access-url/<id>', method=["GET", "POST"])
@action.uses(db, auth.user, url_signer.verify())
def change_access_url(id=None):
    if request.method == "GET":
        assignment = db.assignment[id]
    elif request.method == "POST":
        assignment = db.assignment[id]
        if assignment is None:
            return dict(access_url=None)
        assignment.access_url = random_id()
        assignment.update_record()
    return dict(access_url=URL('invite', assignment.access_url, scheme=True))

@action('edit-assignment/<id>')
@action.uses('edit_assignment.html', db, auth.user, form_assignment_edit)
def edit_assignment(id=None):
    assignment = db.assignment[id]
    print("Assignment owner:", assignment.owner)
    if assignment is None or assignment.owner != get_user_email():
        redirect(URL('teacher-home'))
    form = form_assignment_edit(id=id, cancel_url=URL('teacher-view-assignment', id))
    return dict(form=form)