# Exam Scheduler

Author: Siddhant Tiwari ([finrelemos@gmail.com](mailto:finrelemos@gmail.com)).

Exam Scheduler creates examination timetables from student registrations and approved room capacities.
The suite includes a timetable generator, a timetable editor, and an offline room editor.
It produces Excel timetables, a timetable PDF, and examination attendance PDFs.
It checks total room capacity but does not assign candidates or examinations to individual rooms. Google CP-SAT is used as the solver.

[Install and Use](#install-and-use) · [Real registration data](#prepare-real-registration-data) · [Configuration](#configure-an-examination-period) · [Results](#read-and-keep-the-results) · [Timetable editing](#edit-a-timetable) · [Colab](#use-google-colab) · [HPC](#use-an-hpc-system) · [Troubleshooting](#troubleshooting) · [License](#license-and-author)

## Install and Use

Follow these steps in order for your first local example.
If you only want to edit rooms, complete steps 1 and 2, then open the [room editor instructions](#edit-room-capacities).
If you want to solve remotely, read steps 1 and 2, then follow [Colab](#use-google-colab) or [HPC](#use-an-hpc-system).
You do not need to install the solver on your laptop when you solve remotely.

### 1. Choose where to work

A terminal is a window where you type commands.
Python runs this suite's program files.
A dependency is another software package that the suite needs.
A solver searches for a timetable that satisfies the rules.

| Work location | Suitable use | What you need |
| --- | --- | --- |
| Your computer | All workflows, including small example runs and local solving | Python, permission to install dependencies, and sufficient computing resources for your data |
| Google Colab | Solving in a browser notebook on Google's computers | An approved Google account, internet access, and permission to upload the data |
| HPC | Longer searches on an institutional high-performance computing system | An institutional account and an approved batch-job allocation |

A notebook runs commands in separate cells.
A batch job runs on a cluster after the cluster grants computing resources.
Ask your administrator for help with HPC account, storage, and allocation requirements.
Do not run a long search on a shared cluster login machine.

For a local installation, prepare these items:

1. Use Python 3.10 or later with compatible dependency packages. Python 3.12 is a practical installation choice.
2. Use a current browser for the room editor.
3. Use Excel or another application that can save `.xlsx` workbooks to prepare registrations.
4. Use a PDF viewer to read the generated timetable and attendance sheets.
5. Obtain permission to install dependencies and handle student data on the chosen machine.

Use the same approved Python environment for solving and timetable editing.
Do not use administrator privileges or `sudo` merely to install the suite's dependencies.

### 2. Download and extract the suite

Obtain `exam_scheduler_release.zip` from your software supplier or institution.
A ZIP archive packages files in one compressed download.
Extract it before running any program. Do not run Python files from inside the ZIP viewer.
The extracted project folder is named `exam_scheduler`.
It contains `README.md`, `schedule_exams.py`, `data`, `examples`, and the other suite files.

1. On Windows, right-click the ZIP in File Explorer and select `Extract All`.
2. On macOS, double-click the ZIP in Finder.
3. On Linux, use your file manager's extract action.
4. Open the extracted folders until you see `schedule_exams.py` beside this README.
5. Keep this project in a folder where you can create files.

Success means that you can open `examples/registrations_template.xlsx` from the extracted folder.
If you see another ZIP instead of Python files, finish extracting the archive.
If you cannot find `schedule_exams.py`, open the inner `exam_scheduler` folder.

The following paths are examples, not required installation locations.
Replace the whole quoted path with the actual project-folder path on your machine.
Keep quotation marks around a path that contains spaces.

### 3. Open a terminal in the project folder

#### Windows PowerShell

Open the Windows Start menu, type `PowerShell`, and open it.
The following command changes the terminal's current folder.
For example, replace `YourName` with your Windows account name and adjust the extraction location.

```powershell
cd "C:\Users\YourName\Downloads\exam_scheduler_release\exam_scheduler"
```

Expected result: the prompt ends with your project-folder path. The command normally prints no separate success message.
If PowerShell says that the path does not exist, copy the project-folder path from File Explorer and try again.

Now list the main program file to make sure that you reached the correct folder.
Run this in the same PowerShell window.

```powershell
Get-Item .\schedule_exams.py
```

Expected result: a file listing that includes `schedule_exams.py`.
If the file is missing, return to File Explorer and locate the folder that contains it.
Do not continue from the archive's outer folder.

#### macOS or Linux terminal

On macOS, open Terminal from Applications → Utilities.
On Linux, open your desktop's Terminal application.
The following command enters an example extraction location. Replace it with your actual project-folder path.

```bash
cd "$HOME/Downloads/exam_scheduler"
```

Expected result: no error. The terminal now works in that folder.
If the folder does not exist, use the actual extraction path from your file manager.

The next command lists the main program file from the current folder.

```bash
ls schedule_exams.py
```

Expected result: `schedule_exams.py`.
If the terminal reports that the file is missing, locate the inner project folder before continuing.

### 4. Make sure that Python is available

On Windows PowerShell, this command asks the Python launcher for the installed Python version.
It does not install anything.

```powershell
py --version
```

Expected result: a version such as `Python 3.12.x`. The exact version varies.
If `py` is unavailable, install a compatible Python from [python.org](https://www.python.org/downloads/) or contact your administrator.
Reopen PowerShell after installation, then repeat step 3.
If only `python --version` works, use `python` instead of `py` when creating the environment below.

On macOS or Linux, use this command in the terminal instead.

```bash
python3 --version
```

Expected result: Python 3.10 or later.
If Python is absent or older, install a compatible version through an approved source or ask your administrator.
Do not replace an operating system's own Python installation.

### 5. Create an isolated Python environment

A virtual environment keeps this project's dependencies separate from other Python programs.
Create it once in the extracted project folder.
The name `.venv` identifies its folder.

On Windows PowerShell, this command creates the environment with the Python version found in step 4.

```powershell
py -m venv .venv
```

Expected result: a new `.venv` folder and no error. Creation can take a short time.
If the command fails, resolve the reported Python or folder-permission problem before proceeding.
Do not delete an existing environment that belongs to another project.

On macOS or Linux, create the environment with this command instead.

```bash
python3 -m venv .venv
```

Expected result: a `.venv` folder.
If Linux reports that `venv` or `ensurepip` is unavailable, ask your administrator to enable the Python virtual-environment package.

Activation makes the terminal use the environment's Python.
On Windows PowerShell, activate it with the following command from the project folder.

```powershell
.\.venv\Scripts\Activate.ps1
```

Expected result: the prompt normally starts with `(.venv)`.
If PowerShell blocks script execution, use the [Command Prompt alternative](#powershell-blocks-environment-activation) without changing system security policy.

On macOS or Linux, activate it with this command instead.

```bash
source .venv/bin/activate
```

Expected result: the prompt normally starts with `(.venv)`.
If the activation file is missing, make sure that environment creation succeeded in this same folder.

From this point, local instructions use `python` inside the activated environment on all three operating systems.
In that terminal, the following command shows the Python executable that will run the suite.

```text
python -c "import sys; print(sys.executable)"
```

Expected result: a path inside this project's `.venv` folder.
If it points somewhere else, activate the project environment before installing packages.
When you open a new terminal later, enter the project folder and activate `.venv` again.

### 6. Install only what you need

The installer is `pip`, Python's package installation tool.
`python -m pip` uses the installer attached to the active Python environment.
Installation requires internet access or your institution's approved package source.
No suite program installs packages automatically.
Runtime dependencies are packages needed while the application runs.

| Task | Installation needed |
| --- | --- |
| Open the browser room editor | None |
| Inspect workbooks or save configuration without solving | `requirements-input.txt`, which installs openpyxl |
| Generate or reschedule timetables and export Excel/PDF reports | `requirements-solver.txt`, which installs openpyxl, OR-Tools, and ReportLab |

For the complete local example, run the following command in the activated project terminal.
It installs all runtime dependencies. OR-Tools also installs its own dependencies, including NumPy and pandas.

```text
python -m pip install -r requirements-solver.txt
```

Expected result: successful installation messages, or `Requirement already satisfied` for installed packages.
The exact package versions and installer messages vary.
If installation fails, do not start the example. Use the dependency guidance in [Troubleshooting](#troubleshooting).

If you only want workbook inspection or configuration preparation on this machine, use the smaller installation instead.
Skip the full solver installation above when taking this route.

```text
python -m pip install -r requirements-input.txt
```

Expected result: openpyxl installs or is already present.
You can now inspect registrations and use `--setup-only`, but you must use a solver-equipped machine for generation and rescheduling.
Continue with step 7, then use the [configuration-only workflow](#save-configuration-without-solving) and the remote instructions.

### 7. Inspect the fictional example

A registration is one student's participation in one course.
The supplied workbook contains five fictional registrations, not real student data.
An audit registration is marked for midsem participation only.
Do not change these rows for the first demonstration.

In the activated project terminal, this command reads the workbook and reports its structure without solving or creating a timetable.
`--input` selects the workbook. `--inspect` stops after inspection.

```text
python schedule_exams.py --input examples/registrations_template.xlsx --inspect
```

Expected result for the supplied workbook:

```json
{
  "registration_rows": 5,
  "students": 3,
  "audit_rows": 1,
  "assessments": {
    "written": 4,
    "lab": 1
  },
  "issues": []
}
```

`issues: []` means that the importer found no source-format issues.
It does not prove that a real institution supplied every compulsory registration.
If issues appear for your own workbook, correct the listed rows before generation.

### 8. Generate the example timetable

Complete this step on a machine with the full solver dependencies installed.
A configuration is the set of dates, sessions, and rules for an examination period.
The supplied configuration uses fictional March 2027 dates. It is not approval for an actual examination period.

Run the following command in the activated project terminal.
`--config` selects the supplied configuration and avoids setup questions.
`--solve-minutes 1` gives both search stages a shared one-minute budget, not one minute per stage.
A proof can finish much sooner.

```text
python schedule_exams.py --input examples/registrations_template.xlsx --config examples/exam_config.json --solve-minutes 1
```

Expected result: the program prints its input summary, configuration, runtime information, and completion analysis.
The example has three eligible students, two examination events, and 12 usable dates.
Its final messages resemble the following illustrative excerpt. Paths and run identifiers vary.

```text
Saved timetable: .../runs/RUN_ID/revisions/0001/state.json
Exports: SUCCESS
Completion analysis: ...
```

`SUCCESS` means that all three export stages completed.
If the program prints an error, no successful generation is established.
If it prints `PARTIAL_SUCCESS`, the saved timetable exists but at least one report export failed.
Read [partial export guidance](#a-report-export-fails) before using those reports.

### 9. Open and keep the results

A run is one generation attempt with its own output folder.
`RUN_ID` is a placeholder for the actual folder name printed by the program.
For example, a run identifier can look like `20270301T090000_123456Z`. Do not type that example unless it is your actual folder.

1. Open the project folder in your file manager.
2. Open `runs` and then the folder named in the console's saved-timetable path.
3. Open `revisions`, then `0001`.
4. Open `timetable.xlsx` to review the exam list and student lists.
5. Open `timetable.pdf` to view the printable exam listing.
6. Open `attendance` to view one PDF for each examination event. The fictional example produces two attendance PDFs.
7. Keep `state.json`, the run's `checkpoint.json`, and the original inputs with your results.

A revision is a saved timetable edition that the editor does not overwrite.
`state.json` contains the timetable, registrations, rooms, and configuration used for editing.
A feasible timetable satisfies all configured hard rules.
A checkpoint is a saved feasible timetable that you can solve again.
PDFs alone are not enough to resume or edit a timetable.

### 10. Practice the timetable editor

Practice on the fictional result before changing a real timetable.
The following command opens its saved state in the editor.
Replace `RUN_ID` with the folder name from step 9 and quote the whole path if it contains spaces.
Run it in the activated project terminal.

```text
python edit_timetable.py "runs/RUN_ID/revisions/0001/state.json"
```

Expected result: a menu that begins with `Actions:` and an `Action:` prompt.
If the state cannot be found, copy the saved-state path from your results and use that exact file.

For a safe first exercise:

1. At `Action:`, enter `rebuild` and press Enter.
2. Read the impact preview. This action makes sure that the current timetable follows the rules and regenerates its reports.
3. When asked to save a new revision, enter `yes`.
4. Note the printed `New revision:` path. With no other edits, it ends in `revisions/0002/state.json`.
5. At the next action prompt, enter `quit`.
6. Open revision `0002` and make sure that its reports exist. Revision `0001` remains unchanged.

To move exams, compare alternatives, or change rules, follow [Edit a timetable](#edit-a-timetable).
To use real registrations, continue below rather than reusing the fictional results.

## Prepare real registration data

### Create a separate workbook

Do not mix fictional example rows with real registrations.
A complete registration list is an institutional responsibility. The suite cannot discover missing candidates from an incomplete workbook.

1. Open `examples/registrations_template.xlsx` in your spreadsheet application.
2. Use `Save As` to create `registrations.xlsx` in the project folder. Keep the supplied template unchanged.
3. Open the `Registrations` sheet.
4. Delete every data row whose Student ID starts with `DEMO`. Keep the column headings in row 1.
5. Enter one row for every actual student-course registration.
6. Include compulsory courses, electives, actual minor papers, and repeat registrations for this examination period.
7. Save the file as `.xlsx`, not `.csv` or `.xls`.
8. Close the workbook before replacing it or exporting reports to the same location.

For backlog examinations, supply only the reviewed backlog candidates for that period.
The `Registration Type` label does not automatically select backlog students from a normal-semester list.

### Use the registration columns correctly

The first six column headings are required. The other headings provide optional information.
A blank Course Code is permitted. The other required values must be present on every registration row.

| Column | What to enter |
| --- | --- |
| Student ID | A stable identifier, such as `STU001`. Use the same identifier for that student on every row. Keep identifiers as text to retain leading zeros. |
| Student Name | The student's full display name. Use the same name consistently. |
| Course Code | A consistent code for one paper, such as `MA101`. Leave blank only for an uncoded paper. |
| Course Name | The actual examination paper name, such as `Mathematics I`, not a programme title. |
| Audit | `Yes` or `No` for this registration. Do not leave blank. |
| Assessment | `Written`, `Lab`, `Swayam`, or `None`. |
| Registration Type | A descriptive label, such as `Compulsory`, `Elective`, `Minor`, `Backlog`, or `Repeat`. |
| Status | `Active`, `Dropped`, or `Withdrawn`. Blank means Active. |
| Branch | The student's branch or programme, if available. |
| Notes | Optional information for review. |

For example, a student taking two papers needs two rows with the same Student ID.
If only the second paper is an audit registration, set Audit to Yes only on that row.
An audit registration means participation marked for midsem only in this suite.
It does not remove the student's other registrations from endsem or backlog.

Use the same course code for the same paper across every branch and sheet.
For an uncoded paper, the normalized course name identifies the paper.
Distinct papers need distinct codes or clearly distinct uncoded names.
The program normalizes capitalization and whitespace for several identifiers. Do not rely on punctuation alone to distinguish uncoded papers.

Avoid these input errors:

1. Do not use formulas, merged cells, repeated headings, or separate course-title rows in `Registrations`.
2. Do not use a minor programme title in place of an actual paper.
3. Do not insert standalone Dropped or Withdrawn notes between students. Use the Status column.
4. Resolve duplicate registrations with conflicting audit or status values.
5. Review reported duplicate and name-variant warnings. Identical eligible student-course duplicates count once.

### Inspect your workbook

Run the following command in the activated project terminal after saving `registrations.xlsx`.
It reads your file without solving or creating a run folder.

```text
python schedule_exams.py --input registrations.xlsx --inspect
```

Expected result: counts for your workbook and an `issues` list.
Proceed only after correcting every listed source issue and obtaining approval that the candidate list is complete.
The counts vary with your input. Compare them with an independent institutional roster.
Inspection alone does not test all duplicate, audit, calendar, or capacity conflicts. Setup performs further tests.

### Block-style input

The importer also accepts a repeated-block workbook format when there is no sheet named `Registrations`.
Each block begins with a course heading in column A and no other values on that heading row.
A following header row has `Student ID` in column B and `Student Name` or `Name` in column C.
Student rows use column A for a serial number, B for the identifier, C for the name, and D for the branch.
Later columns become notes.

Identifiers in this format must match the supported pattern, such as `SC26M001`: SC, two digits, one letter, and three digits.
A heading such as `AVD613 - Machine Learning` supplies the course code and name.
The importer recognizes `(AUDIT)` in names without regard to letter case.
Lab names, Laboratory names, and names beginning with Swayam are excluded from written examinations.

Standalone status markers and unresolved programme-only minor headings block scheduling.
After a standalone status marker, a new course heading is required before further student rows can be accepted.
For explicit status, assessment, and registration-type control, use the flat `Registrations` format described above.

## Edit room capacities

The room editor works directly in your browser. It does not need Python, a web server, or an internet connection.
JSON is a text format for structured data. The browser editor lets you edit the room JSON without writing that text yourself.

1. Open the extracted project's `assets` folder.
2. Double-click `room_editor.html`. If necessary, use `Open with` and choose your browser.
3. Use the file picker near the top to open `data/rooms.json` from the project folder.
4. Select a room from the list.
5. Enter its institution-approved examination capacity as a nonnegative whole number.
6. Set the label, block, priority, and Room active option as needed.
7. Select `Apply room changes`.
8. Read the message and capacity totals before editing another room.
9. Select `Download rooms.json` when your changes are complete.
10. Find the downloaded file and save a separate copy named `edited_rooms.json` in the project folder.

Expected result: the browser reports a download request and you obtain a JSON file containing the edited rooms.
The original `data/rooms.json` does not change automatically.
A browser can add a number to repeated downloads, such as `rooms (1).json`. Rename the reviewed file before use.
If the editor shows an error, the attempted change is not applied. Correct the field and select Apply again.

A zero capacity contributes no seats. Enter an explicit `0`, not a blank field.
An inactive room contributes no capacity.
`Add room` creates a room with zero capacity, which you must review before use.
`Remove selected room` deletes a room from the browser copy. `Undo` restores the preceding applied change.
Keep stable Room IDs when changing only display labels.
Priority controls room-list ordering. It does not assign candidates to particular rooms.

The supplied layout has 14 active rooms and total capacity 691.
These numbers are starting data, not institutional approval of room capacities.
The scheduler uses the sum of active capacities after date restrictions.
Restrictions affect every session on each affected date and do not change the permanent room list.

To use the downloaded copy, supply `--rooms edited_rooms.json` during setup or generation.
For example, the following command begins interactive setup with your real workbook and edited room file.
Run it only after reviewing both files and installing solver dependencies on the current machine.

```text
python schedule_exams.py --input registrations.xlsx --rooms edited_rooms.json
```

Expected result: an input summary followed by the complete-candidate-list question.
Follow the next section to answer the questions. No solving begins until the configuration and time budget are approved.
If the downloaded file cannot be read, make sure that it is actual JSON and that its filename matches the command.

### Room JSON fields

For administrators editing JSON directly, the file contains `format_version: 1` and a `rooms` list.
Each room requires a unique nonblank `room_id`, a nonblank `label`, integer `priority`, Boolean `active`, and integer `capacity`.
A Boolean value is `true` or `false`, not quoted text. `block` is optional display information.
Priority and capacity must be nonnegative. Fractional and Boolean capacities are rejected.

### Optional room-workbook conversion

Skip this workflow when you use the supplied room JSON or the browser editor.
It converts approved room totals from a workbook's `ROOMS` worksheet.
That sheet needs `Room ID`, `Room`, `Block`, `Priority`, `Usable Seats`, and `Use For Exams` headings.
Normal scheduling does not require a master workbook.

In the activated terminal, the following command reads `master.xlsx` and creates a new `migrated_rooms.json` without opening a browser.
Replace `master.xlsx` with your actual approved room workbook. The destination must not already exist.

```text
python edit_rooms.py --migrate master.xlsx --rooms migrated_rooms.json --no-browser
```

Expected result: the new room JSON, its room count, and its active capacity printed in the terminal.
Review the totals before using the output with `--rooms`.
The converter accepts whole numeric values and integer text. It rejects fractions, negative values, nonfinite values, and Boolean capacities or priorities.
Publication requires filesystem hard-link support, which allows a complete file to appear only under an unused name.
If conversion fails, correct the source or choose a supported destination. It does not replace an existing output.

## Configure an examination period

### Interactive setup

Start interactive generation with the real workbook command above.
If you use the supplied room file unchanged, omit `--rooms edited_rooms.json`.
The program asks for the following information in order. Enter answers in the terminal, not in a Python file.

| Question or stage | What to enter and what happens next |
| --- | --- |
| Complete candidate list | Answer Yes only after institutional review. No stops setup. For the fictional demonstration, completeness applies only to the demonstration records. |
| Exam type | `midsem`, `endsem`, or `backlog`. |
| Start and end dates | Actual dates in `YYYY-MM-DD` format. For example, `2027-03-01` means March 1, 2027. The end must not precede the start. |
| Daily sessions | A positive whole number. A session is one daily examination time period. |
| Session names and times | Distinct names, such as Morning and Afternoon. Use 24-hour ranges such as `09:30-11:30` and `14:00-16:00`. Ranges must not overlap or cross midnight. |
| Additional holidays | Answer Yes to enter each holiday, then No when finished. Each date must be inside the examination period. |
| Objective | `gaps` prefers spacing across the period. `earliest` prioritizes an earlier finish before spacing improvements. |
| Target calendar-day gap | An integer from 1 to 365. It is a preference, not a guaranteed minimum. |
| Shared-session groups | Declare actual shared papers or separate papers that must share a session. See below. |
| Room-unavailability restrictions | Select rooms and dates when they cannot contribute capacity. |
| Fixed examination rules | Select a paper and its required date, with an optional fixed session. |
| Configuration summary | Read the displayed rules, eligible counts, and runtime information. |
| Solve time | Enter a positive number of minutes. Interactive entry requires at least 0.01 minutes. |
| Start confirmation | Answer Yes to start. No cancels generation. |

A value in square brackets is the default used when you press Enter without typing.
Dates must use the complete year-month-day form. Compact dates and week-date notation are rejected.
If a rule conflicts with another rule, correct the input rather than removing an approved institutional requirement merely to make solving easier.
Some invalid combinations stop setup, so keep your source data and approved settings available for another attempt.

### Groups, fixed rules, and room restrictions

When selecting a course, search using part of its code or name.
Select the numbered result and confirm the full paper name.
A blank search cancels that course selection.
Do not select the same course in multiple groups.

For a group, add at least two distinct eligible courses, then choose its meaning:

| Group kind | Meaning |
| --- | --- |
| `shared` | One actual examination paper represented by several course identities. Overlapping students count once for the paper and its attendance sheet. |
| `same_slot` | Different papers that must run on the same date and in the same session. Their candidate lists must not overlap. |

All groups are collected before aggregate student-load tests during initial setup.
Groups still need valid identities, student relationships, and adequate capacity.
Do not use shared grouping to conceal a clash between different papers.

For room restrictions, search by room ID, label, or block.
Select numbered rooms, separated by commas, and confirm them.
Choose `single` for one unavailable date or `from` for a boundary date through the examination end.
For a from-date restriction, answer whether the boundary date itself is included.
Overlapping restrictions remove each affected room's capacity only once.

For fixed rules, select the paper and enter its date.
The session list uses numbers starting at 1. Leave the session answer blank to fix only the date.
Continue adding rules until you answer No.
A fixed date cannot be a holiday or an otherwise excluded date.
The program does not silently move fixed examinations.

### Save configuration without solving

This route requires only openpyxl on the current machine.
It lets you answer setup questions on a laptop and solve later on Colab or HPC.
Run the following command in the activated project terminal after preparing the complete workbook and room file.
`--setup-only` names a new configuration file and stops before loading the solver or exporting reports.

```text
python schedule_exams.py --input registrations.xlsx --rooms edited_rooms.json --setup-only my_config.json
```

Expected result: setup questions, an eligible-input summary, and `Configuration saved: my_config.json`.
The program also states that no solver was loaded and no timetable was generated.
If that filename already exists, choose another filename. It will not replace it.
The JSON stores configuration only, not registrations or room capacities.
Transfer `my_config.json`, `registrations.xlsx`, and `edited_rooms.json` together to the solving machine.

On a solver-equipped machine, the next command uses those three files without setup questions.
Run it from that machine's project folder in its activated environment.
The example requests 30 minutes of shared search time. Choose a budget appropriate to your approved environment.

```text
python schedule_exams.py --input registrations.xlsx --rooms edited_rooms.json --config my_config.json --solve-minutes 30
```

Expected result: a saved state and export status, as in the fictional walkthrough.
Supplying the configuration and solve time serves as confirmation to start.
Review the files before running the command. It does not ask for another start confirmation.

### Saved configuration reference

Use a plain-text editor, not a word processor, to edit JSON directly.
JSON uses double-quoted field names, commas between items, and lowercase `true`, `false`, and `null` values.
`null` means that an optional value is not set.
The supplied `examples/exam_config.json` is a complete fictional example of the structure.
Do not reuse its completeness approval or dates for real data without review.

| Field | Meaning |
| --- | --- |
| `registrations_complete` | Must be `true` only after reviewing the full candidate list. |
| `exam_type` | `midsem`, `endsem`, or `backlog`. |
| `start_date`, `end_date` | Inclusive period boundaries in `YYYY-MM-DD` format. |
| `sessions` | A list of objects, each with `name` and `time`. List order determines session indices. |
| `holidays` | A list of additional excluded dates. |
| `objective` | `gaps` or `earliest`. |
| `gap_target` | Preferred calendar-day separation, from 1 to 365. |
| `groups` | Objects with a unique `id`, `kind`, and a list of course IDs in `courses`. |
| `fixed` | Objects with `course_id`, `date`, and optional `slot`. |
| `room_restrictions` | Objects with `room_ids`, `start_date`, and `end_date`. |
| `max_exams_per_slot` | A positive integer limit on examination events per session, or `null` for no count limit. Capacity and clash rules still apply. |
| `title` | The title printed on the timetable. |

JSON `slot` indices start at 0: the first configured session is 0, the second is 1.
Interactive session menus start at 1 instead.
Find exact course IDs in confirmed course selections or the exported Course IDs column.
Coded papers have IDs such as `CODE:MA101`. Uncoded papers have generated IDs that you must copy rather than guess.
Every date, room ID, and course ID must agree with the current inputs.

## Scheduling rules and solve time

The following hard rules must hold in every valid timetable:

1. Sundays are excluded for all exam types.
2. Saturdays are available for midsem only.
3. Additional holidays apply to every exam type.
4. Each student has at most one examination per calendar day, even when daily sessions do not overlap.
5. Audit registrations participate in midsem only. Other registrations for that student remain eligible independently.
6. Lab, Swayam, and None assessments do not receive written-examination slots.
7. Names containing the word Lab or Laboratory, or beginning with Swayam, are also excluded.
8. Shared papers count each overlapping student once.
9. Room capacity and examination-count limits apply to each session after room restrictions.
10. Approved fixed dates, fixed sessions, and group relationships remain binding.

The solver does not assign individual rooms or seats.
A group of separate papers consumes the combined candidate capacity.
Changing room priority does not relax capacity or clash rules.

The total optimization budget covers both search stages.
The first stage uses up to 25 percent for earliest-finish search.
The second uses the remaining time, including unused time from the first stage, for the selected timetable objective.
For wider rescheduling, preserving assignments takes priority in both stages.

A proof can finish before the requested time. The program does not wait to consume the whole budget.
Loading the solver and preparing the approved rule structure occur before the optimization clock.
Conflict-bound search and model construction consume the optimization budget and stop cooperatively when it expires.
Individual library calls, mandatory tests, checkpoints, and exports can add wall time.
Give an HPC job more elapsed time than its requested search budget.

A feasible timetable satisfies the rules. It is not necessarily the best timetable.
A lower bound is a necessary minimum, not necessarily an achievable result.
`earliest_finish_proved: true` means that the reported earliest feasible finish is established by a proof or matching necessary bound.
With the gaps objective, the actual exported timetable can finish later to improve spacing.
An optimal preservation objective alone is not proof of a globally earliest finish.
A timeout without a timetable does not prove that the rules are impossible.
A proved-infeasible result from either stage means that the supplied rules cannot all hold together.

## Read and keep the results

### Files and folders

The default output parent is `runs` inside the project folder.
`--output` can select another parent for a generation run.
Every generation and resume attempt uses a new run folder.
A failed attempt can leave diagnostics without a completed timetable.
A manifest is a file that records operation results.

| Location within a run | Purpose |
| --- | --- |
| `input_state.json` | Inputs captured for the attempt. Contains student data. |
| `config.json` | Configuration used for that attempt. |
| `checkpoint.json` | A feasible saved timetable, when one is available. |
| `run_manifest.json` | A machine-readable record of success, partial export success, or failure. |
| `revisions/0001/state.json` | Initial completed timetable state for the editor. |
| `revisions/0001/timetable.xlsx` | Timetable, registrations, attendance, room information, and search summaries. |
| `revisions/0001/timetable.pdf` | Printable examination listing with completion analysis. |
| `revisions/0001/attendance/` | One attendance PDF per examination event. |
| `revisions/0001/export_manifest.json` | Completed exports and any export errors. |

Later revisions use their own numbered folders, such as `0002` and `0003`.
Generated attendance filenames contain the date, session number, and an examination identifier derived by the program.
Do not infer paper names from the identifier. Read the paper name inside the PDF.

### Review before publication

1. Make sure that the correct exam type, dates, title, and session times appear in the reports.
2. Compare included and excluded registrations with the approved candidate roster.
3. Review Import Warnings, room restrictions, shared papers, and fixed rules.
4. Review the search analysis without treating an unproved feasible finish as a minimum.
5. Open every required PDF and inspect its text and page layout.
6. Obtain institutional approval before publishing a timetable or printing attendance sheets.

The Excel workbook includes Exam Timetable, Student Timetable, Attendance, Configuration, Rooms, and Room Restrictions sheets.
It also includes Registrations, Excluded Registrations, Import Warnings, and Solve Report sheets.
Attendance lists contain one row per candidate and examination, sorted by Student ID.
Serial numbers restart at one for each examination.
Shared papers list a candidate once. Attendance sheets do not assign rooms.

### Back up the editable state

Keep the whole run folder, not just the Excel or PDF files.
Back up reviewed input files, room data, and saved configuration with the run.
The JSON state includes student identities and registrations. Protect it as carefully as the source workbook.
Keep completed revisions unchanged and use the editor for approved changes.

### Resume a checkpoint

Use resume when you want another search with the saved inputs and a fresh budget.
It is not the workflow for replacing the registrations or room layout.
The following command runs in the activated project terminal on a solver-equipped machine.
Replace `RUN_ID` with the actual run folder containing the checkpoint.
Do not combine `--resume` with `--input` or `--config`.

```text
python schedule_exams.py --resume "runs/RUN_ID/checkpoint.json" --solve-minutes 30
```

Expected result: a new run folder, a saved timetable, and export status.
The source run is not overwritten.
If the saved timetable remains valid, the program keeps it when the new search returns no better feasible result.
An invalid saved timetable is never used as a fallback.
Search proofs are recalculated rather than inherited blindly.
If the checkpoint does not exist, the earlier attempt did not save one. Use a completed `state.json` or start from reviewed inputs instead.

## Edit a timetable

### Start the editor

Use the saved state of the revision you intend to change.
Run the following command in the activated project terminal after replacing `RUN_ID` with the actual run name.
Replace `0001` too if you are editing a later revision.

```text
python edit_timetable.py "runs/RUN_ID/revisions/0001/state.json"
```

Expected result: the editor's action menu.
Each approved action creates a new revision and regenerates reports.
After saving, the editor continues from the new revision.
If you open an earlier revision deliberately, its data becomes the starting point for your next change.

### Compare alternatives and move a paper

1. Enter `alternatives` at the action prompt.
2. Search for part of the paper name or code. For the fictional example, use `DEMO101`.
3. Select the numbered result and confirm the paper.
4. Read the listed replacement dates and named sessions. No change is saved by this action.
5. Enter `move` at the next action prompt.
6. Select and confirm the same paper.
7. Enter a listed replacement date and its session number from the session menu.
8. Read the impact preview and the final change preview.
9. Answer Yes only if the displayed change is approved.
10. Note the new revision path and inspect its reports.

Alternatives keep every other examination unchanged.
They rank the affected students' minimum gaps first, then average gaps.
The current slot is not listed as a replacement.
A fixed examination can have no alternatives until its fixed rule is deliberately changed.
If papers belong to the same-slot component, they move together.
`No valid alternatives while other exams remain unchanged.` means that a local move is not possible under the current rules.

### Available actions

| Action | What it does |
| --- | --- |
| `alternatives` | Lists safe replacement slots without saving changes. |
| `move` | Moves the selected examination component to a requested date and session. |
| `swap` | Exchanges the slots of two distinct examination components when valid. |
| `fix` | Adds a required date and optional session for a selected course. |
| `release` | Removes a selected fixed rule. It does not remove a course. |
| `holiday` | Adds or removes an additional holiday. |
| `dates` | Changes the examination-period boundaries. Existing holidays, restrictions, and fixed rules are not silently adjusted. |
| `sessions` | Replaces the daily session list. Fixed session indices retain their numbers, so review their meaning. |
| `groups` | Adds or removes a shared-paper or same-slot group. |
| `registrations` | Replaces the complete registration list from a reviewed workbook. Use this to update audit status. |
| `rooms` | Replaces the room layout from a reviewed JSON file. |
| `availability` | Adds or removes dated room-unavailability restrictions. |
| `restore` | Loads an earlier state and saves the approved restoration as a new revision. |
| `rebuild` | Makes sure that the timetable follows its rules and regenerates reports in a new revision. |
| `quit` | Exits the editor. |

For wider rule changes, the editor first tests whether existing assignments remain valid.
If wider rescheduling is necessary, it asks permission and requests a new time budget.
It prioritizes fewer changed assignments before completion-date or gap preferences.
A time-limited result does not establish that the number of changes is minimal.
The tool still asks for final approval before saving.
Declining a change leaves completed revisions intact.

### Apply a JSON patch

A patch replaces selected configuration fields or complete records and layout values.
This is an optional unattended workflow for users comfortable with JSON.
List values replace whole lists. They do not append to them.

For a safe fictional example, use a plain-text editor to save the following content as `title_patch.json` in the project folder.
The `config` object selects configuration replacements. The `title` field changes only the report title.

```json
{"config": {"title": "Practice examination timetable"}}
```

Expected result: a file named exactly `title_patch.json`, not `title_patch.json.txt`.
If JSON parsing later fails, remove word-processor formatting and make sure that quotes and braces match.

The next command previews that patch against the selected state without saving it.
Run it in the activated project terminal and replace `RUN_ID` and the revision number as needed.

```text
python edit_timetable.py "runs/RUN_ID/revisions/0001/state.json" --patch title_patch.json
```

Expected result: impact and final-change previews followed by `Not applied.` No revision is created.
If the program instead reports a rule conflict, resolve the patch before applying it.

After reviewing the preview, the following command approves the same title change and saves a new revision.
`--yes` is explicit permission to save the supplied patch.

```text
python edit_timetable.py "runs/RUN_ID/revisions/0001/state.json" --patch title_patch.json --yes
```

Expected result: `New revision:` and an export status. Existing revision files remain unchanged.
For later work, use that new revision's state rather than accidentally returning to an earlier state.

For a patch that requires wider rescheduling, the next command gives permission for that search and supplies its budget.
Replace `rule_patch.json` with your approved patch file. This file is not supplied by the suite.

```text
python edit_timetable.py "runs/RUN_ID/revisions/0001/state.json" --patch rule_patch.json --reschedule --solve-minutes 30 --yes
```

Expected result: either a valid new revision or a clear rejection or search failure.
Without `--reschedule`, a patch needing wider changes is not applied.
To avoid expensive search during a preliminary preview, omit `--reschedule` until you approve the search.

## Use Google Colab

Use Colab only if your institution permits uploading the registrations and saved results to Google services.
Colab stores files in a temporary session. A disconnect or runtime reset can remove them.
Keep local copies and download completed results promptly.
These instructions describe the supported notebook workflow. A live Colab deployment is not part of the local release tests.

### 1. Upload and extract the suite

1. Open [Google Colab](https://colab.research.google.com/) and create a new notebook.
2. Open the folder icon in the notebook's left sidebar.
3. Upload `exam_scheduler_release.zip` into `/content`.
4. Use a fresh session or an empty destination. Do not extract over edited input files or completed results.

Run the following Python code in a new notebook cell.
`zipfile` opens the trusted distribution archive. The `with` block extracts its project folder into `/content` and closes the archive.
The last line prints the extraction location.

```python
import zipfile
with zipfile.ZipFile("/content/exam_scheduler_release.zip") as archive:
    archive.extractall("/content")
print("Project extracted to /content/exam_scheduler")
```

Expected result: `Project extracted to /content/exam_scheduler` and that folder in the file sidebar.
If the archive is not found, make sure that the uploaded filename matches exactly.
Do not extract untrusted ZIP files with this procedure.

This next cell sets the notebook's working folder to the extracted project.
`%cd` is a notebook command, not ordinary Python syntax.

```ipython
%cd /content/exam_scheduler
```

Expected result: `/content/exam_scheduler` printed below the cell.
If it is missing, complete extraction before installing dependencies.

### 2. Install dependencies and run the example

In the next notebook cell, `%pip` installs runtime dependencies into the notebook's Python environment.
It reads the requirements file from the project folder selected above.

```ipython
%pip install -r requirements-solver.txt
```

Expected result: installation succeeds or packages are already installed.
If Colab requests a runtime restart, restart it and make sure that your uploaded project files still exist before continuing.
Do not start generation after a failed installation.

The following cell runs the fictional example without setup questions.
`%run` runs the script in the notebook and also supports interactive prompts for later real-data runs.

```ipython
%run schedule_exams.py --input examples/registrations_template.xlsx --config examples/exam_config.json --solve-minutes 1
```

Expected result: the same eligible counts and saved-report structure as the local example, under `/content/exam_scheduler/runs`.
If the cell fails, read the error and the troubleshooting section before proceeding.

### 3. Use approved real inputs

Upload `registrations.xlsx` and the reviewed `edited_rooms.json` into `/content/exam_scheduler` using the file sidebar.
Also upload `my_config.json` if you prepared it with `--setup-only` on your laptop.
Do not put the files in `/content` while expecting relative paths from the project folder to find them.

To answer setup questions in the notebook, run this cell after reviewing the files.
It reads the real workbook and room layout, then uses notebook input for the configuration questions.

```ipython
%run schedule_exams.py --input registrations.xlsx --rooms edited_rooms.json
```

Expected result: setup questions followed by a requested solve budget and start confirmation.
Follow [Configure an examination period](#configure-an-examination-period).
Use `%run`, not a background shell command, for interactive setup and editing.

For already reviewed configuration, this cell runs without setup questions and requests a 30-minute budget.

```ipython
%run schedule_exams.py --input registrations.xlsx --rooms edited_rooms.json --config my_config.json --solve-minutes 30
```

Expected result: a new run with its saved state and exports, or a clear error.
Keep the run's JSON files as well as its PDFs.
To edit interactively, use the editor command from [Timetable editing](#edit-a-timetable) with `%run` instead of `python`.

### 4. Download results

Run the following Python cell after results exist in `runs`.
`shutil` creates a ZIP of that folder. `files` opens Colab's browser download.
The temporary download archive uses `/content/exam_scheduler_results.zip` and is replaced when this cell is repeated.
The run folders themselves are not replaced.

```python
import shutil
from google.colab import files
archive_path = shutil.make_archive("/content/exam_scheduler_results", "zip", "/content/exam_scheduler/runs")
files.download(archive_path)
```

Expected result: your browser downloads `exam_scheduler_results.zip`.
Open the downloaded file and make sure that it includes your run's state and reports before closing Colab.
If the download fails, use the file sidebar to download needed files and retain the checkpoint.
Treat the downloaded archive as private student data.

## Use an HPC system

An HPC system is an institutional cluster for computational jobs.
Cluster policies differ. Obtain the correct Python module, package source, file-transfer method, and scheduler instructions from your administrator.
These commands are Bash examples for a single-machine, single-process job.
They do not create an account or reserve resources by themselves.

### 1. Prepare the project and environment

Transfer the extracted `exam_scheduler` folder to an approved cluster location.
Transfer only the reviewed private input files through an institution-approved method.
The following Bash command enters an example installation folder.
Replace `$HOME/exam_scheduler` if your actual cluster path differs.

```bash
cd "$HOME/exam_scheduler"
```

Expected result: no error, with the project selected as the working folder.
Make sure that `README.md` and `schedule_exams.py` appear in your remote file browser there.
If they are absent, correct the transfer location first.

After loading any site-required Python module, the following command displays the available Python version.
The module-loading command is site-specific and must come from your administrator.

```bash
python3 --version
```

Expected result: a compatible Python version, as described in local installation.
If the version is unsupported, ask for an appropriate module rather than changing the cluster's system Python.

The next command creates an isolated environment in the project folder.
Run it on a node where your institution permits environment creation.

```bash
python3 -m venv .venv
```

Expected result: a `.venv` folder. If creation fails, resolve storage permissions or missing Python environment support.

Activate that environment with this command from the same folder.

```bash
source .venv/bin/activate
```

Expected result: an activated environment, normally shown by `(.venv)` in the prompt.
Activate it again in each new shell or batch job.

Install runtime packages with the following command from a permitted installation node.
Use the institution's package mirror if direct internet access is prohibited.

```bash
python -m pip install -r requirements-solver.txt
```

Expected result: installation completes or requirements are already satisfied.
If compute nodes cannot access the internet, complete this installation before submitting the solve job.
Do not use `sudo`.

### 2. Review inputs before submission

Place `registrations.xlsx`, `edited_rooms.json`, and `my_config.json` in the cluster project folder.
Use `--setup-only` locally or in a permitted interactive session to create the reviewed configuration.
Do not expect a batch job to answer interactive setup questions.

If lightweight inspection is permitted on the login node, this command reads the workbook without loading the solver.
Run it in the activated project environment.

```bash
python schedule_exams.py --input registrations.xlsx --inspect
```

Expected result: the reviewed counts and an empty source-issues list.
Correct all source issues before submitting the solve job. Inspection is not approval that the candidate list is complete.

### 3. Submit a Slurm job

Slurm is one common cluster job scheduler. Use your site's equivalent for other schedulers.
In a plain-text editor, save the following as `schedule_job.sh` in the project folder.

A CPU is a processor resource used for calculations.
A worker runs one part of the solver search.
The first line selects Bash.
The `#SBATCH` lines request a job name, ten CPUs, a 75-minute elapsed-time limit, and a log filename.
`set -e` stops the job if a command fails.
The remaining lines enter the project, activate its environment, and start a 60-minute unattended solve.
Replace `/path/to/exam_scheduler` with the actual absolute cluster path before submission.
Your site can also require account, partition, memory, or other directives. Obtain those values from the administrator.

```bash
#!/bin/bash
#SBATCH --job-name=exam-scheduler
#SBATCH --cpus-per-task=10
#SBATCH --time=01:15:00
#SBATCH --output=exam-scheduler-%j.log
set -e
cd /path/to/exam_scheduler
source .venv/bin/activate
python schedule_exams.py --input registrations.xlsx --rooms edited_rooms.json --config my_config.json --solve-minutes 60 --platform hpc
```

Expected result after saving: a text file named `schedule_job.sh`, not `schedule_job.sh.txt`.
The elapsed-time allowance must cover preparation and exports as well as search. Increase it if your approved workload needs more overhead.
Do not run this file as a long search on a shared login node.

From the project folder on a permitted submission node, this command submits the file to Slurm.

```bash
sbatch schedule_job.sh
```

Expected result: a message resembling `Submitted batch job 12345`. The actual job number varies.
If Slurm rejects the request, correct the site-specific directives before resubmitting.

To view the submitted job, the next command asks Slurm for its queue status.
Replace `12345` with the actual job number returned above.

```bash
squeue --job 12345
```

Expected result: a queue entry while the job is pending or running.
If there is no entry, the job can be completed or failed. Read its `exam-scheduler-JOB_ID.log` file and the run manifest.
A completed queue entry is not by itself proof of a successful timetable export.

### 4. Worker limits and result retrieval

Automatic platform detection recognizes Colab, Slurm, PBS, LSF, and SGE markers, with a hostname fallback.
`--platform hpc` explicitly selects HPC behavior when automatic recognition is unavailable.
The scheduler requests up to ten solver workers on HPC, up to eight on Colab, and up to four locally.
It reduces those counts for smaller reported allocations and CPU affinity limits.
For Slurm, it respects both `SLURM_CPUS_PER_TASK` and `SLURM_CPUS_ON_NODE`.
It does not reserve CPUs or distribute one search across multiple machines.

Read the job log for `Saved timetable:` and `Exports:`.
Download the completed run folder through your institution's approved transfer method.
Keep checkpoints and completed states if the batch time limit stops the job.
Do not assume that a missing timetable after a timeout proves infeasibility.
Live HPC submission is not part of the local release tests.

## Command reference

Run commands from the project folder in the activated environment, unless you use notebook `%run`.
A flag is a named command option such as `--input`.
Arguments following flags are paths or values, not additional program names.

| Program | Main options |
| --- | --- |
| `schedule_exams.py` | `--input WORKBOOK`, `--rooms ROOM_JSON`, `--config CONFIG_JSON`, `--inspect`, `--setup-only NEW_CONFIG_JSON`, `--resume STATE_JSON`, `--solve-minutes NUMBER`, `--platform auto/local/colab/hpc`, `--output RUN_PARENT` |
| `edit_timetable.py` | A required state path, then optional `--patch PATCH_JSON`, `--yes`, `--reschedule`, `--solve-minutes NUMBER`, `--platform`, and `--output REVISION_PARENT` |
| `edit_rooms.py` | `--rooms ROOM_JSON`, optional `--migrate WORKBOOK`, and `--no-browser` |

The following three commands display the installed programs' option lists and legal notice without creating timetables.
Run them in the activated project terminal. Each line asks one program for help.

```text
python schedule_exams.py --help
python edit_timetable.py --help
python edit_rooms.py --help
```

Expected result: each program prints its usage and options, then exits.
If Python cannot open a script, return to the extracted project folder.
If a dependency error appears during normal use, install the needed requirements in the same environment.

### Exit codes

An exit code is a number returned to a terminal or job scheduler when a program finishes.
You usually read the console messages instead, but batch operators can use these values.

| Code | Meaning |
| --- | --- |
| `0` | Success, or an intentional no-save cancellation or preview. Read the messages to distinguish them. |
| `1` | Workbook inspection found source issues. |
| `2` | Invalid input, rule conflict, search failure, or another handled operational error. |
| `3` | A timetable was saved, but one or more report exports failed. |
| `130` | Generation or editing stopped through interruption or closed input. |

`edit_rooms.py` reports failures through its error message rather than the generation/editor status scheme.
A successful export does not remove the need for institutional timetable review.

## Troubleshooting

### PowerShell blocks environment activation

Use Command Prompt instead of changing security policy.
Open the Start menu, type `cmd`, and open Command Prompt.
The following command changes both drive and folder in Command Prompt. Replace the quoted path with your project folder.

```bat
cd /d "C:\Users\YourName\Downloads\exam_scheduler_release\exam_scheduler"
```

Expected result: the prompt shows the project folder.
If it does not exist, copy the actual path from File Explorer.

This Command Prompt command activates the environment without running a PowerShell script.
Run it after the folder change above.

```bat
.venv\Scripts\activate.bat
```

Expected result: `(.venv)` normally appears in the prompt.
Continue using `python` commands from this README in that same Command Prompt window.
If the activation file is absent, create `.venv` with the matching Python installation first.

### Python or a dependency is unavailable

| Symptom | What to do |
| --- | --- |
| `py`, `python3`, or `python` is not recognized | Install an approved compatible Python, reopen the terminal, and use the operating-system-specific steps above. |
| `No module named openpyxl` | Activate the correct environment and install `requirements-input.txt` for inspection/setup, or the full solver requirements for solving. |
| `No module named ortools` or `reportlab` | Install `requirements-solver.txt` on the machine doing solving or PDF exports. No automatic installation is attempted. |
| No compatible package distribution | Make sure that your Python version and machine architecture have compatible dependency packages. Python 3.12 is a practical choice. Ask your administrator if needed. |
| Package installation permission error | Use the project virtual environment or an approved cluster environment, not the system Python. |
| Installation cannot reach a package server | Use your institution's approved network or package mirror. Do not bypass institutional controls. |

Repeat the relevant installation command only after correcting the cause.
A package installed under a different Python does not satisfy the active environment.

### Files, input data, or rules are rejected

| Symptom | What to do |
| --- | --- |
| Cannot open `schedule_exams.py` | Enter the inner extracted project folder, not the ZIP viewer or its outer folder. |
| File not found for a workbook, room file, or state | Use its actual filename and folder. Quote paths containing spaces. |
| Workbook source issues | Correct the specified sheet and row. Remove formulas, fill required values, and express statuses explicitly. |
| Conflicting audit or status entries | Resolve the duplicate source records instead of expecting the program to guess. |
| No eligible written-exam registrations | Review exam type, audit flags, assessment values, statuses, and names that identify excluded assessments. |
| Invalid JSON | Use a plain-text editor. Match braces, double quotes, commas, and lowercase JSON values. |
| Invalid dates or session ranges | Use complete `YYYY-MM-DD` dates and non-overlapping 24-hour time ranges. |
| Unknown rooms or courses | Copy exact IDs from reviewed data or confirmed selections. Recheck rules after replacing inputs. |
| No permitted slot or too many examinations for a student | Review dates, holidays, fixed rules, group definitions, and available room capacity. Seek approval for any rule change. |
| Setup-only destination already exists | Choose a new configuration filename. Existing configuration is not overwritten. |

If a file is locked by a spreadsheet viewer, close that viewer before retrying an export to the same location.
Do not rename a text file to `.xlsx` or `.json` as a substitute for saving the correct format.

### Search stops without a timetable

A timeout means that no new feasible timetable was found within the available search budget.
Increase the budget on an approved solving machine or review the rules with the examination authority.
A proved-infeasible error means the rules conflict, so increasing time alone cannot solve that same problem.
Keep any checkpoint and the failure manifest for diagnosis.
Do not remove approved fixed rules or candidate registrations without authorization.

### A report export fails

The program retains independently successful reports and records failures in `export_manifest.json`.
A `PARTIAL_SUCCESS` result is not full publication readiness.
Open the manifest with a text editor and read the failed stage's error.

Unicode assigns a numeric code to each character.
If a PDF font cannot show a character, the message identifies its code, such as `U+4E00`.
Use approved display text supported by an available font, or ask an administrator to provide a suitable font configuration.
Do not silently alter official identities merely to avoid a font error.
A non-writable folder or a file open in another program can also block exports.
After resolving the cause, open the saved state in the editor and use `rebuild` to create a new revision with fresh reports.

If no replacement slots are listed, the current hard rules block local moves while other assignments remain unchanged.
A wider change needs reviewed rule changes and explicit permission to reschedule.

## Privacy, backups, and operational limits

Use access-controlled storage for registration workbooks, states, checkpoints, Excel reports, attendance sheets, and result archives.
Do not include real registrations or generated runs in a software distribution.
Use Colab only where your institution permits cloud handling of student data.
Download results before closing a temporary cloud session.

The suite does not establish that a workbook includes every student or compulsory paper.
It cannot infer actual examination papers from programme titles or decide which differently named courses are the same paper.
It does not select backlog candidates from an unreviewed normal-semester roster.
Room capacities and examination policies require institutional approval.

Timetables use total session capacity, not detailed room allocations or seat plans.
The timetable PDF is an exam listing, not a programme-specific visual grid.
Solve quality and runtime depend on the data, approved rules, budget, hardware, and dependency versions.
Review large institutional datasets in an operational trial before publication.
This README does not claim a live deployment test on every operating system, Colab, or HPC service.

## Package contents and maintenance

End users need only this README for installation and operation.
The package contains no separate documentation PDF or documentation-only PDF generator.
Runtime timetable and attendance PDF generation remain part of the application.
A module is a Python file with related functions.

| Path | Purpose |
| --- | --- |
| `schedule_exams.py` | Inspection, configuration, generation, and resume entry point |
| `edit_timetable.py` | Interactive and patch-based timetable editor |
| `edit_rooms.py` | Room-editor launcher and optional room-workbook converter |
| `exam_scheduler/` | Import, validation, search, interaction, and runtime report modules |
| `assets/room_editor.html` | Offline browser room editor |
| `data/rooms.json` | Supplied room capacities |
| `examples/registrations_template.xlsx` | Fictional input template and dropdowns |
| `examples/exam_config.json` | Fictional complete configuration |
| `requirements-input.txt` | Workbook-only dependency requirements |
| `requirements-solver.txt` | Full runtime dependency requirements |
| `tests/` | Automated synthetic tests |
| `docs/validation_report.md` | Test scope and environment limitations |
| `generate_examples.py` | Optional fictional input generator for maintainers |
| `build_distribution.py` | ZIP builder for maintainers |
| `LICENSE`, `NOTICE` | License terms and attribution |

### Run automated tests

On a solver-equipped machine, run the following command from a fresh extracted project in its activated environment.
It discovers the test files and runs their test cases using temporary outputs.
Node.js is optional and is used only for browser-editor logic tests.
An optional institutional-workbook test is skipped when its external input is absent. Do not supply private input without permission.

```text
python -m unittest discover -s tests -v
```

Expected result: a final `OK`, with any skipped optional tests identified separately.
A failure requires investigation before shipment.
The [validation report](docs/validation_report.md) states what was tested and what remains untested.
Automated PDF tests do not replace a visual review of your actual reports.

### Generate additional fictional inputs

For maintainers, the following command creates examples in a separate `sample_inputs` folder.
Run it in the activated project terminal with openpyxl installed.
Use a destination that contains no existing example files.

```text
python generate_examples.py --output sample_inputs
```

Expected result: paths for `sample_inputs/registrations_template.xlsx` and `sample_inputs/exam_config.json`.
Existing target files cause refusal unless you deliberately supply `--force`.
Do not use `--force` on a folder that contains real or reviewed user inputs.

### Build the shipping ZIP

For maintainers, the following command builds the distribution after all source, documentation, template, and test changes are complete.
Run it in the project terminal. It does not include generated runs, caches, private inputs, or other ZIP files.
`--output` names the shipping file explicitly.

```text
python build_distribution.py --output exam_scheduler_release.zip
```

Expected result: `exam_scheduler_release.zip` is printed and a complete archive is published at that path.
The archive contains one top-level `exam_scheduler` folder.
Extract the actual ZIP into an isolated directory and run its test suite before shipment.
If the destination is open or locked, close it or build to another explicit filename and identify that file to recipients.
Never distribute an unverified archive merely because a file with the intended name already exists.

## License and author

Copyright (c) 2026 Siddhant Tiwari.
Contact: Siddhant Tiwari ([finrelemos@gmail.com](mailto:finrelemos@gmail.com)).
The project is licensed under the GNU Affero General Public License, version 3 only (`AGPL-3.0-only`).
AGPL-3.0-only covers all copyrightable project-owned files in this repository and its distributions, unless a file explicitly states otherwise.
This includes source code, scripts, tests, documentation, assets, configuration files, and project-owned example files and data.
Files do not need an individual license header for this license to apply.

Read [LICENSE](LICENSE) for the complete terms and [NOTICE](NOTICE) for attribution.
The software comes without warranty, as stated in LICENSE.
AGPLv3 is a free software license with copyleft obligations, which require covered derivatives to retain the license terms.
Distributing the program or modified versions carries notice and source-code obligations under the license.
If you modify the program and users interact with it remotely over a network, section 13 requires a source-code offer.
Read section 13 for the precise conditions. The project grants version 3 only, not an automatic later-version option.

Third-party dependencies and materials retain their own licenses and notices.
Institutional data and user-supplied registrations retain their existing ownership and permissions.
Running the software does not, by itself, place user data or output under AGPL-3.0-only.
Output is covered only if its content constitutes a covered work under the license.
