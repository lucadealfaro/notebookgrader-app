import datetime
import uuid

from py4web import request, URL
from pydal.validators import *
from .my_validators import IS_ISO_DATETIME

from .components.grid import Grid

from .constants import *
from .common import db, session, auth, Field
from .util import random_id

from .common import url_signer
from .models import get_user_email

GRADE_HELP = """
The grade shown here is the highest valid grade. 
A grade is valid if it has been assigned before the due date, 
or if the instructor has manually flagged it as valid
"""
class HomeworkGrid(Grid):

    def __init__(self, path, **kwargs):
        super().__init__(path, session, use_id=False,  auth=auth, db=db, signer=url_signer,
                         **kwargs)

    def api(self, id=None):
        """Returns the grid."""
        # Table header.
        header = dict(
            is_header=True,
            cells=[
                dict(text="Assignment"),
                dict(text="Due Date"),
                dict(text="Grade", help="The grade")
            ],
        )
        # Parses the query.
        req = self._get_request_params(header)
        # Forms the database query.
        query = ((db.homework.student == get_user_email()) &
                 (db.homework.assignment_id == db.assignment.id))
        if req.query:
            query &= (db.assignment.name.contains(req.query))
        db_rows = db(query).select(orderby=~db.assignment.submission_deadline,
                                   limitby=req.search_args['limitby']).as_list()
        has_more, result_rows = self._has_more(db_rows)
        # Now creates the results.
        rows = [header] + [dict(
            cells=[
                dict(text=r["assignment"]["name"],
                     url=URL('homework', r["homework"]["id"]),
                     ),
                dict(text=r["assignment"]["submission_deadline"].isoformat(),
                     type='datetime'),
                dict(text=r["homework"]["grade"]),
            ]
        )
            for r in result_rows
        ]
        return dict(
            page=int(req.page),
            has_search=True,
            has_delete=False,
            has_more=has_more,
            rows=rows
        )
