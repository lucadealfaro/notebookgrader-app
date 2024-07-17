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

class AdminAssignmentGrid(Grid):

    def __init__(self, path, **kwargs):
        super().__init__(path, session, use_id=False,  auth=auth, db=db, signer=url_signer,
                         sort_fields=[
                             db.auth_user.first_name,
                             db.auth_user.last_name,
                             db.auth_user.email,
                             db.assignment.domain_restriction,
                             None,
                             db.assignment.submission_deadline,
                             db.assignment.created_on,
                         ],
                         default_sort=[0, 0, 0, 0, 0, 0, -1],
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
                dict(text="Domain", sortable=True),
                dict(text="Assignment"),
                dict(text="Due Date", sortable=True),
                dict(text="Created On", sortable=True),
            ],
        )
        # Parses the query.
        req = self._get_request_params(header)
        # Forms the database query.
        query = ((db.assignment.owner == db.auth_user.email))
        if req.query:
            query &= (
                db.assignment.owner.contains(req.query) |
                db.assignment.domain_restriction.contains(req.query) |
                db.auth_user.first_name.contains(req.query) |
                db.auth_user.last_name.contains(req.query) |
                db.assignment.name.contains(req.query))
        db_rows = db(query).select(**req.search_args).as_list()
        has_more, result_rows = self._has_more(db_rows)
        # Now creates the results.
        rows = [header] + [dict(
            cells=[
                dict(text=r["auth_user"]["first_name"]),
                dict(text=r["auth_user"]["last_name"]),
                dict(text=r["assignment"]["owner"]),
                dict(text=r["assignment"]["domain_restriction"]),
                dict(text=r["assignment"]["name"],
                     url=URL('teacher-view-assignment', r["assignment"]["id"]),
                     ),
                dict(text=r["assignment"]["submission_deadline"].isoformat(),
                     type='datetime'),
                dict(text=r["assignment"]["created_on"].isoformat(),
                     type='datetime'),
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
