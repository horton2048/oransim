# Augur

**Launch foresight for makers** — an open-source causal engine for launch
prediction, combining a Causal Transformer world model, a Causal Neural Hawkes
diffusion forecaster, a 64-node Pearl SCM, and 1M IPF-calibrated virtual
consumers with 10k LLM-driven soul agents. Rehearse a product or content launch
before you spend on it.

Released under **Apache-2.0**. Version: **v0.2.0-alpha**.

---

## Quick navigation

- **Start here**: [Quickstart](en/quickstart.md) — clone, install, run.
- **Understand the system**: [Architecture](en/architecture.md).
- **Add a platform**: [Writing an adapter](en/platforms/writing-an-adapter.md).
- **Add a data source**: [Writing a DataProvider](en/platforms/writing-a-provider.md).
- **Evaluate**: [OrancBench](en/benchmarks/README.md) — 50-scenario canonical benchmark.
- **Schemas**: [Canonical types](en/schemas/README.md).

## What ships today

| Component | Status | Notes |
|---|---|---|
| XHS (RedNote) adapter | ✅ v1 | Reference implementation |
| TikTok adapter | 🟢 MVP | Global priors, synthetic provider |
| Douyin adapter | 🟢 MVP | China priors, livestream boost |
| Instagram Reels | 🟡 stub | Roadmap v0.5 |
| YouTube Shorts | 🟡 stub | Roadmap v0.7 |
| Causal Transformer world model | 📦 Code + training | Weights → v0.2 pretraining |
| Causal Neural Hawkes | 📦 Code + training | Weights → v0.2 pretraining |
| LightGBM baseline | ✅ Shipped pkl | `data/models/world_model_demo.pkl` |
| IPF population synthesizer | ✅ Shipped | Primary baseline |
| BayesianNetworkSynthesizer | ✅ v0.2 | Captures (edu, income) dependency |
| TabDDPM synthesizer | 📋 v0.5 roadmap | Tabular diffusion |
| Causal-DAG-guided TabDDPM | 📋 v1.0 research | Novel, conference target |

## Community

- **GitHub**: <https://github.com/horton2048/augur>
- **Issues**: <https://github.com/horton2048/augur/issues>

## Citing Augur

```bibtex
@software{augur2026,
  title        = {Augur: Launch Foresight for Makers},
  version      = {0.2.0-alpha},
  date         = {2026-04-18},
  url          = {https://github.com/horton2048/augur},
}
```
