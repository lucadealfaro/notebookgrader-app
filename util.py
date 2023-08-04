import io
import re

import hashlib
import json
import uuid

from py4web import redirect, URL
from .models import get_user_email
from .common import db

from googleapiclient.discovery import build
import google.oauth2.credentials
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload


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

def random_id():
    return hashlib.sha1(uuid.uuid1().bytes).hexdigest()

def long_random_id():
    return hashlib.sha256(uuid.uuid1().bytes).hexdigest()

def build_drive_service():
    # Reads the credentials.
    user_info = db(
        db.auth_credentials.email == get_user_email()).select().first()
    if not user_info:
        print("No user credentials")
        redirect(URL('index'))
    credentials_dict = json.loads(user_info.credentials)
    creds = google.oauth2.credentials.Credentials(**credentials_dict)
    drive_service = build('drive', 'v3', credentials=creds)
    return drive_service

def upload_to_drive(drive_service, s, drive_file_name, id=None, shared=None):
    """
    Uploads a string to drive
    Args:
        drive_service: the drive service to use.
        s: string to upload
        drive_file_name: file name to use in drive.
        id: if given, uses the given id.
        shared: if given, shares the file with the given user.
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
    if shared:
        user_permission = {
            'type': 'user',
            'role': 'writer',
            'emailAddress': shared
        }
        drive_service.permissions().create(
            fileId=id,
            body=user_permission,
            fields='id',
            sendNotificationEmail=False,  # otherwise, Google throttles us
        ).execute()
    return id

def read_from_drive(drive_service, drive_id):
    """Reads a drive id into a string."""
    # https://developers.google.com/drive/api/guides/manage-downloads#python
    request = drive_service.files.getMedia(fileID=drive_id)
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    return file.getvalue()

