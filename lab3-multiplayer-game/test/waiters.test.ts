import assert from 'node:assert';

/**
 * Tests for waiter queue behavior and finalization ownership semantics.
 * These tests exercise concurrency edge-cases described in the Memory Scramble
 * specification: when multiple players are waiting for the same card, only
 * one should obtain it immediately on a relinquish, and finalization must
 * not clear ownership if the card has been acquired by a waiter.
 */
describe('waiter queue and finalization tests', function() {
  this.timeout(5000);

  it('multiple waiters: only one acquires on mismatch and others remain waiting until finalization', async function() {
    const mod = await import('../src/board.js');
    const Board = mod.Board;
    // small 1x3 board: A B A so (0,0) and (0,2) are A
    const b: any = new Board(1, 3, ['A', 'B', 'A']);

    // p1 takes (0,0)
    await b.flip('p1', 0, 0);

    // p2 and p3 attempt to take same position and will wait
    const p2 = b.flip('p2', 0, 0).then(() => 'p2').catch(() => 'p2-err');
    const p3 = b.flip('p3', 0, 0).then(() => 'p3').catch(() => 'p3-err');

    // let them enqueue
    await new Promise((r) => setTimeout(r, 5));

    // p1 flips a different card and mismatches -> relinquish first card
    await b.flip('p1', 0, 1);

    // exactly one of p2 or p3 should resolve quickly (acquired ownership)
    const winner = await Promise.race([p2, p3, new Promise((r) => setTimeout(() => r('timeout'), 200))]);
    assert.ok(winner === 'p2' || winner === 'p3', 'expected one waiter to acquire ownership on mismatch');

    // the other waiter should still be waiting (not resolved immediately)
    const otherPromise = winner === 'p2' ? p3 : p2;
    const otherShort = await Promise.race([otherPromise.then(() => 'resolved'), new Promise((r) => setTimeout(() => r('timeout'), 50))]);
    assert.strictEqual(otherShort, 'timeout', 'the non-selected waiter should still be waiting before finalization');

    // trigger finalization by making another move as p1 (flip the remaining card)
    await b.flip('p1', 0, 2);

    // now the other waiter should eventually resolve (either success or error depending on timing)
    const otherFinal = await otherPromise.catch(() => 'err');
    assert.ok(otherFinal === 'p2' || otherFinal === 'p3' || otherFinal === 'p2-err' || otherFinal === 'p3-err');
  });

  it('finalization does not steal ownership from a waiter that acquired the card', async function() {
    const mod = await import('../src/board.js');
    const Board = mod.Board;
    // 1x3 board A B C
    const b: any = new Board(1, 3, ['A', 'B', 'C']);

    // p1 takes (0,0)
    await b.flip('p1', 0, 0);

    // p2 waits for (0,0)
    const p2 = b.flip('p2', 0, 0).then(() => 'p2').catch(() => 'p2-err');

    // let p2 enqueue
    await new Promise((r) => setTimeout(r, 5));

    // p1 flips a different card and mismatches -> relinquish (p2 should acquire)
    await b.flip('p1', 0, 1);

    // wait a bit for p2 to acquire
    await new Promise((r) => setTimeout(r, 5));

    // p1 makes another move to trigger finalization for p1
    await b.flip('p1', 0, 2);

    // ensure p2 actually completed and now controls (0,0)
    const who = (b as any).controlledBy[0][0];
    assert.ok(who === 'p2', `expected p2 to own the card after finalization, got ${who}`);
  });

});
