# Reservoir, SLA print copy - WATER ONLY

These files are print-ready copies of the **frozen** CNC reservoir geometry (`params.json` -> `reservoir_frozen`) for the first,
water-only bench builds (SLA resin, e.g. JLC3DP). **They must never contact insulin**: printed resin is not insulin-compatible,
not validated, not sterile. Insulin tests (into containers only, never a person) use the CNC polypropylene part in
`../reservoir-cnc/`.

* Geometry identical to `../reservoir-cnc/` (same bore 16.00 x 5.00, port d2.0 at the closed end); nothing in `reservoir_frozen` was changed.
* SLA tolerance is about +-0.1 mm: check the bore with the plunger, ream the port to d2.0 if the cap spigot does not enter. If SLA needs a
  different wall or clearance, document it here - do not edit `reservoir_frozen`.
* Print standing on the open end, support the outside only; wash and UV-cure, do not sand the bore.
