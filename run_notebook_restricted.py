# This file contains the functions used to run a notebook.

import ast
import builtins
import RestrictedPython
import nbformat.v4, nbformat
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins
import threading
import traceback
import warnings

warnings.simplefilter("ignore") # Silences nasty warnings from restricted python.

from .notebook_logic import remove_hidden_tests

OTHER_BUILTINS = [
    "__import__",
    "EncodingWarning",
    "InterruptedError",
    "ModuleNotFoundError",
    "NotImplemented",
    "TimeoutError",
    "aiter", "all", "anext", "any", "ascii", "bin", "classmethod",
    "dict", "dir", "enumerate", "filter", "format",
    "frozenset", "iter", "list", "map", "max", "min", "object",
    "reversed", "staticmethod", "sum", "super", "type",
]

WHITELISTED_MODULES = [
    # special
    "pandas", "numpy", "scipy", "math", "random", "matplotlib", "pytorch",
    # text and binary
    "string", "re", "struct",
    # data types
    "datetime", "zoneinfo", "calendar", "collections",
    "heapq", "bisect", "array", "types", "copy", "enum", "graphlib",
    # numbers etc.
    "numbers", "math", "cmath", "decimal", "fractions", "random", "statistics",
    # functions etc.
    "itertools", "functools", "operator",
    # Crypto etc
    "hashlib", "hmac", "secrets",
    # Os and the like.
    "time",
    # Data handling.
    "json", "base64", "binascii",
    ]


class OutputCollector(object):

    result = None

    def __init__(self, _getattr_=None):
        self.txt = []
        self._getattr_ = _getattr_
        OutputCollector.result = self

    @classmethod
    def reset(cls):
        cls.result._reset()

    def write(self, text):
        self.txt.append(text)

    def _reset(self):
        self.txt = []

    def __call__(self):
        return ''.join(self.txt)

    def _call_print(self, *objects, **kwargs):
        if kwargs.get('file', None) is None:
            kwargs['file'] = self
        else:
            self._getattr_(kwargs['file'], 'write')

        print(*objects, **kwargs)


class CleanCode(ast.NodeTransformer):

    def visit_Import(self, node):
        node.names = [n for n in node.names if
                      n.name.split(".")[0] in WHITELISTED_MODULES]
        return node if len(node.names) > 0 else None

    def visit_ImportFrom(self, node):
        return None if node.module.split(".")[
                           0] not in WHITELISTED_MODULES else node

collector = OutputCollector()

cleaner = CleanCode()

def my_setitem(d, i, x):
    d[i] = x

def get_clean_globals():
    my_globals = dict(__builtins__=safe_builtins)
    for k in OTHER_BUILTINS:
        my_globals["__builtins__"][k] = getattr(builtins, k)
    my_globals["_print_"] = OutputCollector
    my_globals["__metaclass__"] = type
    my_globals["__name__"] = "main"
    my_globals["_getiter_"] = RestrictedPython.Eval.default_guarded_getiter
    my_globals["_iter_unpack_sequence_"] = RestrictedPython.Guards.guarded_iter_unpack_sequence
    my_globals["getattr"] = RestrictedPython.Guards.safer_getattr
    my_globals["_write_"] = lambda obj: obj
    my_globals["_getattr_"] = RestrictedPython.Guards.safer_getattr
    my_globals["_unpack_sequence_"] = RestrictedPython.Guards.guarded_unpack_sequence
    my_globals["_getitem_"] = lambda d, i : d[i]
    my_globals["_setitem_"] = my_setitem
    my_globals["_inplacevar_"] = RestrictedPython.Guards.

    return my_globals

class RunCellWithTimeout(object):
    def __init__(self, function, args):
        self.function = function
        self.args = args
        self.answer = "timeout"

    def worker(self):
        self.answer = self.function(*self.args)

    def run(self, timeout=None):
        thread = threading.Thread(target=self.worker)
        thread.start()
        thread.join(timeout=timeout)
        return self.answer


def run_cell(c, my_globals):
    """
    Runs a notebook cell.  This function is called in a thread, to implement
    timeouts.
    Args:
        c: cell to be run.
        my_globals: global environment (a dictionary) in which the cell is to be run.
    Returns:
        True if all went well, False if an exception occurred.
        In any case, the cell output is updated.
    """
    c.outputs = []
    try:
        clean_code = ast.unparse(cleaner.visit(ast.parse(c.source)))
        cr = compile_restricted(clean_code, '<string>', 'exec')
        OutputCollector.reset()
        exec(cr, my_globals)
        add_output(c, OutputCollector.result())
        return True
    except Exception as e:
        err = traceback.format_exception_only(e)[0]
        add_output(c, OutputCollector.result())
        add_output(c, e)
        return False


def add_output(c, text):
    print("Output:", text)
    c.outputs.append(nbformat.v4.new_output(
        "execute_result",
        {"text/plain": text}))


def run_notebook(nb, timeout=10):
    """Runs a notebook, returning a notebook with output cells completed.
    Args:
        nb: notebook to be run.
        timeout: cell timeout to be used.
    Returns:
        The total number of points.
        The notebook is adorned with the results of the execution.
    """
    my_globals = get_clean_globals()
    execution_count = 0
    points_earned = 0
    for c in nb.cells:
        if c.cell_type == "code":
            # Runs the cell.
            runner = RunCellWithTimeout(run_cell, (c, my_globals))
            res = runner.run(timeout=timeout)
            print("----> Result:", res)
            execution_count += 1
            c.execution_count = execution_count
            # If the cell timed out, adds an explanation of it to the outputs.
            if res == "timeout":
                explanation = "Timeout Error: The cell timed out after {} seconds".format(timeout)
                add_output(c, explanation)
            if c.metadata.notebookgrader.is_tests:
                # Gives points for successfully completed test cells.
                points = c.metadata.notebookgrader.test_points
                if res == "ok":
                    points_earned += points
                    c.source = "Tests passed: you earned {}/{} points\n\n".format(points, points) + c.source
                else:
                    c.source = "Tests failed: you earned {}/{} points\n\n".format(0, points) + c.source
                # Puts the source back removing the hidden tests.
                remove_hidden_tests(c)
            execution_count += 1
            c.execution_count = execution_count
    return points_earned


######################
# Tests

code1 = """
import os
import math
from collections import defaultdict
import numpy as np

def f(n):
    if n < 2:
        return n
    else:
        return math.sqrt(2)
        
def g(n):
    print(f(n))
    with open("salsa.txt") as f:
        print(f.read())
        
print(f(4))
"""

code2 = """
class Chicken(object):

    def __init__(self, x):
        self.x = x
        
    def get(self):
        return self.x
        
c = Chicken(3)
print(c.get())
print(type(Chicken))
"""

code3 = """
l = list([2, 3, 4])
d = dict(a=3)
print(d)
for i, el in enumerate(l):
    print (el, ":", i)
al = [el + 1 for el in l]
dd = dict(enumerate(al))
print(dd)
"""

code4 = """
with open("/Users/luca/.cshrc") as f:
    print(f.read())
"""

def test_exec():
    for code in [code1, code2, code3]:
        clean_code = ast.unparse(cleaner.visit(ast.parse(code)))
        cr = compile_restricted(clean_code, '<string>', 'exec')
        OutputCollector.reset()
        exec(cr, get_clean_globals())
        print("---------")
        print(OutputCollector.result())

def test_fail():
    for code in [code4]:
        try:
            clean_code = ast.unparse(cleaner.visit(ast.parse(code)))
            cr = compile_restricted(clean_code, '<string>', 'exec')
            OutputCollector.reset()
            exec(cr, get_clean_globals())
            print("---------")
        except Exception as e:
            traceback.print_exc()

def test_run_notebook():
    from .notebook_logic import create_master_notebook
    with open("test_files/TestoutJuly2023source.ipynb") as f:
        s = create_master_notebook(f.read())
        nb = nbformat.reads(s, as_version=4)
    p = run_notebook(nb)
    print(nbformat.writes(nb, version=4))
    print("You got {} points".format(p))