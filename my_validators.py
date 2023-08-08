import datetime, time
import re

from pydal.validators import IS_EMAIL, IS_DATETIME, ValidationError, Validator
from .util import split_emails
from py4web import Translator
from . import settings

# Creating a translator.
T = Translator(settings.T_FOLDER)

# Validator used to process multiple emails.
class EMAILS(object):
    def __call__(self, value):
        bad_emails = []
        emails = []
        f = IS_EMAIL()
        for email in split_emails(value):
            emails.append(email)
            error = f(email)[1]
            if error: bad_emails.append(email)
        if not bad_emails:
            return (value, None)
        else:
            return (value, T('Invalid emails: ') + ', '.join(bad_emails))
    def formatter(self, value):
        return ', '.join(value or [])

class IS_REAL_LIST_OF_EMAILS(Validator):
    """
    Example:
        Used as::

        Field('emails', 'list:string',
              widget=SQLFORM.widgets.text.widget,
              requires=IS_LIST_OF_EMAILS(),
              represent=lambda v, r: \
                XML(', '.join([A(x, _href='mailto:'+x).xml() for x in (v or [])]))
             )
    """

    REGEX_NOT_EMAIL_SPLITTER = r"[^,;\s]+"

    def __init__(self, error_message="Invalid emails: %s"):
        self.error_message = error_message

    def validate(self, value, record_id=None):
        bad_emails = []
        good_emails = []
        if value is None:
            return []
        f = IS_EMAIL()
        for email in re.findall(self.REGEX_NOT_EMAIL_SPLITTER, value):
            error = f(email)[1]
            if error and email not in bad_emails:
                bad_emails.append(email)
            if not error and email not in good_emails:
                good_emails.append(email)
        if bad_emails:
            raise ValidationError(
                self.translator(self.error_message) % ", ".join(bad_emails)
            )
        return sorted(good_emails)

    def formatter(self, value, row=None):
        return ", ".join(value or [])


def represent_percentage(v, r):
    if v is None:
        return 'None'
    return ("%3.0f%%" % v)


class IS_ISO_DATETIME(IS_DATETIME):

    def validate(self, value, record_id=None):
        if isinstance(value, datetime.datetime):
            return value
        try:
            if value[-1:] == "Z":
                value = value[:-1]
            value = datetime.datetime.fromisoformat(value)
            value = value.replace(tzinfo=datetime.timezone.utc)
            return value.replace(tzinfo=None)
        except:
            raise ValidationError("Wrong date format")

    def formatter(self, value):
        if value is None or value == "":
            return None
        return value.isoformat()
