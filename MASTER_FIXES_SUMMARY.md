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
