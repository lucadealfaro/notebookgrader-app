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
from .api_grades_grid import StudentGradesGrid

homework_grid = HomeworkGrid('homework-grid')
student_grades_grid = StudentGradesGrid('student-grades-grid')

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
        drive_id=student_drive_id,
    )
    redirect(URL('student-home'))

@action('student-home')
@action.uses('student_home.html', db, flash, auth.user, homework_grid)
def student_home():
    return dict(homework_grid=homework_grid())

@action('homework/<id>')
@action.uses('homework.html', db, auth.user, student_grades_grid)
def homework(id=None):
    """Displays details on a student's homework."""
    homework = db.homework[id]
    if homework is None or homework.student != get_user_email():
        redirect(URL('student-home'))
    assignment = db.assignment[homework.assignment_id]
    grid = student_grades_grid(id=id)
    # Checks if we can grade the current version.
    query = ((db.grade.homework_id == id) &
             (db.grade.student == get_user_email()) &
             (db.grade.grade_date > datetime.datetime.utcnow() - datetime.timedelta(hours=24)))
    num_grades_past_24h = db(query).count()
    can_grade = num_grades_past_24h < assignment.max_submissions_in_24h_period
    if can_grade:
        form = Form([Field('grade_my_work_now', 'boolean')],
                    csrf_session=session, formstyle=FormStyleBulma)
        if form.accepted:
            if form.vars['grade_my_work_now']:
                # ---qui--- do the grading
                redirect(URL('homework', homework.id))
    else:
        form = None
    return dict(
        homework=homework,
        assignment=assignment,
        grid=grid,
        num_grades_past_24h=num_grades_past_24h,
        form=form,
    )
