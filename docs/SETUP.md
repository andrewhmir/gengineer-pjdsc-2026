# Setup and Owner Runbook

Operations that touch the **remote repository** — creating it, governing it, and inviting
people to it. These are one-time or rare, owner-level actions, and they are recorded here
in exact commands so that they are a copy-paste rather than a rediscovery.

Human contribution workflow is in [`../CONTRIBUTING.md`](../CONTRIBUTING.md). Local
development setup is in [`../README.md`](../README.md). This document does not repeat
either.

## Facts about this setup

| Fact | Value |
|---|---|
| Repository | `andrewhmir/gengineer-pjdsc-2026` |
| Visibility | **public** |
| Default branch | `main` |
| Required status check | **`ci-success`** (the aggregate gate job) |
| Teams / contributors | currently **one** — this constrains the ruleset; see below |
| Local clone | `C:\Users\Andrew\Desktop\Gengineer\gengineer-pjdsc-2026` |
| Worktrees | `.worktrees/` (gitignored) |

### Which `gh` account is active matters

`gh` and `git` are separate concerns: `gh` controls **push access**, while commit
**authorship** comes from the repository-local `git config`. They are not the same thing,
and changing one does not change the other.

`gh auth switch` writes to:

```text
%APPDATA%\GitHub CLI\hosts.yml
```

That path is **outside the workspace**. On a machine where the agent runs under a
confined file sandbox, the write is denied and the switch fails; run it from an
unconfined shell (or by hand) in that situation. It is not a bug in `gh`.

On this machine the active account has been `andrew-aira`, while the repository is owned
by `andrewhmir`. **A switch is therefore required before pushing**, or the push is
rejected for lack of access:

```powershell
gh auth switch --user andrewhmir
gh auth setup-git
gh auth status
```

Expected: `gh auth status` lists `andrewhmir` with `Active account: true`. If the switch
fails, **stop** — pushing while the wrong account is active creates or writes to a
repository owned by the wrong user.

> **Correction to the design record.** Section 10.1 of
> [`../specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md)
> records the sandbox denial as a hard constraint and hands remote creation to the
> maintainer as a runbook. That was superseded on 2026-10-10: the session's file policy was
> raised to `danger-full-access`, the denial no longer occurs, and remote creation, push,
> and ruleset application are performed as ordinary implementation steps. The **account
> switch itself remains required** whenever the active `gh` account is not the repository
> owner.

## Creating the repository

Only needed once. Confirm the target does not already exist first, because
`gh repo create` on an existing name fails.

```bash
gh repo view andrewhmir/gengineer-pjdsc-2026
```

Expected: a "not found" error. That is the desired state. If the repository **does** exist,
stop and ask the maintainer whether to use it rather than overwriting anything.

```bash
gh repo create gengineer-pjdsc-2026 --public \
  --source=. --remote=origin \
  --description "PJDSC 2026 entry: public health analytics with microcontroller and web application integration." \
  --push
```

Then verify the push and that the local and remote views agree:

```bash
git status -sb
git log --oneline -1
gh repo view andrewhmir/gengineer-pjdsc-2026 --json visibility,defaultBranchRef,url
```

Expected: `main` is up to date with `origin/main`; visibility is `PUBLIC`; the default
branch is `main`.

## Applying the ruleset

The repository is public, and **GitHub Free permits rulesets on public repositories**.
Governance is therefore enforced by the platform rather than merely documented. On a
private repository this would require a paid plan, which is one of the reasons the
repository is public from the start.

### Order of operations

Do not create a required status check for a job that has never reported. The check name
must exist in a completed run before GitHub will accept it as required, or the check sits
"expected" forever and every pull request is blocked.

1. Push `main`.
2. Wait for CI to complete, including the `ci-success` job:

   ```bash
   gh run list --limit 5
   ```

3. Create the ruleset.
4. Read it back and prove `main` is still mergeable.

### The ruleset

The rules, and which of them are safe unconditionally:

| Rule | Safe at one contributor? | Why |
|---|---|---|
| Block deletion of `main` | Yes | Protects history; needs no second person. |
| Block non-fast-forward (force-push) | Yes | Protects history; needs no second person. |
| Require a pull request before merging | Yes, **with 0 required approvals** | Anyone can still open and merge a pull request; see the warning below. |
| Require the `ci-success` status check | Yes | Depends only on CI reporting, not on people. |
| Require linear history | Yes | A merge strategy constraint, not an approval constraint. |
| Require conversation resolution | Yes | The author can resolve their own threads. |
| **Require 1 approving review** | **No** | GitHub does not let a pull request author approve their own pull request, so with a single contributor `main` becomes **unmergeable**. |

`ci-success` is load-bearing rather than decorative: a job that is skipped by its changed-path
guard never reports, and a required check that never reports leaves a pull request
permanently blocked. That is why the aggregate job exists and why it is the required check
rather than `lint` or `test` individually.

### Create it

Write the JSON to a file, `ruleset.json`. This single-line form is used because a heredoc
does not behave consistently across PowerShell and POSIX shells, and a copy-paste command
must work in either:

```json
{"name": "main protection", "target": "branch", "enforcement": "active", "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}, "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "required_linear_history"}, {"type": "pull_request", "parameters": {"required_approving_review_count": 0, "dismiss_stale_reviews_on_push": true, "require_code_owner_review": false, "require_last_push_approval": false, "required_review_thread_resolution": true}}, {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": false, "do_not_enforce_on_create": false, "required_status_checks": [{"context": "ci-success"}]}}]}
```

Then apply it:

```bash
gh api --method POST repos/andrewhmir/gengineer-pjdsc-2026/rulesets \
  --input ruleset.json
```

**Do not set `required_approving_review_count` above `0` while the team has one
contributor.** The ruleset above deliberately sets it to `0`. Raising it early is the
single most common way to deadlock `main` on a solo project: every pull request, including
your own, would show `BLOCKED` with no eligible approver. See
[Enabling required approvals](#enabling-required-approvals) for when and how to raise it.

### Verify by read-back, and prove `main` is still workable

```bash
gh api repos/andrewhmir/gengineer-pjdsc-2026/rulesets --jq '.[] | {id, name, enforcement, target}'
gh api repos/andrewhmir/gengineer-pjdsc-2026/rulesets/<id> --jq '.rules'
```

Expected: enforcement is `active`; target is `branch`; and `.rules` contains `deletion`,
`non_fast_forward`, `required_linear_history`, `pull_request` with
`required_approving_review_count: 0`, and `required_status_checks` listing `ci-success`.

A read-back is not enough on its own — a ruleset can be active and still lock the
repository. Prove a solo pull request can merge:

```bash
git switch -c chore/verify-ruleset
git commit --allow-empty -m "chore: verify ruleset allows solo merge"
git push -u origin chore/verify-ruleset
gh pr create --fill --base main
gh pr view --json mergeable,mergeStateStatus
```

Expected: `mergeable: MERGEABLE`. If it reports `BLOCKED`, the approval rule is set
incorrectly — fix it before continuing, because every future pull request is affected.
Then clean up:

```bash
gh pr merge --squash --delete-branch
git switch main
git pull
```

If the GitHub API rejects any rule, do not assume it applied. Record what was actually
accepted here, with the read-back, and state honestly what could not be enforced.

## Enabling required approvals

**Do this only when a second contributor exists.** It is the final step of the
"Adding a teammate" procedure in [`../CONTRIBUTING.md`](../CONTRIBUTING.md), because a
second contributor is the first moment an eligible approver exists.

`gh api` replaces the ruleset body, not individual fields, so **read the current ruleset
first** and edit that document. Do not hand-write the whole thing again: rebuilding it from
memory is how a working rule gets silently dropped.

```bash
RULESET_ID=<id-from-the-read-back>

# 1. Read the current ruleset and inspect the pull_request rule.
gh api repos/andrewhmir/gengineer-pjdsc-2026/rulesets/$RULESET_ID > ruleset-current.json

# 2. Edit ruleset-current.json: in the pull_request rule, set
#       "required_approving_review_count": 1
#    Leave every other rule exactly as it is.

# 3. Update the ruleset.
gh api --method PUT repos/andrewhmir/gengineer-pjdsc-2026/rulesets/$RULESET_ID \
  --input ruleset-current.json

# 4. Read back and confirm the count is 1 and no rule was lost.
gh api repos/andrewhmir/gengineer-pjdsc-2026/rulesets/$RULESET_ID \
  --jq '.rules[] | select(.type == "pull_request") | .parameters.required_approving_review_count'
gh api repos/andrewhmir/gengineer-pjdsc-2026/rulesets/$RULESET_ID --jq '.rules[].type'

# 5. Prove it end to end: open a pull request with a second person available.
#    It must show REVIEW_REQUIRED (not BLOCKED), and become mergeable once approved.
```

Also consider, once there are two contributors, enabling **`require_code_owner_review: true`**
so that review requests route through `.github/CODEOWNERS` rather than by name.

If a teammate leaves and the team is back to one contributor, **lower the count back to 0**
in the same way, or `main` becomes unmergeable again.

## Setting labels

Labels are the issue triage vocabulary: one `lane:*` label plus any applicable `type:*`
and `priority:*` labels. Replace the colours if you like, but keep the names — they are
referenced by the issue templates.

```bash
REPO=repos/andrewhmir/gengineer-pjdsc-2026

for spec in \
  "lane:firmware|1d76db|CircuitPython sensor node" \
  "lane:data|0e8a16|Data acquisition, cleaning, and policy" \
  "lane:notebooks|5319e7|Analysis notebooks" \
  "lane:webapp|fbca04|Web application" \
  "lane:docs|0075ca|Documentation and governance" \
  "submission|c2e0c6|Slide deck, demo video, checklist" \
  "type:bug|d73a4a|Something is wrong" \
  "type:feature|a2eeef|New capability" \
  "type:task|bfd4f2|Work item" \
  "priority:high|b60205|Do this next" \
  "priority:medium|fbca04|Normal" \
  "priority:low|0e8a16|Nice to have" \
; do
  IFS='|' read -r name color description <<< "$spec"
  gh api --method POST "$REPO/labels" \
    -f name="$name" -f color="$color" -f description="$description"
done

gh api "$REPO/labels" --jq '.[].name'
```

The same commands from PowerShell, for a single label at a time (the loop above is
POSIX `bash` syntax):

```powershell
gh api --method POST repos/andrewhmir/gengineer-pjdsc-2026/labels `
  -f name="lane:firmware" -f color="1d76db" -f description="CircuitPython sensor node"
```

Adding a label that already exists returns a 422 validation error; in that case the label
is already correct and the loop can continue.

## Inviting a teammate

Three steps, and the third is what makes the event's citation promise true. The full
version, with the reasoning, is in
[`../CONTRIBUTING.md`](../CONTRIBUTING.md#adding-a-teammate).

```bash
gh api --method PUT repos/andrewhmir/gengineer-pjdsc-2026/collaborators/<handle> \
  -f permission=push
```

1. Invite them with the command above (or *Settings → Collaborators and teams → Add
   people*).
2. Add their handle to `.github/CODEOWNERS`.
3. Add them to the `authors` list in [`../CITATION.cff`](../CITATION.cff) — the event
   publishes qualifying repositories with proper citation to each contributing member.
4. Then, and only then, raise required approvals to 1 as described above.

## Reference

- GitHub REST API, repository rulesets:
  <https://docs.github.com/en/rest/repos/rules>
- GitHub Docs, available rules for rulesets:
  <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets>
- GitHub CLI manual: <https://cli.github.com/manual/>
- Repository ruleset design rationale:
  [`../specs/2026-10-10-repo-bootstrap-design.md`](../specs/2026-10-10-repo-bootstrap-design.md) §7.4

## What was actually applied

**Not yet recorded.** The remote repository does not exist as this document is written;
`origin` is unset and no ruleset has been created. This section is completed from the
read-backs above, immediately after the remote is created, with:

- the ruleset identifier and its rules as read back;
- the `gh run list` output proving `ci-success` reported before it was made required;
- confirmation that a solo pull request reported `mergeable: MERGEABLE`;
- anything the API rejected, and what was done about it instead.

Until this section is filled in, treat the commands above as the intended procedure rather
than as a description of the live repository. The verification step of the task that
creates the remote must not be marked complete on the strength of this document alone.

