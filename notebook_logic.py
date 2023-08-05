import ast
import json
import nbformat
import re
from nbformat.notebooknode import NotebookNode
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
CELL_DELETION_NOTICE = """### Cell Removed

A spurious cell has been detected in the submission, and has been removed.
"""


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

def remove_hidden_tests(cell):
    remove_from_cell(cell, HIDDEN_TESTS)

def ensure(st, a):
    """Ensures that a structure exists."""
    if a not in st:
        st[a] = NotebookNode()

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
        if "outputs" in c:
            c.outputs = ""
        check_cell_valid(c)
        ensure(c, "metadata")
        ensure(c.metadata, "notebookgrader")
        meta = c.metadata.notebookgrader
        if meta.get('id') is None:
            # We do not want to overwrite old IDs.
            meta.id = random_id()
        if c.cell_type == "code":
            meta.is_tests = False
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
                    new_cell = nbformat.v4.new_markdown_cell(
                        source=TESTS_MARKDOWN.format(points)
                    )
                    new_cell.metadata.notebookgrader = NotebookNode()
                    meta = new_cell.metadata.notebookgrader
                    meta.id = random_id()
                    meta.is_tests = False
                    meta.is_solution = False
                    meta.added = True
                    meta.readonly = True
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


def get_cell_id(c):
    if c is None:
        return None
    if "metadata" not in c or "notebookgrader" not in c.metadata:
        return None
    if "id" not in c.metadata.notebookgrader:
        return None
    return c.metadata.notebookgrader.id


def merge_cells(c_master, c_submission):
    """Matches the cells of master and submitted notebooks,
    creating what will be graded."""
    if c_master.cell_type == "markdown":
        return c_master
    elif c_master.metadata.notebookgrader.readonly:
        return c_master
    else:
        # Cleans the outputs.
        c_submission.outputs = []
        return clean_cell(c_submission)


class RemoveImports(ast.NodeTransformer):

    def visit_Import(self, node):
        return None

def clean_cell(cell):
    """Cleans a cell, removing dangerous statements."""
    # ---qui---
    return cell

def match_notebooks(master_nb, submission_nb):
    """Matches the cells of master and submission, producing a notebook
    that is a candidate for grading."""
    matched_nb = nbformat.v4.new_notebook()
    master_idx, submission_idx = 0, 0
    while master_idx < len(master_nb.cells) and submission_idx < len(submission_nb.cells):
        # Tries to match the cells.
        c_master = master_nb.cells[master_idx]
        c_submission = submission_nb.cells[submission_idx]
        master_id = get_cell_id(c_master)
        submission_id = get_cell_id(c_submission)
        if master_id == submission_id:
            # The cells match.  Merges them.
            matched_nb.cells.append(merge_cells(c_master, c_submission))
            master_idx += 1
            submission_idx += 1
        else:
            # The IDs do not match.
            # The reasonable thing to do is throw out the cell in the submitted
            # notebook, because it comes before its right place, if it has
            # a place at all.
            matched_nb.cells.append(nbformat.v4.new_markdown_cell(source=CELL_DELETION_NOTICE))
            submission_idx += 1
    # If there are any leftover master cells, adds them at this point.
    matched_nb.cells.extend(master_nb.cells[master_idx:])
    return matched_nb


def grade_notebook(master_json, submission_json):
    """Grades a notebook, producing a grade and a feedback notebook."""
    master_nb = nbformat.reads(master_json, as_version=4)
    submission_nb = nbformat.reads(submission_json, as_version=4)
    # Produces a clean notebook by matching the cells of master and submission.
    test_d = match_notebooks(master_nb, submission_nb)




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

