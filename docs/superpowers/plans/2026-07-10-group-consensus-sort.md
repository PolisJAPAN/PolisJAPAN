# グループ横断合意スコア（A-2） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 詳細ページ分析タブ「みんなが賛成した意見」の並びを、全体賛成率順からPolis本家準拠のグループ横断合意スコア（各グループの平滑化賛成率の積）順に変更する。

**Architecture:** `Client/public_html_app/javascript/detail.js` のみ変更。スコア計算関数とソート関数を新設し、`initializeArticles()` の1箇所でグループ数により分岐。UI・データ・他画面は不変。

**Tech Stack:** Vanilla JS / puppeteer-coreで検証（localhost:8081、/csv/は本番プロキシ。1グループのフォールバックはsetRequestInterceptionでCSVフィクスチャ注入）

**仕様書:** `docs/superpowers/specs/2026-07-10-group-consensus-sort-design.md`

**前提知識:**
- detail.jsは既に `toInt`/`toNum` ヘルパーを持つ。`displayData` の各要素は
  `{comment, totalAgreeRate, totalVotes, groupData: [{groupName, agrees, disagrees, passes, totalVotes, ...}]}`
- 現行の並び: `sortByTotalAgreeRate(list)`（detail.js:813付近）。`initializeArticles()`（893付近）の
  `const sortedByTotal = sortByTotalAgreeRate(displayData);` が「みんなが賛成した意見」の並びを決めている
- `groups` は同関数内で `getGroups(csvJson[0])` により先に取得済み（グループ文字の配列）
- detail.jsはSCSS無関係 → sassコンパイル不要。git操作時もsass停止不要（動いていなければそのまま）

---

### Task 1: スコア計算とソート関数の実装

**Files:**
- Modify: `Client/public_html_app/javascript/detail.js`（`sortByTotalAgreeRate` の直後に追加 + `initializeArticles` 1行変更）

- [ ] **Step 1: `sortByTotalAgreeRate` 関数の直後に以下を追加**

```js
/**
 * グループ横断合意スコアを計算する（Polis本家 group-aware-consensus と同一式）。
 * 各グループの平滑化賛成率 (agrees+1)/(totalVotes+2) の積。
 * 未投票グループは0.5（中立）となり、生の0%のように不当に沈まない。
 *
 * 依存: toInt
 *
 * @param {Object} item - displayData要素（groupData配列を含む）。
 * @returns {number|null} - スコア（0〜1）。groupDataが欠損・空なら null。
 */
function getGroupConsensusScore(item) {
    const groupData = item.groupData;
    if (!Array.isArray(groupData) || groupData.length === 0) {
        return null;
    }
    return groupData.reduce((score, g) => {
        const agrees = toInt(g.agrees);
        const votes = toInt(g.totalVotes);
        return score * ((agrees + 1) / (votes + 2));
    }, 1);
}

/**
 * グループ横断合意スコアで降順ソートする（A-2）。
 * スコアが計算できない行（groupData欠損）は totalAgreeRate-1 を代替キーとして
 * 末尾側に回す（スコアは常に正のため負値は必ず下位になる）。
 * 同点の場合は totalVotes の多い順（sortByTotalAgreeRate と同じタイブレーク）。
 *
 * 依存: getGroupConsensusScore, toNum, toInt
 *
 * @param {Array<Object>} list - ソート対象配列。
 * @returns {Array<Object>} - 新しい配列を返す（元配列は変更しない）。
 */
function sortByConsensusScore(list) {
    const sortKey = (item) => {
        const score = getGroupConsensusScore(item);
        return score !== null ? score : toNum(item.totalAgreeRate) - 1;
    };
    return list.slice().sort((a, b) => {
        const ka = sortKey(a);
        const kb = sortKey(b);
        if (ka !== kb) return kb - ka;
        return toInt(b.totalVotes) - toInt(a.totalVotes); // 同点なら票数多い順
    });
}
```

- [ ] **Step 2: `initializeArticles()` 内の並び替え呼び出しを分岐に変更**

変更前:
```js
    // 全体の賛成率が高いリストを取得
    const sortedByTotal = sortByTotalAgreeRate(displayData);
```

変更後:
```js
    // 「みんなが賛成した意見」の並び:
    // グループが2つ以上ならグループ横断合意スコア順（A-2）、
    // 1グループ以下は横断合意が定義できないため従来の全体賛成率順
    const sortedByTotal = (groups.length >= 2)
        ? sortByConsensusScore(displayData)
        : sortByTotalAgreeRate(displayData);
```

※ `groups` はこの行より前で取得済み。グループ別セクションの `sortByGroupAgreeRate` は触らない。

- [ ] **Step 3: 構文チェック**

Run: `node --check Client/public_html_app/javascript/detail.js`
Expected: エラーなし

### Task 2: ブラウザ検証（localhost・実データ+フィクスチャ）

**Files:**
- Create: scratchpad `check-consensus-sort.js`

- [ ] **Step 1: 検証スクリプト作成**（全文）

```js
const puppeteer = require("puppeteer-core");
const results = [];
const check = (n, ok, d = "") => results.push(`${ok ? "✅" : "❌"} ${n}${d ? " — " + d : ""}`);

// 実装と同じ式で期待順を独立計算（配線ミス検出用）
function expectedOrder(rows, gs) {
  const items = rows.map((r) => {
    let score = 1;
    for (const g of gs) {
      const a = parseInt(r[`group-${g}-agrees`] || 0, 10);
      const d = parseInt(r[`group-${g}-disagrees`] || 0, 10);
      const p = parseInt(r[`group-${g}-passes`] || 0, 10);
      score *= (a + 1) / (a + d + p + 2);
    }
    return { c: r.comment, score, tv: parseInt(r["total-votes"] || 0, 10) };
  });
  return items.sort((x, y) => (y.score - x.score) || (y.tv - x.tv)).map((x) => x.c);
}

async function fetchCsvRows(page, cid) {
  return page.evaluate(async (cid) => {
    const text = await (await fetch(`/csv/report/report_${cid}.csv`)).text();
    // 簡易CSVパース（検証用。カンマ含みコメントに対応するため既存のparseCSVを利用）
    return parseCSV(text);
  }, cid);
}

async function renderedTop(page, cid, n) {
  await page.goto(`http://localhost:8081/detail/?conversation_id=${cid}`, { waitUntil: "networkidle2" });
  await page.evaluate(() => switchTabs && switchTabs("reports"));
  await new Promise((r) => setTimeout(r, 2500));
  return page.evaluate((n) =>
    [...document.querySelectorAll(".report-list-container .comments-item .comment-text-content")]
      .slice(0, n).map((e) => e.textContent.trim()), n);
}

(async () => {
  const browser = await puppeteer.launch({
    executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    headless: "new",
  });
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 });
  await page.evaluateOnNewDocument(() => { document.cookie = "tutorial_optout=1; path=/"; });

  // 1-2. 実データ2テーマ: 描画順 = 期待順（積・タイブレークまで一致）
  for (const [cid, name, groups] of [["2ejacv8xnv", "外国人受け入れ", ["a","b","c"]], ["6rxfpkpnda", "理工学部の女子枠", ["a","b"]]]) {
    const top = await renderedTop(page, cid, 5);
    const rows = await fetchCsvRows(page, cid);
    const expected = expectedOrder(rows, groups).slice(0, 5);
    const match = JSON.stringify(top) === JSON.stringify(expected);
    check(`${name}: トップ5が積順の期待値と一致`, match, match ? "" : `\n  実際: ${top.join(" / ")}\n  期待: ${expected.join(" / ")}`);
  }
  await page.screenshot({ path: "consensus-sort.png" });

  // 3. 1グループフィクスチャ: 従来（全体賛成率順）のまま
  const fixtureCsv = [
    "comment-id,comment,total-agrees,total-disagrees,total-passes,total-votes,group-a-agrees,group-a-disagrees,group-a-passes,group-a-votes",
    '0,"低賛成率・多数票",10,80,10,100,10,80,10,100',
    '1,"高賛成率",90,5,5,100,90,5,5,100',
    '2,"中賛成率",50,40,10,100,50,40,10,100',
  ].join("\n");
  await page.setRequestInterception(true);
  page.on("request", (req) => {
    if (req.url().includes("/csv/report/report_fixture1g.csv")) {
      req.respond({ status: 200, contentType: "text/csv", body: fixtureCsv });
      return;
    }
    req.continue();
  });
  const top1g = await renderedTop(page, "fixture1g", 3);
  check("1グループ: 従来の全体賛成率順のまま", JSON.stringify(top1g) === JSON.stringify(["高賛成率", "中賛成率", "低賛成率・多数票"]), top1g.join(" / "));

  // 4. 回帰: グループ別セクション・ツールチップ・エラーなし
  await page.setRequestInterception(false);
  await page.goto("http://localhost:8081/detail/?conversation_id=6rxfpkpnda", { waitUntil: "networkidle2" });
  await page.evaluate(() => switchTabs("reports"));
  await new Promise((r) => setTimeout(r, 2500));
  const reg = await page.evaluate(() => ({
    groupSections: document.querySelectorAll(".report-list-container .comments-container, .report-list-container > *").length > 1,
    circleGraphs: document.querySelectorAll(".circle-graph-item").length > 0,
    groupInfo: document.querySelectorAll(".group-info-container .group-item-list > *").length >= 2,
  }));
  check("回帰: グループ別セクション・円グラフ・グループ紹介", reg.circleGraphs && reg.groupInfo, JSON.stringify(reg));
  check("pageerrorなし", errors.length === 0, errors.join("|"));

  await ctx.close(); await browser.close();
  console.log(results.join("\n"));
  process.exit(results.some((r) => r.startsWith("❌")) ? 1 : 0);
})();
```

- [ ] **Step 2: 実行**

Run: `cd <scratchpad> && node check-consensus-sort.js`
Expected: 全✅。仕様書の期待（外国人受け入れの先頭=「法律に違反したら…」or「税金や社会保険…」）も出力で目視確認

- [ ] **Step 3: スクリーンショット目視**（並び・表示崩れなし）

### Task 3: コミット

- [ ] **Step 1: feature/ux-improvements にコミット・push（mainマージ・デプロイはしない）**

```bash
git add Client/public_html_app/javascript/detail.js
git commit -m "feat: 分析タブ「みんなが賛成した意見」をグループ横断合意スコア順に変更 (A-2)

Polis本家 group-aware-consensus と同一式（各グループの平滑化賛成率
(agrees+1)/(votes+2) の積）で並べ替え。1グループ以下のテーマは従来の
全体賛成率順にフォールバック。UI・表示値は不変（並び順のみ）"
git push origin feature/ux-improvements
```
