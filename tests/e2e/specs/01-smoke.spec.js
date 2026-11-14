// 4.1 疎通（ブラウザ不要・HTTP のみ）
const { test, expect, APP_URL, LP_URL, API_URL, ADMIN_URL, IS_LOCAL } = require('../lib/fixtures');

test('TC-SM01 アプリが配信されている', async ({ request }) => {
  const res = await request.get(`${APP_URL}/`);
  expect(res.status()).toBe(200);
  expect(await res.text()).toContain('id="search-input"');
});

test('TC-SM02 LP が配信されている', async ({ request }) => {
  const res = await request.get(`${LP_URL}/`);
  expect(res.status()).toBe(200);
  expect(await res.text()).toMatch(/<title>\s*Polis JAPAN \| 分断をなくすSNS\s*<\/title>/);
});

test('TC-SM03 API が動いている', async ({ request }) => {
  const res = await request.get(`${API_URL}/batch/healthcheck`);
  expect(res.status()).toBe(200);
  expect(await res.json()).toEqual({ is_success: true });
});

async function loadThemes(request) {
  const res = await request.get(`${APP_URL}/csv/themes.csv`);
  expect(res.status()).toBe(200);
  const lines = (await res.text()).split(/\r?\n/).filter((l) => l.trim() !== '');
  return { header: lines[0], rows: lines.slice(1), text: lines.join('\n') };
}

test('TC-SM04 テーマ一覧のデータが配信されている', async ({ request }) => {
  const { header, rows } = await loadThemes(request);
  for (const col of ['id', 'conversation_id', 'updated_at']) {
    expect(header.split(',').map((c) => c.trim().replace(/^"|"$/g, ''))).toContain(col);
  }
  expect(rows.length).toBeGreaterThanOrEqual(1);
});

test('TC-SM05 テーマ一覧のデータが更新され続けている @warn', async ({ request }) => {
  const { text } = await loadThemes(request);
  // updated_at は「YYYY-MM-DD HH:MM」の日本時間
  const stamps = [...text.matchAll(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}/g)].map((m) => Date.parse(`${m[0].replace(' ', 'T')}:00+09:00`));
  expect(stamps.length).toBeGreaterThan(0);
  const ageHours = (Date.now() - Math.max(...stamps)) / 3_600_000;
  expect(ageHours, `最後の更新から ${ageHours.toFixed(1)} 時間`).toBeLessThanOrEqual(24);
});

test('TC-SM06 管理画面が外部から開けない', async ({ request }) => {
  test.skip(IS_LOCAL, '許可 IP から実行すると 403 にならないため、ローカルでは実行しない');
  const res = await request.get(`${ADMIN_URL}/`);
  expect(res.status()).toBe(403);
});

test('TC-SM07 PWA の定義が配信されている', async ({ request }) => {
  const res = await request.get(`${APP_URL}/manifest.json`);
  expect(res.status()).toBe(200);
  const manifest = await res.json();
  expect(manifest.name).toBe('PolisJAPAN');
  expect(manifest.display).toBe('standalone');
});
