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
from .models import get_user_email, is_admin

GRADE_HELP = "Highest valid grade."
LATE_HELP = "Does the student have a late grade that is not valid?"
FEEDBACK_HELP = """
This is the feedback received by the student.  Note that the student
may have modified the notebook, e.g. by rerunning it, so if you want to see
the original feedback, you need to go to File > Revision history, and 
examine the original revision.
"""
class HomeworkDetailsGrid(Grid):
    """This gives homework details to the teacher."""

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
        homework=db.homework[id]
        assignment = db.assignment[homework.assignment_id]
        rows = [header]
        for r in result_rows:

            if is_admin() and r["submission_id_gcs"] is not None:
                row_notebook = SPAN(
                    A(I(_class="fa fa-file"), _target="_blank", _href=COLAB_BASE + r["drive_id"]),
                    " ",
                    A(I(_class="fa fa-eye"), _target="_blank", _href=URL(
                        'admin_share', 'submission', r["submission_id_gcs"],
                        vars=dict(title="{} by {} on {}, Submission".format(
                            assignment.name,
                            r["student"],
                            r["grade_date"].isoformat(),
                        )),
                        signer=url_signer
                    )),
                    " ",
                    A(I(_class="fa fa-gavel"), _target="_blank", _href=URL(
                        'admin_share', 'submission', r["feedback_id_gcs"],
                        vars=dict(title="{} by {} on {}, Feedback".format(
                            assignment.name,
                            r["student"],
                            r["grade_date"].isoformat(),
                        )),
                        signer=url_signer,
                    )),
                )
            else:
                row_notebook = A(I(_class="fa fa-file"), _target="_blank", _href=COLAB_BASE + r["drive_id"])

            if r["is_valid"]:
                indicator = SPAN(I(_class="fa fa-check-square"), _class="icon has-text-success is-small")
            else:
                indicator = SPAN(I(_class="fa fa-warning"), _class="icon is-small has-text-danger")

            toggle = A(indicator, _href=URL('toggle-grade-validity', r["id"], signer=url_signer))

            rows.append(dict(cells=[
                dict(text="{}/{}".format(r["grade"], assignment.max_points)),
                dict(text=r["grade_date"].isoformat(), type='datetime'),
                dict(html=row_notebook.xml()),
                dict(html=toggle.xml()),
            ]))
        return dict(
            page=int(req.page),
            has_search=False,
            has_delete=False,
            has_more=has_more,
            rows=rows
        )
