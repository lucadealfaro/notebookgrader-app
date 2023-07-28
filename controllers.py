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
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated, flash
from py4web.utils.form import Form, FormStyleBulma
from .models import get_user_email
from .settings import APP_FOLDER, COLAB_BASE

# Google imports
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import google.oauth2.credentials

from .common import url_signer, flash

@action('index')
@action.uses('index.html', db, auth, url_signer, flash)
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
                # Credentials for Google.
                db(db.auth_credentials.email == email).delete()
                # Login information.
                db(db.auth_user.email == email).delete()
                # INSERT HERE DELETION FROM ALL OTHER TABLES.
                # Finally, we delete teh session information.
                # This logs the user out.
                auth.session.clear()
                flash.set("All your personal information has been deleted.", sanitize=True)
                redirect(URL('index'))
        else:
            flash.set("No information is deleted unless you confirm.",
                      sanitize=True)
            redirect(URL('delete_personal_information'))
        redirect(URL('index'))
    return dict(form=form)


@action('share', method=["GET", "POST"])
@action.uses('share.html', db, auth.user)
def share():
    form = Form([Field('name')],
        csrf_session=session, formstyle=FormStyleBulma
    )
    attrs = {
        "_onclick": "window.history.back(); return false;",
        "_class": "button is-default ml-2",
    }
    form.param.sidecar.append(A("Cancel", **attrs))
    if form.accepted:
        # We share the notebook to the current user.
        file_path = os.path.join(APP_FOLDER, "temp_files/TestoutJuly2023.ipynb")
        mime = 'application/vnd.google.colaboratory'
        media = MediaFileUpload(file_path, mimetype=mime, resumable=True)
        file_meta = {'name': form.vars["name"]}
        # Reads the credentials.
        user_info = db(db.auth_credentials.email == get_user_email()).select().first()
        if not user_info:
            print("No user credentials")
            redirect(URL('index'))
        credentials_dict = json.loads(user_info.credentials)
        creds = google.oauth2.credentials.Credentials(**credentials_dict)
        drive_service = build('drive', 'v3', credentials=creds)
        upfile = drive_service.files().create(
            body=file_meta,
            media_body=media,
            fields='id').execute()
        file_id = upfile.get('id')
        print("file_id:", file_id)
        redirect(COLAB_BASE + file_id)

    return dict(form=form)