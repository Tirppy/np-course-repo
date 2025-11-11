/* Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
 * Redistribution of original or derived work requires permission of course staff.
 */

import assert from 'node:assert';
import fs from 'node:fs';

/**
 * Memory Scramble board ADT.
 *
 * Specification (high level):
 * - Function signature: class `Board` is a mutable object representing a
 *   Memory Scramble board. Clients interact with it via the async methods
 *   `look`, `flip`, `map`, and `watch`. A new board is created via
 *   `Board.parseFromFile(filename)` or the constructor.
 *
 * - Representation: the board has a fixed number of rows and columns. Each
 *   position either contains a non-empty string label for a card, or is
 *   empty (removed). Each position also has a boolean `faceUp` flag and an
 *   optional `controlledBy` playerId indicating temporary control during a
 *   player's move.
 *
 * - Threading / concurrency model: public async methods may be called
 *   concurrently by multiple clients. The `Board` enforces the PS4-style
 *   concurrency rules: first-card flips that conflict with a different
 *   player's control wait (via an internal waiter queue), second-card
 *   flips that conflict fail immediately as specified, finalization of a
 *   player's previous two-card attempt happens before the next flip by
 *   that player, and `map` operations provide pairwise consistency.
 *
 * - Safety / nulls: input parameters are required to be non-null and of the
 *   types in the TypeScript signatures; `null` is used internally only to
 *   represent removed cards and is never returned to clients in API
 *   objects (clients receive string state snapshots only).
 */
export class Board {

    // rows and columns
    private readonly rows: number;
    private readonly columns: number;

    // cards[r][c] is the label of the card at (r,c), or null if empty (removed)
    private readonly cards: Array<Array<string|null>>;

    // faceUp[r][c] is true when the card at (r,c) is face up
    private readonly faceUp: Array<Array<boolean>>;

    // controlledBy[r][c] is the playerId who currently controls that card, or null
    private readonly controlledBy: Array<Array<string|null>>;

    // per-player state: which positions the player currently controls (0,1, or 2)
    private readonly players: Map<string, { controlled: Array<[number, number]> }> = new Map();
    // per-card waiter queues (for first-card flips that must wait for control)
    // Each waiter records the Deferred and the playerId that is waiting so
    // ownership can be reserved atomically when woken.
    private readonly waiters: Array<Array<Array<{ deferred: Deferred<void>; pid: string }>>> = [];

    // watchers waiting for the next board change
    private readonly watchers: Array<Deferred<void>> = [];

    // simple mutex to serialize critical sections
    private readonly lock: AsyncLock = new AsyncLock();

    // Abstraction function:
    // Abstraction function:
    //   AF(rows,columns,cards,faceUp,controlledBy,players,waiters,watchers,lock) =
    //     a Memory Scramble board with `rows` rows and `columns` columns where
    //     `cards[r][c]` is either a string label for a card at position (r,c) or
    //     null to indicate the card has been removed. `faceUp[r][c]` indicates if
    //     the card is currently face up. `controlledBy[r][c]` is either null or
    //     the playerId string of the player who currently controls that card.
    //     `players` maps playerId to the list of positions that player currently
    //     controls (length 0,1, or 2). `waiters[r][c]` contains deferreds for
    //     pending first-card flips that must wait until the card becomes
    //     available. `watchers` are deferreds waiting for the next board change.

    // Representation invariant (RI):
    //   - rows and columns are non-negative integers.
    //   - cards, faceUp, controlledBy, and waiters are 2D arrays with dimensions
    //     [rows][columns].
    //   - For all r in [0,rows), c in [0,columns):
    //       * cards[r][c] is either null or a nonempty string.
    //       * faceUp[r][c] is a boolean.
    //       * controlledBy[r][c] is either null or a nonempty string.
    //       * if cards[r][c] === null, then faceUp[r][c] === false and
    //         controlledBy[r][c] === null.
    //   - waiters[r][c] is an (possibly-empty) Array of Deferred<void>.
    //   - watchers is an Array of Deferred<void>.
    //   - players is a Map from nonempty playerId string -> { controlled: Array<[r,c]> }
    //       * For each playerId -> state in players:
    //           - state.controlled.length is 0, 1, or 2.
    //           - each entry [r,c] refers to a valid position and controlledBy[r][c] === playerId
    //   - No player controls more than two positions.

    // Abstraction function (AF):
    //   AF(rows,columns,cards,faceUp,controlledBy,players,...) = the abstract
    //   Memory Scramble board with the given dimensions where a position (r,c)
    //   either contains a card labeled cards[r][c] (if not null) or is empty
    //   (if cards[r][c] === null); faceUp/controlledBy indicate visibility and
    //   current control, and players maps playerIds to the positions they
    //   currently control (0..2 positions).

    // Safety-from-rep-exposure argument (SRE):
    //   - All rep fields are private. No method returns references to internal
    //     arrays or objects.
    //   - Observers (look(), watch(), map(), flip()) only return strings
    //     constructed from the rep (immutable JS strings) and therefore do
    //     not expose internal mutable arrays or objects.
    //   - The Deferred objects kept in waiters/watchers are created internally
    //     (via makeDeferred) and never returned to clients; clients only await
    //     operations that resolve those deferreds, so the deferreds do not
    //     leak references to the rep.
    //   - When cards are replaced in map(), replacements are computed first and
    //     applied under the lock so observers never receive inconsistent
    //     intermediate rep references.

    /**
     * Construct a Board with the given dimensions and optional initial card labels.
     *
     * @param rows number of rows in the board; requires rows to be an integer >= 0
     * @param columns number of columns in the board; requires columns to be an integer >= 0
     * @param initialCards optional flat array of card labels in row-major order;
     *        if provided, its length must equal rows*columns and every element
     *        must be a non-empty string. Use `null` values are not allowed in
     *        initialCards (removed cards are represented internally as `null`).
     *
     * @effects constructs a new Board instance whose abstraction corresponds to
     *          an empty board of the given size or with the provided card labels.
     * @throws Error if `initialCards` is supplied and its length does not match
     *         the requested dimensions.
     */
    public constructor(rows = 0, columns = 0, initialCards?: string[]) {
        this.rows = rows;
        this.columns = columns;
        this.cards = [];
        this.faceUp = [];
        this.controlledBy = [];

        for (let r = 0; r < rows; ++r) {
            this.cards.push(new Array<string|null>(columns).fill(null));
            this.faceUp.push(new Array<boolean>(columns).fill(false));
            this.controlledBy.push(new Array<string|null>(columns).fill(null));
            this.waiters.push(Array.from({ length: columns }, () => [] as { deferred: Deferred<void>; pid: string }[]));
        }

        if (initialCards) {
            if (initialCards.length !== rows * columns) {
                throw new Error('initialCards length does not match dimensions');
            }
            for (let r = 0; r < rows; ++r) {
                for (let c = 0; c < columns; ++c) {
                    const v = initialCards[r * columns + c]!;
                    this.cards[r]![c] = v;
                }
            }
        }
        this.checkRep();
    }

    private checkRep(): void {
        // basic numeric invariants
        assert(Number.isInteger(this.rows) && this.rows >= 0);
        assert(Number.isInteger(this.columns) && this.columns >= 0);

        // matrix dimension invariants
        assert(this.cards.length === this.rows);
        assert(this.faceUp.length === this.rows);
        assert(this.controlledBy.length === this.rows);
        assert(this.waiters.length === this.rows);
        for (let r = 0; r < this.rows; ++r) {
            assert(this.cards[r]!.length === this.columns);
            assert(this.faceUp[r]!.length === this.columns);
            assert(this.controlledBy[r]!.length === this.columns);
            assert(this.waiters[r]!.length === this.columns);
            for (let c = 0; c < this.columns; ++c) {
                const card = this.cards[r]![c];
                // card is either null or nonempty string
                assert(card === null || (typeof card === 'string' && card.length > 0));
                // faceUp is boolean
                assert(typeof this.faceUp[r]![c] === 'boolean');
                // controlledBy is either null or nonempty string
                const owner = this.controlledBy[r]![c];
                assert(owner === null || (typeof owner === 'string' && owner.length > 0));
                // if card is null then it cannot be face up or controlled
                if (card === null) {
                    assert(this.faceUp[r]![c] === false);
                    assert(this.controlledBy[r]![c] === null);
                }
                // waiters entry must be an array
                assert(Array.isArray(this.waiters[r]![c]!));
            }
        }

        // watchers should be an array (elements are Deferreds created internally)
        assert(Array.isArray(this.watchers));

        // players map consistency
        for (const [pid, state] of this.players.entries()) {
            // keys must be nonempty strings
            assert(typeof pid === 'string' && pid.length > 0);
            assert(state && Array.isArray(state.controlled));
            // controlled length is 0..2
            assert(state.controlled.length >= 0 && state.controlled.length <= 2);
            for (const p of state.controlled) {
                assert(Array.isArray(p) && p.length === 2);
                const r = p[0]!, c = p[1]!;
                // positions must be within bounds
                assert(Number.isInteger(r) && Number.isInteger(c));
                assert(r >= 0 && r < this.rows && c >= 0 && c < this.columns);
                // The players map records positions that the player either
                // currently controls (controlledBy[r][c] === pid) or that
                // were involved in the player's most recent move and are
                // awaiting finalization. While awaiting finalization the
                // control slot may have been transferred to another waiter
                // or left null; therefore we accept any case where the card
                // still exists and is face-up, or where the player still
                // retains control.
                const owner = this.controlledBy[r]![c];
                assert(owner === pid || (this.cards[r]![c] !== null && this.faceUp[r]![c] === true));
            }
        }
    }

    /**
     * Return the board state string from playerId's perspective.
     *
     * @param playerId non-empty player identifier (precondition: non-empty string)
     * @returns a textual snapshot of the board state from `playerId`'s
     *          perspective formatted according to the PS4 handout. The
     *          returned string is a fresh immutable string and does not expose
     *          internal data structures.
     * @effects observational only (does not mutate the board)
     */
    public async look(playerId: string): Promise<string> {
        // reading the board does not require the lock because we never mutate here,
        // but to ensure a consistent snapshot we take the lock briefly.
        return this.lock.run(async () => {
            this.checkRep();
            const lines: string[] = [];
            lines.push(`${this.rows}x${this.columns}`);
            for (let r = 0; r < this.rows; ++r) {
                for (let c = 0; c < this.columns; ++c) {
                    const card = this.cards[r]![c];
                    if (card === null) {
                        lines.push('none');
                    } else if (!this.faceUp[r]![c]) {
                        lines.push('down');
                    } else {
                        const owner = this.controlledBy[r]![c];
                        if (owner === playerId) {
                            lines.push(`my ${card}`);
                        } else {
                            lines.push(`up ${card}`);
                        }
                    }
                }
            }
            return lines.join('\n') + '\n';
        });
    }

    /**
     * Attempt to flip the card at (row,column) on behalf of playerId.
     *
     * Preconditions (requires):
     *  - `playerId` is a non-empty string identifying the player.
     *  - `row` and `column` are integers with 0 <= row < rows and 0 <= column < columns.
     *
     * Effects / postconditions:
     *  - If this is a legal flip that completes without waiting, the board is
     *    updated according to the PS4 handout rules (control acquisition,
     *    face-up state, possible removal on match) and the returned string is
     *    the new board snapshot from `playerId`'s perspective.
     *  - If the flip is a "first-card" flip but the card is currently
     *    controlled by another player, the operation waits (promise does not
     *    settle) until it either acquires control or the waiter is rejected.
     *  - If the flip fails according to the handout rules (for example no card
     *    at location, target controlled for a second-card attempt), the returned
     *    promise is rejected with an Error describing the failure.
     *
     * @param playerId player performing the flip
     * @param row row index of the target card
     * @param column column index of the target card
     * @returns a promise that fulfills to the board snapshot string for
     *          `playerId` after the flip completes
     * @throws Error (promise rejection) if the coordinates are invalid or the
     *         flip fails immediately as specified in the handout.
     */
    public async flip(playerId: string, row: number, column: number): Promise<string> {
        // Overall strategy: acquire lock around checks and state updates. For first-card
        // flips where card is controlled by another, enqueue a waiter and await release.
        if (!this.players.has(playerId)) {
            this.players.set(playerId, { controlled: [] });
        }

        // bounds check
        if (row < 0 || row >= this.rows || column < 0 || column >= this.columns) {
            throw new Error('invalid coordinates');
        }

        // finish previous play before attempting new flip (rule 3)
        await this.lock.run(async () => {
            await this.finishPreviousForPlayer_locked(playerId);
        });

        // Try to perform the flip, but if waiting is required for first-card, wait.
        while (true) {
            // fast check under lock
            const result = await this.lock.run(async () => {
                this.checkRep();
                const card = this.cards[row]![column];
                const playerState = this.players.get(playerId)!;
                const owner = this.controlledBy[row]![column];

                if (playerState.controlled.length === 0) {
                    // first card
                    if (card === null) {
                        return { kind: 'fail', reason: 'no card at location' } as const;
                    }
                        if (owner && owner !== playerId) {
                            // must wait: enqueue a waiter (record pid so we can reserve
                            // ownership when we wake them)
                            const d = makeDeferred<void>();
                            if (process.env['DEBUG_BOARD']) console.log(`enqueue waiter for (${row},${column}) pid=${playerId}`);
                            this.waiters[row]![column]!.push({ deferred: d, pid: playerId });
                            return { kind: 'wait', deferred: d } as const;
                        }
                    // take control and turn face up if needed
                    this.faceUp[row]![column] = true;
                    this.controlledBy[row]![column] = playerId;
                    if (process.env['DEBUG_BOARD']) console.log(`acquired first (${row},${column}) pid=${playerId}`);
                    playerState.controlled.push([row, column]);
                    // notify watchers: face up occurred
                    this.notifyWatchers_locked();
                    return { kind: 'ok' } as const;
                } else if (playerState.controlled.length === 1) {
                    // second card attempt
                    // if there is no card -> fail; relinquish control of first but leave face up for now
                    const [r0, c0] = playerState.controlled[0]!;
                    if (card === null) {
                        // relinquish control of first (leave face up)
                        this.controlledBy[r0]![c0] = null;
                        // keep record of the player's previous controlled card so finishPrevious can finalize it
                        playerState.controlled = [[r0, c0]];
                        // DO NOT wake waiters here: defer wake until finishPreviousForPlayer_locked
                        return { kind: 'fail', reason: 'no card at location' } as const;
                    }
                    // 2-B: if target is face up and controlled by a player -> fail without waiting
                    if (this.faceUp[row]![column] && this.controlledBy[row]![column]) {
                        // relinquish control of first (leave face up) and record it for finalization
                        this.controlledBy[r0]![c0] = null;
                        playerState.controlled = [[r0, c0]];
                        // DO NOT wake waiters here: defer wake until finishPreviousForPlayer_locked
                        return { kind: 'fail', reason: 'target controlled by a player' } as const;
                    }
                    // otherwise, flip face up if needed and take control
                    if (!this.faceUp[row]![column]) {
                        this.faceUp[row]![column] = true;
                    }
                    this.controlledBy[row]![column] = playerId;
                    if (process.env['DEBUG_BOARD']) console.log(`acquired second (${row},${column}) pid=${playerId}`);
                    // check match
                    const [r00, c00] = playerState.controlled[0]!;
                    const label0 = this.cards[r00]![c00];
                    const label1 = this.cards[row]![column];
                    if (label0 !== null && label1 !== null && label0 === label1) {
                        // successful match: keep control of both for finalization
                        playerState.controlled.push([row, column]);
                        this.notifyWatchers_locked();
                        return { kind: 'ok' } as const;
                    } else {
                        // mismatch: relinquish control of both but leave face up for now
                        // ensure both positions are recorded for finalization on next move
                        this.controlledBy[r00]![c00] = null;
                        this.controlledBy[row]![column] = null;
                        playerState.controlled = [[r00, c00], [row, column]];
                        // notify watchers that both cards are face up now
                        this.notifyWatchers_locked();
                        // wake waiter for the FIRST card immediately so ownership transfers now
                        this.wakeNextWaiter_locked(r00, c00);
                        // DO NOT wake waiter for the second card here; finalization will handle it
                        return { kind: 'ok' } as const;
                    }
                } else {
                    // should not happen: player had 2 controlled cards; finish previous
                    return { kind: 'retry' } as const;
                }
            });

            if (result.kind === 'ok') {
                return this.look(playerId);
            } else if (result.kind === 'fail') {
                throw new Error(result.reason);
            } else if (result.kind === 'wait') {
                // wait until deferred resolves, then retry
                try {
                    await result.deferred.promise;
                } catch (e) {
                    // if deferred was rejected, consider it a failure
                    throw e;
                }
                // loop to retry
            } else if (result.kind === 'retry') {
                // small pause to avoid tight loop
                await Promise.resolve();
            }
        }
    }

    // locked version: must be called while holding the lock or from within lock.run
    private async finishPreviousForPlayer_locked(playerId: string): Promise<void> {
        const state = this.players.get(playerId);
        if (!state) return;
        if (state.controlled.length === 2) {
            const p1 = state.controlled[0]!;
            const p2 = state.controlled[1]!;
            const r1 = p1[0], c1 = p1[1];
            const r2 = p2[0], c2 = p2[1];
            const lab1 = this.cards[r1]![c1];
            const lab2 = this.cards[r2]![c2];
            if (lab1 !== null && lab2 !== null && lab1 === lab2) {
                // remove them from the board
                this.cards[r1]![c1] = null;
                this.cards[r2]![c2] = null;
                this.faceUp[r1]![c1] = false;
                this.faceUp[r2]![c2] = false;
                this.controlledBy[r1]![c1] = null;
                this.controlledBy[r2]![c2] = null;
                state.controlled = [];
                // ensure no other player's recorded controlled lists reference
                // these removed positions (they are no longer valid)
                this.removePositionFromAllPlayers_locked(r1, c1);
                this.removePositionFromAllPlayers_locked(r2, c2);
                // removals are changes
                this.notifyWatchers_locked();
                // wake waiters for those locations
                this.wakeNextWaiter_locked(r1, c1);
                this.wakeNextWaiter_locked(r2, c2);
                return;
            } else {
                // relinquish control for positions this player still owns; cards remain face up for now
                for (const p of state.controlled) {
                    const r = p[0], c = p[1];
                    if (this.cards[r]![c] !== null && this.controlledBy[r]![c] === playerId) {
                        this.controlledBy[r]![c] = null;
                    }
                }
                state.controlled = [];
                // now for each of those cards, if still on board, faceUp, and not controlled -> turn face down
                let changed = false;
                for (const pair of [[r1, c1], [r2, c2]] as Array<[number, number]>) {
                    const r = pair[0], c = pair[1];
                    if (this.cards[r]![c] !== null && this.faceUp[r]![c] && this.controlledBy[r]![c] === null) {
                        this.faceUp[r]![c] = false;
                        // remove any stale references in other players' controlled lists
                        this.removePositionFromAllPlayers_locked(r, c);
                        changed = true;
                    }
                }
                if (changed) this.notifyWatchers_locked();
                // wake waiters for those locations
                this.wakeNextWaiter_locked(r1, c1);
                this.wakeNextWaiter_locked(r2, c2);
            }
        } else if (state.controlled.length === 1) {
            // finalize a single previously-controlled card only if control has already been relinquished
            const p = state.controlled[0]!;
            const r = p[0], c = p[1];
            // only finalize if the card is no longer controlled by the player
            if (this.cards[r]![c] !== null && this.controlledBy[r]![c] === null) {
                // state.controlled records the previously-controlled card(s); clear and flip down if appropriate
                state.controlled = [];
                if (this.faceUp[r]![c]) {
                    this.faceUp[r]![c] = false;
                    // remove any stale references in other players' controlled lists
                    this.removePositionFromAllPlayers_locked(r, c);
                    this.notifyWatchers_locked();
                }
                this.wakeNextWaiter_locked(r, c);
            }
        }
    }

    // Remove the position (r,c) from all players' controlled lists while
    // holding the lock. This prevents players from holding stale references
    // to positions that were turned face-down or removed.
    private removePositionFromAllPlayers_locked(r: number, c: number): void {
        for (const [_pid, state] of this.players.entries()) {
            state.controlled = state.controlled.filter((pp) => !(pp[0] === r && pp[1] === c));
        }
    }

    // notify watchers (safe to call outside lock)
    private notifyWatchers(): void {
        // schedule under lock so we drain the watchers atomically
        void this.lock.run(async () => this.notifyWatchers_locked());
    }

    // notify watchers while holding the lock
    private notifyWatchers_locked(): void {
        while (this.watchers.length > 0) {
            const d = this.watchers.shift()!;
            d.resolve();
        }
    }

    // wake next waiter while holding lock
    private wakeNextWaiter_locked(r: number, c: number): void {
        const q = this.waiters[r]![c]!;
        if (q && q.length > 0) {
            // choose one waiter at random to acquire ownership; leave others waiting
            const idx = Math.floor(Math.random() * q.length);
            const item = q.splice(idx, 1)[0]!;
            if (process.env['DEBUG_BOARD']) console.log(`waking waiter for (${r},${c}); remaining queue=${q.length} pid=${item.pid}`);
            // If the card has been removed in the meantime, resolving the
            // waiter will cause the waiting flip to re-check and fail with
            // "no card at location" as expected. In this case we must NOT
            // reserve ownership or set faceUp, which would violate the rep.
            if (this.cards[r]![c] === null) {
                if (process.env['DEBUG_BOARD']) console.log(`woken waiter for removed card (${r},${c}) pid=${item.pid}`);
                item.deferred.resolve();
            } else {
                // Reserve ownership for the chosen waiter before resolving its deferred
                // to avoid races where another waiter or finalization interleaves.
                this.faceUp[r]![c] = true;
                this.controlledBy[r]![c] = item.pid;
                // Notify watchers that the card became face-up / ownership changed
                this.notifyWatchers_locked();
                item.deferred.resolve();
            }
        }
    }

    // wake next waiter (safe to call outside lock)
    private wakeNextWaiter(r: number, c: number): void {
        void this.lock.run(async () => this.wakeNextWaiter_locked(r, c));
    }

    /**
     * Replace every existing card label `c` with `await f(c)` and return the
     * board snapshot for `playerId` after the replacements.
     *
     * Preconditions:
     *  - `playerId` is a non-empty string.
     *  - `f` is a pure mathematical function on card labels: for the same
     *    input `c` it must always return the same result and must not mutate
     *    shared state in a way that violates pairwise consistency.
     *
     * Effects / postconditions:
     *  - All card replacements are computed first and then applied atomically
     *    under the board lock so observers never see a partially-applied map.
     *  - The returned string is a snapshot from `playerId`'s perspective after
     *    the replacements. If `f` rejects for some card, that rejection
     *    propagates and the map operation is rejected.
     *
     * @param playerId id of the player invoking the map
     * @param f async mapping from old card label to new card label (called only
     *          for positions that currently contain a card)
     * @returns a promise fulfilled with the board snapshot for `playerId` after
     *          the mapping completes
     */
    public async map(playerId: string, f: (card: string) => Promise<string>): Promise<string> {
        // To ensure pairwise consistency, compute all replacements first,
        // then apply them atomically under the lock.
        const replacements: Array<{ r: number; c: number; newCard: string } > = [];
        for (let r = 0; r < this.rows; ++r) {
            for (let c = 0; c < this.columns; ++c) {
                const card = this.cards[r]![c];
                if (card != null) {
                    const newCard = await f(card);
                    replacements.push({ r, c, newCard });
                }
            }
        }

        await this.lock.run(async () => {
            for (const rep of replacements) {
                this.cards[rep.r]![rep.c] = rep.newCard;
            }
            // replacing cards is a change
            this.notifyWatchers_locked();
        });
        return this.look(playerId);
    }

    /**
     * Suspend until the next observable board change and then return the
     * board snapshot from `playerId`'s perspective.
     *
     * Preconditions: `playerId` is a non-empty string.
     * Effects: waits (suspends) until a change occurs (card faceUp toggles,
     * removal, or label change), then returns the new snapshot. The current
     * simplified implementation enqueues a waiter and resolves on the next
     * change; clients should expect the returned value to reflect the state
     * after that change.
     *
     * @param playerId id of the player waiting for the next change
     * @returns a promise fulfilled with the board snapshot after the next change
     */
    public async watch(playerId: string): Promise<string> {
        // Create a deferred and wait until a change occurs, then return the new state
        const d = makeDeferred<void>();
        await this.lock.run(async () => {
            this.watchers.push(d);
        });
        await d.promise;
        return this.look(playerId);
    }

    /**
     * Make a new board by parsing a file.
     * 
     * PS4 instructions: the specification of this method may not be changed.
     * 
     * @param filename path to game board file
     * @returns a new board with the size and cards from the file
     * @throws Error if the file cannot be read or is not a valid game board
     */
    public static async parseFromFile(filename: string): Promise<Board> {
        const text = (await fs.promises.readFile(filename)).toString();
    // Split on line breaks and ignore blank/whitespace-only lines so trailing
    // newlines in board files don't create extra empty card lines.
    const lines = text.split(/\r?\n/).filter((l: string) => l.trim().length > 0);
        if (lines.length === 0) {
            throw new Error('empty board file');
        }
    const first = lines[0]!.trim();
    const match = first.match(/^(\d+)x(\d+)$/);
    if (!match) throw new Error('invalid board header');
    const rows = parseInt(match[1]!, 10);
    const cols = parseInt(match[2]!, 10);
        const cardLines = lines.slice(1);
        if (cardLines.length !== rows * cols) {
            throw new Error('wrong number of card lines');
        }
    const cards = cardLines.map((l: string) => l.trim());
        return new Board(rows, cols, cards);
    }
}

/* Helper types and classes for concurrency primitives */

interface Deferred<T> {
    promise: Promise<T>;
    resolve: (value: T) => void;
    reject: (reason?: any) => void;
}

function makeDeferred<T>(): Deferred<T> {
    let resolve!: (value: T) => void;
    let reject!: (reason?: any) => void;
    const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
}

// Deferred and AsyncLock ADT documentation and invariants
// Deferred<T> (the small promise wrapper) RI/SRE:
//  - RI: `promise` is a Promise<T>, and `resolve`/`reject` are functions that
//    settle that promise. Deferreds are created internally by makeDeferred()
//    and are not part of the public API; they therefore do not need defensive
//    copies.
//  - SRE: Deferred objects are never returned to clients by any Board method;
//    they are only stored in private waiters/watchers arrays and used to
//    coordinate internal asynchronous control flow.

class AsyncLock {
    // Rep invariant:
    //  - queue is an Array of zero-argument functions to be invoked when the
    //    lock becomes available.
    //  - locked is a boolean indicating whether the lock is held.
    //  - queue elements are internal callbacks and are never exposed.
    // Safety-from-rep-exposure:
    //  - Both fields are private and no method returns them; the AsyncLock
    //    interface only exposes run(), which accepts a function to execute under
    //    the lock. The lock's internals are not shared with callers.
    private queue: Array<() => void> = [];
    private locked = false;

    public async run<T>(f: () => Promise<T>): Promise<T> {
        /**
         * Execute the async function `f` while holding the lock.
         *
         * Preconditions: none beyond proper typing of `f`.
         * Effects: `f` is executed with mutual exclusion relative to other
         * callers of `run`. The lock is acquired before `f` starts and
         * released after `f` completes or throws/rejects. Any rejection from
         * `f` propagates out of `run`.
         *
         * @param f async function to execute under the lock
         * @returns the result of `f()` or a rejected promise if `f` rejects
         */
        this.checkRep();
        await this.acquire();
        try {
            return await f();
        } finally {
            this.release();
        }
    }

    private acquire(): Promise<void> {
        this.checkRep();
        if (!this.locked) {
            this.locked = true;
            return Promise.resolve();
        }
        const d = makeDeferred<void>();
        this.queue.push(() => d.resolve());
        return d.promise;
    }

    private release(): void {
        const next = this.queue.shift();
        if (next) {
            next();
        } else {
            this.locked = false;
        }
        this.checkRep();
    }

    private checkRep(): void {
        assert(Array.isArray(this.queue));
        assert(typeof this.locked === 'boolean');
    }
}

// Methods to wake waiters and notify watchers
/* eslint-disable-next-line @typescript-eslint/no-unused-vars */
function _dummy() {}

// Add helper methods to Board prototype via declaration merging is messy here; instead,
// implement these functions as closures that will be bound to `this` via call in methods above.

