'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('events');
const http = require('http');
const cdp = require('../../lib/cdp');

const originalRequest = http.request;

test.afterEach(() => {
  http.request = originalRequest;
});

test('closeTarget calls Chrome close endpoint once with target id', async () => {
  const requests = [];
  http.request = (options, callback) => {
    requests.push(options);
    const req = new EventEmitter();
    req.end = () => {
      const res = new EventEmitter();
      res.statusCode = 200;
      callback(res);
      res.emit('data', Buffer.from('Target is closing'));
      res.emit('end');
    };
    req.destroy = () => {};
    return req;
  };

  const result = await cdp.closeTarget('target-123');

  assert.deepEqual(result, { closed: true, targetId: 'target-123' });
  assert.equal(requests.length, 1);
  assert.equal(requests[0].method, 'GET');
  assert.equal(requests[0].path, '/json/close/target-123');
});
