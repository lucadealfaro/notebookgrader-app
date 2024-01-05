import datetime
import uuid

from py4web import request, URL
from pydal.validators import *
from .my_validators import IS_ISO_DATETIME, IS_REAL_LIST_OF_EMAILS, IS_DOMAIN

from .components.vueform import VueForm

from .constants import *
from .common import db, session, auth, Field, gcs
from .util import random_id, long_random_id, upload_to_drive, share_drive_file, unshare_drive_file
from .common import url_signer
from .models import get_assignment_teachers, set_assignment_teachers, get_user_email, build_drive_service
from .util import normalize_email_list
from .settings import MAX_GRADES_24H, GCS_BUCKET
from .private.private_settings import TESTER_EMAILS

FIELDS = [
    Field('name', length=STRING_FIELD_LENGTH, required=True,
          requires=[IS_NOT_EMPTY(), IS_LENGTH(STRING_FIELD_LENGTH)],
          help="Name of the assignment."),  # Assignment name.
    Field('domain_restriction', length=STRING_FIELD_LENGTH,
          requires=IS_DOMAIN(),
          help="If specified, students must use Google accounts from the domain.  For instance, if you specify ucsc.edu as domain restrictions, students must use accounts of the form name@ucsc.edu to participate in the assignment."),
    Field('instructors', length=STRING_FIELD_LENGTH,
          requires=IS_REAL_LIST_OF_EMAILS(),
          help="List of email addresses of additional instructors.  These instructors will be able to view student submissions, but they will not be able to edit the assignment."),
    Field('available_from', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()],
          help="Date from which students can access the assignment."),
    Field('submission_deadline', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()],
          label="Due Date",
          help="Date when students need to submit the assignment for it to be considered submitted on time."),
    Field('available_until', 'datetime', required=True, requires=[IS_ISO_DATETIME(), IS_NOT_EMPTY()],
          help="Date until when student can access the assignment and submit a solution, even if late."),
    Field('max_submissions_in_24h_period', 'integer', default=3, requires=[IS_INT_IN_RANGE(1, MAX_GRADES_24H), IS_NOT_EMPTY()], label="Maximum number of submissions in a 24h period", help="Students will be able to only submit this many solutions in any 24h period."),
    Field('ai_feedback', 'integer', default=0, requires=IS_INT_IN_RANGE(0, 3), label="Maximum number of AI feedback requests", 
          help="Students will be able to request AI feedback this many times."),
]


class AssignmentForm(VueForm):

    def __init__(self, fields, path, **kwargs):
        super().__init__(fields, session, path, auth=auth, db=db, signer=url_signer, **kwargs)

    def read_values(self, record_id):
        values = {}
        assert record_id is not None
        row = self.db.assignment[record_id]
        if row is not None:
            for f_name, f in self.fields.items():
                values[f_name] = f.formatter(row.get(f_name))
            # Reads the additional instructors.
            values['instructors'] = ", ".join(get_assignment_teachers(record_id))
        return values


class AssignmentFormView(AssignmentForm):

    def __init__(self, path, **kwargs):
        super().__init__(FIELDS, path, use_id=True, readonly=True, **kwargs)


class AssignmentFormEdit(AssignmentForm):
    """This class must also enforce the ordering relations between dates."""

    def __init__(self, path, use_id=True, redirect_url=None, readonly=False,
                 validate=None, **kwargs):
        super().__init__(FIELDS, path, use_id=use_id, readonly=readonly,
                         validate=validate or self.validate, **kwargs)
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
        user = get_user_email()
        if user not in validated_values['instructors']:
            validated_values['instructors'].append(user)
        validated_values['instructors'] = normalize_email_list(validated_values['instructors'])
        return errors
    
    def validate_ai_feedback(self, fields, validated_values):
        errors = {}
        n = validated_values['ai_feedback']
        email = get_user_email()
        if n > 0 and not (email in TESTER_EMAILS or email.endswith("@ucsc.edu")):
            errors['ai_feedback'] = "This feature is in preview; only testers can create assignments with AI feedback."
        return errors

    def validate(self, fields, validated_values):
        e = self.validate_dates(fields, validated_values)
        e.update(self.validate_ai_feedback(fields, validated_values))
        return e

    def process_post(self, record_id, validated_values):
        assignment = self.db.assignment[record_id]
        old_instructors = set(get_assignment_teachers(record_id)) | {assignment.owner}
        new_instructors = set(validated_values['instructors']) | {assignment.owner}
        set_assignment_teachers(record_id, new_instructors)
        del validated_values['instructors']
        assignment.update_record(**validated_values)
        # Updates the instructors on the master notebook.
        remove_instructors = set(old_instructors) - set(new_instructors)
        add_instructors = set(new_instructors) - set(old_instructors)
        # Shares the notebooks with the new users. 
        drive_service = build_drive_service()
        if assignment.master_id_drive is not None:
            for u in add_instructors:
                share_drive_file(drive_service, assignment.master_id_drive, u, "reader")
            for u in remove_instructors:
                unshare_drive_file(drive_service, assignment.master_id_drive, u)
        if assignment.student_id_drive is not None:
            for u in add_instructors:
                share_drive_file(drive_service, assignment.student_id_drive, u, "reader")
            for u in remove_instructors:
                unshare_drive_file(drive_service, assignment.student_id_drive, u)        
        return dict(redirect_url=URL(self.redirect_url, record_id))


class AssignmentFormCreate(AssignmentFormEdit):

    def __init__(self, path, redirect_url=None, **kwargs):
        super().__init__(path, use_id=False, readonly=False,
                         validate=self.validate, **kwargs)
        self.redirect_url = redirect_url
        
    def __call__(self, duplicate_id=None, **kwargs):
        if duplicate_id is not None:
            self.duplicated_assignment = self.db.assignment[duplicate_id]
        else:
            self.duplicated_assignment = None
        return super().__call__(**kwargs)

    def read_values(self, record_id):
        values = {}
        for f_name, f in self.fields.items():
            if self.duplicated_assignment is not None and f_name == "name":
                values[f_name] = f.formatter("Copy of " + self.duplicated_assignment[f_name])
            else:
                values[f_name] = f.formatter(None)
        return values

    def process_post(self, null_record_id, validated_values):
        new_instructors = validated_values['instructors']
        del validated_values['instructors']
        new_id = self.db.assignment.insert(**validated_values)
        user = get_user_email()
        if user not in new_instructors:
            new_instructors.append(user)
        set_assignment_teachers(new_id, new_instructors)
        # Copies the notebooks if needed.
        if self.duplicated_assignment is not None:
            assignment = db.assignment[new_id]
            tas = get_assignment_teachers(assignment.id, exclude=assignment.owner)
            drive_service = build_drive_service()
            master_json = gcs.read(GCS_BUCKET, self.duplicated_assignment.master_id_gcs)
            student_json = gcs.read(GCS_BUCKET, self.duplicated_assignment.student_id_gcs)
            master_id_gcs = long_random_id() + ".json"
            student_id_gcs = long_random_id() + ".json"
            gcs.write(GCS_BUCKET, master_id_gcs, master_json, type="application/json")
            gcs.write(GCS_BUCKET, student_id_gcs, student_json, type="application/json")
            assignment.master_id_gcs = master_id_gcs
            assignment.student_id_gcs = student_id_gcs
            date_string = datetime.datetime.utcnow().isoformat()
            master_file_name = "{}, version: {}".format(assignment.name, date_string)
            student_file_name = "{}, version: {}".format(assignment.name, date_string)
            assignment.master_id_drive = upload_to_drive(
                drive_service, master_json, master_file_name,
                read_share=tas, id=assignment.master_id_drive)
            assignment.student_id_drive = upload_to_drive(
                drive_service, student_json, student_file_name,
                read_share=tas, id=assignment.student_id_drive)            
            assignment.update_record()
        return dict(redirect_url=URL(self.redirect_url, new_id))

