"""
This file defines the database models
"""

import datetime
from .common import db, Field, auth
from pydal.validators import *
from .util import random_id

def get_user_email():
    return auth.current_user.get('email') if auth.current_user else None

def get_time():
    return datetime.datetime.utcnow()


### Define your table below
#
# db.define_table('thing', Field('name'))
#
## always commit your models to avoid problems later

db.define_table(
    'assignment',
    Field('owner', default=get_user_email), # Email of owner.
    Field('name'), # Assignment name.
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
    'homework',
    Field('student', default=get_user_email), # Email of student.
    Field('assignment_id', 'reference assignment'),
    Field('created_on', 'datetime', default=get_time),
    Field('grade', 'float'),
    Field('drive_id'),
)

db.define_table(
    'grade',
    Field('student', default=get_user_email),
    Field('assignment_id', 'reference assignment'),
    Field('grade_date', 'datetime', default=get_time),
    Field('homework_id', 'reference homework'),
    Field('grade', 'float'),
    Field('input_id_gcs'), # Location in GCS of what was graded.
    Field('drive_id'), # Location in Drive of feedback
    Field('is_valid', 'boolean', default=False),
)

db.commit()
