# Paper 1 — Housing affordability index for Greater Kampala

**Title:** Priced out of the formal market: A housing affordability index for Greater Kampala, Uganda, from online listings and spatial machine learning

- `scripts/`: analysis stages 03–11, figures, animations, social graphics, the interactive explorer, and the manuscript builds. Each script starts with `import _paper`, which loads the shared pipeline and sets this folder's `outputs/` as the output location.
- `outputs/`: tables, maps, animations, social graphics and explorer data.
- `docs/manuscript/`: the manuscript (source, compiled draft, Word versions kept locally) and supplement.
- `docs/explorer/`: the interactive explorer (public copy: https://gavacharles.github.io/kampala-affordability-explorer/).

Reproduce the paper on the frozen dataset (10,643 listings, `data/paper_snapshot_2026-09-24`):

```bash
zsh paper1_affordability/scripts/run_paper.sh
```

Run single stages from the project root, e.g. `.venv/bin/python paper1_affordability/scripts/09_affordability_index.py`.
