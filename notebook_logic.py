import ast
import json
import traceback

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
IS_TEST_REGEXP = r"^# *Tests? (\d+) points"
TEST_NAME_REGEXP = r"^# *Tests \d+ points *: *([^\n]*)"


test_regexp = re.compile(IS_TEST_REGEXP)
test_name_regexp = re.compile(TEST_NAME_REGEXP)

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

def get_test_name(cell):
    """Returns the name the user assigned to the tests."""
    g = re.match(test_name_regexp, cell.source)
    try:
        return g[1].strip().capitalize()
    except Exception as e:
        return "Unnamed"

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

def remove_all_hidden_tests(nb):
    for cell in nb.cells:
        remove_hidden_tests(cell)

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
    assigned to students.
    Returns:
        - Json of master notebook
        - total points
        - list of (test_id, test_name, test_points) in the notebook.
    """
    nb = nbformat.reads(notebook_string, as_version=4)
    new_nb = nbformat.reads(notebook_string, as_version=4)
    new_nb.cells = []
    total_points = 0
    test_list = []
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
            meta.is_solution = False
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
                test_name = get_test_name(c)
                test_list.append((meta.id, test_name, points))
        c.metadata.notebookgrader = meta
        new_nb.cells.append(c)
    ensure(new_nb, 'metadata')
    # Changes the kernel to the one used by Colab.
    new_nb.metadata.kernelspec = NotebookNode()
    new_nb.metadata.kernelspec.name = "python3"
    new_nb.metadata.kernelspec.display_name = "Python 3"
    new_nb.metadata.language_info = NotebookNode()
    new_nb.metadata.language_info.name = "python"
    # Adds total points into notebook.
    ensure(new_nb.metadata, 'notebookgrader')
    new_nb.metadata.notebookgrader.total_points = total_points
    return nbformat.writes(new_nb, version=4), total_points, test_list

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


def extract_awarded_points(nb):
    """Returns a dictionary mapping cell id to awarded points."""
    d = {}
    for c in nb.cells:
        if c.cell_type == "code":
            meta = c.metadata.notebookgrader
            if hasattr(meta, "is_tests") and meta.is_tests:
                d[meta.id] = meta.points_earned
    return d


# Logic to check absence of imports in submissions.
class ForbiddenImport(Exception):
    pass


class ImportInspector(ast.NodeTransformer):

    def visit_Import(self, node):
        raise ForbiddenImport()

    def visit_ImportFrom(self, node):
        raise ForbiddenImport()

import_inspector = ImportInspector()

def is_solution(c):
    return (c.cell_type == "code"
            and hasattr(c, "metadata")
            and hasattr(c.metadata, "notebookgrader")
            and hasattr(c.metadata.notebookgrader, "is_solution")
            and c.metadata.notebookgrader.is_solution)

def is_notebook_well_formed(notebook_string):
    """
    Checks whether the notebook is well-formed and can be graded.
    Args:
        notebook_string:

    Returns:

    """
    nb = nbformat.reads(notebook_string, as_version=4)
    for c in nb.cells:
        if is_solution(c):
            try:
                parse_tree = ast.parse(c.source)
            except SyntaxError as e:
                return False, c.source, "Syntax error"
            try:
                import_inspector.visit(parse_tree)
            except ForbiddenImport as e:
                return False, c.source, "Imports are not allowed in solution cells"
    return True, None, None




##################################

def test_total_points():
    with open("./test_files/TestoutJuly2023source.json") as f:
        s0 = f.read()
    s1, pts, _ = create_master_notebook(s0)
    assert pts == 65

def test_produce_master_twice():
    with open("./test_files/TestoutJuly2023source.json") as f:
        s0 = f.read()
    s1, _, _ = create_master_notebook(s0)
    s2, _, _ = create_master_notebook(s1)
    assert s1 == s2

def test_no_solution():
    with open("./test_files/TestoutJuly2023source.json") as f:
        s0 = f.read()
    s1, _, _ = create_master_notebook(s0)
    s2 = produce_student_version(s1)
    nb = nbformat.reads(s2, as_version=4)
    for c in nb.cells:
        assert BEGIN_SOLUTION not in c.source

def test_no_hidden_tests():
    with open("./test_files/TestoutJuly2023source.json") as f:
        s0 = f.read()
    s1, _, _ = create_master_notebook(s0)
    s2 = produce_student_version(s1)
    nb = nbformat.reads(s2, as_version=4)
    for c in nb.cells:
        assert BEGIN_HIDDEN_TESTS not in c.source

def test_no_solution_imports():
    with open("./test_files/TestoutJuly2023source_with_imports.json") as f:
        s0 = f.read()
    s1, _, _ = create_master_notebook(s0)
    v, c, r = is_notebook_well_formed(s1)
    # print(r)
    assert v is False

def test_syntax_errors():
    with open("./test_files/TestoutJuly2023source_with_syntax_errors.json") as f:
        s0 = f.read()
    s1, _, _ = create_master_notebook(s0)
    v, c, r = is_notebook_well_formed(s1)
    # print(r)
    assert v is False
