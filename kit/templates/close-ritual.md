# Chunk-close ritual (minimal)

Run at every direction change: work landed, a decision locked, a durable
finding, a scope change.

1. Does it conflict with an invariant in the recipe? Stop and ask.
2. Write the chunk: `chunks/NN-<slug>.md` (next free number), frontmatter
   `chunk-type`, `title`, `created`, `status: active`. Lead with the conclusion
   in 1–3 sentences, then the reasoning; it must stand alone.
3. Add a one-liner to the parent file (`log.md` for events, `notes.md` for
   findings, `design.md` for decisions): `- [[chunks/NN-<slug>]] <one line>`.
4. If it replaces an earlier chunk: mark that one `status: superseded`,
   `superseded-by:`, and move its one-liner to `discarded.md`.
5. Refresh the recipe: Where I am now, Next step, Links, `updated:`.
6. Commit the brain.
