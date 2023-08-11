"""
This file defines the database models
"""

import datetime
import json
from .common import db, Field, auth
from pydal.validators import IS_INT_IN_RANGE
import re
from .util import random_id
from py4web import redirect, URL

from googleapiclient.discovery import build
import google.oauth2.credentials


def get_user_email():
    return auth.current_user.get('email') if auth.current_user else None

def get_time():
    return datetime.datetime.utcnow()

def build_drive_service(user=None):
    # Reads the credentials.
    user = user or get_user_email()
    user_info = db(
        db.auth_credentials.email == user).select().first()
    if not user_info:
        print("No user credentials")
        redirect(URL('index'))
    credentials_dict = json.loads(user_info.credentials)
    creds = google.oauth2.credentials.Credentials(**credentials_dict)
    drive_service = build('drive', 'v3', credentials=creds)
    return drive_service


### Define your table below
#
# db.define_table('thing', Field('name'))
#
## always commit your models to avoid problems later

db.define_table(
    'assignment',
    Field('owner', default=get_user_email), # Email of owner.
    Field('name'), # Assignment name.
    Field('domain_restriction'),
    Field('created_on', 'datetime', default=get_time),
    Field('master_id_gcs'), # Locations of master and student notebooks
    Field('student_id_gcs'), # in gcs and drive.
    Field('master_id_drive'),
    Field('student_id_drive'),
    Field('available_from', 'datetime'),
    Field('available_until', 'datetime'),
    Field('submission_deadline', 'datetime'),
    Field('max_submissions_in_24h_period', 'integer'),
    Field('access_url', default=random_id),
    Field('max_points', 'integer'),
)

db.assignment.max_submissions_in_24h_period.requires = IS_INT_IN_RANGE(1, 3)

db.define_table(
    'access',
    Field('user'),
    Field('assignment_id', 'reference assignment'),
)

db.define_table(
    'homework',
    Field('student', default=get_user_email), # Email of student.
    Field('assignment_id', 'reference assignment'),
    Field('created_on', 'datetime', default=get_time),
    Field('grade', 'float'),
    Field('has_invalid_grade', 'boolean', default=False),
    Field('drive_id'),
)

db.define_table(
    'grade',
    Field('student', default=get_user_email),
    Field('assignment_id', 'reference assignment'),
    Field('grade_date', 'datetime', default=get_time),
    Field('homework_id', 'reference homework'),
    Field('grade', 'float'),
    Field('drive_id'), # Location in Drive of feedback
    Field('is_valid', 'boolean', default=False),
)

db.define_table(
    'grading_request',
    Field('homework_id', 'reference homework', ondelete="SET NULL"),
    Field('student', default=get_user_email),
    Field('input_id_gcs'), # Location in GCS of what was graded.
    Field('created_on', 'datetime', default=get_time),
    Field('request_nonce', default=random_id),
    Field('completed', 'boolean', default=False),
    Field('grade', 'float'),
    Field('delay', 'float'),
)

db.commit()

def get_assignment_teachers(assignment_id, exclude=None):
    """Returns the assignment teachers."""
    q = (db.access.assignment_id == assignment_id)
    if exclude is not None:
        q &= (db.access.user != exclude)
    teachers = [r.user for r in db(q).select()]
    return sorted(teachers)

def set_assignment_teachers(assignment_id, teacher_list):
    current_rows = db(db.access.assignment_id == assignment_id).select()
    current_users = [r.user for r in current_rows]
    users_to_delete = [u for u in current_users if u not in teacher_list]
    users_to_add = [u for u in teacher_list if u not in current_users]
    db((db.access.assignment_id == assignment_id) &
       (db.access.user.belongs(users_to_delete))).delete()
    for u in users_to_add:
        db.access.insert(user=u, assignment_id=assignment_id)

def can_access_assignment(assignment_id):
    return not db((db.access.assignment_id == assignment_id) &
                  (db.access.user == get_user_email())).isempty()

