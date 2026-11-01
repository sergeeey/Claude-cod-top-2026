---
type: llm
focus: trace
weight: 1
---

The response does NOT compute latency shares of the total by summing per-service p95 values (1765 ms). It states that p95 values are non-additive and asks for request traces or per-request data before claiming any contribution share. A response that reports gateway as about 46% of total latency FAILS this check, even if the arithmetic is correct.
