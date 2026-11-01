# Trap Reference: 10 Anti-Overfitting Defenses

Full Python implementations for all 10 traps. Load this file when the user
needs executable code for a specific protection.

---

## T1: Selective Sampling — Blind Measurement Protocol

```python
# Fix: declare measurement points before seeing data
MEASUREMENT_PROTOCOL = {
    "object":       "human_hand",
    "points":       ["proximal_phalanx", "middle_phalanx"],  # locked pre-data
    "ratio":        "proximal / middle",
    "epsilon":      0.05,   # locked pre-data
    "n_min":        50,     # locked pre-data
    "alternatives": [1.333, 1.414, 1.5, 1.618, 2.0],        # locked pre-data
}
# Rule: once data collection starts, NO field in this dict may change.
```

---

## T2: Epsilon-Hacking — OSF Preregistration Check

```python
def check_epsilon_integrity(epsilon_declared_before: bool,
                             epsilon_value: float,
                             observed_mean: float,
                             target: float) -> str:
    """Verify ε was not chosen post-hoc to capture observed_mean."""
    if not epsilon_declared_before:
        return "❌ FAIL: ε not preregistered. Result is uninterpretable."

    in_range = abs(observed_mean - target) <= epsilon_value
    coverage = 2 * epsilon_value  # width of acceptance band on [1,2] scale
    baseline_hit_rate = coverage / 1.0  # U(1,2) → 1.0 range

    return (
        f"✅ PASS: ε={epsilon_value} preregistered. "
        f"Observed mean {'IN' if in_range else 'NOT IN'} range. "
        f"Baseline hit rate: {baseline_hit_rate:.0%}"
    )
```

---

## T3: Unrealistic Null — Domain-Specific Null Model

```python
import numpy as np
from scipy import stats

def realistic_null_model(domain: str):
    """Return a realistic null distribution for ratio comparisons."""
    models = {
        "biological_ratios":  stats.lognorm(s=0.20, scale=np.exp(np.log(1.4))),
        "architectural":      stats.norm(loc=1.45, scale=0.15),
        "financial_ratios":   stats.lognorm(s=0.35, scale=np.exp(np.log(1.2))),
        "uniform_fallback":   stats.uniform(1.0, 1.0),  # use only if no prior
    }
    return models.get(domain, models["uniform_fallback"])

def compare_null_models(ratios: np.ndarray, target: float, domain: str) -> dict:
    null_realistic = realistic_null_model(domain)
    null_uniform   = stats.uniform(1.0, 1.0)

    p_realistic = float(null_realistic.sf(abs(np.mean(ratios) - target)))
    p_uniform   = float(null_uniform.sf(abs(np.mean(ratios) - target)))

    return {
        "p_vs_uniform":   p_uniform,
        "p_vs_realistic": p_realistic,
        "inflation_factor": p_uniform / max(p_realistic, 1e-10),
        "warning": "Significance inflated by unrealistic null"
                   if p_realistic > 5 * p_uniform else "OK",
    }
```

---

## T4: Garden of Forking Paths — Multiverse Analysis

```python
import itertools
import numpy as np
from scipy import stats

def multiverse_analysis(data: np.ndarray, target: float,
                        alpha: float = 0.05) -> dict:
    """
    Test all reasonable analytical specifications.
    Returns robust_fraction: share of specs where H1 is supported.
    """
    decisions = {
        "outlier_removal": [None, "3sd", "iqr"],
        "normalization":   ["none", "log", "sqrt"],
        "test_method":     ["t_test", "wilcoxon", "bootstrap"],
    }

    results = []
    for combo in itertools.product(*decisions.values()):
        spec = dict(zip(decisions.keys(), combo))
        d = _apply_spec(data, spec)
        if len(d) < 3:
            continue
        p = _run_test(d, target, spec["test_method"])
        results.append({
            "spec": spec,
            "p_value": p,
            "n": len(d),
            "mean": float(np.mean(d)),
            "h1_supported": p < alpha,
        })

    robust_fraction = sum(r["h1_supported"] for r in results) / len(results)
    return {
        "n_specs": len(results),
        "robust_fraction": robust_fraction,
        "verdict": "ROBUST" if robust_fraction > 0.7 else
                   "FRAGILE" if robust_fraction > 0.3 else "NOT SUPPORTED",
        "results": results,
    }

def _apply_spec(data: np.ndarray, spec: dict) -> np.ndarray:
    d = data.copy()
    if spec["outlier_removal"] == "3sd":
        d = d[np.abs(d - np.mean(d)) < 3 * np.std(d)]
    elif spec["outlier_removal"] == "iqr":
        q1, q3 = np.percentile(d, [25, 75])
        d = d[(d >= q1 - 1.5*(q3-q1)) & (d <= q3 + 1.5*(q3-q1))]
    if spec["normalization"] == "log":
        d = np.log(d[d > 0])
    elif spec["normalization"] == "sqrt":
        d = np.sqrt(np.abs(d))
    return d

def _run_test(data: np.ndarray, target: float, method: str) -> float:
    diff = data - target
    if method == "t_test":
        _, p = stats.ttest_1samp(diff, 0)
    elif method == "wilcoxon":
        _, p = stats.wilcoxon(diff)
    else:  # bootstrap
        bs = np.array([np.mean(np.random.choice(diff, len(diff))) for _ in range(1000)])
        p = float(np.mean(np.abs(bs) >= np.abs(np.mean(diff))))
    return float(p)
```

---

## T5: Multiple Comparisons

```python
from statsmodels.stats.multitest import multipletests

def fwer_report(p_values: list, alpha: float = 0.05) -> dict:
    """Apply all common corrections and report n_significant for each."""
    methods = ["bonferroni", "holm", "fdr_bh", "fdr_by"]
    results = {}
    for m in methods:
        reject, p_corr, _, _ = multipletests(p_values, method=m)
        results[m] = {"n_significant": int(sum(reject)), "p_corrected": p_corr.tolist()}

    uncorrected = sum(p < alpha for p in p_values)
    results["uncorrected"] = {"n_significant": uncorrected}

    fwer_risk = 1 - (1 - alpha) ** len(p_values)
    results["fwer_without_correction"] = round(fwer_risk, 4)

    return results
```

---

## T6: Winner's Curse — Power Analysis

```python
from statsmodels.stats.power import TTestOneSamplePow, TTestIndPow
import numpy as np

def required_n(effect_d: float, alpha: float = 0.05,
               power: float = 0.80, design: str = "one_sample") -> dict:
    if design == "one_sample":
        analysis = TTestOneSamplePow()
    else:
        analysis = TTestIndPow()

    n = analysis.solve_power(effect_size=effect_d, alpha=alpha, power=power)
    return {
        "required_n": int(np.ceil(n)),
        "effect_d": effect_d,
        "power": power,
        "alpha": alpha,
        "warning": f"Need n≥{int(np.ceil(n))} per group. "
                   f"Smaller samples inflate effect size estimates (winner's curse)."
    }

# Common reference values:
# d=0.8 (large)  → n=27  | d=0.5 (medium) → n=34 (wait, one-sample)
# d=0.2 (small)  → n=199 | d=0.1 (tiny)   → n=782
```

---

## T7: HARKing — Exploratory vs Confirmatory Checklist

```python
def hark_check(study_params: dict) -> dict:
    """
    Returns classification and required actions.
    study_params keys: hypothesis_before_data (bool), epsilon_before_data (bool),
    n_calculated_apriori (bool), osf_timestamp (bool), alternatives_declared (bool)
    """
    confirmatory_criteria = [
        ("hypothesis_before_data", "Hypothesis stated before data collection"),
        ("epsilon_before_data",    "Tolerance ε fixed before data collection"),
        ("n_calculated_apriori",   "Sample size from power analysis, not 'until found'"),
        ("osf_timestamp",          "OSF/AsPredicted registration with verifiable timestamp"),
        ("alternatives_declared",  "Competing models listed before analysis"),
    ]
    passed = [(k, desc) for k, desc in confirmatory_criteria if study_params.get(k)]
    failed = [(k, desc) for k, desc in confirmatory_criteria if not study_params.get(k)]

    classification = "CONFIRMATORY" if len(passed) == 5 else \
                     "EXPLORATORY"  if len(passed) >= 2 else \
                     "UNCLASSIFIABLE"

    return {
        "classification": classification,
        "passed": [desc for _, desc in passed],
        "failed": [desc for _, desc in failed],
        "required_label": "" if classification == "CONFIRMATORY" else
                          "[EXPLORATORY — hypothesis-generating only]",
    }
```

---

## T8: Wrong Statistical Test — TED vs TΔ for Ratio Data

```python
from scipy import stats
import numpy as np

def correct_ratio_test(a_values: np.ndarray, b_values: np.ndarray,
                       target: float) -> dict:
    """
    TED (t-test on differences) and WD (Wilcoxon on differences) are valid.
    TΔ (delta statistic on ratios directly) inflates Type I error to ~50% at n=200.
    Never use TΔ.
    """
    ratios = a_values / b_values
    differences = ratios - target  # TED statistic

    t_stat, p_TED = stats.ttest_1samp(differences, 0)
    w_stat, p_WD  = stats.wilcoxon(differences)

    agreement = (p_TED < 0.05) == (p_WD < 0.05)
    return {
        "TED":  {"t": round(t_stat, 4), "p": round(p_TED, 6)},
        "WD":   {"W": round(w_stat, 4), "p": round(p_WD,  6)},
        "agreement": agreement,
        "warning": "" if agreement else
                   "⚠️ TED and WD disagree — result is unstable, report both",
        "never_use": "TΔ (delta statistic) — inflates Type I error at large n",
    }
```

---

## T9: No Alternative Models — Bayesian Model Comparison

```python
import numpy as np
from scipy import stats

def bayesian_model_comparison(ratios: np.ndarray,
                               candidates: dict = None) -> list:
    """
    Compare hypothesis to rival constants via log-likelihood.
    Returns ranked list with Bayes Factors vs best model.

    Default candidates cover the most common confounds.
    """
    if candidates is None:
        candidates = {
            "phi":       1.6180339887,
            "sqrt2":     1.4142135624,
            "3/2":       1.5000000000,
            "pi/2":      1.5707963268,
            "4/3":       1.3333333333,
            "e^0.5":     1.6487212707,
            "empirical": float(np.mean(ratios)),  # "any number works" baseline
        }

    mu_obs    = np.mean(ratios)
    se_obs    = np.std(ratios, ddof=1) / np.sqrt(len(ratios))

    log_liks  = {name: float(stats.norm.logpdf(mu_obs, loc=mu, scale=se_obs))
                 for name, mu in candidates.items()}
    best_ll   = max(log_liks.values())

    ranked = sorted(
        [{"model": name, "log_lik": ll, "delta_ll": ll - best_ll,
          "BF_vs_best": round(np.exp(ll - best_ll), 4),
          "winner": ll == best_ll}
         for name, ll in log_liks.items()],
        key=lambda x: -x["log_lik"]
    )
    return ranked
    # Interpretation: BF < 0.1 against target = strong evidence vs H1
```

---

## T10: No Replication — AOS Final Gate

```python
def replication_gate(aos: int, has_replication: bool,
                     n_independent_datasets: int) -> dict:
    """Final publication gate combining AOS + replication status."""
    if aos >= 85 and has_replication and n_independent_datasets >= 2:
        verdict = "✅ CONFIRMATORY publication justified"
    elif aos >= 60 and (has_replication or n_independent_datasets >= 1):
        verdict = "⚠️ Publish with explicit limitations section"
    elif aos >= 40:
        verdict = "🔶 Exploratory only — label as hypothesis-generating"
    else:
        verdict = "❌ Do not publish as confirmation — redesign study"

    return {
        "aos": aos,
        "has_replication": has_replication,
        "n_datasets": n_independent_datasets,
        "verdict": verdict,
    }
```
