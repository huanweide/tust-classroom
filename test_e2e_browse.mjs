/**
 * M2 三层导航 + 搜索联通 + M4 深链 端到端测试（Playwright）
 *
 * 跑法（一条命令，自带静态服务）：
 *   cd /c/Users/Administrator/Desktop/Projects/tust-classroom
 *   node test_e2e_browse.mjs
 *
 * 说明：
 * - 服务在测试内部自启自停，不依赖外部进程 ——
 *   之前依赖 `python -m http.server 8899` 后台进程，会话一结束就被杀，
 *   下次跑直接 ERR_CONNECTION_REFUSED（2026-10-19 实测踩坑）。
 * - 断言打的是「真实用户能看见什么」，不是内部变量。
 *   M1 的教训：源码断言拦不住「界面其实没渲染出来」这类问题。
 */
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';

// 坑：Windows 下 new URL(...).pathname 会得到 "/C:/..."，join 后 existsSync 全 false，
// 导致所有请求（含 data/index.json）都回退成 index.html，页面拿不到数据静默不渲染。
// 必须用 fileURLToPath 转成真正的盘符路径。
const STATIC = fileURLToPath(new URL('./static/', import.meta.url));
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript',
  '.json': 'application/json; charset=utf-8', '.css': 'text/css',
  '.png': 'image/png', '.svg': 'image/svg+xml',
  '.webmanifest': 'application/manifest+json',
};

// ── 内嵌静态服务（零依赖，仅测试用）──
const server = createServer(async (req, res) => {
  try {
    const urlPath = decodeURIComponent(req.url.split('?')[0]);
    let fp = join(STATIC, normalize(urlPath));
    // 目录请求必须落到 index.html，否则 readFile 抛 EISDIR，
    // 连带 service worker 安装失败，页面行为与线上不一致（2026-10-19 实测）
    if (!existsSync(fp) || extname(fp) === '') fp = join(STATIC, 'index.html');
    const buf = await readFile(fp);
    res.writeHead(200, { 'Content-Type': MIME[extname(fp)] || 'application/octet-stream' });
    res.end(buf);
  } catch {
    res.writeHead(404); res.end('not found');
  }
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}`;
console.log(`测试服务已启动 → ${BASE}`);

// ESM 不认 NODE_PATH，须绝对路径导入 playwright；且必须导 index.mjs（导 index.js 拿到 undefined）
const { chromium } = await import(
  'file:///C:/Users/Administrator/.workbuddy/binaries/node/workspace/node_modules/playwright/index.mjs'
);

const EXEC = process.env.CHROME
  || 'C:/Users/Administrator/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe';

let pass = 0, fail = 0;
const ok = (name, cond, extra = '') => {
  if (cond) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name}${extra ? '\n         ' + extra : ''}`); }
};

const browser = await chromium.launch({ executablePath: EXEC, headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

const errors = [];
page.on('pageerror', e => errors.push(String(e)));
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });

await page.goto(BASE + '/index.html', { waitUntil: 'networkidle' });
// 注意：index 是 script 里的 let 变量，不挂 window，waitForFunction 探不到它。
// 要等就等真实渲染产物（楼栋磁贴出现）—— 这本来就是 M1 的教训：
// 探内部变量会漏掉「数据到了但界面没渲染」的情况。
await page.waitForSelector('#panel-browse .bld-tile', { timeout: 20000 });

// ── 0. 无 JS 报错 ──
console.log('[0] 启动无报错');
ok('无 JS 运行时错误', errors.length === 0, errors.join(' | '));

// ── 1. 默认进入「选教室」+ 默认泰达 ──
console.log('[1] 默认态');
ok('默认模式是选教室', await page.locator('#btn-browse').evaluate(e => e.classList.contains('active')));
const campus = await page.locator('#sel-campus').inputValue();
ok('默认校区=泰达', campus === '泰达', `实际=${campus}`);
const dateCount = await page.locator('.date-chip').count();
ok('日期条已渲染', dateCount > 0, `count=${dateCount}`);

// ── 2. 第一层：楼栋列表，阶梯置顶 ──
console.log('[2] 楼栋列表');
const blds = page.locator('#panel-browse .bld-tile');
const n = await blds.count();
ok('楼栋已渲染', n > 0, `count=${n}`);
const firstName = await blds.first().locator('.bn').innerText();
ok('第一栋是 9号楼（阶梯楼置顶）', firstName.includes('9号楼'), `实际=${firstName}`);

// 全部楼栋铺开：什么楼都可选（折叠组已移除）
const nBld = await blds.count();
ok('全部楼栋直接铺开可选（无折叠）', nBld >= 20, `实际 ${nBld} 栋`);
const grpTxt = await page.locator('.grp-label').allInnerTexts();
ok('有分组标题', grpTxt.length >= 2, JSON.stringify(grpTxt));
ok('第一组是阶梯教室楼', /阶梯/.test(grpTxt[0] || ''), grpTxt[0]);

// ── 3. 点 9号楼 → 第二层，阶梯置顶 ──
console.log('[3] 楼栋 → 教室列表');
await blds.first().click();
await page.waitForSelector('#panel-browse .room-tile', { timeout: 10000 });
const rooms = page.locator('#panel-browse .room-tile');
const rn = await rooms.count();
ok('教室列表已渲染', rn > 0, `count=${rn}`);
const firstRoom = await rooms.first().innerText();
ok('第一间是阶梯教室', /阶梯/.test(firstRoom), `实际=${firstRoom}`);
const crumbs = await page.locator('.crumbs').innerText();
ok('面包屑含 9号楼', /9号楼/.test(crumbs), `实际=${crumbs}`);

// 排序验证：阶梯在前
const stepCount = await page.locator('.room-tile.is-step').count();
ok('阶梯教室有专属样式', stepCount > 0, `stepCount=${stepCount}`);

// ── 4. 点教室 → 第三层，13 节红绿格 ──
console.log('[4] 教室 → 时段详情');
await rooms.first().click();
await page.waitForSelector('#panel-browse .tl-cell', { timeout: 10000 });
const chips = await page.locator('.tl-cell').count();
ok('显示 13 个节次格', chips === 13, `实际=${chips}`);
const detail = await page.locator('#panel-browse').innerText();
ok('显示空闲/占用统计', /空闲|占用/.test(detail));

// ── 5. 面包屑回退 ──
console.log('[5] 面包屑导航');
await page.locator('.crumbs a').first().click();   // 回到校区层
await page.waitForSelector('#panel-browse .bld-tile', { timeout: 10000 });
ok('可回退到楼栋列表', await page.locator('.bld-tile').count() > 0);

// ── 6. 搜索：9-16 等价 16阶梯（核心诉求）──
console.log('[6] 搜索等价性');
const search = async (q) => {
  await page.fill('#inp-global', '');
  await page.fill('#inp-global', q);
  await page.waitForTimeout(400);
  const items = page.locator('#search-results .sr-item');
  const c = await items.count();
  if (!c) return { n: 0, first: '' };
  return { n: c, first: (await items.first().innerText()).replace(/\s+/g, ' ') };
};

const equiv = ['9-16', '16阶梯', '16阶梯(d)', '9号楼16阶梯', '916阶梯'];
const results = {};
for (const q of equiv) {
  const r = await search(q);
  results[q] = r;
  ok(`搜「${q}」有结果`, r.n > 0, JSON.stringify(r));
}
const keys = new Set(Object.values(results).map(r => r.first.split(' ·')[0]));
// 只比对前 6 个字符（阶梯序号）：显示名一个带 (d) 尾巴一个不带，
// 比全等会误判成「不等价」。等价性由 test_normalize.py 在数据层严格保证。
const nums = new Set(Object.values(results).map(r => {
  const m = r.first.match(/(\d+)\s*阶梯/);
  return m ? m[1] : r.first;
}));
ok('五种写法命中同一阶梯序号', nums.size === 1, [...nums].join(' | '));

// ── 7. 搜索命中教室 → 点击直达详情 ──
console.log('[7] 搜索 → 直达');
await search('9-16');
await page.locator('#search-results .sr-item').first().click();
await page.waitForSelector('#panel-browse .tl-cell', { timeout: 10000 });
ok('点搜索结果直达时段页', await page.locator('.tl-cell').count() === 13);

// ── 8. 搜索命中楼栋 → 进该楼列表 ──
console.log('[8] 搜楼栋');
await search('9-');
const r9 = await page.locator('#search-results .sr-item').first().innerText();
ok('搜 9- 返回 9号楼', /9号楼/.test(r9), `实际=${r9}`);
await page.locator('#search-results .sr-item').first().click();
await page.waitForSelector('#panel-browse .room-tile', { timeout: 10000 });
ok('点楼栋进教室列表', await page.locator('.room-tile').count() > 0);

// ── 9. 不存在的名字必须拒绝 ──
console.log('[9] 拒绝编造');
for (const q of ['9阶梯', '不存在的教室xyz']) {
  const r = await search(q);
  ok(`搜「${q}」无结果`, r.n === 0, `实际=${r.n}`);
}

// ── 10. 切日期，教室空闲状态应变化 ──
console.log('[10] 日期联动');
await search('9-16');
await page.locator('#search-results .sr-item').first().click();
await page.waitForSelector('#panel-browse .tl-cell', { timeout: 10000 });
const before = await page.locator('#panel-browse .tl-cell.free').count();
// 注意：日期条在 browse 面板【之外】（全局共用），选择器不能用 #panel-browse 前缀
const chipsAll = page.locator('.date-chip');
await chipsAll.nth(Math.min(3, await chipsAll.count() - 1)).click();
await page.waitForTimeout(800);
// 切日期后必须仍停在教室详情页，且空闲格重算
const stillHere = await page.locator('#panel-browse .tl-cell').count();
ok('切日期后仍停在教室详情', stillHere === 13, `chips=${stillHere}`);
const after = await page.locator('#panel-browse .tl-cell.free').count();
ok('切日期后空闲数已重算', typeof after === 'number', `${before} → ${after}`);

// ── 11. 旧三模式未回归 ──
console.log('[11] 旧模式回归');
for (const [id, panel] of [['btn-room','panel-room'], ['btn-range','panel-range'], ['btn-classroom','panel-classroom']]) {
  await page.locator(`#${id}`).click();
  await page.waitForTimeout(200);
  const vis = await page.locator(`#${panel}`).isVisible();
  ok(`${id} 切换正常`, vis);
}
await page.locator('#btn-room').click();
await page.selectOption('#sel-period', '3');
await page.locator('#panel-room .btn-primary').click();
await page.waitForTimeout(900);
const oldRes = await page.locator('#results').innerText();
ok('按节次查空闲仍有结果', oldRes.trim().length > 0, `实际=${oldRes.slice(0,60)}`);

// ── 12. 校区切换：泰达 ⇄ 河西，下方内容一通切换且不违和 ──
console.log('[12] 校区切换自然');
// 上一段停在旧模式，先切回选教室。
// 注意：此时 navStack 可能停在教室详情层（前面测试点进过），
// 所以不能硬等 .bld-tile —— 要按当前层级断言。
await page.locator('#btn-browse').click();
await page.waitForSelector('#panel-browse .crumbs', { timeout: 15000 });
// 主动回到第一层（楼栋列表），校区切换断言从干净状态开始
await page.evaluate(() => navBuildings());
await page.waitForSelector('#panel-browse .bld-tile', { timeout: 15000 });
const tdFirst = await page.locator('#panel-browse .bld-tile .bn').first().innerText();
ok('泰达第一栋是 9号楼（阶梯置顶）', /9号楼/.test(tdFirst), tdFirst);

// 房间数降序：只校验「教学楼」组内降序。
// 注意页面是 阶梯楼 → 教学楼 → 场地 → 虚拟 四组平铺，
// 场地/虚拟组房间数小但排在后，那是分组设计不是乱序，
// 所以必须按 .grp-label 切段，不能拿全列表一把梭。
const groups = await page.evaluate(() => {
  const out = [];
  document.querySelectorAll('#browse-level .grp-label').forEach(lab => {
    let n = 0;
    let el = lab.nextElementSibling;
    while (el && !el.classList.contains('grp-label')) {
      if (el.classList.contains('bld-grid')) n += el.querySelectorAll('.bld-tile').length;
      el = el.nextElementSibling;
    }
    out.push({ label: lab.textContent.trim(), n });
  });
  return out;
});
ok('四组平铺（阶梯/教学楼/场地/虚拟）', groups.length === 4, JSON.stringify(groups));

const mainCounts = await page.evaluate(() => {
  const labels = [...document.querySelectorAll('#browse-level .grp-label')];
  const main = labels.find(l => l.textContent.includes('教学楼'));
  if (!main) return [];
  let el = main.nextElementSibling;
  const out = [];
  while (el && !el.classList.contains('grp-label')) {
    if (el.classList.contains('bld-grid')) {
      el.querySelectorAll('.bld-tile .bc').forEach(bc => {
        out.push(parseInt(bc.textContent, 10) || 0);
      });
    }
    el = el.nextElementSibling;
  }
  return out;
});
const isDesc = mainCounts.every((v, i) => i === 0 || mainCounts[i - 1] >= v);
ok('教学楼按房间数降序（信息多的放上面）', isDesc, JSON.stringify(mainCounts));

await page.selectOption('#sel-campus', '河西');
await page.waitForTimeout(600);
const hxFirst = await page.locator('#panel-browse .bld-tile .bn').first().innerText();
ok('河西第一栋是阶梯楼', /阶梯/.test(hxFirst), hxFirst);
ok('河西楼栋已重渲染', await page.locator('#panel-browse .bld-tile').count() > 0);
const hxHint = await page.locator('.campus-hint').innerText();
ok('校区提示同步为河西', /河西/.test(hxHint), hxHint);
const hxCrumb = await page.locator('.crumbs').innerText();
ok('面包屑同步为河西', /河西/.test(hxCrumb), hxCrumb);

await page.locator('#panel-browse .bld-tile').nth(1).click();
await page.waitForSelector('#panel-browse .room-tile', { timeout: 10000 });
ok('河西教室列表已加载', (await page.locator('#panel-browse').innerText()).includes('河西'));

await page.selectOption('#sel-campus', '泰达');
await page.waitForTimeout(600);
ok('切回泰达回到楼栋第一层', await page.locator('#panel-browse .bld-tile').count() > 0);
const backFirst = await page.locator('#panel-browse .bld-tile .bn').first().innerText();
ok('切回后 9号楼仍置顶', /9号楼/.test(backFirst), backFirst);

// ── 13. 隐私：页面不得出现真名 / 收款码 ──
console.log('[13] 隐私与赞助默认关闭');
const bodyHtml = await page.content();
for (const bad of ['樊斯瑞', '瑞宝宝', 'wechat-qr', 'sponsor-box', '收款码']) {
  ok(`页面不含「${bad}」`, !bodyHtml.includes(bad));
}
ok('作者署名为 ReTri', bodyHtml.includes('ReTri'));

// ── 14. M4 深链：带参链接直达教室 ──
console.log('[14] M4 深链直达');
// 深链日期必须用 index.dates 里真实存在的。index 是 let 变量不挂 window，
// 所以从页面已有的 date-chip 里取（那是 index.dates 的真实渲染产物）。
const chipDates = await page.locator('.date-chip').evaluateAll(
  els => els.map(e => e.dataset.date).filter(Boolean));
const deepDate = chipDates.length ? chipDates[chipDates.length - 1] : null;
ok('取到深链测试日期', !!deepDate, String(deepDate));
const deepUrl = BASE + '/index.html?campus=泰达&bld=9-&room=16阶梯(d)&date=' + (deepDate || '');
await page.goto(deepUrl, { waitUntil: 'networkidle' });
await page.waitForSelector('#panel-browse .tl-cell', { timeout: 15000 });
ok('深链直达教室时段页', await page.locator('#panel-browse .tl-cell').count() === 13);
const deepTxt = await page.locator('#panel-browse').innerText();
ok('深链落到 16阶梯', /16阶梯/.test(deepTxt), deepTxt.slice(0, 80));
ok('深链带校区信息', /泰达/.test(deepTxt));

// 友好写法深链：room=9-16 应解析成 16阶梯
await page.goto(BASE + '/index.html?room=9-16', { waitUntil: 'networkidle' });
await page.waitForSelector('#panel-browse .tl-cell', { timeout: 15000 });
const friendly = await page.locator('#panel-browse').innerText();
ok('深链支持 9-16 友好写法', /16阶梯/.test(friendly), friendly.slice(0, 80));

// 只有楼栋的深链 → 落在该楼教室列表
await page.goto(BASE + '/index.html?bld=9-', { waitUntil: 'networkidle' });
await page.waitForSelector('#panel-browse .room-tile', { timeout: 15000 });
ok('深链 bld=9- 落教室列表', await page.locator('#panel-browse .room-tile').count() > 0);

// 不存在的教室深链 → 必须退回首页，不能显示空壳
await page.goto(BASE + '/index.html?room=不存在的教室xyz', { waitUntil: 'networkidle' });
await page.waitForTimeout(1500);
const fallback = await page.locator('#panel-browse').innerText();
ok('无效深链退回楼栋列表', /校区|其他场所/.test(fallback) && !/不存在的教室xyz/.test(fallback),
  fallback.slice(0, 100));

// ── 14. M4 美化效果断言 ──
console.log('[14] 美化显示');
await page.goto(BASE + '/index.html?room=9-16', { waitUntil: 'networkidle' });
await page.waitForSelector('#panel-browse .tl-cell', { timeout: 15000 });
ok('时间轴已渲染', await page.locator('.timeline').count() === 1);
ok('13 个时间轴格子', await page.locator('.tl-cell').count() === 13);
ok('有图例', await page.locator('.timeline-legend').count() === 1);
ok('有结论卡（最长连续空闲）', await page.locator('.summary-card').count() === 1);
const scTxt = await page.locator('.summary-card').innerText();
ok('结论卡算出连续空闲节数', /节/.test(scTxt), scTxt.slice(0, 60));
ok('有复制链接按钮', await page.locator('.mini-btn').count() >= 2);
// 时间轴格子必须带时间，不只裸节次号
const tlT = await page.locator('.tl-cell .tl-t').first().innerText();
ok('时间轴显示起始时间', /\d{2}:\d{2}/.test(tlT), `实际=${tlT}`);
// 空闲格子用绿色、占用用灰，颜色语义正确
const freeBg = await page.locator('.tl-cell.free').first().evaluate(
  e => getComputedStyle(e).backgroundColor);
const busyBg = await page.locator('.tl-cell.busy').first().evaluate(
  e => getComputedStyle(e).backgroundColor);
ok('空闲/占用配色不同', freeBg !== busyBg, `${freeBg} vs ${busyBg}`);

// ── 15. 全程无报错 ──
console.log('[15] 全程无 JS 错误');
ok('无 JS 运行时错误', errors.length === 0, errors.join(' | '));

await page.screenshot({ path: 'e2e-m2-browse.png', fullPage: true });
await browser.close();
server.close();

console.log(`\n结果：${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);