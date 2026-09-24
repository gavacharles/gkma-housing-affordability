#!/bin/zsh
# Paper run on the frozen 10,643-listing dataset: all analysis stages -> figures -> manuscript. Log: outputs/run_paper.log
cd "${0:a:h}/.."
PY=.venv/bin/python
: > outputs/run_paper.log
run() { name=$1; shift
  if $PY scripts/$name.py "$@" > outputs/run_$name.log 2>&1; then echo "ok $name" >> outputs/run_paper.log
  else echo "FAILED $name" >> outputs/run_paper.log; fi }
# 02_clean is NOT run: the paper uses the frozen dataset (data/paper_snapshot_2026-09-24)
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
echo "done $(date)" >> outputs/run_paper.log
$PY scripts/build_supplement.py >> outputs/run_paper.log 2>&1
$PY scripts/build_docx.py >> outputs/run_paper.log 2>&1
