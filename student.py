import datetime
import json
import nbformat
import requests
import time

from py4web import action, request, redirect, URL, HTTP
from .common import db, session, auth
from .models import get_user_email
from .settings import APP_FOLDER, COLAB_BASE, GCS_BUCKET, GCS_SUBMISSIONS_BUCKET
from .settings import MIN_TIME_BETWEEN_GRADE_REQUESTS
from .settings import GRADING_URL, FEEDBACK_URL

from .common import flash, url_signer, gcs
from .util import upload_to_drive, read_from_drive, long_random_id, random_id, send_function_request
from .run_notebook import match_notebooks
from .notebook_logic import remove_all_hidden_tests, extract_awarded_points, is_notebook_well_formed
from .models import build_drive_service, get_assignment_teachers

from .api_homework_grid import HomeworkGrid
from .api_grades_grid import StudentGradesGrid

# Debug
# from google.auth.exceptions import RefreshError

homework_grid = HomeworkGrid('homework-grid')
student_grades_grid = StudentGradesGrid('student-grades-grid')


def share_assignment_with_student(assignment):
    """Shares an assignment with a student, creating the Google Colab,
    and returning its id."""
    notebook_json = gcs.read(GCS_BUCKET, assignment.student_id_gcs)
    drive_service = build_drive_service()
    student_drive_id = upload_to_drive(drive_service, notebook_json.decode('utf-8'),
                                       assignment.name,
                                       write_share=get_assignment_teachers(assignment.id))
    return student_drive_id

@action('invite/<access_url>')
@action.uses('invite.html', db, auth.user)
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
        return dict(
            name=assignment.name,
            message="You are already participating in this assignment.")
    # Checks for any domain restrictions.
    if assignment.domain_restriction:
        user_domain = get_user_email().split("@")[-1]
        if user_domain != assignment.domain_restriction:
            dom = assignment.domain_restriction
            msg = """This assignment is only available to students in the {} domain.
            To access it, please log out, and log in again using an account of the form
            yourname@{}. 
            """.format(dom, dom)
            return dict(name=assignment.name, message=msg)
    # If the notebook does not exist, or the assignment is not available,
    # students cannot participate.
    now = datetime.datetime.utcnow()
    if now > assignment.available_until:
        return dict(name=assignment.name, message="The assignment has already closed.")
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
    print("Redirect 3")
    redirect(URL('student-home'))

@action('student-home')
@action.uses('student_home.html', db, flash, auth.user, homework_grid)
def student_home():
    return dict(
        has_no_homework=db(db.homework.student == get_user_email()).isempty(),
        grid=homework_grid(),
    )


@action('homework/<id>')
@action.uses('homework.html', db, auth.user)
def homework(id=None):
    """Displays details on a student's homework."""
    homework = db.homework[id]
    if homework is None or homework.student != get_user_email():
        redirect(URL('student-home'))
    assignment = db.assignment[homework.assignment_id]
    return dict(
        assignment_name=assignment.name,
        homework_api_url=URL('api-homework-details', id, signer=url_signer),
        homework_grades_url=URL('api-homework-grades', id, signer=url_signer),
        grade_homework_url=URL('grade-homework', id, signer=url_signer),
        obtain_assignment_url=URL('obtain-assignment', id, signer=url_signer),
        error_url=URL('credentials_error'),
        internal_error_url=URL('internal_error'),
    )


@action('api-homework-details/<id>', method="GET")
@action.uses(db, auth.user, url_signer.verify())
def api_homework_details(id=None):
    """Returns the details of a homework, except its list of grades."""
    homework = db.homework[id]
    if homework is None or homework.student != get_user_email():
        raise HTTP(403)
    assignment = db.assignment[homework.assignment_id]
    assert assignment is not None
    return dict(
        submission_deadline=assignment.submission_deadline.isoformat(),
        available_from=assignment.available_from.isoformat(),
        available_until=assignment.available_until.isoformat(),
        max_in_24h=assignment.max_submissions_in_24h_period,
        can_obtain_notebook=assignment.master_id_gcs is not None,
        drive_url=None if homework.drive_id is None else COLAB_BASE + homework.drive_id,
        num_ai_feedback = assignment.ai_feedback or 0,
    )

@action('api-homework-grades/<id>', method="GET")
@action.uses(db, auth.user, url_signer.verify())
def api_homework_grades(id=None):
    """Returns the grades the student received in the homeworks."""
    homework = db.homework[id]
    if homework is None or homework.student != get_user_email():
        raise HTTP(403)
    grades = db(db.grade.homework_id == id).select(orderby=~db.grade.grade_date)
    grades_list = [
        dict(id=g.id,
             is_valid=g.is_valid,
             grade="{:.2f}".format(g.grade),
             grade_date=g.grade_date.isoformat(),
             feedback=None if g.drive_id is None else COLAB_BASE + g.drive_id,
             ai_url=URL('api-ai-feedback', g.id, signer=url_signer),
        ) for g in grades]
    # I also want to know if there are any pending grades.
     
    has_pending_grades = not db((db.grading_request.homework_id == id) &
                                (db.grading_request.completed == False)).isempty()
    last_request = db(db.grading_request.homework_id == id).select(
        orderby=~db.grading_request.created_on).first()
    return dict(    
        grades=grades_list,
        has_pending_grades=has_pending_grades,
        most_recent_request=None if last_request is None 
        else last_request.created_on.isoformat(),
        )


@action('grade-homework/<id>', method=["POST"])
@action.uses(db, auth.user, url_signer.verify())
def grade_homework(id=None):
    homework = db.homework[id]
    assignment = db.assignment[homework.assignment_id]
    assert homework is not None and assignment is not None
    now = datetime.datetime.utcnow()
    student = get_user_email()
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
                      (db.grading_request.student == student)).select(
        orderby=~db.grading_request.created_on).first()
    if (last_request is not None and
            now - last_request.created_on < datetime.timedelta(seconds=MIN_TIME_BETWEEN_GRADE_REQUESTS)):
        return dict(
            is_error=True,
            outcome="You can ask for grading only once every {} seconds.".format(MIN_TIME_BETWEEN_GRADE_REQUESTS))
    # The assignment can be graded.
    # Reads the student assignment.
    drive_service = build_drive_service()
    submission_json = read_from_drive(drive_service, homework.drive_id)
    # Checks for the well-formedness of the notebook.
    is_well_formed, cell_source, reason = is_notebook_well_formed(submission_json)
    if not is_well_formed:
        # Gives feedback to the student immediately.
        return dict(
            is_error=True,
            outcome=reason,
            cell_source=cell_source,
        )
    # Reads the master copy.
    master_json = gcs.read(GCS_BUCKET, assignment.master_id_gcs)
    # Saves the submission json, to have a record of what has been graded.
    submission_id_gcs = long_random_id()
    gcs.write(GCS_SUBMISSIONS_BUCKET, submission_id_gcs, submission_json,
              type="application/json")
    # Matches the notebooks.
    master_nb = nbformat.reads(master_json, as_version=4)
    submission_nb = nbformat.reads(submission_json, as_version=4)
    # Produces a clean notebook by matching the cells of master and submission.
    test_nb = match_notebooks(master_nb, submission_nb)
    # Creates the grade request.
    # The grading is via a callback.
    nonce = random_id()
    db.grading_request.insert(
        homework_id=homework.id,
        request_nonce=nonce,
        input_id_gcs=submission_id_gcs,
    )
    db.commit() # So no db work pending.
    # Enqueues the grade request.
    payload = dict(
        nonce=nonce,
        notebook_json=nbformat.writes(test_nb, 4),
        callback_url = URL('receive-grade', scheme=True)
    )
    send_function_request(payload, GRADING_URL)
    return dict(is_error=False,
                watch=True,
                outcome="Your request has been enqueued, and a new grade will be available soon.")


@action('request_ai_feedback/<id>')
@action.uses(db, session, auth.user, url_signer.verify())
def request_ai_feedback(id=None):
    # Gets the grade and assignment. 
    info = db((db.grade.id == id) & 
              (db.grade.homework_id == db.homework.id) &
              (db.homework.assignment_id == db.assignment.id)).select().first()
    if info is None:
        raise HTTP(403)
    # Checks how many grades have feedback already requested. 
    num_given_ai_feedback = db(
        (db.grade.homework_id == info.homework.id) &
        (db.grade.student == get_user_email()) &
        (db.grading_request.grade_id == db.grade.id)
    ).count()
    max_num_ai_feedback = info.assignment.ai_feedback or 0
    if num_given_ai_feedback >= max_num_ai_feedback:
        # Exhausted the feedback. 
        raise HTTP(403)
    # Prepares the information for the feedback: the master notebook, and the student notebook.
    master_json = gcs.read(GCS_BUCKET, info.assignment.master_id_gcs)
    submission_json = gcs.read(GCS_SUBMISSIONS_BUCKET, info.submission_id_gcs)
    # Produces a clean notebook by matching the cells of master and submission.
    master_nb = nbformat.reads(master_json, as_version=4)
    submission_nb = nbformat.reads(submission_json, as_version=4)
    test_nb = match_notebooks(master_nb, submission_nb)
    # Creates the grade request.
    # The grading is via a callback.
    nonce = random_id()
    db.ai_feedback_request.insert(
        grade_id=info.grade.id,
        request_nonce=nonce,
    )
    db.commit() # So no db work pending.
    # Enqueues the grade request.
    payload = dict(
        nonce=nonce,
        master_json=master_json,
        student_json=nbformat.writes(test_nb, 4),
        callback_url = URL('receive-ai-feedback', scheme=True)
    )
    send_function_request(payload, FEEDBACK_URL)
    redirect(URL('homework', info.homework.id))


@action('receive-grade', method=["POST"])
@action.uses(db, session)
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
    print("Grading request for assignment id:", assignment.id)
    now = datetime.datetime.utcnow()
    is_valid = grading_request.created_on < assignment.submission_deadline
    process_grade(homework, assignment, grading_request.created_on,
                  grading_request.student, is_valid, points, graded_json,
                  submission_id_gcs=grading_request.input_id_gcs)
    # Marks that the request has been done.
    grading_request.completed = True
    grading_request.grade = points
    grading_request.delay = (now - grading_request.created_on).total_seconds()
    grading_request.update_record()
    return "ok"


def process_grade(homework, assignment, grade_date, student, is_valid, points, notebook_json,
                  submission_id_gcs=None):
    """Processes a grading outcome, whether immediate or via callback."""
    # Removes the hidden tests from the feedback.
    feedback_nb = nbformat.reads(notebook_json, as_version=4)
    remove_all_hidden_tests(feedback_nb)
    feedback_json = nbformat.writes(feedback_nb, 4)
    # Uploads the feedback.
    feedback_name = "Feedback for {} {}, on {}".format(
        assignment.name, get_user_email(), grade_date.isoformat()
    )
    print("Building credentials for:", student)
    drive_service = build_drive_service(user=student)
    # We share with the teachers in write mode so that they can go back
    # in the revision history.
    write_share = get_assignment_teachers(assignment.id)
    feedback_id = upload_to_drive(drive_service, feedback_json,
                                  feedback_name, write_share=write_share, locked=True)
    # We store the feedback in GCS.
    feedback_id_gcs = long_random_id()
    gcs.write(GCS_SUBMISSIONS_BUCKET, feedback_id_gcs, feedback_json)
    # We use the time of submission to determine validity.
    db.grade.insert(
        student=student,
        assignment_id=assignment.id,
        grade_date=grade_date,
        homework_id=homework.id,
        grade=points,
        submission_id_gcs=submission_id_gcs,
        feedback_id_gcs=feedback_id_gcs,
        drive_id=feedback_id,
        is_valid=is_valid,
        cell_id_to_points=json.dumps(extract_awarded_points(feedback_nb)),
    )
    # Updates the grade in the homework.
    if is_valid:
        homework.grade = max([0] + list(filter(None, [homework.grade, points])))
    else:
        homework.has_invalid_grade = True
    homework.update_record()


@action('receive-ai-feedback', method=["POST"])
@action.uses(db, session)
def receive_ai_feedback():
    nonce = request.params.nonce
    feedback_json = request.params.feedback_json
    had_errors = request.params.had_errors
    assert not had_errors
    ai_feedback_request = db(db.ai_feedback_request.request_nonce == nonce).select().first()
    if ai_feedback_request is None:
        return "No request"
    if ai_feedback_request.completed:
        return "Already done"
    # Writes the feedback.
    now = datetime.datetime.utcnow()
    grade = db.grade[ai_feedback_request.grade_id]
    assignment = db.assignment[grade.assignment_id]
    assert grade is not None and assignment is not None
    feedback_name = "AI Feedback for {} {}".format(
        assignment.name, grade.student, now.isoformat()
    )
    print("Building credentials for:", grade.student)
    drive_service = build_drive_service(user=grade.student)
    # We share with the teachers in write mode so that they can go back
    # in the revision history.
    write_share = get_assignment_teachers(assignment.id)
    feedback_id_drive = upload_to_drive(drive_service, feedback_json,
                                        feedback_name, write_share=write_share, locked=True)
    # We store the feedback in GCS.
    ai_feedback_id_gcs = long_random_id()
    gcs.write(GCS_SUBMISSIONS_BUCKET, ai_feedback_id_gcs, feedback_json)
    # Updates the feeback ids. 
    grade.ai_feedback_id_gcs = ai_feedback_id_gcs
    grade.ai_feedback_id_drive = feedback_id_drive
    grade.update_record()
    # Marks that the request has been done.
    ai_feedback_request.completed = True
    ai_feedback_request.delay = (now - ai_feedback_request.created_on).total_seconds()
    ai_feedback_request.update_record()
    return "ok"


@action('obtain-assignment/<id>', method=["POST"])
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


