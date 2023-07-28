from py4web import request, URL
from pydal.validators import *
from .my_validators import IS_ISO_DATETIME

from .components.vueform import VueForm

from .constants import *
from .common import db, session, auth, Field


FIELDS = [
    Field('name', length=STRING_FIELD_LENGTH, required=True,
          requires=[IS_NOT_EMPTY(), IS_LENGTH(STRING_FIELD_LENGTH)]),  # Assignment name.
    Field('available_from', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()]),
    Field('submission_deadline', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()]),
    Field('available_until', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()]),
    Field('max_submissions_in_24h_period', 'integer', default=3, requires=[IS_INT_IN_RANGE(1, 5), IS_NOT_EMPTY()], label="Maximum number of submissions in a 24h period"),
]


class AssignmentForm(VueForm):

    def __init__(self, fields, path, **kwargs):
        super().__init__(fields, session, path, auth=auth, db=db, **kwargs)

    def read_values(self, record_id):
        values = {}
        assert record_id is not None
        row = self.db(self.db.assignment.id == record_id).select().first()
        if row is not None:
            for f in self.fields.values():
                ff = f["field"]
                values[ff.name] = ff.formatter(row.get(ff.name))
                # print("Field", ff.name, "has value", row.get(ff.name), "formatted:", ff.formatter(row.get(ff.name)))
        return values


class AssignmentFormView(AssignmentForm):

    def __init__(self, path, **kwargs):
        super().__init__(FIELDS, path, use_id=True, readonly=True, **kwargs)


class AssignmentFormEdit(AssignmentForm):
    """This class must also enforce the ordering relations between dates."""

    def __init__(self, path, use_id=True, redirect_url=None, readonly=False,
                 validate=None, **kwargs):
        super().__init__(FIELDS, path, use_id=use_id, readonly=readonly,
                         validate=validate or self.validate_dates, **kwargs)
        self.redirect_url = redirect_url

    def validate_dates(self, fields):
        d1 = fields['available_from']['validated_value']
        d2 = fields['submission_deadline']['validated_value']
        d3 = fields['available_until']['validated_value']
        if d2 < d1:
            fields['submission_deadline']['error'] = "The submission deadline should come after the assignment is available"
        if d3 < d2:
            fields['available_until']['error'] = "An assignment should be available at least until its deadline"

    def process_post(self, record_id, values):
        self.db(self.db.assignment.id == record_id).update(**values)
        return dict(redirect_url=URL(self.redirect_url, signer=self.signer))


class AssignmentFormCreate(AssignmentFormEdit):

    def __init__(self, path, redirect_url=None, **kwargs):
        super().__init__(path, use_id=False, readonly=False,
                         validate=self.validate_dates, **kwargs)
        self.redirect_url = redirect_url

    def read_values(self, record_id):
        values = {}
        for f in self.fields.values():
            ff = f["field"]
            values[ff.name] = ff.formatter(None)
        return values

    def process_post(self, record_id, values):
        new_id = self.db.assignment.insert(**values)
        return dict(redirect_url=URL(self.redirect_url, signer=self.signer))

