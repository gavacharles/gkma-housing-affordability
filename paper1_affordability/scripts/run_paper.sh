#!/bin/zsh
# Paper run on the frozen 10,643-listing dataset: all analysis stages -> figures -> manuscript. Log: paper1_affordability/outputs/run_paper.log
cd "${0:a:h}/../.."
PY=.venv/bin/python
: > paper1_affordability/outputs/run_paper.log
run() { name=$1; shift
  if $PY $([ -f paper1_affordability/scripts/$name.py ] && echo paper1_affordability/scripts || echo scripts)/$name.py "$@" > paper1_affordability/outputs/run_$name.log 2>&1; then echo "ok $name" >> paper1_affordability/outputs/run_paper.log
  else echo "FAILED $name" >> paper1_affordability/outputs/run_paper.log; fi }
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
echo "done $(date)" >> paper1_affordability/outputs/run_paper.log
$PY paper1_affordability/scripts/build_supplement.py >> paper1_affordability/outputs/run_paper.log 2>&1
$PY paper1_affordability/scripts/build_docx.py >> paper1_affordability/outputs/run_paper.log 2>&1
