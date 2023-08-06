# This file contains the functions used to run a notebook.

import ast
import builtins
import nbformat.v4, nbformat
import threading
import traceback
import warnings

warnings.simplefilter("ignore") # Silences nasty warnings from restricted python.

from .notebook_logic import remove_hidden_tests

class IllegalImport(Exception):
    pass

SAFE_BUILTINS = [
    'ArithmeticError',
    'AssertionError',
    'AttributeError',
    'BaseException',
    'BaseExceptionGroup',
    'BlockingIOError',
    'BrokenPipeError',
    'BufferError',
    'BytesWarning',
    'ChildProcessError',
    'ConnectionAbortedError',
    'ConnectionError',
    'ConnectionRefusedError',
    'ConnectionResetError',
    'DeprecationWarning',
    'EOFError',
    'Ellipsis',
    'EncodingWarning',
    'EnvironmentError',
    'Exception',
    'ExceptionGroup',
    'False',
    'FileExistsError',
    'FileNotFoundError',
    'FloatingPointError',
    'FutureWarning',
    'GeneratorExit',
    'IOError',
    'ImportError',
    'ImportWarning',
    'IndentationError',
    'IndexError',
    'InterruptedError',
    'IsADirectoryError',
    'KeyError',
    'KeyboardInterrupt',
    'LookupError',
    'MemoryError',
    'ModuleNotFoundError',
    'NameError',
    'None',
    'NotADirectoryError',
    'NotImplemented',
    'NotImplementedError',
    'OSError',
    'OverflowError',
    'PendingDeprecationWarning',
    'PermissionError',
    'ProcessLookupError',
    'RecursionError',
    'ReferenceError',
    'ResourceWarning',
    'RuntimeError',
    'RuntimeWarning',
    'StopAsyncIteration',
    'StopIteration',
    'SyntaxError',
    'SyntaxWarning',
    'SystemError',
    'SystemExit',
    'TabError',
    'TimeoutError',
    'True',
    'TypeError',
    'UnboundLocalError',
    'UnicodeDecodeError',
    'UnicodeEncodeError',
    'UnicodeError',
    'UnicodeTranslateError',
    'UnicodeWarning',
    'UserWarning',
    'ValueError',
    'Warning',
    'ZeroDivisionError',
    '__build_class__',
    '__debug__',
    '__doc__',
    '__import__',
    # '__loader__',
    '__name__',
    '__package__',
    '__spec__',
    'abs',
    'aiter',
    'all',
    'anext',
    'any',
    'ascii',
    'bin',
    'bool',
    # 'breakpoint',
    'bytearray',
    'bytes',
    'callable',
    'chr',
    'classmethod',
    # 'compile',
    'complex',
    'copyright',
    'credits',
    'delattr',
    'dict',
    # 'dir',
    'divmod',
    'enumerate',
    # 'eval',
    # 'exec',
    # 'execfile',
    'filter',
    'float',
    'format',
    'frozenset',
    'getattr',
    # 'globals',
    'hasattr',
    'hash',
    'help',
    'hex',
    'id',
    'input',
    'int',
    'isinstance',
    'issubclass',
    'iter',
    'len',
    'license',
    'list',
    # 'locals',
    'map',
    'max',
    'memoryview',
    'min',
    'next',
    'object',
    'oct',
    # 'open',
    'ord',
    'pow',
    # 'print', # replaced
    'property',
    'range',
    'repr',
    'reversed',
    'round',
    'set',
    'setattr',
    'slice',
    'sorted',
    'staticmethod',
    'str',
    'sum',
    'super',
    'tuple',
    'type',
    'vars',
    'zip'
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
    # "time",
    # Data handling.
    "json", "base64", "binascii",
    ]




class CleanCode(ast.NodeTransformer):

    def visit_Import(self, node):
        for n in node.names:
            module_name = n.name.split(".")[0]
            if module_name not in WHITELISTED_MODULES:
                raise IllegalImport("You cannot import module {}".format(module_name))
        return node

    def visit_ImportFrom(self, node):
        module_name = node.module.split(".")[0]
        if module_name not in WHITELISTED_MODULES:
            raise IllegalImport("You cannot import module {}".format(module_name))
        return node

cleaner = CleanCode()

def my_setitem(d, i, x):
    d[i] = x

def get_clean_globals():
    my_builtins = {k: getattr(builtins, k) for k in SAFE_BUILTINS}
    my_globals = dict(__builtins__=my_builtins)

    return my_globals


class OutputCollector(object):

    def __init__(self, _getattr_=None):
        self.txt = []
        self.lock = threading.Lock()

    def write(self, text):
        with self.lock:
            self.txt.append(text)

    def result(self):
        with self.lock:
            return '\n'.join(self.txt)

    def clear(self):
        with self.lock:
            self.txt = []

    def __call__(self, *args):
        with self.lock:
            self.txt.append(" ".join([str(a) for a in args]))


class RunCellWithTimeout(object):
    def __init__(self, function, collector, args):
        self.function = function
        self.collector = collector
        self.args = args
        self.answer = "timeout"

    def worker(self):
        self.answer = self.function(*self.args)
        # print("Cell answered:", self.answer)

    def run(self, timeout=None):
        thread = threading.Thread(target=self.worker)
        thread.start()
        thread.join(timeout=timeout)
        return self.answer



def run_cell(c, my_globals, collector):
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
        collector.clear()
        clean_code = ast.unparse(cleaner.visit(ast.parse(c.source)))
        cr = compile(clean_code, '<string>', 'exec')
        exec(cr, my_globals)
        add_output(c, collector.result())
        # print("Returning True")
        return True
    except IllegalImport as e:
        add_output(c, collector.result())
        add_output(c, "Import Error: {}".format(str(e)))
        # print("Returning False")
        return False
    except Exception as e:
        err = traceback.format_exception_only(e)[0]
        add_output(c, collector.result())
        add_output(c, err)
        # print("Returning False")
        return False


def add_output(c, text):
    # print("Output:", text) # DEBUG
    c.outputs.append(nbformat.v4.new_output(
        "execute_result",
        {"text/plain": text}))

def add_feedback(c, text):
    c.outputs.insert(0, nbformat.v4.new_output(
        "execute_result", {"text/html": "<b>{}</b>".format(text)}
    ))

def run_notebook(nb, timeout=10):
    """Runs a notebook, returning a notebook with output cells completed.
    Args:
        nb: notebook to be run.
        timeout: cell timeout to be used.
    Returns:
        The total number of points.
        The notebook is adorned with the results of the execution.
    """
    collector = OutputCollector()
    my_globals = get_clean_globals()
    my_globals["__builtins__"]["print"] = collector
    execution_count = 0
    points_earned = 0
    for c in nb.cells:
        if c.cell_type == "code":
            # Runs the cell.
            runner = RunCellWithTimeout(run_cell, collector,(c, my_globals, collector))
            res = runner.run(timeout=timeout)
            # print("----> Result:", res) # DEBUG
            execution_count += 1
            # c.execution_count = execution_count
            # If the cell timed out, adds an explanation of it to the outputs.
            if res == "timeout":
                explanation = "Timeout Error: The cell timed out after {} seconds".format(timeout)
                add_feedback(c, explanation)
            if c.metadata.notebookgrader.is_tests:
                # Gives points for successfully completed test cells.
                points = c.metadata.notebookgrader.test_points
                # print("Cell worth", points, "points") # DEBUG
                if res is True:
                    points_earned += points
                    add_feedback(c, "Tests passed, you earned {}/{} points".format(points, points))
                else:
                    add_feedback(c, "Tests failed, you earned {}/{} points".format(0, points))
                # Puts the source back removing the hidden tests.
                remove_hidden_tests(c)
            execution_count += 1
            c.execution_count = execution_count
    return points_earned


######################
# Tests

code1 = """
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

code5 = """
import os
"""

def test_exec():
    for code in [code1, code2, code3]:
        collector = OutputCollector()
        my_globals = get_clean_globals()
        my_globals["__builtins__"]["print"] = collector
        clean_code = ast.unparse(cleaner.visit(ast.parse(code)))
        cr = compile(clean_code, '<string>', 'exec')
        exec(cr, my_globals)
        print("---------")
        print(collector.result())

def test_fail():
    for code in [code4, code5]:
        try:
            collector = OutputCollector()
            my_globals = get_clean_globals()
            my_globals["__builtins__"]["print"] = collector
            clean_code = ast.unparse(cleaner.visit(ast.parse(code)))
            cr = compile(clean_code, '<string>', 'exec')
            exec(cr, my_globals)
            print(collector.result())
            print("---------")
            result = False
        except Exception as e:
            result = True
        assert result, "Let something incorrect happen."

def test_run_notebook():
    from .notebook_logic import create_master_notebook
    with open("test_files/TestoutJuly2023source.ipynb") as f:
        s = create_master_notebook(f.read())
        nb = nbformat.reads(s, as_version=4)
    p = run_notebook(nb)
    with open("test_files/run_result.ipynb", "w") as f:
        f.write(nbformat.writes(nb, version=4))
    print("You got {} points".format(p))

def test_run_bad_notebook():
    from .notebook_logic import create_master_notebook
    with open("test_files/notebook_w_errors.ipynb") as f:
        s = create_master_notebook(f.read())
        nb = nbformat.reads(s, as_version=4)
    p = run_notebook(nb)
    with open("test_files/result_w_errors.ipynb", "w") as f:
        f.write(nbformat.writes(nb, version=4))
    print("You got {} points".format(p))