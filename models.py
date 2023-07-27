"""
This file defines the database models
"""

import datetime
from .common import db, Field, auth
from pydal.validators import *


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
    Field('owner'), # Email of owner.
    Field('name'), # Assignment name.
    Field('created_on', 'datetime', default=get_time),
    Field('source_notebook_id_gcs'),
    Field('student_notebook_id_gcs'),
    Field('source_notebook_id_drive'),
    Field('student_notebook_id_drive'),
    Field('available_from', 'datetime'),
    Field('available_until', 'datetime'),
    Field('on_time_deadline', 'datetime'),
    Field('max_submissions_in_24h_period', 'integer'),
)

db.assignment.max_submissions_in_24h_period.requires = IS_INT_IN_RANGE(1, 3)

db.define_table(
    'homework',
    Field('student'), # Email of student.
    Field('assignment_id', 'reference assignment'),
    Field('created_on', 'datetime', default=get_time),
    Field('google_drive_id'),
)

db.define_table(
    'grade',
    Field('student'),
    Field('assignment_id', 'reference assignment'),
    Field('grade_date', 'datetime', default=get_time),
    Field('homework_id', 'reference homework'),
    Field('grade', 'float'),
)

db.commit()
