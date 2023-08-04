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
from .util import build_drive_service, upload_to_drive, read_from_drive, long_random_id
from .notebook_logic import grade_notebook

from .api_homework_grid import HomeworkGrid
from .api_grades_grid import StudentGradesGrid

homework_grid = HomeworkGrid('homework-grid')
student_grades_grid = StudentGradesGrid('student-grades-grid')

def share_assignment_with_student(assignment):
    """Shares an assignment with a student, creating the Google Colab,
    and returning its id."""
    notebook_json = gcs.read(GCS_BUCKET, assignment.student_id_gcs)
    drive_service = build_drive_service()
    student_drive_id = upload_to_drive(drive_service, notebook_json,
                                       assignment.name,
                                       shared=assignment.owner)
    return student_drive_id

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
    # Is the student already in the assignment?
    membership = db((db.homework.student == get_user_email()) &
                    (db.homework.assignment_id == assignment.id)).select().first()
    if membership is not None:
        flash.set("You are already participating in this assignment.")
        redirect(URL('student-home'))
    # If the notebook does not exist, or the assignment is not available,
    # students cannot participate.
    now = datetime.datetime.utcnow()
    if now > assignment.available.until:
        flash.set("The assignment has already closed.")
        redirect(URL('student-home'))
    if assignment.student_id_gcs is None or assignment.available_from > now:
        # The notebook is not accessible from the student yet.
        student_drive_id = None
    else:
        # The student can be shared the assignment on drive.
        student_drive_id = share_assignment_with_student(assignment)
    # Adds the student to the assignment.
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
    now = datetime.datetime.utcnow()
    query = ((db.grade.homework_id == id) &
             (db.grade.student == get_user_email()) &
             (db.grade.grade_date > now - datetime.timedelta(hours=24)))
    num_grades_past_24h = db(query).count()
    can_grade = homework.drive_id is not None
    can_grade = can_grade and assignment.available_from < now < assignment.until
    can_grade = can_grade and num_grades_past_24h < assignment.max_submissions_in_24h_period
    # We compute validity of a new grade now, since grading can take time.
    is_valid = now < assignment.submission_deadline
    if can_grade:
        form = Form([Field('grade_my_work_now', 'boolean')],
                    csrf_session=session, formstyle=FormStyleBulma)
        if form.accepted:
            if form.vars['grade_my_work_now']:
                # Reads the master copy.
                master_json = gcs.read(GCS_BUCKET, assignment.master_id_gcs)
                # Reads the student assignment.
                drive_service = build_drive_service()
                submission_json = read_from_drive(drive_service, homework.drive_id)
                # Saves the submission json, to have a record of what has been graded.
                submission_id_gcs = long_random_id()
                gcs.write(GCS_BUCKET, submission_id_gcs, submission_json,
                          type="application/json")
                # ---qui--- do the grading
                new_grade, feedback_json = grade_notebook(master_json, submission_json)
                # Uploads the feedback.
                feedback_name = "Feedback for {} {}, on {}".format(
                    assignment.name, get_user_email(), now.isoformat()
                )
                feedback_id = upload_to_drive(drive_service, feedback_json,
                                              feedback_name, shared=assignment.owner)
                db.grade.insert(
                    assignment_id=assignment.id,
                    grade_date=now,
                    homework_id=homework.id,
                    grade=new_grade,
                    input_id_gcs=submission_id_gcs,
                    drive_id=feedback_id,
                    is_valid=is_valid,
                )
            redirect(URL('homework', homework.id))
    else:
        form = None
    return dict(
        homework=homework,
        assignment=assignment,
        grid=grid,
        num_grades_past_24h=num_grades_past_24h,
        form=form,
        obtain_assignment_url=URL('obtain-assignment', id, signer=url_signer),
        homework_details_url=URL('homework-details', id, signer=url_signer),
    )

@action('obtain-assignment/<id>')
@action.uses(db, auth.user, url_signer.verify())
def obtain_assignment(id=None):
    homework = db.homework[id]
    assert homework is not None and homework.student == get_user_email()
    # If the drive id already exists, gives it.
    if homework.drive_id is not None:
        return dict(drive_id=homework.drive_id)
    assignment = db.assignment[homework.assignment_id]
    assert assignment is not None
    now = datetime.datetime.utcnow()
    if assignment.available_from < now < assignment.available_until:
        drive_id = share_assignment_with_student(assignment)
        homework.drive_id = drive_id
        homework.update_record()
    else:
        drive_id = None
    return dict(drive_url=None if drive_id is None else COLAB_BASE + drive_id)


@action('homework-details/<id>')
@action.uses(db, auth.user, url_signer.verify())
def homework_details(id=None):
    homework = db.homework[id]
    assert homework is not None and homework.student == get_user_email()
    assignment = db.assignment[homework.assignment_id]
    assert assignment is not None
    return dict(
        available_from=assignment.available_from,
        submission_deadline=assignment.submission_deadline,
        available_until=assignment.available_until,
        drive_url=None if homework.drive_id is None else COLAB_BASE + homework.drive_id
    )
