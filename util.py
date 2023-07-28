import re

import hashlib
import uuid

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