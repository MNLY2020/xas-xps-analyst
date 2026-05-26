# XPS Reference Valence/Chemical-State Candidates

These rows are reference-library candidates from fitted peak centers and common binding-energy windows. They are not final chemical-state, oxidation-state, valence, coordination-number, or publication-grade assignments.

- Candidate rows: 15
- Confidence counts: {'low_medium': 11, 'low': 2, 'medium': 1, 'medium_high': 1}
- Review required: true for every row

| file | record | peak_id | peak_center_ev | region | candidate_state | confidence | fit_quality | review_required |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| XPS-fresh/20260311MaNing-1.vms | wide | l2 | 529.590103 | O 1s | lattice O2- / oxide oxygen | low_medium | 偏弱 | True |
| XPS-fresh/20260311MaNing-1.vms | O 1s | l1 | 529.199747 | O 1s | lattice O2- / oxide oxygen | low | 可参考 | True |
| XPS-fresh/20260311MaNing-1.vms | Al 2p | l1 | 72.43048 | Al 2p | Al(0) / metallic Al | medium | 可参考 | True |
| XPS-fresh/20260311MaNing-1.vms | Pd 3d | l3 | 335.211407 | Pd 3d5/2 | Pd(0) / metallic Pd | low_medium | 可参考 | True |
| XPS-fresh/20260311MaNing-1.vms | Pd 3d | l5 | 338.378768 | Pd 3d5/2 | Pd(IV) / PdO2-like | low_medium | 可参考 | True |
| XPS-fresh/20260311MaNing-1.xlsx | Sheet5 | l1 | 74.23313 | Al 2p | Al(III) / Al2O3-like | low_medium | 可参考 | True |
| XPS-fresh/20260311MaNing-1.xlsx | Sheet4 | l1 | 284.800979 | C 1s | adventitious C-C/C-H | low_medium | 可参考 | True |
| XPS-fresh/20260311MaNing-1.xlsx | Sheet3 | l1 | 531.003579 | O 1s | hydroxyl / defect oxygen | low | 可参考 | True |
| XPS-fresh/20260311MaNing-1.xlsx | Sheet2 | l2 | 531.390133 | O 1s | hydroxyl / defect oxygen | low_medium | 偏弱 | True |
| XPS-fresh/20260311MaNing-2.vms | wide | l2 | 529.393723 | O 1s | lattice O2- / oxide oxygen | low_medium | 偏弱 | True |
| XPS-fresh/20260311MaNing-2.vms | O 1s | l1 | 529.633373 | O 1s | lattice O2- / oxide oxygen | medium_high | 可参考 | True |
| XPS-fresh/20260311MaNing-2.xlsx | Sheet6 | l1 | 284.939048 | C 1s | adventitious C-C/C-H | low_medium | 偏弱 | True |
| XPS-fresh/20260311MaNing-2.xlsx | Sheet4 | l1 | 74.334994 | Al 2p | Al(III) / Al2O3-like | low_medium | 可参考 | True |
| XPS-fresh/20260311MaNing-2.xlsx | Sheet3 | l1 | 531.635048 | O 1s | hydroxyl / defect oxygen | low_medium | 可参考 | True |
| XPS-fresh/20260311MaNing-2.xlsx | Sheet2 | l2 | 531.390332 | O 1s | hydroxyl / defect oxygen | low_medium | 偏弱 | True |

## How to use

- Treat `candidate_state` as a reference candidate for Codex/backend triage, not as a final scientific conclusion.
- Use `confidence` to prioritize manual review; even `medium_high` still requires calibration and expert confirmation.
- Inspect `evidence_basis` in the JSON file to see whether the match came from a region hint or only a binding-energy window.
