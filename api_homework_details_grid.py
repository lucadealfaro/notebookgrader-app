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

class HomeworkDetailsGrid(Grid):

    def __init__(self, path, **kwargs):
        super().__init__(path, session, use_id=True,  auth=auth, db=db, signer=url_signer,
                         **kwargs)

    def api(self, id=None):
        """Returns the grid."""
        # Table header.
        header = dict(
            is_header=True,
            cells=[
                dict(text="Grade"),
                dict(text="Graded On"),
                dict(text="Feedback"),
                dict(text="Valid", help="You can toggle the validity of a grade"),
            ],
        )
        # Parses the query.
        req = self._get_request_params(header)
        # Forms the database query.
        query = (db.grade.homework_id == id)
        db_rows = db(query).select(orderby=~db.grade.grade_date,
                                   limitby=req.search_args['limitby']).as_list()
        has_more, result_rows = self._has_more(db_rows)
        # Now creates the results.
        assignment = db.assignment[r["assignment_id"]]
        rows = [header]
        for r in result_rows:
            if r["is_valid"]:
                indicator = SPAN(I(_class="fa fa-check-square"), _class="icon is-success is-small")
            else:
                indicator = SPAN(I(_class="fa fa-warning"), _class="icon is-small is-danger")
            toggle = A(indicator, _href=URL('toggle-grade-validity', r["id"], signer=url_signer))
            rows.append([
                dict(text="{}/{}".format(r["grade"], assignment.grade)),
                dict(text=r["grade_date"], type='datetime'),
                dict(html=A(I(_class="fa fa-file"), _target="_blank", _href=COLAB_BASE + r["drive_id"]).xml()),
                dict(html=toggle),
            ])
        return dict(
            page=int(req.page),
            has_search=False,
            has_delete=False,
            has_more=has_more,
            rows=rows
        )
