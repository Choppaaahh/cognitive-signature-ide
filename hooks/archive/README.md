# Archived hooks

Hooks retired from active use but preserved for reference / future resurrection.

## `post-tool-use.sh.stub`

**Original intent (from file header):** live-signature-update — refresh signature JSON
visibly during a session when user edits a file via Write/Edit. Marked "Day 5 target"
during hackathon development.

**Why archived:** hackathon shipped at commit `0d6f64a` with the hook as a stub that
drained stdin and no-op'd. The post-hackathon audit graded it BEHAVIORAL_ONLY-acceptable
because the file honestly marked itself as a planned stub, but keeping unwired hooks in a
shipping plugin is dead weight that compiles into the distribution.

**When to resurrect:** if live-signature-refresh-during-session becomes a product
roadmap priority. At that point, restore to `../post-tool-use.sh`, implement the
Write/Edit detection + background re-extract logic, register in `hooks.json`.
