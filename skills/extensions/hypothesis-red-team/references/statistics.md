# Statistics Reference

Advanced statistical tools for hypothesis validation. Load when SKILL.md §3
references are insufficient for the specific test needed.

---

## Circular Statistics (V-test for directional hypotheses)

Use when data are angles, phases, or periodic values.
**Never use arithmetic mean for circular data** — average of 1° and 359° is 0°, not 180°.

```python
import numpy as np
from scipy.stats import norm

def v_test(angles_rad: np.ndarray, target_rad: float) -> dict:
    """
    V-test: tests H1 that circular mean = target_rad (specific direction).
    More powerful than Rayleigh when direction is predicted a priori.
    Reference: Mardia & Jupp (2000), p. 103.
    """
    n = len(angles_rad)
    sin_sum = np.sum(np.sin(angles_rad))
    cos_sum = np.sum(np.cos(angles_rad))
    R_bar   = np.sqrt(sin_sum**2 + cos_sum**2) / n
    mu_hat  = np.arctan2(sin_sum, cos_sum)

    V = n * R_bar * np.cos(mu_hat - target_rad)
    z = V * np.sqrt(2 / n)
    p = float(1.0 - norm.cdf(z))  # one-sided

    return {
        "mean_angle_deg": float(np.degrees(mu_hat)),
        "concentration_R": round(R_bar, 4),
        "V_statistic": round(V, 4),
        "z": round(z, 4),
        "p_value_one_sided": round(p, 6),
        "target_deg": float(np.degrees(target_rad)),
        "verdict": "PASS" if p < 0.05 else "FAIL",
    }

def rayleigh_test(angles_rad: np.ndarray) -> dict:
    """
    Rayleigh test: tests H1 that distribution is NOT uniform (no specific direction).
    Use when you have no prior on the target angle.
    """
    n = len(angles_rad)
    R = np.sqrt(np.sum(np.sin(angles_rad))**2 + np.sum(np.cos(angles_rad))**2) / n
    z = n * R**2
    p = float(np.exp(-z) * (1 + (2*z - z**2) / (4*n) - (24*z - 132*z**2 + 76*z**3 - 9*z**4) / (288*n**2)))
    return {"R_bar": round(R, 4), "z": round(z, 4), "p_value": round(p, 6)}
```

---

## Optimization Method Comparison

When testing search algorithms, compare all four — never use golden-section alone.

```python
import numpy as np
from scipy.optimize import minimize_scalar

def benchmark_search_methods(f, a: float, b: float,
                               tol: float = 1e-6, n_runs: int = 100) -> dict:
    """
    Compare golden-section, Fibonacci, ternary, and Brent on function f.
    Returns mean call counts and paired p-values vs golden-section.
    """
    from scipy.stats import ttest_rel

    call_counts = {"golden": [], "brent": [], "ternary": []}

    for _ in range(n_runs):
        # Brent (scipy default, superlinear on smooth functions)
        counter = [0]
        def f_counted(x):
            counter[0] += 1
            return f(x)

        minimize_scalar(f_counted, bounds=(a, b), method='bounded')
        call_counts["brent"].append(counter[0])

        # Golden-section (manual)
        calls = [0]
        _golden_section(f, a, b, tol, calls)
        call_counts["golden"].append(calls[0])

        # Ternary search
        calls = [0]
        _ternary_search(f, a, b, tol, calls)
        call_counts["ternary"].append(calls[0])

    results = {}
    for method, counts in call_counts.items():
        results[method] = {
            "mean_calls": round(np.mean(counts), 2),
            "std_calls":  round(np.std(counts), 2),
        }
        if method != "golden":
            _, p = ttest_rel(call_counts["golden"], counts)
            results[method]["p_vs_golden"] = round(p, 6)

    return results

def _golden_section(f, a, b, tol, calls):
    phi = (np.sqrt(5) - 1) / 2
    c, d = b - phi*(b-a), a + phi*(b-a)
    while (b - a) > tol:
        calls[0] += 2
        if f(c) < f(d):
            b = d; d = c; c = b - phi*(b-a)
        else:
            a = c; c = d; d = a + phi*(b-a)
    return (a + b) / 2

def _ternary_search(f, a, b, tol, calls):
    while (b - a) > tol:
        m1 = a + (b-a)/3
        m2 = b - (b-a)/3
        calls[0] += 2
        if f(m1) < f(m2):
            b = m2
        else:
            a = m1
    return (a + b) / 2
```

---

## Dose-Response: 4PL Bayesian Adaptive Fitting

Use when optimizing context length, sample size, or any "dose → accuracy" relationship.

```python
import numpy as np
from scipy.optimize import minimize

def fit_4pl(x: list, y: list) -> dict:
    """
    4-parameter logistic: y = bottom + (top-bottom) / (1 + 10^((EC50-x)*slope))
    Returns fitted params and next recommended x for adaptive sampling.
    """
    def loss(params):
        top, bottom, log_ec50, slope = params
        if top < bottom or slope <= 0:
            return 1e10
        y_hat = bottom + (top-bottom) / (1 + 10**((log_ec50 - np.array(x)) * slope))
        return float(np.sum((np.array(y) - y_hat)**2))

    x0 = [max(y), min(y), np.log10(np.median(x)), 1.0]
    res = minimize(loss, x0, method='Nelder-Mead',
                   options={'xatol': 1e-6, 'fatol': 1e-6, 'maxiter': 5000})

    top, bottom, log_ec50, slope = res.x
    next_x = 10**log_ec50  # EC50 = point of maximum uncertainty → sample here next

    return {
        "top": round(top, 4),
        "bottom": round(bottom, 4),
        "EC50": round(next_x, 4),
        "slope": round(slope, 4),
        "next_recommended_x": round(next_x, 4),
        "converged": res.success,
    }
```

---

## McNemar (paired binary outcomes)

```python
import numpy as np
from statsmodels.stats.contingency_tables import mcnemar

def mcnemar_test(baseline: np.ndarray, experimental: np.ndarray) -> dict:
    a = int(np.sum((baseline==1) & (experimental==1)))
    b = int(np.sum((baseline==1) & (experimental==0)))
    c = int(np.sum((baseline==0) & (experimental==1)))
    d = int(np.sum((baseline==0) & (experimental==0)))
    result = mcnemar([[a,b],[c,d]], exact=True)
    return {
        "contingency": {"a":a,"b":b,"c":c,"d":d},
        "statistic": result.statistic,
        "p_value": result.pvalue,
        "direction": "experimental > baseline" if c > b else "no improvement",
        "verdict": "PASS" if result.pvalue < 0.05 and c > b else "FAIL",
    }
```

---

## Bayesian Factor Reference (Jeffreys Scale)

| BF₁₀ | Interpretation |
|------|----------------|
| > 100 | Decisive evidence for H1 |
| 30–100 | Very strong for H1 |
| 10–30 | Strong for H1 |
| 3–10 | Moderate for H1 |
| 1–3 | Anecdotal for H1 |
| 1/3–1 | Anecdotal for H0 |
| 1/10–1/3 | Moderate for H0 |
| < 1/10 | Strong evidence **against** H1 |

Rule: BF < 1/3 against H1 → reject H1 regardless of p-value.
