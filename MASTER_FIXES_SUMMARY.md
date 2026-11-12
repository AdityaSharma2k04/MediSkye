# Master Fixes Summary

## Prompt Quality Pass (Branch: prompt-quality-pass)

### What Changed
- **P1 (`REPORT_WALKTHROUGH_RULES`, item 1):** Replaced "single flagged value is common..." with directive to name the one or two most significant findings plainly, match clinical urgency to findings, and never call flagged results common, routine, or usual.
- **P2 (`REPORT_WALKTHROUGH_RULES`, item 2):** Replaced everyday comparisons directive with plain opening sentence describing what the test group looks at without metaphors or analogies.
- **P3 (`REPORT_WALKTHROUGH_RULES`, item 3):** Clarified that near-boundary markers always receive a short interpretation even when status is Normal.
- **P4 (`REPORT_WALKTHROUGH_RULES`, item 5):** Added constraint that next steps must not state or imply any test is missing or omitted unless listed under `verified_absent_adjacent_tests`.
- **P5 (`REPORT_WALKTHROUGH_RULES`, item 6):** Forbade naming unmeasured tests as absent, not included, needed, or typically needed.
- **P6 (`SHARED_CORE_RULES`, EVIDENCE AND SAFETY):** Instructed to state range status as fact and potential conditions as possibilities; strictly forbade "you have", "this confirms", "this indicates you have", or stating organs are underactive, overactive, or damaged unless report explicitly diagnoses it.
- **P7 (`SHARED_CORE_RULES`, EVIDENCE AND SAFETY):** Forbade offering lifestyle factors as general possibilities for the user's own results unless present in user tags.
- **P8 (`SHARED_CORE_RULES`, GROUNDING):** Clarified that general factor explanations follow the lifestyle safety rule.
- **B1 (`biomarkers.py`):** Added British spelling patterns (`h(?:a)?emoglobin`, `h(?:a)?ematocrit`) to biomarker regexes.
- **B2 (`biomarkers.py`):** Added `# 12b. Urine albumin/creatinine ratio` returning `"urine_acr"` before BUN/Creatinine to prevent serum creatinine mis-keying.
  - Side effect: Urine ACR was previously keyed as serum creatinine, so metrics.py dedup could silently drop it and trend matching mixed the two; it is now tracked separately and falls into 'Other' until mapped to a panel.

### Why
To prevent overfitting, eliminate dismissive language, avoid unprompted lifestyle attributions, stop false missing-test claims, recognize British spelling, and isolate urine ACR from serum creatinine.

### Tests Added
- `backend/tests/test_prompt_quality_regression.py` (8 tests: `test_british_spelling_is_recognised`, `test_acr_is_not_serum_creatinine`, `test_near_boundary_markers_are_listed`, `test_followup_hints_reach_the_block`, `test_acr_gets_no_serum_creatinine_hint`, `test_rbc_indices_absence_respects_british_spelling`, `test_prompt_wording_changes`, `test_build_prompt_still_assembles`).

### Tests Modified
- None.

### Rollback
- Revert the commits on branch `prompt-quality-pass`: `git checkout main && git branch -D prompt-quality-pass`.


## Prompt Quality Pass 2 (Branch: prompt-quality-pass)

### What Changed
- **R1 (`REPORT_WALKTHROUGH_RULES`, item 6):** Made "What This Report Does Not Cover" a closed list. Prohibited stating any named test is not measured, not included, or missing unless listed under `verified_absent_adjacent_tests`.
- **R2 (`SHARED_CORE_RULES`, EVIDENCE AND SAFETY):** Explicitly prohibited using "confirm", "confirms", "confirming", or "confirmed" to state what a result shows, and prohibited saying results "point toward" a condition/cause (instructed to use "may suggest" or "can be consistent with").
- **R3 (`REPORT_WALKTHROUGH_RULES`, item 2):** Allowed grouping by the report's own section titles; enforced plain text with no emoji for panel headings; strictly forbade using a single heading when there are more than six markers.
- **R4 (`REPORT_WALKTHROUGH_RULES`, item 5):** Constrained next steps to discuss management only in general terms without naming specific supplements, medications, or diet changes, and forbade presupposing medications, supplements, diet, or activity not present in user tags.
- **R5 (`REPORT_WALKTHROUGH_RULES`, item 7):** Forbade questions to ask your doctor from presupposing any medication, supplement, diet, or activity not in the user's tags.

### Why
To address issues where answers named other tests as missing, used "confirming" or "point toward" for causes, produced one-heading output with emoji, and presupposed medications or supplements in next steps and questions to the doctor.

### Tests Added
- `backend/tests/test_prompt_quality_regression.py` (4 tests: `test_absent_test_rule_is_a_closed_list`, `test_diagnosis_wording_rules_cover_variants`, `test_heading_rules`, `test_next_steps_and_questions_do_not_presuppose_lifestyle`).

### Tests Modified
- None.

### PROMPT_VERSION
- Unchanged at `"v3"` because the cached document-summary prompt is untouched.

### Rollback
- Before merge: delete the branch (`git checkout main && git branch -D prompt-quality-pass`).
- After merge: revert the pass-2 commits (`git revert <pass-2-commits>`).
