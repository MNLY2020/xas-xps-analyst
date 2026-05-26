# Limitations

- XPS: numeric workbook sheets receive a dependency-light peak-fit draft and, when an isolated fitting environment is used, a guarded lmfit Gaussian least-squares backend fit can be attempted.
- XPS: supported REGULAR VAMAS/VMS numeric blocks are reconstructed into dependency-free peak-fit drafts; unsupported VMS layouts remain 未拟合 with a specific reason.
- XPS: the selected backend is reported in `xps_backend_probe.*`; lmfit outputs are still numerical fits for triage/backend integration, not publication-grade chemical interpretation.
- XPS: the fitting handoff file contains backend-preparation tasks and initial guesses; use `xps_backend_fit_results.*` for the actual numerical backend outputs where available.
- XPS: `xps_reference_assignments.*` reports reference-library candidate valence/chemical-state matches from fitted peak centers and common binding-energy windows; every row remains 需人工确认.
- XAS: 未建模。This run did not perform XANES linear-combination fitting, EXAFS fitting, coordination-number estimation, or valence assignment.
- No final valence, chemical state, oxidation state, or coordination conclusion is made from the peak-fit draft or reference-candidate table.
- Publication-grade or chemistry-claim-bearing XPS fitting still requires explicit background choice, constraints, backend provenance, and human review.
