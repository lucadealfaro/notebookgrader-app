import datetime
import io

from py4web import action, request, abort, redirect, URL, Flash
from pydal import Field
from yatl.helpers import A, BUTTON, SPAN
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated, flash
from py4web.utils.url_signer import URLSigner
from py4web.utils.form import Form, FormStyleBulma
from .models import get_user_email, build_drive_service
from .settings import APP_FOLDER, COLAB_BASE, GCS_BUCKET

from .common import flash, url_signer, gcs
from .util import random_id, long_random_id, upload_to_drive
from .notebook_logic import create_master_notebook, produce_student_version, InvalidCell

from .api_assignment_form import AssignmentFormCreate, AssignmentFormEdit, AssignmentFormView
from .api_assignment_grid import TeacherAssignmentGrid


# The ID is the ID of the course for which the assignment is created.
form_assignment_create = AssignmentFormCreate('api-assignment-create',
                                              redirect_url='teacher-view-assignment')
# The ID is the ID of the assignment.  This form is used for instructors.
form_assignment_view = AssignmentFormView('api-assignment-view')
# The ID is the ID of the assignment.  This form is used for instructors.
form_assignment_edit = AssignmentFormEdit('api-assignment-edit',
                                          redirect_url='teacher-view-assignment')
teacher_assignment_grid = TeacherAssignmentGrid('api-teacher-assignment-grid')

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
    print("Assignment owner:", assignment.owner)
    if assignment is None or assignment.owner != get_user_email():
        redirect(URL('teacher-home'))
    # Displays the assignment.
    form = form_assignment_view(id=id)
    return dict(
        form=form,
        assignment_id=assignment.id,
        change_access_url=URL('change-access-url', id, signer=url_signer),
        notebook_version_url=URL('notebook-version', id, signer=url_signer),
        upload_url=URL('upload-notebook', id, signer=url_signer),
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
        master_notebook_json = create_master_notebook(notebook_json)
    except InvalidCell as e:
        return dict(error=str(e))
    # Produces the student version.
    student_notebook_json = produce_student_version(master_notebook_json)
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
        error=None,
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
    print("Assignment owner:", assignment.owner)
    if assignment is None or assignment.owner != get_user_email():
        redirect(URL('teacher-home'))
    form = form_assignment_edit(id=id, cancel_url=URL('teacher-view-assignment', id))
    return dict(form=form)

@action('delete-assignment/<id>', method=["GET", "POST"])
@action.uses('delete_assignment.html', db, auth.user)
def delete_assignment(id=None):
    # Checks permissions.
    assignment = db.assignment[id]
    print("Assignment owner:", assignment.owner)
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
            db(db.assignment.id == id).delete()
            redirect(URL('teacher-home'))
        else:
            redirect(URL('teacher-view-assignment', id))
    # Displays the assignment.
    return dict(
        form=form,
        assignment=assignment,
    )
