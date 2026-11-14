#!/usr/bin/env node
// Playwright の結果（results/results.json）から通知文を作る。
// - やり直しても失敗したケースを「失敗」、タイトルに @warn を含むものを「警告」に分ける
// - results/summary.txt に通知文を書き、GITHUB_OUTPUT に failed / warned / notify を出す
// - 失敗が 1 件以上あれば終了コード 1
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'results');
const file = path.join(dir, 'results.json');

function collect(suite, out) {
  for (const spec of suite.specs || []) {
    for (const t of spec.tests || []) {
      const last = (t.results || [])[t.results.length - 1] || {};
      out.push({
        title: spec.title,
        status: t.status, // expected | unexpected | flaky | skipped
        error: ((last.error && last.error.message) || '').replace(/\u001b\[[0-9;]*m/g, '').split('\n')[0].slice(0, 200),
      });
    }
  }
  for (const child of suite.suites || []) collect(child, out);
}

let tests = [];
let fatal = '';
try {
  const json = JSON.parse(fs.readFileSync(file, 'utf8'));
  for (const suite of json.suites || []) collect(suite, tests);
  if ((json.errors || []).length) fatal = String(json.errors[0].message || json.errors[0]).split('\n')[0];
} catch (err) {
  fatal = `結果のファイルを読めませんでした: ${err.message}`;
}
if (!fatal && tests.length === 0) fatal = 'テストが 1 件も実行されませんでした';

const bad = tests.filter((t) => t.status === 'unexpected');
const warned = bad.filter((t) => t.title.includes('@warn'));
const failed = bad.filter((t) => !t.title.includes('@warn'));
const flaky = tests.filter((t) => t.status === 'flaky');
const skipped = tests.filter((t) => t.status === 'skipped');
const passed = tests.filter((t) => t.status === 'expected');

const line = (t) => `- ${t.title.replace(/\s*@warn/, '')}${t.error ? `\n    ${t.error}` : ''}`;
const lines = [
  'PolisJAPAN 本番定期テストの結果',
  '',
  `成功 ${passed.length} 件 / 失敗 ${failed.length} 件 / 警告 ${warned.length} 件 / やり直しで成功 ${flaky.length} 件 / スキップ ${skipped.length} 件`,
];
if (fatal) lines.push('', '■ テストを実行できませんでした', fatal);
if (failed.length) lines.push('', '■ 失敗（やり直しても失敗）', ...failed.map(line));
if (warned.length) lines.push('', '■ 警告', ...warned.map(line));
if (flaky.length) lines.push('', '■ やり直しで成功', ...flaky.map((t) => `- ${t.title}`));
if (skipped.length) lines.push('', '■ スキップ', ...skipped.map((t) => `- ${t.title}`));
lines.push('', 'テストケースの内容: docs/本番定期テストケース.md', '対応の手順: docs/運用手順書.md');
if (process.env.RUN_URL) lines.push(`実行の記録: ${process.env.RUN_URL}`);

const summary = lines.join('\n') + '\n';
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path.join(dir, 'summary.txt'), summary);
process.stdout.write(summary);

const failedCount = failed.length + (fatal ? 1 : 0);
if (process.env.GITHUB_OUTPUT) {
  fs.appendFileSync(process.env.GITHUB_OUTPUT, `failed=${failedCount}\nwarned=${warned.length}\nnotify=${failedCount + warned.length > 0}\n`);
}
process.exit(failedCount > 0 ? 1 : 0);
