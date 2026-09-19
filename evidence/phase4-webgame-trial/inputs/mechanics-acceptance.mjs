import assert from 'node:assert/strict';
import api from './game.js';

for (const name of ['createState', 'start', 'togglePause', 'restart', 'step']) {
  assert.equal(typeof api[name], 'function', `missing mechanics function: ${name}`);
}

const initial = api.createState({ width: 800, height: 600 });
assert.equal(initial.width, 800);
assert.equal(initial.height, 600);
assert.equal(initial.status, 'ready');
assert.equal(initial.score, 0);
assert.equal(initial.lives, 3);
assert.ok(initial.paddle && initial.ball);
assert.ok(Array.isArray(initial.bricks) && initial.bricks.length >= 12);
assert.ok(initial.bricks.every(brick => brick.alive === true && brick.points > 0));

let running = api.start(initial);
assert.equal(running.status, 'running');
const moved = api.step(running, 0.05, { right: true });
assert.ok(moved.paddle.x > running.paddle.x, 'right input moves paddle');
const left = api.step(moved, 0.05, { left: true });
assert.ok(left.paddle.x < moved.paddle.x, 'left input moves paddle');

const paused = api.togglePause(left);
assert.equal(paused.status, 'paused');
const frozen = api.step(paused, 0.25, { right: true });
assert.deepEqual(frozen, paused, 'paused state is unchanged by step');
const resumed = api.togglePause(paused);
assert.equal(resumed.status, 'running');
const progressed = api.step(resumed, 0.05, {});
assert.notDeepEqual(progressed.ball, resumed.ball, 'resumed ball advances');

let wall = api.start(api.createState({ width: 800, height: 600 }));
wall = { ...wall, ball: { ...wall.ball, x: wall.ball.radius / 2, vx: -Math.abs(wall.ball.vx) } };
const wallBounce = api.step(wall, 0.02, {});
assert.ok(wallBounce.ball.vx > 0, 'side wall reverses horizontal velocity');

let paddle = api.start(api.createState({ width: 800, height: 600 }));
paddle = { ...paddle, ball: { ...paddle.ball,
  x: paddle.paddle.x + paddle.paddle.width / 2,
  y: paddle.paddle.y - paddle.ball.radius / 2,
  vy: Math.abs(paddle.ball.vy) } };
const paddleBounce = api.step(paddle, 0.01, {});
assert.ok(paddleBounce.ball.vy < 0, 'paddle reverses downward velocity');

let brick = api.start(api.createState({ width: 800, height: 600 }));
const target = brick.bricks.find(item => item.alive);
brick = { ...brick, ball: { ...brick.ball,
  x: target.x + target.width / 2,
  y: target.y + target.height / 2,
  vy: Math.abs(brick.ball.vy) } };
const brickHit = api.step(brick, 0.001, {});
assert.equal(brickHit.bricks.find(item => item === target ||
  (item.x === target.x && item.y === target.y)).alive, false, 'brick becomes inactive');
assert.ok(brickHit.score >= target.points, 'brick collision increases score');

let lostLife = api.start(api.createState({ width: 800, height: 600 }));
lostLife = { ...lostLife, ball: { ...lostLife.ball, y: lostLife.height + lostLife.ball.radius + 2 } };
const afterLoss = api.step(lostLife, 0.01, {});
assert.equal(afterLoss.lives, 2);
assert.notEqual(afterLoss.status, 'lost');

let winning = api.start(api.createState({ width: 800, height: 600 }));
const last = winning.bricks[0];
winning = { ...winning,
  bricks: winning.bricks.map((item, index) => ({ ...item, alive: index === 0 })),
  ball: { ...winning.ball, x: last.x + last.width / 2, y: last.y + last.height / 2 } };
const won = api.step(winning, 0.001, {});
assert.equal(won.status, 'won');

let losing = api.start(api.createState({ width: 800, height: 600 }));
losing = { ...losing, lives: 1,
  ball: { ...losing.ball, y: losing.height + losing.ball.radius + 2 } };
const lost = api.step(losing, 0.01, {});
assert.equal(lost.status, 'lost');

const restarted = api.restart({ ...won, score: 999, lives: 1 });
assert.equal(restarted.status, 'ready');
assert.equal(restarted.score, 0);
assert.equal(restarted.lives, 3);
assert.ok(restarted.bricks.every(item => item.alive));
assert.deepEqual(restarted, api.createState({ width: restarted.width, height: restarted.height }),
  'restart is deterministic');

console.log('controller-owned Breakout mechanics acceptance passed');
