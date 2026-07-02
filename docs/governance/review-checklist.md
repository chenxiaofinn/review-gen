# Review Checklist

Use this checklist before implementation, before commit, and before push.

## Before Implementation

- [ ] `git status` is checked and unrelated user changes are identified.
- [ ] Intent Gate is answered:
  - What user problem does this solve?
  - What does success look like?
  - What is explicitly out of scope?
  - How can the change be rolled back?
- [ ] Boundary Gate is answered:
  - Does this touch search, corpus, manifest, planner, writer, or orchestrator?
  - Does it preserve existing workspace paths and manual user fields?
  - Does it keep optional features optional?
- [ ] Architecture Gate is answered:
  - Which files change?
  - What data is read and written?
  - What happens when network or LLM calls fail?
  - What tests or fixtures prove the behavior?
- [ ] Story Gate is satisfied:
  - The work is split into a small story file or a clearly scoped task.
  - The story can be tested and reverted independently.

## Before Commit

- [ ] Existing tests pass.
- [ ] New tests or fixtures cover new behavior.
- [ ] No secrets, generated reports, PDFs, caches, or private corpora are staged.
- [ ] Documentation matches behavior.
- [ ] The diff is small enough to review.
- [ ] Documentation, configuration, code, and generated outputs are not mixed in
      one large commit.

## Before Push

- [ ] Local branch is the intended branch.
- [ ] `git status` is clean after commit.
- [ ] The branch is compared against its upstream.
- [ ] Tests were run after the final change.
- [ ] The user explicitly asked to push.

## Adversarial Review Questions

- What product boundary could this accidentally weaken?
- What existing workflow might this break?
- What user-edited field could this overwrite?
- What hidden network or LLM dependency could make offline use fail?
- What did this change make harder to test, revert, or explain?
- Is this a small reviewable change or the start of an uncontrolled rewrite?
