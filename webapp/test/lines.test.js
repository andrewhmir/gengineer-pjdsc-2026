'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { LineSplitter, recordOf, droppedOf } = require('../src/lines');

test('lines survive any chunk boundary and CRLF endings', () => {
  const split = new LineSplitter();
  assert.deepEqual(split.push('CSI_DATA,1,a'), []);
  assert.deepEqual(split.push('b\r\nCSI_DA'), ['CSI_DATA,1,ab']);
  assert.deepEqual(split.push(Buffer.from('TA,2\nnext')), ['CSI_DATA,2']);
});

test('a record keeps only what follows its keyword, so boot noise before it is dropped', () => {
  assert.deepEqual(recordOf('ÿþ\u0013CSI_DATA,5,1a:00:00:00:00:01 '), { kind: 'CSI_DATA', text: 'CSI_DATA,5,1a:00:00:00:00:01' });
  assert.equal(recordOf('HINIGRAM_RX,receiver=1').kind, 'HINIGRAM_RX');
  assert.equal(recordOf('type,id,mac,rssi'), null); // csi_rx's header line carries no record
});

test("the receiver's drop counter is read from both firmware formats", () => {
  assert.equal(droppedOf('# dropped=12'), 12);
  assert.equal(droppedOf('HINIGRAM_RX,receiver=1,logged=900,dropped=3'), 3);
  assert.equal(droppedOf('CSI_DATA,1,1a:00:00:00:00:01,-50'), null);
});

test('a runaway line without a newline is discarded instead of growing forever', () => {
  const split = new LineSplitter();
  split.push('x'.repeat(20000));
  assert.deepEqual(split.push('\nCSI_DATA,1\n'), ['', 'CSI_DATA,1']);
});
