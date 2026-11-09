# Validation report

## Scope and environment

This report describes the distribution's automated validation and its limits.
The installation and complete user instructions are in README.md.
The shipping filename is exam_scheduler_release.zip.
The project license is GNU AGPL version 3 only, identified as AGPL-3.0-only.
The author contact is Siddhant Tiwari <finrelemos@gmail.com>.

The full suite contains 83 tests.
82 passed and one optional institutional-workbook test was skipped.
The external workbook was not opened. Tests used fictional registrations and isolated temporary outputs.
No real timetable, reviewed room layout, or private registration workbook was replaced.

| Component | Validation environment |
| --- | --- |
| Operating system | Windows |
| Python | 3.13.2 |
| openpyxl | 3.1.5 |
| OR-Tools | 9.15.6755 |
| ReportLab | 5.0.1 |
| Node.js | 22.23.2, for browser-editor logic tests |

Dependencies were already installed.
A separate fresh Python virtual environment was created in a temporary directory.
Its Python executable and pip worked. No network dependency installation was attempted.

## Documentation and end-user workflows

The README starts with Install and Use after a short introduction and navigation links.
Its local relative links and heading anchors passed automated tests.
The registration template and its generator direct users to README.md.
Input-format and missing-dependency messages also direct users to README.md.
No shipped end-user instruction requires a separate guide.

Tests execute the documented Python commands with a local interpreter and temporary project copies.
The documented command arguments are read directly from the README.
The following workflows passed:

- Inspection of the five fictional registrations, with the documented counts and no source issues.
- Saved-configuration generation with two examination events and complete exports.
- Interactive configuration-only preparation without generating a timetable.
- Interactive generation after answering the documented sequence of questions.
- Editor rebuild with a new revision and an unchanged original state.
- Alternative-slot selection and a valid manual move through the editor prompts.
- JSON patch preview without saving, followed by explicit approval and a new revision.
- Checkpoint resume into a new run without changing the original completed revision.

The example produces a timetable workbook, a timetable PDF, and two attendance PDFs.
Tests make sure that the PDF files contain PDF data and that the export manifest records success.
The report tests also cover export text where the optional PDF inspection library is available.
These tests do not establish that every institution's eventual report has an approved visual layout.

## Application coverage

The automated suite also covers these behaviors:

- Flat and block-style workbook import, compulsory registrations, audit flags, duplicates, and conflicting statuses.
- Rejection of unresolved standalone status markers and programme-only minor headings.
- Assessment exclusions, weekends, holidays, strict dates, and non-overlapping sessions.
- Shared papers, separate papers in one session, candidate overlap, and group setup before aggregate feasibility tests.
- Room capacities, inactive rooms, dated closures, fixed dates, and fixed sessions.
- An earliest-finish result compared with exhaustive search on a small problem.
- Shared deadlines, partial conflict bounds, cancellation during model construction, and timeout diagnosis.
- Main-stage infeasibility reporting, including a real solver test of an impossible conflict cycle.
- Preservation of unchanged assignments during repair and valid fallback schedules during resume.
- Alternatives, moves, swaps, revision immutability, and invalidation of outdated proof claims.
- Excel timetables and attendance, runtime PDF exports, partial export failures, and font-coverage rejection.
- Protection against Excel formula injection from external text.
- Browser-editor capacity changes, invalid or blank values, explicit zero, room creation, deletion, disabling, and undo.
- Platform detection, CPU allocation limits, and smaller affinity limits through simulated environments.
- Room-workbook conversion, lossless numeric validation, and refusal to replace an existing output.
- Synchronized concurrent room conversion and archive publication on the local filesystem.
- Author and email metadata, AGPL-3.0-only declarations, attribution, and project-license scope.
- The complete AGPLv3 text, compared by SHA-256 with the official GNU license text.
- Consistent license and contact notices in Python headers, CLI help, the browser editor, and generated workbook/PDF metadata.

## Distribution checks

The ZIP builder uses an explicit set of permitted top-level files.
It includes the runtime scripts, Python package, requirements, browser editor, approved room data, fictional examples, tests, README, LICENSE, and NOTICE.
The validation report is included as supplementary test information.

The package excludes separate documentation guides, documentation-only PDF generation scripts, and internal audit records.
It also excludes private input workbooks, generated runs, caches, temporary files, and other ZIP files.
The runtime reporting module and ReportLab dependency remain included.
No repository guide or generator was deleted merely because it is excluded from the ZIP.

Publication tests cover archive integrity, portable paths, required members, and excluded files.
The license body matches the official GNU AGPLv3 text at https://www.gnu.org/licenses/agpl-3.0.txt.
Its SHA-256 digest is 0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0.
They also confirm that an explicit alternative output path leaves an existing default archive unchanged.
The actual shipping ZIP passed its integrity test and contains 24 members.
Every packaged member matched its current source file byte for byte.
The archive was extracted into an isolated directory for the full-suite run.
The extracted package discovered 83 tests. 82 passed and the optional institutional-workbook test was skipped.
The README's links and documented workflows passed from the extracted package as part of that suite.

A separate example run from the extracted ZIP completed all export stages.
The timetable PDF and both attendance PDFs contained readable text with the configured examination dates.
The documented additional-example generator command also completed successfully in the isolated extraction.

## Static checks

Python syntax parsing passed for all 15 repository Python files, including the unshipped documentation builder.
Targeted Ruff error/import checks passed.
The two added test modules pass the broader active Ruff rules.
The broader repository-wide Ruff run reports 22 existing style, maintainability, and test-convention diagnostics.
No automatic lint fixes were applied.

A limited Mypy run passed for the 11 shipped application Python files.
It ignores missing imports and skips dependency analysis.
Most functions lack type annotations, so this result does not establish complete type safety.

## Limits and operational review

No live Colab session or institutional HPC batch job was available.
Native macOS and Linux installation, PowerShell activation policy, and cluster-specific module and scheduler commands were not exercised here.
The README labels commands by operating system and execution environment. Site-specific HPC values require administrator approval.
Dependency installation over the internet was not tested in a clean environment.

Browser-editor tests use simulated document elements in Node.js, not manual browser interaction.
PDF tests cover generation, text, and error handling, not a full visual review.
Concurrency tests use synchronized threads on the local Windows filesystem, not a distributed HPC filesystem.
Room conversion fails safely if atomic hard-link publication is unsupported by the destination filesystem.

Search cancellation is cooperative. Individual library calls, validation, required bounds, and exports can add elapsed time.
Large datasets require an operational trial on the intended machine.
Candidate-list completeness, room capacities, grouping decisions, fixed rules, and publication approval remain institutional responsibilities.
