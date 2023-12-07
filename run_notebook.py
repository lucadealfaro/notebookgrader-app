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

CELL_MISSING_NOTICE = """### Cell Missing

A cell of the original notebook is missing from the submission.

To recover from this: 

* Make a copy of the current notebook in Drive, so you avoid losing any work. 
* Look at the original notebook in the revision history to see what is missing, 
and identify the last revision when it is still present. 
* Revert to that revision. 
* Add any missing work to the notebook, by cut and pasting code from your saved copy if necessary. 

You cannot simply insert a cell with the same content, because each cell has a unique id
(you can see it if you go into the revision history and ask to see the raw form).
So if you just add text to a cell, the cell IDs will still not match.
"""

PROBLEM_NOTICE = """
### Something went wrong

Please notify your instructor.  Something is wrong with the instructor version of this notebook. 
"""

def get_cell_id(c):
    """Returns the notebookgrader cell id of a cell."""
    if c is None:
        return None
    if "metadata" not in c or "notebookgrader" not in c.metadata:
        return None
    if "id" not in c.metadata.notebookgrader:
        return None
    return c.metadata.notebookgrader.id


def get_original_cell_id(c):
    """Returns the original (jupyter) cell id of a cell."""
    if c is None or "metadata" not in c or "id" not in c.metadata:
        return None
    return c.metadata.id


def match_notebooks(master_nb, submission_nb):
    """Matches the cells of master and submission, producing a notebook
    that is a candidate for grading."""
    matched_nb = nbformat.v4.new_notebook()
    # Builds a dictionary from ids to cells for the submission. 
    original_id_to_cell = {}
    nbg_id_to_cell = {}
    for c in submission_nb.cells:
        original_id = get_original_cell_id(c)
        if original_id is not None:
            original_id_to_cell[original_id] = c
        nbg_id = get_cell_id(c)
        if nbg_id is not None:
            nbg_id_to_cell[nbg_id] = c
    # Goes through the master notebook, and tries to match the cells.
    for c in master_nb.cells:
        new_cell = None
        if c.cell_type == "markdown":
            new_cell = c
        elif c.metadata.notebookgrader.readonly:
            c.execution_count = None
            c.outputs = []
            new_cell = c
        else:
            # This is a solution cell, and we need to get it from the submission.
            master_id = get_original_cell_id(c)
            if master_id is not None:
                if master_id in original_id_to_cell:
                    # The cells match.  Merges them.
                    new_cell = original_id_to_cell[master_id]
                    new_cell.outputs = []
                    new_cell.execution_count = 0
                    new_cell.metadata.notebookgrader = c.metadata.notebookgrader
                else:
                    new_cell = nbformat.v4.new_markdown_cell(source=CELL_MISSING_NOTICE)
            else:
                # We try to match by notebook id. 
                master_nbg_id = get_cell_id(c)
                if master_nbg_id is not None:
                    if master_nbg_id in nbg_id_to_cell:
                        # The cells match.  Merges them.
                        new_cell = nbg_id_to_cell[master_nbg_id]
                        new_cell.outputs = []
                        new_cell.execution_count = 0
                        new_cell.metadata.notebookgrader = c.metadata.notebookgrader
                    else:
                        new_cell = nbformat.v4.new_markdown_cell(source=CELL_MISSING_NOTICE)
                else:
                    new_cell = nbformat.v4.new_markdown_cell(source=PROBLEM_NOTICE)
        matched_nb.cells.append(new_cell)
    return matched_nb

