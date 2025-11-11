import { Board } from './dist/src/board.js';

async function run() {
  const b = await Board.parseFromFile('boards/ab.txt');
  console.log('p1 flip 0,0');
  console.log(await b.flip('p1',0,0));
  console.log('internal after p1 first flip:', JSON.stringify({controlledBy:(b).controlledBy, players:Array.from((b).players.entries())}, null, 2));
  console.log('p2 attempts flip 0,0 (should wait)');
  const p2flip = b.flip('p2',0,0).then(()=>({ok:true}), (e)=>({ok:false,err:e}));
  // allow small delay
  await new Promise(r=>setTimeout(r,10));
  console.log('p1 flips 0,2');
  console.log(await b.flip('p1',0,2));
  console.log('internal after p1 second flip:', JSON.stringify({controlledBy:(b).controlledBy, players:Array.from((b).players.entries())}, null, 2));
  console.log('p1 flips 1,0 to finalize');
  console.log(await b.flip('p1',1,0));
  console.log('internal after p1 finalize:', JSON.stringify({controlledBy:(b).controlledBy, players:Array.from((b).players.entries())}, null, 2));
  const res = await p2flip;
  console.log('p2 result', res);
}
run().catch(e=>{console.error(e); process.exit(1)});
