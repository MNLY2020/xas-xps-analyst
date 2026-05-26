# XPS Backend Probe

- Selected backend: `lmfit_gaussian_least_squares_v1`
- Selected backend available: True
- Scope: headless lmfit Gaussian least-squares refinement over existing XPS handoff guesses

## Python modules

| module | available |
| --- | --- |
| lmfit | True |
| matplotlib | False |
| numpy | True |
| pandas | False |
| scipy | True |
| wx | False |

## External backend candidates

| backend | available | note |
| --- | --- | --- |
| khervefitting_source | False | Local source is present, but this monolithic GUI-style source was not executed headlessly unless required GUI/scientific-stack modules were available. |
| lmfit | True |  |

This probe is not a fit result and does not support final chemical-state, valence, oxidation-state, or coordination claims.
