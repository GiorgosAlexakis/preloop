const directions = [ {x:-1,y:-1}, {x:1,y:-1}, {x:-1,y:1}, {x:1,y:1} ]
let np = { 'A': {x:-350, y:-350}, 'B': {x:350, y:-350} }
let items = ['C', 'D', 'A', 'B']

items.forEach((id, index) => {
  if (!np[id]) {
    const layer = Math.floor(index / 4);
    const posPos = index % 4;
    const dir = directions[posPos];
    const distance = 350 + (layer * 200);
    np[id] = { x: dir.x * distance, y: dir.y * distance };
  }
});
console.log(np);
