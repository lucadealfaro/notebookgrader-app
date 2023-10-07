import csv
import datetime
import io
import json
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
from .util import random_id, long_random_id, upload_to_drive, send_grading_request
from .notebook_logic import create_master_notebook, produce_student_version, InvalidCell

from .api_assignment_form import AssignmentFormCreate, AssignmentFormEdit, AssignmentFormView
from .api_assignment_grid import TeacherAssignmentGrid
from .api_participants_grid import ParticipantsGrid
from .api_homework_details_grid import HomeworkDetailsGrid


# The ID is the ID of the course for which the assignment is created.
form_assignment_create = AssignmentFormCreate('api-assignment-create',
                                              redirect_url='teacher-view-assignment')
# The ID is the ID of the assignment.  This form is used for instructors.
form_assignment_view = AssignmentFormView('api-assignment-view')
# The ID is the ID of the assignment.  This form is used for instructors.
form_assignment_edit = AssignmentFormEdit('api-assignment-edit',
                                          redirect_url='teacher-view-assignment')
teacher_assignment_grid = TeacherAssignmentGrid('api-teacher-assignment-grid')
grid_participants = ParticipantsGrid('api-participants-grid')
grid_homework_details = HomeworkDetailsGrid('api-homework-details-grid')

@action('teacher-home')
@action.uses('teacher_home.html', db, auth.user, teacher_assignment_grid)
def teacher_home():
    return dict(grid=teacher_assignment_grid())

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
    if assignment is None or not can_access_assignment(id):
        redirect(URL('teacher-home'))
    is_owner = assignment.owner == get_user_email()
    # Displays the assignment.
    form = form_assignment_view(id=id)
    return dict(
        form=form,
        assignment_id=assignment.id,
        is_owner=is_owner,
        change_access_url=URL('change-access-url', id, signer=url_signer),
        notebook_version_url=URL('notebook-version', id, signer=url_signer),
        upload_url=URL('upload-notebook', id, signer=url_signer) if is_owner else None,
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
        is_owner = assignment.owner == get_user_email()
        if is_owner:
            assignment.access_url = random_id()
            assignment.update_record()
    return dict(access_url=URL('invite', assignment.access_url, scheme=True))

@action('notebook-version/<id>', method=['GET'])
@action.uses(db, auth.user, url_signer.verify())
def notebook_version(id=None):
    assignment = db.assignment[id]
    return dict(
        instructor_version=COLAB_BASE + assignment.master_id_drive if assignment.master_id_drive else None,
        student_version=COLAB_BASE + assignment.student_id_drive if assignment.student_id_drive else None,
    )

@action('upload-notebook/<id>', method=['GET', 'POST'])
@action.uses(db, auth.user, url_signer.verify())
def upload_notebook(id=None):
    assignment = db.assignment[id]
    if request.method == "GET":
        # Nothing special implemented here.
        return "ok"
    # This is a POST for the file.
    notebook_json = request.params.notebook_content
    date_string = request.params.date_string or datetime.datetime.utcnow().isoformat()
    # Tries to process the notebook
    try:
        master_notebook_json, total_points, test_list = create_master_notebook(notebook_json)
    except Exception as e:
        return dict(error="Your notebook is in an invalid format. Please upload a valid notebook.")
    assignment.max_points = total_points
    assignment.test_ids = json.dumps(test_list)
    # Produces the student version.
    student_notebook_json = produce_student_version(master_notebook_json)
    # Runs the instructor notebook.
    # Enqueues the request.
    payload = dict(
        notebook_json=master_notebook_json,
    )
    r = send_grading_request(payload, is_student=False)
    res = r.json()
    points = res.get("points")
    has_errors = res.get("had_errors")
    master_notebook_json = res.get("graded_json")
    # Puts both versions on GCS.
    if assignment.master_id_gcs is None:
        create_notebooks = True
        assignment.master_id_gcs = long_random_id() + ".json"
        assignment.student_id_gcs = long_random_id() + ".json"
    gcs.write(GCS_BUCKET, assignment.master_id_gcs, master_notebook_json,
              type="application/json")
    gcs.write(GCS_BUCKET, assignment.student_id_gcs, student_notebook_json,
              type="application/json")
    # Now shares both notebooks to drive.
    drive_service = build_drive_service()
    master_file_name = "{}, version: {}".format(assignment.name, date_string)
    student_file_name = "{}, version: {}".format(assignment.name, date_string)
    assignment.master_id_drive = upload_to_drive(
        drive_service, master_notebook_json, master_file_name, id=assignment.master_id_drive)
    assignment.student_id_drive = upload_to_drive(
        drive_service, student_notebook_json, student_file_name, id=assignment.student_id_drive)
    assignment.update_record()
    return dict(
        error="The notebook could not be executed correctly, please check the results." if has_errors else None,
        instructor_version=COLAB_BASE + assignment.master_id_drive,
        student_version=COLAB_BASE + assignment.student_id_drive,
    )

@action('notebook-guidelines')
@action.uses('notebook_guidelines.html', db, auth)
def notebook_guidelines():
    return dict()

@action('edit-assignment/<id>')
@action.uses('edit_assignment.html', db, auth.user, form_assignment_edit)
def edit_assignment(id=None):
    assignment = db.assignment[id]
    if assignment is None or assignment.owner != get_user_email():
        redirect(URL('teacher-home'))
    form = form_assignment_edit(id=id, cancel_url=URL('teacher-view-assignment', id))
    return dict(form=form)

@action('delete-assignment/<id>', method=["GET", "POST"])
@action.uses('delete_assignment.html', db, auth.user)
def delete_assignment(id=None):
    # Checks permissions.
    assignment = db.assignment[id]
    if assignment is None or assignment.owner != get_user_email():
        redirect(URL('teacher-home'))
    form = Form([Field('confirm_deletion', 'boolean')],
                csrf_session=session, formstyle=FormStyleBulma)
    attrs = {
        "_onclick": "window.history.back(); return false;",
        "_class": "button is-default ml-2",
    }
    form.param.sidecar.append(A("Cancel", **attrs))
    if form.accepted:
        if form.vars['confirm_deletion']:
            if assignment.master_id_gcs is not None:
                gcs.delete(GCS_BUCKET, assignment.master_id_gcs)
            if assignment.student_id_gcs is not None:
                gcs.delete(GCS_BUCKET, assignment.student_id_gcs)
            db(db.assignment.id == id).delete()
            redirect(URL('teacher-home'))
        else:
            redirect(URL('teacher-view-assignment', id))
    # Displays the assignment.
    return dict(
        form=form,
        assignment=assignment,
    )


@action('participants/<id>')
@action.uses('participants.html', db, auth.user, grid_participants)
def participants(id=None):
    """Displays student notebooks and grades."""
    assignment = db.assignment[id]
    if assignment is None or not can_access_assignment(id):
        redirect(URL('teacher-home'))
    return dict(
        assignment=assignment,
        grid=grid_participants(id),
        download_url=URL('download-grades', id, signer=url_signer),
    )

@action('download-grades/<id>')
@action.uses(db, session, url_signer.verify())
def download_grades(id=None):
    """Returns a csv file."""
    s = io.StringIO()
    fieldnames = ["First Name", "Last Name", "Email", "Grade", "Max Grade"]
    writer = csv.DictWriter(s, fieldnames=fieldnames)
    writer.writeheader()
    assignment = db.assignment[id]
    filename = assignment.name.replace(" ", "_") + ".csv"
    for row in db((db.homework.assignment_id == id) &
                  (db.homework.student == db.auth_user.email)).select():
        writer.writerow({
            "First Name": row.auth_user.first_name,
            "Last Name": row.auth_user.last_name,
            "Email": row.auth_user.email,
            "Grade": row.homework.grade,
            "Max Grade": assignment.max_points,
        })
    return dict(csvfile=s.getvalue(), filename=filename)

@action('teacher-homework-details/<id>')
@action.uses('homework_details.html', db, auth.user, grid_homework_details)
def homework_details(id=None):
    """Displays the details on a homework: its list of grades."""
    homework = db.homework[id]
    if homework is None:
        redirect(URL('teacher-home'))
    assignment = db.assignment[homework.assignment_id]
    assert assignment is not None
    if not can_access_assignment(assignment.id):
        redirect(URL('teacher-home'))
    student = db(db.auth_user.email == homework.student).select().first()
    return dict(
        assignment=assignment,
        student=student,
        notebook_url=COLAB_BASE + homework.drive_id,
        grid=grid_homework_details(id),
    )


@action('toggle-grade-validity/<id>')
@action.uses(db, auth.user, url_signer.verify())
def toggle_grade_validity(id=None):
    grade = db.grade[id]
    assert grade is not None
    homework = db.homework[grade.homework_id]
    assert homework is not None
    grade.update_record(is_valid = not grade.is_valid)
    # Recomputes the highest valid grade.
    grades = db(db.grade.homework_id == homework.id).select().as_list()
    grade_list = [r["grade"] for r in grades if r["is_valid"]] + [0]
    homework.grade = max([0] + list(filter(None, grade_list)))
    homework.has_invalid_grade = any([(not r["is_valid"]) for r in grades])
    homework.update_record()
    redirect(URL('teacher-homework-details', homework.id))

# TODO:
# - Payments
