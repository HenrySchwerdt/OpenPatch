# Aufruf: make all   (benoetigt .venv: UV_HTTP_TIMEOUT=300 uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt)
PY=.venv/bin/python
all: netlist check dxf svg
netlist:
	cd schematic && ../$(PY) -W ignore build.py > ../build.log 2>&1; grep -E "ERC|BOM" ../build.log
check:
	cd schematic && ../$(PY) -W ignore check_netlist.py | tail -2
dxf:
	cd layout && ../$(PY) -W ignore board_outline.py
svg:
	cd layout && ../$(PY) -W ignore placement_plan.py
