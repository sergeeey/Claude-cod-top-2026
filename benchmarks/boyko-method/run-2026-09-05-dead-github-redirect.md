# boyko-method — dead GitHub redirect, root-cause analysis

**Date:** 2026-09-05 / 06
**Object:** why does `github.com/sergeeey/claude-code-config` return a clean
404 instead of GitHub's normal automatic redirect to the renamed
`Claude-cod-top-2026`, for the 2 stale local clones this session found
earlier?

## Why this run exists

Real, unresolved question from earlier this session (see the sibling
`brainstorming` benchmark, which deferred the DECISION on what to do with
these clones without ever explaining WHY the redirect was dead in the first
place). A genuine 3+-component system: GitHub's repo-identity/rename
mechanism, the local clones' cached `origin` URLs, and git's server-side
remote resolution -- exactly the multi-component shape this skill targets.

## Protocol

Ran the skill's 5-stage pipeline (context: fork, executed as a forked
sub-agent automatically per the skill's own frontmatter). Real tool calls
throughout: `git config` inspection of both clones, `git fetch`/`gh api`
reproduction of the 404, and a real `WebFetch` on GitHub's own
rename-a-repository documentation rather than reasoning from memory about
how redirects work.

## Result

**Key finding, overturning the user's own initial framing:** the premise
"GitHub usually keeps the redirect" is not just usually true -- it's the
*documented default behavior*, confirmed via real WebFetch of GitHub's docs.
So the real question shifted from "why didn't the redirect work" to "what
destroyed a redirect that was working."

**Root-cause hypothesis (H1), documented not invented:** GitHub's own docs
state a redirect is permanently destroyed if a NEW repository is later
created reusing the old name. This is `[VERIFIED-DOCS]` as a GENERAL rule;
whether it's what actually happened here is `[INFERRED]`, not directly
observed -- honestly labeled as the one missing link in the causal chain
(Model of the Whole's explicit "unknown zone").

**A plausible alternative was explicitly tested and killed, not just
listed:** the intuitive "local `.git/config` caches the dead URL" theory
predicts the 404 is a client-side artifact. This was falsified directly:
`gh api repos/sergeeey/claude-code-config` (a server-side call, no local
cache involved) returns the identical 404 -- the map explicitly marks this
link `[РАЗОРВАНА]` (broken) rather than silently dropping it.

**Two testable hypotheses with a named cheapest differentiating test:** H1
(a competing repo was created under the old name at some point) vs. H2
(the original operation was a transfer-to-new-owner, not a simple rename,
which GitHub's docs don't guarantee redirects for as strongly). The plan
explicitly names the cheapest test (one direct question to the user) before
a more expensive one (comparing repo numeric IDs against historical CI logs).

**Result vs. Step 8 explicit non-claims:** the analysis explicitly states
what it does NOT establish -- confirming H1 would not identify WHO created
the competing repo or why, and fixing the local clones' `origin` URL (a
practical action taken independent of resolving the causal question) does
NOT restore the GitHub-level redirect, which stays dead by design once
broken.

## Result vs the object question

Yes: produced a real, documented (not invented) root-cause mechanism, killed
a plausible wrong theory with a real server-side test rather than listing it
uncommitted, and named a concrete, cheap next differentiating test rather
than stopping at "it's broken, unclear why."

## Limitation

n=1, and the central causal link (H1 vs H2) remains genuinely unresolved --
this run correctly stopped at "here is the cheapest test to run next" rather
than fabricating a confirmed answer. The `fork` execution context also means
this ran with less visibility into the exact atomization/lens sub-steps than
a non-forked run would expose for inspection.
