# Vendor notes

## JLC3DP (jlc3dp.com) - default
* Upload STL (or STEP) per part; choose process per the table in README.md. MJF: "PA12-HP Nylon" (grey).
  Pick standard finishing only. SLA: choose a tough resin (8001-type) for carriage/plunger/mould, clear for the reservoir.
* Minimum wall for MJF is about 0.5-0.8 mm depending on the tool; our 0.4 mm tongue and 0.45 mm skirt may be flagged
  or break in depowdering. If rejected: re-order the housing in SLA (0.4 mm is fine there) - the lid/bottom STEP is the same.
* Order everything in one order (shared shipping). Add a note: "dimensions critical on bores; no support marks inside bores".

## PCBWay (pcbway.com) - alternative
* 3D Printing -> MJF Nylon PA12 / SLA; CNC Machining -> PP (optional reservoir halves).
* Upload STEP for CNC (STL for printing). Notes field: "prototype, +-0.1 mm on marked bores, deburr, no coating".
* Good for hand-reviewed thin features and for combining with PCB/PCBA orders.

## Both
* Water-test parts (reservoir, plunger core) are NOT biocompatible or sterile. The pump is never filled with insulin or any other drug and nothing that
  goes to a person through printed Rev A parts.
* Always request the quote for the smallest size (OP-70) first to see per-part minimums before ordering 3 sizes.
