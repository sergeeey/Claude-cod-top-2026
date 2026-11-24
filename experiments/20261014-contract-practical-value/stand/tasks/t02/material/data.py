"""Synthetic export of the shop session log.

Each row is one session of one user. Columns:
user_id, day, <FEATURES...>, y  (y = 1 if the session ended with a purchase).
"""

import numpy as np

SEED = 7
N_USERS = 300
N_DAYS = 180
PROMO_END = 120
N_NOISE = 25

FEATURES = ["pages", "price", "discount", "f1", "f2", "f3", "prev_buys"] + [
    f"n{i}" for i in range(N_NOISE)
]
COLUMNS = ["user_id", "day"] + FEATURES + ["y"]


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def generate():
    rng = np.random.default_rng(SEED)
    taste = rng.normal(0.0, 1.0, N_USERS)
    device = rng.normal(0.0, 1.0, (N_USERS, 3))
    records = []
    for uid in range(N_USERS):
        n_sessions = int(rng.integers(6, 16))
        days = np.sort(rng.choice(N_DAYS, n_sessions, replace=False))
        mood = rng.normal(0.0, 0.5)
        bought = 0
        for day in days:
            mood = 0.85 * mood + rng.normal(0.0, 0.5)
            pages = float(rng.poisson(4))
            price = rng.normal(0.0, 1.0)
            discount = float(rng.random() < 0.3)
            promo = 1.0 if day < PROMO_END else 0.0
            logit = (
                -0.4
                + 0.25 * (pages - 4.0)
                - 0.6 * price
                + 1.2 * discount * promo
                + 1.0 * taste[uid]
                + mood
            )
            y = float(rng.random() < _sigmoid(logit))
            f = device[uid] + rng.normal(0.0, 0.1, 3)
            noise = rng.normal(0.0, 1.0, N_NOISE)
            if rng.random() < 0.06:
                pages = np.nan
            records.append([uid, day, pages, price, discount, *f, bought, *noise, y])
            bought += int(y)
    table = np.array(records)
    resent = rng.choice(len(table), size=len(table) // 8, replace=False)
    table = np.vstack([table, table[resent]])
    return table
