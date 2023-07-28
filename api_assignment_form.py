import datetime

from py4web import request, URL
from pydal.validators import *
from .my_validators import IS_ISO_DATETIME

from .components.vueform import VueForm

from .constants import *
from .common import db, session, auth, Field


FIELDS = [
    Field('name', length=STRING_FIELD_LENGTH, required=True,
          requires=[IS_NOT_EMPTY(), IS_LENGTH(STRING_FIELD_LENGTH)],
          help="Name of the assignment."),  # Assignment name.
    Field('available_from', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()],
          help="Date from which students can access the assignment."),
    Field('submission_deadline', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()],
          help="Date when students need to submit the assignment for it to be considered submitted on time."),
    Field('available_until', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()],
          help="Date until when student can access the assignment and submit a solution, even if late."),
    Field('max_submissions_in_24h_period', 'integer', default=3, requires=[IS_INT_IN_RANGE(1, 5), IS_NOT_EMPTY()], label="Maximum number of submissions in a 24h period", help="Students will be able to only submit this many solutions in any 24h period."),
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

    def validate_dates(self, fields, validated_values):
        d1 = validated_values['available_from']
        d2 = validated_values['submission_deadline']
        d3 = validated_values['available_until']
        errors = {}
        if d2 < d1:
            errors['submission_deadline'] = "The submission deadline should come after the assignment is available"
        if d3 < d2:
            errors['available_until'] = "An assignment should be available at least until its deadline"
        return errors

    def process_post(self, record_id, validated_values):
        self.db(self.db.assignment.id == record_id).update(**validated_values)
        return dict(redirect_url=URL(self.redirect_url, signer=self.signer))


class AssignmentFormCreate(AssignmentFormEdit):

    def __init__(self, path, redirect_url=None, **kwargs):
        super().__init__(path, use_id=False, readonly=False,
                         validate=self.validate_dates, **kwargs)
        self.redirect_url = redirect_url

    def validate_dates(self, fields, validated_values):
        d1 = validated_values['available_from']
        d2 = validated_values['submission_deadline']
        d3 = validated_values['available_until']
        errors = {}
        if d2 < datetime.datetime.utcnow():
            errors['submission_deadline'] = "The submission deadline should be in the future"
        if d2 < d1:
            errors['submission_deadline'] = "The submission deadline should come after the assignment is available"
        if d3 < d2:
            errors['available_until'] = "An assignment should be available at least until its deadline"
        return errors

    def read_values(self, record_id):
        values = {}
        for f_name, f in self.fields.items():
            values[f_name] = f.formatter(None)
        return values

    def process_post(self, record_id, validated_values):
        new_id = self.db.assignment.insert(**validated_values)
        return dict(redirect_url=URL(self.redirect_url, signer=self.signer))

