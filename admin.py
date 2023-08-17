import csv
import datetime
import io
import nbformat
import requests

from py4web import action, request, abort, redirect, URL, Flash
from pydal import Field
from yatl.helpers import A, BUTTON, SPAN
from .common import db, session, T, cache, auth, logger, authenticated, unauthenticated, flash

from .api_admin_assignment_grid import AdminAssignmentGrid


admin_assignment_grid = AdminAssignmentGrid('api-admin-assignment-grid')

@action('admin-home')
@action.uses('admin_home.html', db, auth.user, admin_assignment_grid)
def teacher_home():
    return dict(grid=admin_assignment_grid())
