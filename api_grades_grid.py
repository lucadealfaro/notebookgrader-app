import datetime
import uuid

from py4web import request, URL
from pydal.validators import *
from .my_validators import IS_ISO_DATETIME

from .components.grid import Grid
from yatl.helpers import BUTTON, I, A, SPAN, DIV

from .constants import *
from .common import db, session, auth, Field
from .util import random_id

from .settings import COLAB_BASE
from .common import url_signer
from .models import get_user_email

GRADE_HELP = """
A grade is valid if it has been assigned before the due date, 
or if the instructor has manually flagged it as valid.
"""

FEEDBACK_HELP = """ 
This is the feedback you received. 
Note that if you rerun the notebook, the feedback is over-written! 
To recover it, click on File > Revision history, and view the original version of the file. 
"""

class StudentGradesGrid(Grid):

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
                dict(text="Feedback", help=FEEDBACK_HELP),
                dict(text="Valid", help=GRADE_HELP)
            ],
        )
        # Parses the query.
        req = self._get_request_params(header)
        # Forms the database query.
        query = ((db.grade.homework_id == id) &
                 (db.grade.student == get_user_email()) &
                 (db.grade.assignment_id == db.assignment.id))
        db_rows = db(query).select(orderby=~db.grade.grade_date,
                                   limitby=req.search_args['limitby']).as_list()
        has_more, result_rows = self._has_more(db_rows)
        # Now creates the results.
        rows = [header] + [dict(
            cells=[
                dict(text="{}/{}".format(r["grade"]["grade"], r["assignment"]["max_points"])),
                dict(text=r["grade"]["grade_date"].isoformat(), type='datetime'),
                dict(html=A(I(_class="fa fa-file"), _target="_blank", _href=COLAB_BASE + r["grade"]["drive_id"]).xml()),
                dict(html=I(_class="fa fa-check").xml() if r["grade"]["is_valid"]
                else I(_class="fa fa-warning is-danger").xml()),
            ]
        )
            for r in result_rows
        ]
        return dict(
            page=int(req.page),
            has_search=False,
            has_delete=False,
            has_more=has_more,
            rows=rows
        )
