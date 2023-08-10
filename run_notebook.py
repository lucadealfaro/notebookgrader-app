# This file contains the functions used to run a notebook.

import ast
import builtins
import importlib
import nbformat.v4, nbformat
import threading
import traceback
import warnings


warnings.simplefilter("ignore") # Silences nasty warnings from restricted python.

CELL_DELETION_NOTICE = """### Cell Removed

A spurious cell has been detected in the submission, and has been removed.
"""

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
        c_master.outputs = []
        return c_master
    else:
        c_submission.outputs = []
        return c_submission

def match_notebooks(master_nb, submission_nb):
    """Matches the cells of master and submission, producing a notebook
    that is a candidate for grading."""
    matched_nb = nbformat.v4.new_notebook()
    master_idx, submission_idx = 0, 0
    while master_idx < len(master_nb.cells) and submission_idx < len(
            submission_nb.cells):
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
            matched_nb.cells.append(
                nbformat.v4.new_markdown_cell(source=CELL_DELETION_NOTICE))
            submission_idx += 1
    # If there are any leftover master cells, adds them at this point.
    matched_nb.cells.extend(master_nb.cells[master_idx:])
    return matched_nb

