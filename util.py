import datetime
import re

from yatl.helpers import *
from .common import T

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

def ribbon(link_list):
    """Makes the ribbon."""
    return UL(*[l for l in link_list], _class='btnbar')

def MT(s):
    return str(T(s))
