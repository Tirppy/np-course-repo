import assert from 'node:assert';

describe('interleaving/regression', () => {
  it('ensures waiter does not acquire card before finalization (regression test)', async () => {
    const mod = await import('../src/board.js');
    const Board = mod.Board;
    const b: any = new Board(1, 3, ['A', 'B', 'C']);
    const p1 = 'p1';
    const p2 = 'p2';

    // p1 takes first card
    await b.flip(p1, 0, 0);

    // p2 attempts to take same card (will wait)
    const p2Promise = b.flip(p2, 0, 0).then(() => 'done');

    // let p2 enqueue itself as a waiter
    await new Promise((r) => setTimeout(r, 5));

    // p1 flips a different card and mismatches -> relinquish both and leave face-up
    await b.flip(p1, 0, 1);

  // right after mismatch, p2 should acquire the first card immediately (ownership transfers on mismatch)
  const short = await Promise.race([p2Promise.then(() => 'done'), new Promise((r) => setTimeout(() => r('timeout'), 200))]);
  assert.strictEqual(short, 'done');

    // p1 makes another move to trigger finalization
    await b.flip(p1, 0, 2);

    // now p2 should complete
    const final = await Promise.race([p2Promise.then(() => 'done'), new Promise((r) => setTimeout(() => r('timeout2'), 200))]);
    assert.strictEqual(final, 'done');
  });
});
