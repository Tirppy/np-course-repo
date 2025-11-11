#!/usr/bin/env node
// Simulation of the transcript scenario using the Board implementation
// Run with: node debug-transcript.js

import { fileURLToPath } from 'node:url';
const __filename = fileURLToPath(import.meta.url);
import path from 'node:path';

async function main() {
  const mod = await import('./dist/src/board.js');
  const Board = mod.Board;
  const board = await Board.parseFromFile('boards/transcript.txt');

  const A = 'Alice';
  const B = 'Bob';
  const C = 'Charlie';

  function printAll() {
    console.log('--- Board views ---');
    return Promise.all([
      board.look(A).then(s => console.log('Alice view:\n' + s)),
      board.look(B).then(s => console.log('Bob view:\n' + s)),
      board.look(C).then(s => console.log('Charlie view:\n' + s)),
    ]);
  }

  console.log('Initial');
  await printAll();

  console.log('\n1) Alice flips top-left (0,0)');
  await board.flip(A, 0, 0);
  await printAll();

  console.log('\n2) Bob and Charlie concurrently try to flip (0,0)');
  const bobFlip1 = board.flip(B, 0, 0).then(() => ({ who: 'Bob', ok: true })).catch(e => ({ who: 'Bob', ok: false, err: e.message }));
  const charlieFlip1 = board.flip(C, 0, 0).then(() => ({ who: 'Charlie', ok: true })).catch(e => ({ who: 'Charlie', ok: false, err: e.message }));

  // small delay to let them enqueue
  await new Promise(r => setTimeout(r, 20));
  await printAll();

  console.log('\n3) Alice flips bottom-right (2,2) -> mismatch');
  await board.flip(A, 2, 2);
  await printAll();

  // check who acquired (0,0)
  const winner = await Promise.race([bobFlip1, charlieFlip1, new Promise(r => setTimeout(() => r('none'), 200))]);
  console.log('After mismatch, waiter result (who acquired or timed out):', winner);
  await printAll();

  console.log('\n4) Alice flips center (1,1) as new first card');
  await board.flip(A, 1, 1);
  await printAll();

  console.log('\n5) Whoever acquired R (Bob or Charlie) flips top-right (0,2) to try match R');
  // attempt for Bob then Charlie
  try { await board.flip(B, 0, 2); console.log('Bob flipped 0,2'); } catch (e) { console.log('Bob failed to flip 0,2:', e.message); }
  try { await board.flip(C, 0, 2); console.log('Charlie flipped 0,2'); } catch (e) { console.log('Charlie failed to flip 0,2:', e.message); }
  await printAll();

  console.log('\n6) Bob flips new first card (1,0) to trigger finalization/removal if he had a match');
  try { await board.flip(B, 1, 0); } catch (e) { console.log('Bob flip failed:', e.message); }
  await printAll();

  console.log('\n7) If Charlie was waiting for (0,0), he may get a wake and then find it gone or be ready to flip a new card');
  // await any remaining waiter attempts' promises (they may reject with 'no card at location')
  try {
    const [bres, cres] = await Promise.all([bobFlip1, charlieFlip1].map(p => p.catch(e => ({ ok: false, err: e && e.message }))));
    ;
  } catch (e) {
    // ignore
  }
  await printAll();

  console.log('\nSimulation complete');
}

main().catch(e => { console.error(e); process.exit(1); });
