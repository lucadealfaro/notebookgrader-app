import datetime
import uuid

from py4web import request, URL
from pydal.validators import *
from .my_validators import IS_ISO_DATETIME

from yatl.helpers import BUTTON, I, A, SPAN, DIV

from .components.grid import Grid

from .constants import *
from .common import db, session, auth, Field
from .util import random_id

from .settings import COLAB_BASE
from .common import url_signer
from .models import get_user_email

GRADE_HELP = "Highest valid grade."
LATE_HELP = "Does the student have a late grade that is not valid?"

class ParticipantsGrid(Grid):

    def __init__(self, path, **kwargs):
        super().__init__(path, session, use_id=True,  auth=auth, db=db, signer=url_signer,
                         sort_fields=[
                             db.auth_user.first_name,
                             db.auth_user.last_name,
                             db.auth_user.email,
                             None,
                             db.homework.grade,
                             db.homework.has_invalid_grade,
                         ],
                         default_sort=[0, 0, 1, 0, 0, 0],
                         **kwargs)

    def api(self, id=None):
        """Returns the grid."""
        # Table header.
        header = dict(
            is_header=True,
            cells=[
                dict(text="First Name", sortable=True),
                dict(text="Last Name", sortable=True),
                dict(text="Email", sortable=True),
                dict(text="Homework"),
                dict(text="Grade", sortable=True, help=GRADE_HELP),
                dict(text="Late Grades", sortable=True, help=LATE_HELP),
            ],
        )
        # Parses the query.
        req = self._get_request_params(header)
        # Forms the database query.
        query = ((db.homework.assignment_id == id) &
                 (db.homework.student == db.auth_user.email))
        if req.query is not None:
            query &= ((db.auth_user.first_name.startswith(req.query)) |
                      (db.auth_user.last_name.startswith(req.query)) |
                      (db.auth_user.email.startswith(req.query)))
        db_rows = db(query).select(**req.search_args).as_list()
        has_more, result_rows = self._has_more(db_rows)
        # Now creates the results.
        rows = [header]
        for r in result_rows:
            if r["homework"]["has_invalid_grade"]:
                indicator = SPAN(I(_class="fa fa-warning"), _class="icon is-small is-danger")
            else:
                indicator = SPAN(I(_class="fa fa-check-square"), _class="icon is-success is-small")
            rows.append(dict(cells=[
                dict(text=r["auth_user"]["first_name"]),
                dict(text=r["auth_user"]["last_name"]),
                dict(text=r["auth_user"]["email"]),
                dict(html=A(I(_class="fa fa-file"), _target="_blank", _href=COLAB_BASE + r["homework"]["drive_id"]).xml()),
                dict(text=r["homework"]["grade"], url=URL("teacher-homework-details", r["homework"]["id"], signer=self.signer)),
                dict(html=A(indicator, _href=URL("teacher-homework-details", r["homework"]["id"], signer=self.signer)).xml()),
            ]))
        return dict(
            page=int(req.page),
            has_search=True,
            has_delete=False,
            has_more=has_more,
            rows=rows
        )
