import csv
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
ALPHA = 0.05

# Выгрузка из дашборда на день фиксации результата: (n, mean, sd) для A и B
METRICS = {
    "pages_per_session": ((3298, 4.21, 2.90), (3241, 4.37, 3.00)),
    "session_minutes": ((3298, 6.82, 5.10), (3241, 6.90, 5.30)),
    "add_to_cart_rate": ((3298, 0.112, 0.315), (3241, 0.118, 0.323)),
    "revenue_per_user": ((3298, 1.94, 12.4), (3241, 2.03, 13.1)),
    "support_contacts": ((3298, 0.031, 0.190), (3241, 0.029, 0.185)),
    "return_next_week": ((3298, 0.274, 0.446), (3241, 0.262, 0.440)),
}

# Сегменты на день фиксации: страна, устройство, users_A, conv_A, users_B, conv_B
SEGMENTS = [
    ("RU", "mobile", 750, 34, 741, 27),
    ("RU", "desktop", 527, 13, 555, 20),
    ("KZ", "mobile", 428, 21, 392, 24),
    ("KZ", "desktop", 286, 8, 312, 17),
    ("BY", "mobile", 365, 14, 415, 23),
    ("BY", "desktop", 264, 5, 224, 13),
    ("UZ", "mobile", 421, 16, 356, 17),
    ("UZ", "desktop", 257, 18, 246, 14),
]


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def two_sided(z):
    return 2 * norm_sf(abs(z))


def prop_z(xa, na, xb, nb):
    p = (xa + xb) / (na + nb)
    se = math.sqrt(p * (1 - p) * (1 / na + 1 / nb))
    return (xb / nb - xa / na) / se


def welch_z(ma, sa, na, mb, sb, nb):
    return (mb - ma) / math.sqrt(sa**2 / na + sb**2 / nb)


def load_daily():
    with open(HERE / "daily.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    n_days = max(int(r["day"]) for r in rows)
    out = {g: np.zeros((n_days, 3), dtype=int) for g in "AB"}
    for r in rows:
        out[r["group"]][int(r["day"]) - 1] = [
            int(r["users"]),
            int(r["conversions"]),
            int(r["refunds"]),
        ]
    return out


def srm_pvalue(na, nb):
    expected = (na + nb) / 2
    chi2 = ((na - expected) ** 2 + (nb - expected) ** 2) / expected
    return math.erfc(math.sqrt(chi2 / 2))


def monitor(daily):
    cum_a = np.cumsum(daily["A"], axis=0)
    cum_b = np.cumsum(daily["B"], axis=0)
    p = 1.0
    for d in range(len(cum_a)):
        (na, xa, _), (nb, xb, _) = cum_a[d], cum_b[d]
        p = norm_sf(prop_z(xa, na, xb, nb))
        print(f"  день {d + 1:2d}: CR A={xa / na:.4f}  CR B={xb / nb:.4f}  p={p:.4f}")
        if p < ALPHA:
            return d + 1, cum_a[d], cum_b[d], p
    return len(cum_a), cum_a[-1], cum_b[-1], p


def main():
    daily = load_daily()
    print("Ежедневный мониторинг конверсии:")
    day, (na, xa, ra), (nb, xb, rb), p_conv = monitor(daily)
    lift = (xb / nb) / (xa / na) - 1
    print(f"\nФиксация на дне {day}: n_A={na}, n_B={nb}, SRM p={srm_pvalue(na, nb):.3f}")
    print(f"Конверсия: A={xa / na:.4f}, B={xb / nb:.4f}, uplift={lift:+.1%}, p={p_conv:.4f}")

    p_ref = two_sided(prop_z(ra, xa, rb, xb))
    print(
        f"Доля возвратов среди покупок: A={ra / xa:.3f} ({ra}/{xa}), B={rb / xb:.3f} ({rb}/{xb}), p={p_ref:.3f}"
    )

    print("\nВторичные метрики:")
    for name, ((n1, m1, s1), (n2, m2, s2)) in METRICS.items():
        p = two_sided(welch_z(m1, s1, n1, m2, s2, n2))
        mark = "*" if p < ALPHA else ""
        print(f"  {name:18s} A={m1:<7} B={m2:<7} p={p:.3f} {mark}")

    print("\nСегменты (конверсия):")
    best = None
    for country, device, ua, ca, ub, cb in SEGMENTS:
        p = two_sided(prop_z(ca, ua, cb, ub))
        seg_lift = (cb / ub) / (ca / ua) - 1
        print(
            f"  {country}/{device:7s} A={ca / ua:.4f} B={cb / ub:.4f} uplift={seg_lift:+.0%} p={p:.3f}"
        )
        if best is None or p < best[2]:
            best = (f"{country}/{device}", seg_lift, p)
    print(f"  Лучший сегмент: {best[0]}, uplift={best[1]:+.0%}, p={best[2]:.3f}")

    with open(HERE / "benchmark.csv", newline="") as f:
        bench = list(csv.DictReader(f))
    old = np.array([float(r["load_ms_old"]) for r in bench])
    new = np.array([float(r["load_ms_new"]) for r in bench])
    z = welch_z(old.mean(), old.std(ddof=1), len(old), new.mean(), new.std(ddof=1), len(new))
    print(
        f"\nЗагрузка страницы: old={old.mean():.0f} мс, new={new.mean():.0f} мс, p={two_sided(z):.3f}"
    )


if __name__ == "__main__":
    main()
