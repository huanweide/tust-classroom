/**
 * 前端端到端测试（真实浏览器点击，不是模拟 DOM）
 *
 * 以前这个脚本把 Chrome 路径、截图目录全写死在作者本机，别人 clone 下来
 * 根本跑不了。现在改成：浏览器路径自动探测 / 可用环境变量覆盖，
 * 静态站点由本脚本自己起，跑完自动关。
 *
 * 用法：
 *   npm install && npm run e2e
 *   或：node e2e_test.cjs
 *
 * 可用环境变量：
 *   CHROME_PATH  本机 Chrome/Edge 可执行文件（不填则自动探测）
 *   E2E_PORT     静态服务端口（默认 8123）
 *   E2E_SHOTS    截图输出目录（默认 ./e2e_shots）
 */
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const http = require('http');
const path = require('path');

const ROOT = __dirname;
const STATIC_DIR = path.join(ROOT, 'static');
const PORT = Number(process.env.E2E_PORT || 8123);
const URL = process.env.E2E_URL || `http://127.0.0.1:${PORT}/index.html`;
const SHOTS = process.env.E2E_SHOTS || path.join(ROOT, 'e2e_shots');
const RESULT_FILE = process.env.E2E_RESULT || path.join(ROOT, 'e2e_result.json');

// 浏览器路径自动探测：先认环境变量，再按系统常见位置找一遍
const CANDIDATES = [
  process.env.CHROME_PATH,
  path.join(ROOT, '..', '.cache', 'puppeteer'),
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
].filter(Boolean);

function findChrome() {
  for (const c of CANDIDATES) {
    if (c.includes('*')) continue;
    if (fs.existsSync(c) && fs.statSync(c).isFile()) return c;
    // 支持给一个 puppeteer 缓存目录，递归找 chrome.exe
    if (fs.existsSync(c) && fs.statSync(c).isDirectory()) {
      const found = walkFind(c, /^(chrome|headless_shell)(\.exe)?$/i, 4);
      if (found) return found;
    }
  }
  return null;
}

function walkFind(dir, re, maxDepth) {
  if (maxDepth < 0) return null;
  let entries = [];
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return null; }
  for (const e of entries) {
    const p = path.join(dir, e.name);
    if (e.isFile() && re.test(e.name)) return p;
    if (e.isDirectory()) {
      const hit = walkFind(p, re, maxDepth - 1);
      if (hit) return hit;
    }
  }
  return null;
}

const CHROME = findChrome();
if (!CHROME) {
  console.error(
    '[FATAL] 没找到 Chrome/Edge。请设置环境变量 CHROME_PATH 指向浏览器可执行文件。\n' +
    '        例：CHROME_PATH="C:/Program Files/Google/Chrome/Application/chrome.exe" npm run e2e'
  );
  process.exit(2);
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webmanifest': 'application/manifest+json',
};

function startStaticServer() {
  const server = http.createServer((req, res) => {
    const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '');
    const file = path.join(STATIC_DIR, rel || 'index.html');
    // 防目录穿越
    if (!file.startsWith(STATIC_DIR)) { res.writeHead(403).end(); return; }
    fs.readFile(file, (err, data) => {
      if (err) { res.writeHead(404).end('not found'); return; }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
      res.end(data);
    });
  });
  return new Promise(resolve => server.listen(PORT, '127.0.0.1', () => resolve(server)));
}

fs.mkdirSync(SHOTS, { recursive: true });

const results = [];
const rec = (name, pass, detail) => {
  results.push({ name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} | ${name} | ${detail}`);
};
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const server = await startStaticServer();
  console.log(`[e2e] 静态服务：${URL}`);
  console.log(`[e2e] 浏览器：${CHROME}`);
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 414, height: 896 });
  const jsErrors = [];
  page.on('pageerror', e => jsErrors.push(String(e)));
  page.on('console', m => { if (m.type() === 'error') jsErrors.push(m.text()); });

  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  // 等 init 完成：校区下拉已填充并选中
  await page.waitForFunction(() => {
    const e = document.getElementById('sel-campus');
    return e && e.options.length > 0 && e.value;
  }, { timeout: 20000 });
  await sleep(500);

  // T1 默认校区
  const campus = await page.$eval('#sel-campus', e => e.value);
  rec('T1 默认校区=泰达', campus === '泰达', `实际=${campus}`);
  await page.screenshot({ path: `${SHOTS}/01_initial.png` });

  // T2 模式1：按节次查空闲
  await page.select('#sel-period', '1');
  await page.click('button[onclick="queryFreeRooms()"]');
  await sleep(900);
  const r2html = await page.$eval('#results', e => e.innerHTML);
  const r2txt = await page.$eval('#results', e => e.textContent);
  const t2ok = /result-card/.test(r2html) && !/请选择日期/.test(r2txt);
  rec('T2 按节次查空闲有结果', t2ok, r2txt.slice(0, 36).replace(/\s+/g, ' '));
  await page.screenshot({ path: `${SHOTS}/02_room.png` });

  // T3 模式2：时间范围查空闲
  await page.click('#btn-range');
  await sleep(250);
  const rangeActive = await page.$eval('#btn-range', e => e.classList.contains('active'));
  rec('T3a 切换到时间范围模式', rangeActive, `btn-range.active=${rangeActive}`);
  const ends = await page.$$eval('#sel-end option', os => os.map(o => o.value));
  await page.select('#sel-start', '1');
  await page.select('#sel-end', ends[ends.length - 1]);
  await page.click('button[onclick="queryFreeRange()"]');
  await sleep(900);
  const r3txt = await page.$eval('#results', e => e.textContent);
  rec('T3b 时间范围查询有结果', !/请选择日期/.test(r3txt) && r3txt.trim().length > 3, r3txt.slice(0, 36).replace(/\s+/g, ' '));
  await page.screenshot({ path: `${SHOTS}/03_range.png` });

  // T4 模式3：查教室时段 9-3
  await page.click('#btn-classroom');
  await sleep(250);
  await page.$eval('#inp-classroom', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, '9-3');
  await page.click('button[onclick="queryClassroomSlots()"]');
  await sleep(900);
  const r4 = await page.$eval('#results', e => e.textContent);
  rec('T4 查教室 9-3 → 3阶梯(d)', /3阶梯/.test(r4), r4.slice(0, 48).replace(/\s+/g, ' '));
  await page.screenshot({ path: `${SHOTS}/04_classroom_9-3.png` });

  // T5 模式3：3阶梯
  await page.$eval('#inp-classroom', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, '3阶梯');
  await page.click('button[onclick="queryClassroomSlots()"]');
  await sleep(900);
  const r5 = await page.$eval('#results', e => e.textContent);
  rec('T5 查教室 3阶梯 → 3阶梯(d)', /3阶梯/.test(r5), r5.slice(0, 48).replace(/\s+/g, ' '));

  // T6 校区切换 → 河西
  await page.select('#sel-campus', '河西');
  await sleep(500);
  const bldOpts = await page.$$eval('#sel-building-room option', os => os.map(o => o.textContent));
  const hasJieti = bldOpts.some(t => t.includes('阶梯'));
  rec('T6 切河西→教学楼含"阶梯"楼', hasJieti, `楼栋数=${bldOpts.length}`);
  await page.screenshot({ path: `${SHOTS}/05_hexibuildings.png` });

  // T7 教学楼过滤（河西选 阶梯 楼）
  if (hasJieti) {
    const jt = bldOpts.find(t => t.includes('阶梯'));
    await page.select('#sel-building-room', jt);
    await page.click('#btn-room');
    await sleep(250);
    await page.click('button[onclick="queryFreeRooms()"]');
    await sleep(900);
    const r7 = await page.$eval('#results', e => e.textContent);
    rec('T7 教学楼过滤生效', !/请选择日期/.test(r7) && r7.trim().length > 3, `楼=${jt} ${r7.slice(0, 28).replace(/\s+/g, ' ')}`);
  }

  // T8 日期后一天导航
  const before = await page.$eval('#date-scroll .date-chip.active', e => e.dataset.date).catch(() => null);
  await page.click('button[onclick="shiftDate(1)"]');
  await sleep(400);
  const after = await page.$eval('#date-scroll .date-chip.active', e => e.dataset.date).catch(() => null);
  rec('T8 日期后一天导航', !!(before && after && before !== after), `before=${before} after=${after}`);

  // T9 搜索自动补全（切回泰达，搜"阶梯"——泰达教室名含"阶梯"）
  await page.select('#sel-campus', '泰达');
  await sleep(400);
  await page.click('#btn-classroom');
  await sleep(250);
  await page.$eval('#inp-classroom', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, '阶梯');
  await sleep(1200);
  const sugCount = await page.$$eval('#classroom-suggestions option', os => os.length);
  rec('T9 搜索自动补全有建议', sugCount > 0, `建议数=${sugCount}`);

  const realErrs = jsErrors.filter(e => !/MIME type|serviceWorker|sw\.js/i.test(e));
  rec('T10 页面无JS错误(忽略本地sw MIME)', realErrs.length === 0, realErrs.slice(0, 2).join(' | '));

  await browser.close();
  server.close();
  const pass = results.filter(r => r.pass).length;
  console.log(`\n=== 端到端结果: ${pass}/${results.length} 通过 ===`);
  console.log(`[e2e] 截图目录：${SHOTS}`);
  fs.writeFileSync(RESULT_FILE, JSON.stringify(results, null, 2));
  process.exit(pass === results.length ? 0 : 1);
})().catch(e => { console.error('FATAL', e); process.exit(2); });
