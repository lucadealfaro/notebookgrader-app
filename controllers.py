"""
This file defines actions, i.e. functions the URLs are mapped into
The @action(path) decorator exposed the function at URL:

    http://127.0.0.1:8000/{app_name}/{path}

If app_name == '_default' then simply

    http://127.0.0.1:8000/{path}

If path == 'index' it can be omitted:

    http://127.0.0.1:8000/

The path follows the bottlepy syntax.

@action.uses('generic.html')  indicates that the action uses the generic.html template
@action.uses(session)         indicates that the action uses the session
@action.uses(db)              indicates that the action uses the db
@action.uses(T)               indicates that the action uses the i18n & pluralization
@action.uses(auth.user)       indicates that the action requires a logged in user
@action.uses(auth)            indicates that the action requires the auth object

session, db, T, auth, and tempates are examples of Fixtures.
Warning: Fixtures MUST be declared with @action.uses({fixtures}) else your app will result in undefined behavior
"""

import json
import os

from py4web import action, request, abort, redirect, URL, Flash
from pydal import Field
from yatl.helpers import A, BUTTON, SPAN
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated
from py4web.utils.form import Form, FormStyleBulma
from .models import get_user_email, is_admin, build_drive_service
from .settings import APP_FOLDER, COLAB_BASE, GCS_BUCKET, GCS_SUBMISSIONS_BUCKET

# Google imports
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import google.oauth2.credentials

from .common import url_signer, gcs
from .util import upload_to_drive

@action('index')
@action.uses('index.html', db, auth, url_signer)
def index():
    return dict(
        # COMPLETE: return here any signed URLs you need.
        my_callback_url = URL('my_callback', signer=url_signer),
    )

@action('privacy_policy')
@action.uses('privacy_policy.html')
def privacy_policy():
    return dict()

@action('terms_of_use')
@action.uses('terms_of_use.html')
def terms_of_use():
    return dict()

@action('about')
@action.uses('about.html')
def about():
    return dict()


@action('admin_share/<source>/<id>')
@action.uses(db, auth.user, url_signer.verify())
def admin_share(source, id):
    """Shares the id from source (typically, a gcs id from a GCS)
    with the admin as a COLAB notebook."""
    if not is_admin():
        redirect(URL('index'))
    if source == "submission" and id is not None:
        # Reads the file from gcs.
        notebook_json = gcs.read(GCS_SUBMISSIONS_BUCKET, id)
        admin = get_user_email()
        print("Building credentials for:", admin)
        drive_service = build_drive_service(user=admin)
        # We share with the teachers in write mode so that they can go back
        # in the revision history.
        title = request.vars.title or "Submission"
        share_id = upload_to_drive(drive_service, notebook_json, title)
        redirect(COLAB_BASE + share_id)
    redirect(URL('index'))


@action('delete_personal_information', method=["GET", "POST"])
@action.uses('delete_personal_information.html', db, auth.user)
def delete_personal_information():
    form = Form([Field('yes_i_confirm', 'boolean')],
                csrf_session=session, formstyle=FormStyleBulma
                )
    attrs = {
        "_onclick": "window.history.back(); return false;",
        "_class": "button is-default ml-2",
    }
    form.param.sidecar.append(A("Cancel", **attrs))
    if form.accepted:
        if form.vars['yes_i_confirm']:
            # Deletes all user info.
            email = auth.current_user.get('email') if auth.current_user else None
            if email is not None:
                # Deletes the assignments owned.
                for row in db(db.assignment.owner == email).select():
                    delete_gcs(row.master_id_gcs)
                    delete_gcs(row.student_id_gcs)
                    # NOT the drive ones.
                db(db.assignment.owner == email).delete()
                # Deletes the things one can access (but not the things).
                db(db.access.user == email).delete()
                # Deletes the homework.  This also deletes all grades.
                db(db.homework.student == email).delete()
                # We leave the grading requests, as these are our logs and are
                # necessary to track abuse, but we delete the grades.
                db(db.grading_request.student == email).update(grade=None)
                # Credentials for Google.
                db(db.auth_credentials.email == email).delete()
                # Login information.
                db(db.auth_user.email == email).delete()
                # Finally, we delete the session information.
                # This logs the user out.
                auth.session.clear()
                redirect(URL('index'))
        else:
            redirect(URL('delete_personal_information'))
        redirect(URL('index'))
    return dict(form=form)


def delete_gcs(gcs_id):
    """Deletes an id from GCS."""
    if gcs_id is not None:
        gcs.delete(GCS_BUCKET, gcs_id)

@action("credentials_error")
@action.uses("credentials_error.html")
def credentials_errors():
    return dict()
