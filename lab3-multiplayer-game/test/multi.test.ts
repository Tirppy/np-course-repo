import assert from 'node:assert';
import { Board } from '../src/board.js';

describe('concurrency and map tests', function() {

    this.timeout(5000);

    it('first-card waiter is woken and fails if card removed before it obtains control', async function() {
        const b = await Board.parseFromFile('boards/ab.txt');

        // p1 takes (0,0)
        const s1 = await b.flip('p1', 0, 0);
        assert(s1.includes('my A'));

        // p2 attempts to take the same first card; this should wait
        const p2flip = b.flip('p2', 0, 0).then(
            () => ({ ok: true }),
            (err) => ({ ok: false, err })
        );

        // p1 completes a matching pair with (0,2)
        await b.flip('p1', 0, 2);
        // p1 makes another move to finalize removal
        await b.flip('p1', 1, 0);

        const res = await p2flip;
        // Because p1 removed the card before p2 obtained control, p2's flip should fail
        assert.equal(res.ok, false, 'p2 flip should have failed after card removal');
    });

    it('map can run concurrently and completes without crashing', async function() {
        const b = await Board.parseFromFile('boards/ab.txt');

        // start a map that replaces 'A' -> 'Z' slowly
        const mapPromise = b.map('admin', async (card) => {
            // introduce a tiny async delay to allow interleaving
            await new Promise((r) => setTimeout(r, 5));
            return card === 'A' ? 'Z' : card;
        });

        // While map is in progress, do some flips that may interleave
        try {
            const f1 = b.flip('p1', 0, 0).catch(() => undefined);
            const f2 = b.flip('p2', 2, 2).catch(() => undefined);
            await Promise.all([f1, f2, mapPromise]);
        } catch (e) {
            // tests should not crash
            assert.fail(`concurrent map/flip threw: ${e}`);
        }
    });

});
