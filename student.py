import datetime
import json
import os
import time

from py4web import action, request, abort, redirect, URL, Flash
from pydal import Field
from yatl.helpers import A, BUTTON, SPAN
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated, flash
from py4web.utils.url_signer import URLSigner
from py4web.utils.form import Form, FormStyleBulma
from .models import get_user_email
from .settings import APP_FOLDER, COLAB_BASE, GCS_BUCKET

# Google imports
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import google.oauth2.credentials

from .common import flash, url_signer, gcs
from .util import build_drive_service, upload_to_drive

from .api_homework_grid import HomeworkGrid

homework_grid = HomeworkGrid('homework-grid')
@action('invite/<access_url>')
@action.uses(db, auth.user, flash)
def invite(access_url=None):
    if access_url is None:
        redirect(URL('student-home'))
    # One can try a failed invitation once a minute.
    t = time.time()
    if t - session['last_failed_invite_time'] < 60:
        redirect(URL('student-home'))
    assignment = db(db.assignment.access_url == access_url).select().first()
    if assignment is None:
        session['last_failed_invite_time'] = t
        redirect(URL('student-home'))
    # If the notebook does not exist, or the assignment is not available,
    # students cannot participate.
    now = datetime.datetime.utcnow()
    if assignment.student_id_gcs is None or assignment.available_from > now:
        flash.set("The assignment is not open yet.")
    # Is the student already in the assignment?
    membership = db((db.homework.student == get_user_email()) &
                    (db.homework.assignment_id == assignment.id)).select().first()
    if membership is not None:
        flash.set("You are already participating in this assignment.")
        redirect(URL('student-home'))
    # Adds the student to the assignment.
    # First, makes a copy of the assignment from gcs and puts it into drive.
    notebook_json = gcs.read(GCS_BUCKET, assignment.student_id_gcs)
    drive_service = build_drive_service()
    student_drive_id = upload_to_drive(drive_service, notebook_json, assignment.name,
                                       shared=assignment.owner)
    # Then, writes the new homework.
    db.homework.insert(
        student=get_user_email(),
        assignment_id=assignment.id,
        google_drive_id=student_drive_id,
    )
    redirect(URL('student-home'))

@action('student-home')
@action.uses('student_home.html', db, flash, auth.user, homework_grid)
def student_home():
    return dict(homework_grid=homework_grid())
