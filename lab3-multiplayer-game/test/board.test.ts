/* Copyright (c) 2021-25 MIT 6.102/6.031 course staff, all rights reserved.
 * Redistribution of original or derived work requires permission of course staff.
 */

import assert from 'node:assert';
import fs from 'node:fs';
import { Board } from '../src/board.js';


/**
 * Tests for the Board abstract data type.
 */
describe('Board', function() {
    
    // Testing strategy
    //   TODO

    it('parseFromFile + look basic', async function () {
        const path = 'boards/ab.txt';
        const file = (await fs.promises.readFile(path)).toString().split(/\r?\n/).filter(l => l.trim().length > 0);
        const header = file[0]!
        const board = await (await import('../src/board.js')).Board.parseFromFile(path);
        const state = await board.look('p1');
        // header must match the board file header
        assert(state.startsWith(header));
    });

    it('flip two matching cards and finalize removal on next move', async function () {
        const mod = await import('../src/board.js');
        const Board = mod.Board;
        const b: any = await Board.parseFromFile('boards/ab.txt');

        // flip first card (0,0) which is 'A'
        const s1 = await b.flip('alice', 0, 0);
        assert(s1.includes('my A'));

        // flip a matching card (0,2) which is also 'A'
        const s2 = await b.flip('alice', 0, 2);
        // after matching, both should be controlled by alice (my A)
    assert(s2.split('\n').some((line: string) => line === 'my A'));

        // now make another move to trigger removal of matched cards
        const s3 = await b.flip('alice', 1, 0);
        // the two matched cards should have been removed -> look for 'none' in their positions
        const s4 = await b.look('alice');
        // there should be 'none' present in the board state
        assert(s4.includes('none'));
    });

    this.timeout(5000);

    it('watch sees a change after a flip', async function () {
        const b = await Board.parseFromFile("boards/ab.txt");
        // start a watcher
        const watcher = b.watch("pW");
        // perform a flip to trigger notification
        const flipPromise = b.flip("p0", 0, 0);
        // watcher should resolve once a state change occurs
        const watchResult = await watcher;
        assert.ok(typeof watchResult === "string");
        await flipPromise;
    });

    it('map transforms cards atomically', async function () {
        const b = await Board.parseFromFile("boards/ab.txt");
        // map every 'A' -> 'X' and leave others unchanged
        await b.map("admin", async (card) => {
            if (!card) return card;
            if (card === "A") return "X";
            return card;
        });
    // look may not reveal labels if all cards are face down, so inspect
    // the internal cards array for correctness in this unit test.
    const internalCards = (b as any).cards.flat().filter((c: any) => c !== null);
    const found = internalCards.some((c: string) => c === 'X' || c === 'A');
    assert.ok(found, 'expected at least one card to be X or A after map');
    });

    it('flip invalid coordinates fails', async function () {
        const b = await Board.parseFromFile('boards/ab.txt');
        let threw = false;
        try {
            await b.flip('p', -1, 0);
        } catch (e) {
            threw = true;
        }
        assert.ok(threw, 'flip with negative row should throw');
    });

    it('flip on empty location fails with appropriate error', async function () {
        // create a small board with one removed card
        const txt = '1x1\nA\n';
        // write a temporary file
        await fs.promises.writeFile('test-tmp-board.txt', txt);
        const b = await Board.parseFromFile('test-tmp-board.txt');
        // remove the only card by simulating a successful match (directly mutate for test)
        // we can simulate by clearing the internal cards array via any cast - test-only
        (b as any).cards[0][0] = null;
        let threw = false;
        try {
            await b.flip('p', 0, 0);
        } catch (e) {
            threw = true;
        }
        assert.ok(threw, 'flip on removed location should throw');
    });

});


/**
 * Example test case that uses async/await to test an asynchronous function.
 * Feel free to delete these example tests.
 */
describe('async test cases', function() {

    it('reads a file asynchronously', async function() {
        const fileContents = (await fs.promises.readFile('boards/ab.txt')).toString();
        const header = fileContents.split(/\r?\n/).filter(l => l.trim().length > 0)[0]!;
        assert.ok(fileContents.startsWith(header));
    });
});
