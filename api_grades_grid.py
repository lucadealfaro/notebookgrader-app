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

AI_FEEDBACK_HELP = """
You can request AI feedback on your notebook.  You can request up to a specified maximum
number of AI feedbacks for each assignment.
"""

class StudentGradesGrid(Grid):

    def __init__(self, path, **kwargs):
        super().__init__(path, session, use_id=True,  auth=auth, db=db, signer=url_signer,
                         **kwargs)

    def api(self, id=None):
        """Returns the grid."""
        hw_assignment = db((db.homework.id == id) & 
                           (db.homework.assignment_id == db.assignment.id)).select().first()
        # Maximum number of AI feedback that students can ask for this assignment.
        ai_feedback = hw_assignment.assignment.ai_feedback or 0        
        # Table header.
        header = dict(
            is_header=True,
            cells=[
                dict(text="Valid", help=GRADE_HELP),
                dict(text="Grade"),
                dict(text="Graded On"),
                dict(text="Graded Assignment", help=FEEDBACK_HELP),
            ],
            
        )
        # If there can be AI feedback, add a column for it.
        if ai_feedback > 0:
            header['cells'].append(dict(
                text=f"AI Feedback", help=AI_FEEDBACK_HELP))
        
        # Parses the query.
        req = self._get_request_params(header)
        # Forms the database query.
        query = ((db.grade.homework_id == id) &
                 (db.grade.student == get_user_email()) &
                 (db.grade.assignment_id == db.assignment.id))
        db_rows = db(query).select(orderby=~db.grade.grade_date,
                                   limitby=req.search_args['limitby']).as_list()
        has_more, result_rows = self._has_more(db_rows)
        # Checks whether we can still ask for AI feedback. 
        num_given_ai_feedback = db(
            (db.grade.homework_id == id) &
            (db.grade.student == get_user_email()) &
            (db.ai_feedback_request.grade_id == db.grade.id)
        ).count()
        can_request_ai_feedback = num_given_ai_feedback < ai_feedback
        # Now creates the results.
        rows = [header]
        for r in result_rows:
            row_notebook = A(SPAN(I(_class="fa fa-file"), " View"), _class="button is-success", _target="_blank", _href=COLAB_BASE + r["grade"]["drive_id"])
            cells=[
                dict(html=I(_class="fa fa-check").xml() if r["grade"]["is_valid"]
                else I(_class="fa fa-warning is-danger").xml()),
                dict(text="{}/{}".format(r["grade"]["grade"], r["assignment"]["max_points"])),
                dict(text=r["grade"]["grade_date"].isoformat(), type='datetime'),
                dict(html=row_notebook.xml()),
            ]
            # Inserts the info on AI feedback. 
            if ai_feedback > 0:
                if r["grade"]["ai_feedback_id_gcs"]:
                    # There is feedback already.
                    ai_feedback_info = A(SPAN(I(_class="fa fa-life-buoy"), "AI Feedback"),
                                         _target="_blank", 
                                         _href=COLAB_BASE + r["grade"]["ai_feedback_id_drive"])
                else:
                    # Checks if there is feedback pending. 
                    ai_feedback_pending = db(
                        (db.ai_feedback_request.grade_id == r["grade"]["id"]) & 
                        (db.ai_feedback_request.completed == False)
                    ).select().first()
                    if ai_feedback_pending:
                        # There is feedback pending. 
                        ai_feedback_info = SPAN(I(_class="fa fa-spinner fa-spin"), " Pending")
                    elif can_request_ai_feedback:
                        # We can request AI feedback.
                        ai_feedback_info = A(SPAN(I(_class="fa fa-life-buoy"), " Request AI Feedback ({} left)".format(ai_feedback - num_given_ai_feedback)),
                                            _target="_blank", _class="button is-primary",
                                            _href=URL('request_ai_feedback', r["grade"]["id"], signer=url_signer))
                    else: 
                        # No info for this row. 
                        ai_feedback_info = ""
                cells.append(dict(html=ai_feedback_info.xml()))
            rows.append(dict(cells=cells))
        return dict(
            page=int(req.page),
            has_search=False,
            has_delete=False,
            has_more=has_more,
            rows=rows
        )
