import json
import nbformat
import re
from nbformat._struct import Struct
from .util import random_id

BEGIN_SOLUTION = "### BEGIN SOLUTION"
END_SOLUTION = "### END SOLUTION"
SOLUTION = (BEGIN_SOLUTION, END_SOLUTION)
SOLUTION_REPLACEMENT = "### YOUR SOLUTION HERE"
BEGIN_HIDDEN_TESTS = "### BEGIN HIDDEN TESTS"
END_HIDDEN_TESTS = "### END HIDDEN TESTS"
HIDDEN_TESTS = (BEGIN_HIDDEN_TESTS, END_HIDDEN_TESTS)
IS_TESTS = "# Tests"
IS_TEST_REGEXP = "^# Tests (\d+) points"
TESTS_MARKDOWN = "***Tests: {} points***\n"

test_regexp = re.compile(IS_TEST_REGEXP)

class InvalidCell(Exception):
    pass

def is_cell_solution(cell):
    """Returns whether a cell contains text to be a solution."""
    return cell.get('cell_type') != 'markdown' and BEGIN_SOLUTION in cell.source

def is_cell_tests(cell):
    return cell.cell_type != 'markdown' and re.match(test_regexp, cell.source) is not None

def get_test_points(cell):
    if not is_cell_tests(cell):
        return 0
    g = re.match(test_regexp, cell.source)
    return int(g[1])

def check_cell_valid(cell):
    if is_cell_solution(cell) and is_cell_tests(cell):
        raise InvalidCell("Cell is invalid: you cannot have tests and solution in the same cell: {}".format(cell.source[:80]))
    if BEGIN_HIDDEN_TESTS in cell.source and not is_cell_tests(cell):
        raise InvalidCell("Cell is invalid: it contains hidden tests but no points: {}".format(cell.source[:80]))

def remove_from_cell(cell, delimiters, replacement=None):
    """Removes from the cell any portion between the delimiter strings."""
    lines = cell.source.split("\n")
    out_lines = []
    outside = True
    start_region, end_region = delimiters
    for l in lines:
        if start_region in l:
            outside = False
            # Adds replacement text if necessary.
            if replacement is not None:
                k = l.index(start_region)
                out_lines.append(l[:k] + replacement)
        if outside:
            out_lines.append(l)
        if end_region in l:
            outside = True
    cell.source = "\n".join(out_lines)

def ensure(st, a):
    """Ensures that a structure exists."""
    if a not in st:
        st[a] = Struct()

def create_master_notebook(notebook_string):
    """Checks the constraints on an assignment notebook, and derives from it the
    grading master.
    The grading master looks like a normal notebook, but contains the metadata
    that can be used for grading.
    From the grading master, it is possible to derive the notebook that is
    assigned to students."""
    nb = nbformat.reads(notebook_string, as_version=4)
    new_nb = nbformat.reads(notebook_string, as_version=4)
    new_nb.cells = []
    total_points = 0
    for i, c in enumerate(nb.cells):
        if hasattr(c, "outputs"):
            c.outputs = ""
        check_cell_valid(c)
        ensure(c, "metadata")
        ensure(c.metadata, "notebookgrader")
        meta = c.metadata.notebookgrader
        if meta.get('id') is None:
            # We do not want to overwrite old IDs.
            meta.id = random_id()
        if is_cell_solution(c):
            meta.readonly = False
            meta.is_solution = True
            meta.is_tests = False
        else:
            meta.readonly = True
            if is_cell_tests(c):
                meta.is_tests = True
                points = get_test_points(c)
                meta.test_points = points
                total_points += points
                # Creates a new cell to highlight the tests, if it's not
                # already there.
                if i == 0 or not nb.cells[i - 1].get('metadata', {}).get('notebookgrader', {}).get('added'):
                    new_cell = Struct()
                    new_cell.cell_type = 'markdown'
                    new_cell.source = TESTS_MARKDOWN.format(points)
                    new_meta = Struct()
                    new_meta.id = random_id()
                    new_meta.is_tests = False
                    new_meta.is_solution = False
                    new_meta.added = True
                    new_meta.readonly = True
                    new_cell.metadata = Struct()
                    new_cell.metadata.notebookgrader = new_meta
                    new_nb.cells.append(new_cell)
        c.metadata.notebookgrader = meta
        new_nb.cells.append(c)
    ensure(new_nb, 'metadata')
    ensure(new_nb.metadata, 'notebookgrader')
    new_nb.metadata.notebookgrader.total_points = total_points
    return nbformat.writes(new_nb, version=4)

def produce_student_version(master_notebook_string):
    """Given a master notebook string, produces the student version.
    Using strings enables us to clone the notebook."""
    nb = nbformat.reads(master_notebook_string, as_version=4)
    for i, c in enumerate(nb.cells):
        meta = c.metadata.notebookgrader
        if meta.get('is_tests'):
            # We need to remove the hidden tests.
            remove_from_cell(c, HIDDEN_TESTS)
        elif meta.get('is_solution'):
            remove_from_cell(c, SOLUTION, SOLUTION_REPLACEMENT)
    return nbformat.writes(nb, version=4)


def match_cells(master_d, submission_d):
    """Matches the cells of master and submission, producing a notebook
    that is a candidate for grading."""
    # ---qui---
    return {}

def grade_notebook(master_json, submission_json):
    """Grades a notebook, producing a grade and a feedback notebook."""
    master_d = json.loads(master_json)
    submission_d = json.loads(submission_json)
    # Produces a clean notebook by matching the cells of master and submission.
    test_d = match_cells(master_d, submission_d)



def test_produce_master_twice():
    with open("./test_files/TestoutJuly2023source.json") as f:
        s0 = f.read()
    s1 = create_master_notebook(s0)
    s2 = create_master_notebook(s1)
    assert s1 == s2

def test_no_solution():
    with open("./test_files/TestoutJuly2023source.json") as f:
        s0 = f.read()
    s1 = create_master_notebook(s0)
    s2 = produce_student_version(s1)
    nb = nbformat.reads(s2, as_version=4)
    for c in nb.cells:
        assert BEGIN_SOLUTION not in c.source

def test_no_hidden_tests():
    with open("./test_files/TestoutJuly2023source.json") as f:
        s0 = f.read()
    s1 = create_master_notebook(s0)
    s2 = produce_student_version(s1)
    nb = nbformat.reads(s2, as_version=4)
    for c in nb.cells:
        assert BEGIN_HIDDEN_TESTS not in c.source

