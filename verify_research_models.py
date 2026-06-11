"""Smoke-check the two trained research models load + predict (factual + counterfactual).
Run: .\.venv\Scripts\python.exe verify_research_models.py
"""
import json

from oransim.world_model import CausalTransformerWorldModel
from oransim.diffusion.neural_hawkes import CausalNeuralHawkesProcess
from backend.scripts.train_transformer_wm import _featurize_row

print("=== Causal Transformer World Model ===")
wm = CausalTransformerWorldModel.load_pretrained()  # auto-resolves data/models/causal_transformer_wm/model.pt
raw = {
    "scenario_id": "DEMO_001", "niche": "beauty", "platform_id": 0,
    "budget": 80000, "kol_tier": "mid", "kol_fan_count": 500000,
    "kol_engagement_rate": 0.04,
}
feat = _featurize_row(raw, seed=42)  # raw scenario -> numeric tensor dict predict() expects
fact = wm.predict(feat)
print("factual kpi_quantiles:", json.dumps(fact.kpi_quantiles, ensure_ascii=False))
cf = wm.counterfactual(feat, arm_idx=1)  # do(T = arm 1)  # noqa
print("counterfactual(arm=1):", json.dumps(cf.kpi_quantiles, ensure_ascii=False))

print("\n=== Causal Neural Hawkes ===")
nh = CausalNeuralHawkesProcess.load_pretrained()  # auto-resolves data/models/causal_neural_hawkes/model.pt
seed = [(0.0, "impression"), (12.0, "like"), (30.0, "paid_impression"), (45.0, "comment")]
f = nh.forecast(seed)
print("factual per_type_totals:", json.dumps(f.per_type_totals, ensure_ascii=False))
cf2 = nh.counterfactual_forecast(seed, intervention={"mute_at_min": 40})  # stop boosting at min 40
print("counterfactual(mute@40) per_type_totals:", json.dumps(cf2.per_type_totals, ensure_ascii=False))
print("\nOK — both trained research models load + predict (factual + counterfactual).")
