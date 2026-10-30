# Map mode

For an effort too big and too foggy for one plan: the way from here to the
destination is not visible yet. Adapted from mattpocock/skills `wayfinder`
(MIT); the map lives in the brain, not on an issue tracker.

**Plan, don't build.** Each ticket resolves a decision. The map is done when
nothing is left to decide before the work can go through the normal chain, and
the pull to start building is the sign you have reached its edge.

## The map

`<brain>/idea/<slug>/<slug>.md` (or wherever the brain keeps pre-implementation
thinking). Its body is an index, never a store:

    ## Destination
    <what reaching the end looks like, one or two lines>

    ## Notes
    <agents to use, standing preferences>

    ## Decisions so far
    - <ticket>: <one-line gist> → <link to its chunk>

    ## Tickets
    - [ ] <name> · <type> · blocked by: <names, or none> — <the question>

    ## Not yet specified
    <questions you can tell are coming but cannot phrase sharply yet>

    ## Out of scope
    - <what was ruled out, and why>

| Ticket type | Resolved by |
| --- | --- |
| `research` | `scout` in research mode, with receipts, checked by `validator` |
| `prototype` | `designer` draws options, the human picks |
| `grilling` | you ask the human, in the grilling format |
| `decision` | `arbiter`, when the charter-to-be or the pack's policy already answers it |
| `task` | work that must happen before a decision can be made (access, a data sample) |

The **frontier** is the open, unblocked tickets. A question you can state
precisely is a ticket even if blocked; one you cannot is fog.

## Chart it (first session)

1. Name the destination with the human until it is one or two lines.
2. Fan out across the whole space, breadth first, for the open decisions and
   the first steps takeable now. No fog means no map: go to the charter.
3. Write the map and the tickets you can state, with their blocked-by edges.
4. Spawn `scout` for the research tickets (at most `limits.in_flight`).
5. Stop. Charting is one session.

## Work it (each later session)

1. Read the map only. Take the ticket the human names, or the first on the
   frontier.
2. Resolve it with its type's agent or with the human.
3. Write the answer as a chunk, remove its line from Tickets, add one line to
   Decisions so far.
4. Turn fog the answer made sharp into tickets; move what it ruled out to Out of
   scope.
5. Frontier empty and nothing left in Not yet specified: the map becomes the
   job's charter (its decisions become *Decided in advance*), and the chain
   takes it from the plan.
