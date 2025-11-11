/* Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
 * Redistribution of original or derived work requires permission of course staff.
 */

import assert from 'node:assert';
import fs from 'node:fs';
import { Board } from './board.js';
import './promise-resolvers.js';

/**
 * Example code for simulating a game.
 * 
 * PS4 instructions: you may use, modify, or remove this file,
 *   completing it is recommended but not required.
 * 
 * @throws Error if an error occurs reading or parsing the board
 */
async function simulationMain(): Promise<void> {
    const filename = 'boards/ab.txt';
    const board: Board = await Board.parseFromFile(filename);
    // allow overrides via environment variables for easy experimentation
    const sizeFromBoard = (board as any).rows ?? 5;
    const size = process.env['SIZE'] ? Number(process.env['SIZE']) : sizeFromBoard;
    const players = process.env['PLAYERS'] ? Number(process.env['PLAYERS']) : 4;
    // number of moves per player (each move = one flip)
    const tries = process.env['TRIES'] ? Number(process.env['TRIES']) : 100;
    // delay range between flips (ms). Defaults set narrow and small for stress test
    const minDelayMilliseconds = process.env['MIN_DELAY'] ? Number(process.env['MIN_DELAY']) : 0.1;
    const maxDelayMilliseconds = process.env['MAX_DELAY'] ? Number(process.env['MAX_DELAY']) : 2;
    // enable verbose simulation logging when SIM_VERBOSE=1 or VERBOSE=1
    const verbose = process.env['SIM_VERBOSE'] === '1' || process.env['VERBOSE'] === '1';
    // compact per-move logging when SIM_COMPACT=1: prints one short line per flip
    const compact = process.env['SIM_COMPACT'] === '1';

    // quick indicator of logging mode
    if (compact) console.log('SIM_COMPACT=1 (compact per-move logging)');
    if (verbose) console.log('SIM_VERBOSE=1 (verbose logging)');
    // if compact, show a short legend and the set of labels on the board (helps explain 'A' and 'B')
    if (compact) {
        try {
            const snap = await board.look('admin');
            const labels = new Set<string>();
            for (const line of snap.split(/\r?\n/)) {
                const m = line.match(/^\s*(?:my|up)\s+(\S+)/);
                if (m && m[1]) labels.add(m[1]);
            }
            const labelsList = Array.from(labels).sort().join(', ');
            console.log('Legend: my X = your face-up card X; up X = someone else\'s face-up X; down = face-down; none = removed');
            if (labelsList.length > 0) console.log(`Card labels on this board: ${labelsList} (matching labels form pairs)`);
            else console.log('Card labels: (none detected)');
        } catch (e) {
            // ignore errors when computing legend
        }
    }

    // per-player statistics collected during the run
    const stats: Record<string, { attempts: number; successes: number; failures: number; removals: number; totalTimeMs: number }> = {};

    // start up one or more players as concurrent asynchronous function calls
    const playerPromises: Array<Promise<void>> = [];
    for (let ii = 0; ii < players; ++ii) {
        playerPromises.push(player(ii));
    }
    // wait for all the players to finish (unless one throws an exception)
    await Promise.all(playerPromises);

    /** @param playerNumber player to simulate */

    async function player(playerNumber: number): Promise<void> {
        // TODO set up this player on the board if necessary
        const playerId = `p${playerNumber}`;
        stats[playerId] = { attempts: 0, successes: 0, failures: 0, removals: 0, totalTimeMs: 0 };

        for (let jj = 0; jj < tries; ++jj) {
            try {
                // random delay between min and max
                await timeout(randomDelay(minDelayMilliseconds, maxDelayMilliseconds));
                // perform a single random flip (count as one move)
                const r1 = randomInt(size);
                const c1 = randomInt(size);
                const start = Date.now();
                stats[playerId].attempts++;
                try {
                    // perform flip and detect if the flip is waiting for control
                    const flipPromise = board.flip(playerId, r1, c1);
                    const waitDetectMs = process.env['SIM_WAIT_DETECT_MS'] ? Number(process.env['SIM_WAIT_DETECT_MS']) : 5;
                    // race flip against a short timeout to detect waiting
                    const race = await Promise.race([
                        flipPromise.then((s) => ({ state: 'done', snapshot: s } as const)),
                        timeout(waitDetectMs).then(() => ({ state: 'pending' } as const)),
                    ] as const);
                    if (race.state === 'pending') {
                        // indicate waiting; then await the actual flip result
                        console.log(`${playerId} flip=(${r1},${c1}): WAITING`);
                    }
                    const snap = race.state === 'done' ? race.snapshot : await flipPromise;
                    const dur = Date.now() - start;
                    stats[playerId].successes++;
                    stats[playerId].totalTimeMs += dur;
                    // compact mode: parse the returned snapshot and show the line for (r1,c1)
                    if (compact) {
                        const lines = snap.trim().split(/\r?\n/);
                        const header = lines[0] || '';
                        const hm = header.match(/^(\d+)x(\d+)$/);
                        const cols = hm ? Number(hm[2]) : size;
                        const idx = 1 + r1 * cols + c1;
                        const posLine = lines[idx] ?? '(unknown)';
                        console.log(`${playerId} flip=(${r1},${c1}): ${posLine}`);
                    } else if (verbose) {
                        console.log(`player=${playerId} flip=(${r1},${c1}) success duration=${dur}ms`);
                    }
                } catch (e) {
                    const dur = Date.now() - start;
                    stats[playerId].failures++;
                    stats[playerId].totalTimeMs += dur;
                    if (compact) {
                        console.log(`${playerId} flip=(${r1},${c1}): ERROR: ${(e && (e as Error).message) || e}`);
                    } else if (verbose) {
                        console.log(`player=${playerId} flip=(${r1},${c1}) failed duration=${dur}ms reason=${(e && (e as Error).message) || e}`);
                    }
                }
                // periodic progress from this player
                if (verbose && jj % Math.max(1, Math.floor(tries / 5)) === 0) {
                    const s = stats[playerId];
                    console.log(`progress player=${playerId} attempts=${s.attempts} succ=${s.successes} fail=${s.failures} removals=${s.removals}`);
                }
            } catch (err) {
                console.error('attempt to flip a card failed (unexpected):', err);
            }
        }
    }

    // wait for all players to finish and report
    await Promise.all(playerPromises).then(() => {
        console.log(`simulation finished: players=${players}, tries=${tries}`);
        if (verbose) {
            console.log('--- simulation summary ---');
            for (const [pid, s] of Object.entries(stats)) {
                console.log(`player=${pid} attempts=${s.attempts} successes=${s.successes} failures=${s.failures} removals=${s.removals} avgTime=${(s.totalTimeMs / Math.max(1, s.attempts)).toFixed(2)}ms`);
            }
            console.log('--------------------------');
        }
    }).catch((err) => {
        console.error('simulation encountered an error:', err);
    });
}

/**
 * Random positive integer generator
 * 
 * @param max a positive integer which is the upper bound of the generated number
 * @returns a random integer >= 0 and < max
 */
function randomInt(max: number): number {
    return Math.floor(Math.random() * max);
}

/**
 * Return a random floating-point delay between min (inclusive) and max (inclusive).
 *
 * @param min lower bound (inclusive). Precondition: min is a finite number and min <= max.
 * @param max upper bound (inclusive). Precondition: max is a finite number and max >= min.
 * @returns a number x such that min <= x <= max. Distribution is uniform on [min,max).
 */
function randomDelay(min: number, max: number): number {
    return min + Math.random() * (max - min);
}


/**
 * @param milliseconds duration to wait
 * @returns a promise that fulfills no less than `milliseconds` after timeout() was called
 */
async function timeout(milliseconds: number): Promise<void> {
    const { promise, resolve } = Promise.withResolvers<void>();
    setTimeout(resolve, milliseconds);
    return promise;
}

void simulationMain();
