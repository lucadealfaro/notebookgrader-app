import datetime
import nbformat
import requests
import time

from py4web import action, request, abort, redirect, URL, Flash
from pydal import Field
from yatl.helpers import A, BUTTON, SPAN
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated, flash
from py4web.utils.url_signer import URLSigner
from py4web.utils.form import Form, FormStyleBulma
from .models import get_user_email
from .settings import APP_FOLDER, COLAB_BASE, GCS_BUCKET, MIN_TIME_BETWEEN_GRADE_REQUESTS

from .common import flash, url_signer, gcs
from .util import upload_to_drive, read_from_drive, long_random_id, random_id
from .run_notebook import match_notebooks
from .notebook_logic import remove_all_hidden_tests
from .models import build_drive_service
from .settings import GRADING_URL

from .api_homework_grid import HomeworkGrid
from .api_grades_grid import StudentGradesGrid

homework_grid = HomeworkGrid('homework-grid')
student_grades_grid = StudentGradesGrid('student-grades-grid')

def share_assignment_with_student(assignment):
    """Shares an assignment with a student, creating the Google Colab,
    and returning its id."""
    notebook_json = gcs.read(GCS_BUCKET, assignment.student_id_gcs)
    drive_service = build_drive_service()
    student_drive_id = upload_to_drive(drive_service, notebook_json.decode('utf-8'),
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
    if session.get('last_failed_invite_time') is not None and t - session.get('last_failed_invite_time') < 60:
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
    if now > assignment.available_until:
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
    return dict(grid=homework_grid())

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
    can_grade = can_grade and assignment.available_from < now < assignment.available_until
    can_grade = can_grade and num_grades_past_24h < assignment.max_submissions_in_24h_period
    return dict(
        homework=homework,
        assignment=assignment,
        grid=grid,
        can_grade=can_grade,
        grade_homework_url=URL('grade-homework', id, signer=url_signer),
        num_grades_past_24h=num_grades_past_24h,
        obtain_assignment_url=URL('obtain-assignment', id, signer=url_signer),
        homework_details_url=URL('student-homework-details', id, signer=url_signer),
    )

@action('grade-homework/<id>', method=["POST"])
@action.uses(db, auth.user, url_signer.verify())
def grade_homework(id=None):
    homework = db.homework[id]
    assignment = db.assignment[homework.assignment_id]
    assert homework is not None and assignment is not None
    now = datetime.datetime.utcnow()
    query = ((db.grade.homework_id == id) &
             (db.grade.student == get_user_email()) &
             (db.grade.grade_date > now - datetime.timedelta(hours=24)))
    num_grades_past_24h = db(query).count()
    is_valid = now < assignment.submission_deadline
    if homework.drive_id is None:
        return dict(
            is_error=True,
            outcome="You do not have an assignment to work on.")
    if not assignment.available_from < now < assignment.available_until:
        return dict(
            is_error=True,
            outcome="The assignment is not available for grading.")
    if num_grades_past_24h >= assignment.max_submissions_in_24h_period:
        return dict(
            is_error=True,
            outcome="You have already asked for {} grades in the past 24h.".format(num_grades_past_24h))
    # Checks previous requests for this homework.
    last_request = db((db.grading_request.homework_id == homework.id) &
                      (db.grading_request.student == get_user_email())).select(
        orderby=~db.grading_request.created_on).first()
    if (last_request is not None and
            now - last_request.created_on < datetime.timedelta(seconds=MIN_TIME_BETWEEN_GRADE_REQUESTS)):
        return dict(
            is_error=True,
            outcome="You can ask for grading only once every {} seconds.".format(MIN_TIME_BETWEEN_GRADE_REQUESTS))
    # The assignment can be graded.
    # Reads the master copy.
    master_json = gcs.read(GCS_BUCKET, assignment.master_id_gcs)
    # Reads the student assignment.
    drive_service = build_drive_service()
    submission_json = read_from_drive(drive_service, homework.drive_id)
    # Saves the submission json, to have a record of what has been graded.
    submission_id_gcs = long_random_id()
    gcs.write(GCS_BUCKET, submission_id_gcs, submission_json,
              type="application/json")
    # Creates the grade request.
    nonce = random_id()
    db.grading_request.insert(
        homework_id=homework.id,
        request_nonce=nonce,
        input_id_gcs=submission_id_gcs,
    )
    db.commit() # So no db work pending.
    # Matches the notebooks.
    master_nb = nbformat.reads(master_json, as_version=4)
    submission_nb = nbformat.reads(submission_json, as_version=4)
    # Produces a clean notebook by matching the cells of master and submission.
    test_nb = match_notebooks(master_nb, submission_nb)
    # Enqueues the grade request.
    payload = dict(
        nonce=nonce,
        notebook_json=nbformat.writes(test_nb, 4)
    )
    grading_url = GRADING_URL or URL('run-notebook', scheme=True).replace('notebookgrader', 'notebookrunner')
    r = requests.post(grading_url, json=payload)
    r.raise_for_status()
    return dict(is_error=False,
                watch=True,
                outcome="Your request has been enqueued, and a new grade will be available soon.")


@action('receive-grade', method=["POST"])
@action.uses(db)
def receive_grade():
    nonce = request.params.nonce
    graded_json = request.params.graded_json
    points = request.params.points
    had_errors = request.params.had_errors
    grading_request = db(db.grading_request.request_nonce == nonce).select().first()
    if grading_request is None:
        return "No request"
    if grading_request.completed:
        return "Already done"
    homework = db.homework[grading_request.homework_id]
    assignment = db.assignment[homework.assignment_id]
    now = datetime.datetime.utcnow()
    # Removes the hidden tests from the feedback.
    feedback_nb = nbformat.reads(graded_json, as_version=4)
    remove_all_hidden_tests(feedback_nb)
    feedback_json = nbformat.writes(feedback_nb, 4)
    # Uploads the feedback.
    feedback_name = "Feedback for {} {}, on {}".format(
        assignment.name, get_user_email(), now.isoformat()
    )
    drive_service = build_drive_service(user=grading_request.student)
    feedback_id = upload_to_drive(drive_service, feedback_json,
                                  feedback_name, shared=assignment.owner)
    # We use the time of submission to determine validity.
    is_valid = grading_request.created_on < assignment.submission_deadline
    db.grade.insert(
        student=grading_request.student,
        assignment_id=assignment.id,
        grade_date=now,
        homework_id=homework.id,
        grade=points,
        drive_id=feedback_id,
        is_valid=is_valid,
    )
    # Updates the grade in the homework.
    if is_valid:
        homework.grade = max(filter(None, [homework.grade, points]))
    else:
        homework.has_invalid_grade = True
    homework.update_record()
    # Marks that the request has been done.
    grading_request.completed = True
    grading_request.grade = points
    grading_request.delay = (now - grading_request.created_on).total_seconds()
    grading_request.update_record()
    return "ok"


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


@action('student-homework-details/<id>')
@action.uses(db, auth.user, url_signer.verify())
def homework_details(id=None):
    homework = db.homework[id]
    assert homework is not None and homework.student == get_user_email()
    assignment = db.assignment[homework.assignment_id]
    assert assignment is not None
    return dict(
        available_from=assignment.available_from.isoformat(),
        submission_deadline=assignment.submission_deadline.isoformat(),
        available_until=assignment.available_until.isoformat(),
        drive_url=None if homework.drive_id is None else COLAB_BASE + homework.drive_id
    )
