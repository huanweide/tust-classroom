> 本文档只记录「怎么加回去」，资源文件本地保留备用。

---

## 一、资源在哪

| 项 | 位置 | 状态 |
|---|---|---|
| git 忽略规则 | `.gitignore` 的 `static/sponsor/` | 已生效 |
| 页面挂载点 | `static/index.html` 页脚 | 已移除 |

### 为什么 git 忽略

历史提交里会永久留存（即使后续删除，`git log` 仍可翻出），
且 GitHub 的 fork / 缓存 / 第三方镜像都可能带走。
所以不只是"当前分支不显示"，而是**根本不能进版本库**。

---

## 二、加回去的三步（只有明确授权才做）

### 1. 放图


### 2. 页面加挂载块

在 `static/index.html` 的 `<div class="brand">` **之前**插入：

```html
<div id="sponsor-box" style="margin-top:14px;display:flex;flex-direction:column;align-items:center;gap:6px;">
       style="width:160px;height:160px;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,.12);background:#fff;"
       onerror="document.getElementById('sponsor-box').style.display='none';" />
  <span style="font-size:12px;color:#94a3b8;">自愿赞助</span>
</div>
```

要点：

- **`onerror` 必须有** —— 图片缺失时自动隐藏，不留破图。
- 容器 `display:flex` + `flex-direction:column`，与页脚其他块对齐。

### 3. 页脚文字补一句

在 `.notes` 区块加一条，指向下方二维码：

```html
<div class="n"><b>4 · 赞助</b>　开源维护不易，欢迎 <a href="https://github.com/huanweide/tust-classroom" target="_blank" rel="noopener">GitHub Star</a> 支持；也可扫下方二维码</div>
```

---

## 三、撤下来的三步（反向操作）

1. 删掉 `static/index.html` 里的 `#sponsor-box` 整块与第 4 条 `.n`。
2. 确认 `.gitignore` 仍有 `static/sponsor/`。
3. 本地图片留着别删 —— 下次要加直接回到第二节。

---

## 四、自检清单

改完后逐条确认：

- [ ] `git ls-files static/sponsor/` 输出为空
- [ ] 页脚 alt 文字不含姓名 / 昵称 / 手机号
- [ ] 图片路径写错时，页面不出现破图图标（onerror 生效）
- [ ] 移动端（390px 宽）下二维码不溢出

---

## 五、为什么默认不放

3. **产品定位**：这是校园工具，赞助应该是可选项而不是默认项；
   默认展示会让「查教室」这个主线任务变味。

所以默认关闭，需要时按本文档手动开启。
