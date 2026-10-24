'use strict';

// The receiver prints one record per line. A reset makes the ESP32 print its boot text at 115,200 baud, which
// arrives as noise at 921,600, so a line may start with junk before the record it carries.
const KINDS = ['CSI_DATA', 'HINIGRAM_RX'];
const MAX_LINE = 16384; // a CSI_DATA line is about 600 characters; anything far longer is noise without a newline

/** Splits a byte stream into lines, whatever the chunk boundaries. */
class LineSplitter {
  constructor() {
    this.buf = '';
  }

  push(chunk) {
    this.buf += typeof chunk === 'string' ? chunk : chunk.toString('latin1');
    const parts = this.buf.split('\n');
    this.buf = parts.pop();
    if (this.buf.length > MAX_LINE) this.buf = '';
    return parts.map((p) => p.replace(/\r$/, ''));
  }
}

/** The record a line carries, with any junk before it removed, or null for anything else. */
function recordOf(line) {
  for (const kind of KINDS) {
    const i = line.indexOf(kind);
    if (i >= 0) return { kind, text: line.slice(i).trim() };
  }
  return null;
}

/** The receiver's own count of lines it could not send: `# dropped=N` (csi_rx) or `...,dropped=N` (HINIGRAM_RX). */
function droppedOf(line) {
  const m = /(?:^#\s*|,)dropped=(\d+)/.exec(line);
  return m ? Number(m[1]) : null;
}

/** The bundle receiver's count of lines it has written: `HINIGRAM_RX,...,logged=N,...`. */
function loggedOf(line) {
  const m = /,logged=(\d+)/.exec(line);
  return m ? Number(m[1]) : null;
}

module.exports = { LineSplitter, recordOf, droppedOf, loggedOf };
