# XPS Fitting Handoff

This file converts the dependency-free peak draft into backend-fitting preparation tasks. It is not a nonlinear fit result and must not be used as final chemical-state, valence, oxidation-state, or coordination evidence.

- Total XPS tasks: 28
- Ready for a future approved backend fit: 24
- Not ready without more input/cleanup: 4

| task_id | status | file | record | grade | peak_guesses | blockers |
| --- | --- | --- | --- | --- | --- | --- |
| XPS-fresh_20260311MaNing-1.vms__wide | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.vms | wide | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-1.vms__O_1s | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.vms | O 1s | 可参考 | 1 | [] |
| XPS-fresh_20260311MaNing-1.vms__C_1s | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.vms | C 1s | 偏弱 | 2 | [] |
| XPS-fresh_20260311MaNing-1.vms__Al_2p | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.vms | Al 2p | 可参考 | 1 | [] |
| XPS-fresh_20260311MaNing-1.vms__Vb | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.vms | Vb | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-1.vms__Pd_3d | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.vms | Pd 3d | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-1.xlsx__Sheet8 | not_ready_for_backend_fit | XPS-fresh/20260311MaNing-1.xlsx | Sheet8 | 未拟合 | 0 | ["not enough numeric rows for dependency-free peak fitting", "record_is_unfitted"] |
| XPS-fresh_20260311MaNing-1.xlsx__Sheet7 | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.xlsx | Sheet7 | 偏弱 | 3 | [] |
| XPS-fresh_20260311MaNing-1.xlsx__Sheet6 | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.xlsx | Sheet6 | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-1.xlsx__Sheet5 | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.xlsx | Sheet5 | 可参考 | 1 | [] |
| XPS-fresh_20260311MaNing-1.xlsx__Sheet4 | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.xlsx | Sheet4 | 偏弱 | 2 | [] |
| XPS-fresh_20260311MaNing-1.xlsx__Sheet3 | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.xlsx | Sheet3 | 可参考 | 1 | [] |
| XPS-fresh_20260311MaNing-1.xlsx__Sheet2 | ready_for_backend_fit | XPS-fresh/20260311MaNing-1.xlsx | Sheet2 | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-1.xlsx__Sheet1 | not_ready_for_backend_fit | XPS-fresh/20260311MaNing-1.xlsx | Sheet1 | 未拟合 | 0 | ["not enough numeric rows for dependency-free peak fitting", "record_is_unfitted"] |
| XPS-fresh_20260311MaNing-2.vms__wide | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.vms | wide | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-2.vms__O_1s | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.vms | O 1s | 可参考 | 1 | [] |
| XPS-fresh_20260311MaNing-2.vms__Al_2p | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.vms | Al 2p | 可参考 | 1 | [] |
| XPS-fresh_20260311MaNing-2.vms__Vb | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.vms | Vb | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-2.vms__C_1s | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.vms | C 1s | 偏弱 | 5 | [] |
| XPS-fresh_20260311MaNing-2.vms__Pd_3d | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.vms | Pd 3d | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-2.xlsx__Sheet8 | not_ready_for_backend_fit | XPS-fresh/20260311MaNing-2.xlsx | Sheet8 | 未拟合 | 0 | ["not enough numeric rows for dependency-free peak fitting", "record_is_unfitted"] |
| XPS-fresh_20260311MaNing-2.xlsx__Sheet7 | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.xlsx | Sheet7 | 偏弱 | 3 | [] |
| XPS-fresh_20260311MaNing-2.xlsx__Sheet6 | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.xlsx | Sheet6 | 偏弱 | 5 | [] |
| XPS-fresh_20260311MaNing-2.xlsx__Sheet5 | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.xlsx | Sheet5 | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-2.xlsx__Sheet4 | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.xlsx | Sheet4 | 可参考 | 1 | [] |
| XPS-fresh_20260311MaNing-2.xlsx__Sheet3 | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.xlsx | Sheet3 | 可参考 | 1 | [] |
| XPS-fresh_20260311MaNing-2.xlsx__Sheet2 | ready_for_backend_fit | XPS-fresh/20260311MaNing-2.xlsx | Sheet2 | 偏弱 | 6 | [] |
| XPS-fresh_20260311MaNing-2.xlsx__Sheet1 | not_ready_for_backend_fit | XPS-fresh/20260311MaNing-2.xlsx | Sheet1 | 未拟合 | 0 | ["not enough numeric rows for dependency-free peak fitting", "record_is_unfitted"] |

## How to use

- Use `peak_guesses` as initial values only after approving a real fitting backend and choosing background/peak-shape constraints.
- Keep rows marked `not_ready_for_backend_fit` out of automated fitting until their blocking reasons are resolved.
- Do not report final chemical-state or oxidation-state conclusions from this handoff file.
