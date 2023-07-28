import datetime, time
import traceback

from pydal.validators import IS_EMAIL, IS_DATETIME, ValidationError
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
            return value.replace(tzinfo=datetime.timezone.utc)
        except:
            raise ValidationError("Wrong date format")

    def formatter(self, value):
        if value is None or value == "":
            return None
        return value.isoformat()
