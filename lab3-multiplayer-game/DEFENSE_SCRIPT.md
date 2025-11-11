# Defense Script — Memory Scramble Lab 3

Use this as your spoken/scripted notes while defending the lab. It's structured by the grading points. Each section contains: what to say, the important commands to run live, which files and lines to open and point at, and suggested short answers for likely questions.

---

## Quick startup (what to run before you begin)

1. Open a terminal (cmd) and compile:

```cmd
npx tsc --pretty
```

2. Run tests to show they pass:

```cmd
npm test
```

If you want to run the simulation (PowerShell recommended for env vars):

```powershell
$env:PLAYERS='4'; $env:TRIES='100'; $env:MIN_DELAY='0.1'; $env:MAX_DELAY='2'; npm run simulation
```

To start the server for a live demo on port 3000:

```cmd
npm start 3000 boards/ab.txt
```

(If you started the server with port `0`, inspect the console output for the chosen port.)

---

## Implementation (10 points) — The game works correctly according to all the rules

What to say:
- "The `Board` ADT implements the Memory Scramble rules: first-card flips can wait if the card is controlled by another player; second-card flips that are invalid fail immediately; successful matches remove both cards; finalization of prior moves is enforced before a player's next flip."
- Mention concurrency: "Public methods are async and may be called concurrently. I used an `AsyncLock` to serialize critical updates and structured waiter/watcher queues for waiting behavior." 

Commands to demonstrate:
- Open the board implementation in the editor and show the core flip path:
  - `src/board.ts` — search for `public async flip(` and `finishPreviousForPlayer_locked`
  - Point to the logic branches for first-card vs second-card and where waiters are enqueued: `this.waiters[row]![column]!.push(d)`
  - Point to where matching removes cards: in `finishPreviousForPlayer_locked` where `this.cards[r1]![c1] = null` happens.
- Run a short interactive trace: start server and use curl or the UI to flip two matching cards and show they are removed.

Code locations to highlight (open these files and lines):
- `src/board.ts`:
  - flip method: show beginning checks, waiter enqueue, taking control (faceUp, controlledBy), and match/mismatch handling.
  - `finishPreviousForPlayer_locked`: demonstrates finalization behavior (removal, face-down, wake waiters).
  - `wakeNextWaiter_locked`: shows how a waiter is resumed.
  - `checkRep()` at top/bottom of class: explains runtime assertions that validate invariants.
- `src/commands.ts`: show delegation to `Board` functions — this proves API surface alignment.

Key proof points to say:
- "Waiters are per-card; watchers are global for changes. This allows first-card waiting but immediate failure semantics for second-card flips." 
- Show `this.waiters` and `this.watchers` declarations.

Likely question and answer:
- Q: "What happens if two players try to take the same first card at the same time?"
  - A: "One will win the lock and acquire it; the other will, if the card is controlled, enqueue a Deferred in the waiters queue and await resolution. When the owner relinquishes, `wakeNextWaiter_locked` chooses a waiter and resolves it."

[Placeholder image: highlight of flip() branches and finishPreviousForPlayer_locked in `src/board.ts`]

---

## Unit tests (10 points) — Board ADT tests

What to say:
- "Unit tests are in `test/board.test.ts`. They follow the spec and exercise all important cases: successful match and removal, mismatch behavior, waiter handling, and the finalization steps. Tests are documented with inline comments describing the scenario."
- Show that tests are reproducible and passing.

Commands to run during defense:

```cmd
npm test
```

Files to open and point at:
- `test/board.test.ts`: point at test cases that show
  - First-card conflicts and waiter wakeups
  - Second-card immediate failure paths
  - Successful removal after match
  - checkRep-driven assertions (if tests create any negative tests)

What to show in the output:
- Mocha test summary: all tests passing. Show the terminal output after `npm test`.

Likely question and short answer:
- Q: "Do your tests rely on internal implementation details?"
  - A: "No. Tests are written to follow the specification (preconditions and effects) rather than implementation specifics. They assert the observable behavior (board snapshots and side effects)."

[Placeholder image: snippet of the test file with clear test comments and the mocha output showing all tests passed]

---

## Simulation (4 points) — multi-player stress run

What to say:
- "I wrote a simulation harness in `src/simulation.ts` to stress concurrency with multiple players. It is configurable through environment variables and was executed with the required parameters." 
- State the requirements and confirm you ran them: 4 players, delays between 0.1ms and 2ms, no shuffling, 100 moves each.

Command to run (PowerShell):

```powershell
$env:PLAYERS='4'; $env:TRIES='100'; $env:MIN_DELAY='0.1'; $env:MAX_DELAY='2'; npm run simulation
```

What to show:
- Console output showing `simulation finished: players=4, tries=100` and no crash traces.
- Explain that the simulation uses random choices; to make it deterministic we could add a seedable RNG.

Likely question and answer:
- Q: "Why are min delays sub-millisecond, and how reliable are they?"
  - A: "JS timers are millisecond-resolution in many environments; specifying 0.1 ms sets a small target; the simulation still produces tight interleavings. We noted this in the report and suggested a seedable RNG for reproducibility."

[Placeholder image: console output of the simulation finishing]

---

## Design and documentation (6 + 6 + 8 points)

### Module structure and `commands` module (6 points)

What to say:
- "`src/commands.ts` is a thin delegating module (required by the PS4 handout). It exports `look`, `flip`, `map`, and `watch` functions that simply call the same-named `Board` methods. This keeps the server and UI code decoupled from the board implementation and matches the required API."

Files to open:
- `src/commands.ts`: show the function signatures and one example where it delegates: `return board.flip(playerId, row, column);`

Command to show this in terminal (print a small snippet):

```cmd
sed -n "1,200p" src/commands.ts
```

(Or just open file in editor.)

Key talking points:
- Mention you preserved exact function names and signatures as required.
- Point out how `server.ts` imports these functions and uses them in HTTP endpoints.

[Placeholder image: `src/commands.ts` showing function declarations delegating to Board]

### Representation invariants & safety-from-rep-exposure (6 points)

What to say:
- "I documented an Abstraction Function (AF), a thorough Representation Invariant (RI), and a Safety-from-Rep-Exposure (SRE) argument for the Board ADT and its helpers. I enforced the RI at runtime using `checkRep()` which asserts matrix sizes, non-nullness constraints, players map consistency, and waiter/watcher shapes."

Files and lines to show:
- `src/board.ts` top of class — AF/RI/SRE comment block.
- `src/board.ts` `checkRep()` — show the assertions.
- `src/board.ts` `AsyncLock` comments and small `checkRep()` (private) that asserts internal queue and locked flag.

What to say about SRE:
- "All rep fields are private and not returned to clients. Methods produce string snapshots, not raw references. Deferred objects are internal and never returned."

Likely question and short answer:
- Q: "How would you detect a rep violation during tests?"
  - A: "`checkRep()` throws an AssertionError which will fail tests; we can add targeted negative tests that temporarily violate the rep to ensure `checkRep()` fires."

[Placeholder image: AF/RI/SRE comment block and checkRep() snippet]

### Specifications for every method (8 points)

What to say:
- "Following `References/Specifications.html`, I added TypeDoc-style JSDoc comments for every public function and method describing signature, `@param`, preconditions (`requires`), effects/postconditions (`@returns`/`@throws`). This makes the contract explicit for clients and for testing."

Files to show:
- `src/board.ts` constructor JSDoc, `look`, `flip`, `map`, `watch` JSDoc blocks.
- `src/simulation.ts` `randomDelay` JSDoc.
- `src/commands.ts` top-level comment that notes these functions are required and must not be changed.

Explain the motivation:
- TypeDoc-style specs act as the contract; tests and other modules respect the preconditions; exceptions or union return types are used when a function can legitimately return a special result. This aligns with the `Specifications.html` reading.

Likely question and short answer:
- Q: "Why use JSDoc comments instead of runtime checks everywhere?"
  - A: "TypeDoc comments document the pre/postconditions for clients and complement runtime `checkRep()` assertions; we use both where appropriate. Preconditions are documented and enforced where it's reasonable to do so."

[Placeholder image: multiple JSDoc blocks from `src/board.ts` and `src/simulation.ts`]

---

## Additional notes: References from the `References/` folder

Make sure to cite these during your defense when asked about methodology or expectations:
- `References/Specifications.html` — use to justify TypeDoc-style `@param/@returns` and preconditions/postconditions structure.
- `References/RepInvariants.html` — use to justify what to include in RI and SRE and how to argue safety from rep exposure.
- `References/look.html`, `flip.html`, `map.html`, `watch.html` — these are the PS4 handout pages that define the exact API semantics; reference them when explaining the required `commands` signatures and semantics.

When asked, show the precise wording in the handout for e.g. when flips should wait vs fail immediately.

[Placeholder image: small collage of the `References` HTML filenames or snippets showing relevant lines]

---

## Quick Q&A cheat-sheet (short bullets you can say)

- "Where do I enforce concurrency?" → `AsyncLock` serializes critical sections; waiter queues implement blocking semantics for first-card flips.
- "How do I prevent exposing internal state?" → methods return string snapshots; rep fields are private; Deferred objects are internal.
- "How do unit tests avoid implementation details?" → Tests only examine observable board snapshots (strings) and side effects as specified.
- "How do you ensure pairwise consistency during `map()`?" → Compute replacements first, then apply them under the lock so observers never see partial replacements.
- "How deterministic is the simulation?" → Not deterministic (Math.random used); for reproducible failure traces we can add a seedable RNG.

---

## Demo plan (order to present live)

1. Show the `References` pages that define the API and specifications (quickly, to establish the contract).
2. Show `src/commands.ts` to prove module shape is preserved.
3. Open `src/board.ts` and walk through: AF/RI/SRE, `checkRep()`, `flip()`, `finishPreviousForPlayer_locked()`, `wakeNextWaiter_locked()`.
4. Run `npm test` and show tests pass.
5. Run the simulation with the required env vars and show it completes without crashing.
6. Start the server and demonstrate a small manual interaction (flip a card from the UI or curl) and show observable board snapshots.
7. Answer questions using the Q&A cheat-sheet and point to code lines as needed.

---

If you want, I can also produce a condensed one-page slide (PDF) of these talking points or add inline line numbers/comments to the critical files to make in-person pointing easier.

Good luck with the defense — tell me which part you'd like me to expand into a slide or into actual screenshot images and I will add them to `DEFENSE_SCRIPT.md`. 
