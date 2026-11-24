import csv
import sys

import numpy as np

r = list(csv.DictReader(open(sys.argv[1])))
d = [x for x in r if x["completed"] == "1"]
print(
    "completers by group",
    sum(x["group"] == "tutoring" for x in d),
    sum(x["group"] == "control" for x in d),
)
print(
    "completers pre>=85", [(x["id"], x["group"], x["site"]) for x in d if int(x["pre_score"]) >= 85]
)
t = [x for x in d if x["group"] == "tutoring"]
g = np.array([float(x["post_score"]) - float(x["pre_score"]) for x in t])
s = np.array([float(x["sessions"]) for x in t])
print("r sessions-gain (completers tutoring)", np.corrcoef(s, g)[0, 1])
print("resp>=5 among completers tutoring", (g >= 5).sum(), len(t))
print("alloc tutoring", sum(x["group"] == "tutoring" for x in r))
print("drop by group T", sum(x["group"] == "tutoring" and x["completed"] == "0" for x in r))
print("site counts", {k: sum(x["site"] == k for x in r) for k in "ABC"})
print("site counts completers", {k: sum(x["site"] == k for x in d) for k in "ABC"})
