import io
import json
import re

import base64
import hashlib
import requests
import uuid


import google.auth.transport.requests
import google.oauth2.id_token
from google.cloud import tasks_v2

from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

from .settings import IS_TEST, IS_CLOUD, GRADING_URL, STUDENT_GRADING_USES_QUEUE
from .settings import QUEUE_SERVICE_ACCOUNT, STUDENT_GRADING_QUEUE_LOCATION
from .settings import STUDENT_GRADING_QUEUE_NAME, STUDENT_GRADING_QUEUE_PROJECT

email_split_pattern = re.compile('[,\s]+')
whitespace = re.compile('\s+$')
all_whitespace = re.compile('\s*$')
vowels = 'aeiouy'
consonants = 'bcdfgmnpqrstvwz'

def split_emails(s):
    """Splits the emails that occur in a string s, returning the list of emails."""
    l = email_split_pattern.split(s)
    if l == None:
        return []
    else:
        r = []
        for el in l:
            if len(el) > 0 and not whitespace.match(el):
                r += [el.lower()]
        return r

def normalize_email_list(l):
    if isinstance(l, str):
        l = [l]
    r = []
    for el in l:
        ll = split_emails(el)
        for addr in ll:
            if addr not in r:
                r.append(addr.lower())
    r.sort()
    return r

def short_random_id():
    return base64.urlsafe_b64encode(hashlib.sha1(uuid.uuid1().bytes).digest()).decode()[:12]

def random_id():
    return hashlib.sha1(uuid.uuid1().bytes).hexdigest()

def long_random_id():
    return hashlib.sha256(uuid.uuid1().bytes).hexdigest()

def upload_to_drive(drive_service, s, drive_file_name, id=None,
                    write_share=None, read_share=None, locked=False):
    """
    Uploads a string to drive
    Args:
        drive_service: the drive service to use.
        s: string to upload
        drive_file_name: file name to use in drive.
        id: if given, uses the given id.
        write_share: Optional list of people with whom to share in write mode.
        read_share: Optional list of people with whom to share in read mode.
        locked: Whether to lock the file to edits.
    Returns:
        The file id.
    """
    sio = io.BytesIO(s.encode('utf-8'))
    media = MediaIoBaseUpload(sio,
        mimetype='application/vnd.google.colaboratory', resumable=True)
    meta = {'name': drive_file_name}
    if id is None:
        # We upload a new file.
        upfile = drive_service.files().create(
            body=meta,
            media_body=media,
            fields='id').execute()
        id = upfile.get('id')
    else:
        # We update an existing file.
        drive_service.files().update(
            body=meta,
            media_body=media,
            fileId=id,
        ).execute()
    # Shares the file if requested.
    for user in (write_share or []):
        share_drive_file(drive_service, id, user, "writer")
    for user in (read_share or []):
        share_drive_file(drive_service, id, user, "reader")
    # Locks the file if requested.
    if locked:
        drive_service.files().update(
            fileId=id,
            body={"contentRestrictions":
                      [{"readOnly": "true", "reason": "Homework feedback."}]
                  })
    return id


def share_drive_file(drive_service, file_id, user, mode):
    """Shares a drive file with a user in the requested mode."""
    user_permission = {
        'type': 'user',
        'role': mode,
        'emailAddress': user
    }
    drive_service.permissions().create(
        fileId=file_id,
        body=user_permission,
        fields='id',
        sendNotificationEmail=False,  # otherwise, Google throttles us
    ).execute()


def read_from_drive(drive_service, drive_id):
    """Reads a drive id into a string."""
    # https://developers.google.com/drive/api/guides/manage-downloads#python
    request = drive_service.files().get_media(fileId=drive_id)
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return file.getvalue()


def send_grading_request(payload, is_student=True):
    """
    Sends a grading request.
    Args:
        payload: The payload of the request. Consisting of:
            nonce: a nonce for the callback
            notebook_json: to be graded
            callback_url: to report the results
        is_student: The request comes from a student.
    Returns: the result of the request.

    """
    if IS_CLOUD:
        # Enqueues the request.
        return enqueue_request(payload)
    else:        
        # This request can use a callback.
        r = requests.post(GRADING_URL, json=payload)
        r.raise_for_status()
        return r


def send_ai_feedback_request(payload):
    """
    Sends an ai feedback request.
    Args:
        payload: The payload of the request. Consisting of:
            nonce: a nonce for the callback
            master_notebook_json: instructor version
            student_notebook_json: student version
            callback_url: to report the results
    Returns: the result of the request.

    """
    if IS_TEST:
        # This request can use a callback.
        r = requests.post(GRADING_URL, json=payload)
        r.raise_for_status()
        return r
    else:
        # Enqueues the request.
        return enqueue_request(payload)


def send_request(payload, TARGET_URL):
    """See https://cloud.google.com/tasks/docs/creating-http-target-tasks"""
    if not IS_CLOUD:
        # This request can use a callback.
        r = requests.post(TARGET_URL, json=payload)
        r.raise_for_status()
        return r
    else:
        # Create a client.
        client = tasks_v2.CloudTasksClient()
        # Construct the request body.
        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=TARGET_URL,
                oidc_token=tasks_v2.OidcToken(
                    service_account_email=QUEUE_SERVICE_ACCOUNT,
                    audience=TARGET_URL,
                ),
                headers={"Content-Type": "application/json"},
                body=json.dumps(payload).encode('utf-8'),
            ),
        )
        # Use the client to build and send the task.
        return client.create_task(
            tasks_v2.CreateTaskRequest(
                parent=client.queue_path(
                    STUDENT_GRADING_QUEUE_PROJECT,
                    STUDENT_GRADING_QUEUE_LOCATION,
                    STUDENT_GRADING_QUEUE_NAME),
                task=task,
            )
        )

