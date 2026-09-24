#!/bin/zsh
# Final full run: clean -> all analysis stages -> figures -> manuscript. Log: outputs/run_final.log
cd "${0:a:h}/.."
PY=.venv/bin/python
: > outputs/run_final.log
run() { name=$1; shift
  if $PY scripts/$name.py "$@" > outputs/run_$name.log 2>&1; then echo "ok $name" >> outputs/run_final.log
  else echo "FAILED $name" >> outputs/run_final.log; fi }
run 02_clean --nominatim
run 03_spatial_patterns
run 04_hedonic_gwr --mgwr
run 05_machine_learning --gwr
run 06_affordability
run 07_land_value
run 08_validation
run 09_affordability_index
run 10_sample_adequacy
run 11_robustness
run fig_income
run fig_conceptual_framework
run social_affordability_map
run build_manuscript
echo "done $(date)" >> outputs/run_final.log
