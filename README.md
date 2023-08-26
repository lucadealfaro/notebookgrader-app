# NotebookGrader

Author: Luca de Alfaro <luca@ucsc.edu> <luca.de.alfaro@gmail.com>

This web app is written for [py4web](https://py4web.com).
The app enables the assignment and grading of Python Notebooks via a mix of 
Google Drive, and [Google Colab](https://colab.research.google.com).  The 
flow is roughly as follows: 

* The instructor creates an assignment, setting deadlines etc. 
* The instructor uploads a notebook to the assignment. 
* The instructor shares with students an invitation URL. 
* The students click on the invitation URL, and a Colab notebook is shared 
  with them on Google Drive. 
* The students work on their Colab notebook.  
* When students like, up to a certain number of times a day (default: 3), 
  students click on a "Grade My Work" button, and receive both a grade, and 
  feedback on what tests pass and what do not. 
* Once the assignment closes, the instructor can download all grades. 

## The benefits of Colab

Having students work in Colab yields several benefits: 

* All students need is a browser.  No Python installations required.  If 
  they don't have a laptop or their laptop breaks, they can work from a 
  library computer. 
* The instructors have access to the notebooks where the students work, so 
  they can offer help looking at what the students have done, e.g. in online 
  office hours. 
* Colab keeps a full revision history of the student work.  
  * This is a disincentive to plagiarism.
  * If something happens, the instructor can look at the revision history 
    and help the student (e.g., the power goes out, the student says they 
    finished the work before the deadline, the instructor can check and accept).

## Notebook Format

The notebook follows a very simple format. 

### Solution cells

Solution code is delimited between a pair of ### BEGIN/END SOLUTION as follow:

```python
def factorial(n):
    ### BEGIN SOLUTION
    return 1 if n < 2 else n * factorial(n - 1)
    ### END SOLUTION
```

The solutions will be removed from the notebooks shared with the students, 
of course. 

### Test cells

A test cell must begin with `# Tests 10 points: What-you-are-testing` (or 
whatever the number of points is) as its very first line.  
The What-you-are-testing is used so you can see later how many points 
students got, on average, on that test. 
You can include hidden tests between 
pairs of ### BEGIN/END HIDDEN TESTS as follows: 

```python
# Tests 10 points: Tests for factorial 

assert factorial(2) == 2
assert factorial(3) == 6

### BEGIN HIDDEN TESTS
assert factorial(9) == 362880
### END HIDDEN TESTS
```

Hidden tests are used to ensure that the student code generalizes, and is 
not just written to pass the given visible tests. 

## Grading

Before a notebook is graded, NotebookGrader replaces all cells except 
solution cells with the instructor version of the cells, so students cannot 
subvert the tests. 

The students can ask for their work to be graded multiple times; the highest 
grade is kept. Students can submit late work, which is graded.  However, the 
grade is considered "invalid" and not used to compute the highest grade, 
unless the insructor manually marks it as valid.  So to allow for late 
submissions, all the instructor has to do is click to validate them.

## Deployment

To deploy this app, you need:

* A [Google Cloud project](https://cloud.google.com/?hl=en) with [Oauth 
  setup](https://support.google.com/cloud/answer/6158849?hl=en). 
* [Py4web](https://py4web.com). 
* An SQL database server.  The database object `db` is created in `common.py` 
  using parameters that describe a connection to the database; see the [pydal 
  documentation](https://py4web.com/_documentation/static/en/chapter-07.html)
  for how to connect to the database. 
* [Google Cloud Storage](https://cloud.google.com/storage) with properly configured buckets.
* A serverless environment, such as [Google Cloud Functions](https://cloud.google.com/functions) for running the grading. 
* The [grading function](https://github.com/lucadealfaro/grading-function) itself. 
* [Task queues](https://cloud.google.com/tasks/docs/creating-queues) for 
  sending the homework to be graded at appropriate rates. 
* You also need to provide pages for the terms of use and privacy policy 
  (you need them also to get the Oauth setup).

I am sure it's possible to adapt the code to run e.g. on AWS or Azure, using 
S3 instead of GCS, AWS Lambda instead of Google Cloud Functions, etc.  But 
the code here is written for the Google Cloud.

In particular, these are things you need to do for deployment: 

* You should create a `private` folder, and put in it: 
  * An `__init__.py` file. 
  * `about.html`, `privacy_policy.html`, and `terms_of_use.html` templates 
    that specify who is behind your side, what is its privacy policy, and 
    what are the terms of use. 
  * The json keys for GCS access; these are read in `common.py` to create 
    the `gcs` object.   
  * The OAuth secrets, as a json file. These secrets are passed to the 
    Google scoped login plugin in `common.py`.
  * A file `private_settings.py` containing constant declarations; look at 
    `settings.py` to see what is imported from `private_settings.py`. 
* Deployment instructions for Google App Engine can be found in the [Learn 
  Py4web](https://learn-py4web.github.io/unit20.html) class by the author. 
  There, you can find also instructions for OAuth and GCS. 

## Using it without deploying it

The author is hosting the system at https://notebookgrader.com, and you can 
use it there.  Notes: 

* The system there is fully scalable, but if you want to use it for large 
  numbers of students (several thousands or more), please send a note to the 
  author (luca.de.alfaro@gmail.com) to ensure that task queues etc. have 
  sufficient rates. 
* The grader can only grade packages it has installed.  If you use uncommon 
  python packages, check with the author.  It's easy to add packages to the 
  grader, but it needs to be done before they can be imported. 

