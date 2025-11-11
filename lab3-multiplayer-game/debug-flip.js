import { Board } from './dist/src/board.js';

async function run() {
  const b = await Board.parseFromFile('boards/ab.txt');
  console.log('initial look:\n' + await b.look('alice'));
  console.log('flip 0,0');
  console.log(await b.flip('alice',0,0));
  console.log('flip 0,2');
  console.log(await b.flip('alice',0,2));
  console.log('flip 1,0 to finalize');
  console.log(await b.flip('alice',1,0));
  console.log('after finalize look:\n' + await b.look('alice'));
}

run().catch(e=>{console.error(e); process.exit(1)});
