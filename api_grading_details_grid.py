
from py4web import URL

from .components.grid import Grid
from yatl.helpers import BUTTON, I, A, SPAN, DIV

from .constants import *
from .common import db, session, auth

from .settings import COLAB_BASE
from .common import url_signer
from .models import get_user_email, is_admin

GRADE_HELP = """
A grade is valid if it has been assigned before the due date, 
or if the instructor has manually flagged it as valid.
"""

FEEDBACK_HELP = """ 
This is the feedback you received. 
Note that if you rerun the notebook, the feedback is over-written! 
To recover it, click on File > Revision history, and view the original version of the file. 
"""

class AssignmentGradingGrid(Grid):

    def __init__(self, path, **kwargs):
        super().__init__(path, session, use_id=True,  auth=auth,
                         db=db, signer=url_signer,
                         sort_fields=[
                             db.grading_request.student,
                             None,
                             db.grading_request.created_on,
                             db.grading_request.completed,
                             db.grading_request.delay,
                             db.grading_request.grade,
                             ],
                         default_sort=[0, 0, 0, 0, -1, 0],
                         **kwargs)

    def api(self, id=None):
        """Returns the grid."""
        # Table header.
        header = dict(
            is_header=True,
            cells=[
                dict(text="Student", sortable=True),
                dict(text="Submission", sortable=False),
                dict(text="Date", sortable=True),
                dict(text="Completed", sortable=True),
                dict(text="Delay", sortable=True),
                dict(text="Grade", sortable=True),
            ],
        )
        # Parses the query.
        req = self._get_request_params(header)
        # Forms the database query.
        query = (db.grading_request.homework_id == id)
        if req.query:
            query &= (db.grading_request.student.startswith(req.query))
        db_rows = db(query).select(**req.search_args).as_list()
        has_more, result_rows = self._has_more(db_rows)

        # Now creates the results.
        assignment = db.assignment[id]
        rows = [header]
        for r in result_rows:
            row_notebook = SPAN(
                A(I(_class="fa fa-file"), _target="_blank", _href=URL(
                    'admin_share', 'submission', r["input_id_gcs"],
                    vars=dict(title="{} by {} on {}, Submission".format(
                        assignment.name,
                        r["student"],
                        r["created_on"].isoformat(),
                    )),
                    signer=url_signer
                )))
            rows.append(dict(
            cells=[
                dict(text=r["student"]),
                dict(html=row_notebook.xml()),
                dict(text=r["created_on"].isoformat(), type='datetime'),
                dict(html=I(_class="fa fa-check").xml() if r["completed"]
                else I(_class="fa fa-warning is-danger").xml()),
                dict(text="{:.2f}".format(r["delay"])),
                dict(text="{}/{}".format(r["grade"], assignment.max_points)),
            ]))
        return dict(
            page=int(req.page),
            has_search=True,
            has_delete=False,
            has_more=has_more,
            rows=rows
        )
