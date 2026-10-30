/* 博客前端小脚本：主题切换 / 代码复制 / 站内搜索 */
(function () {
  "use strict";

  /* ---------- 主题切换 ---------- */
  var root = document.documentElement;
  var toggle = document.getElementById("theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) { /* 隐私模式忽略 */ }
    });
  }

  /* ---------- 代码块复制按钮 ---------- */
  document.querySelectorAll(".code-block").forEach(function (block) {
    var code = block.querySelector("pre code");
    if (!code) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.textContent = "复制";
    btn.addEventListener("click", function () {
      var text = code.innerText;
      var done = function () {
        btn.textContent = "已复制";
        setTimeout(function () { btn.textContent = "复制"; }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {});
      } else {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); done(); } catch (e) {}
        document.body.removeChild(ta);
      }
    });
    block.appendChild(btn);
  });

  /* ---------- 站内搜索 ---------- */
  var input = document.getElementById("search-input");
  var results = document.getElementById("search-results");
  var hint = document.getElementById("search-hint");
  if (!input || !results) return;

  var index = null;
  var loading = false;

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function load(cb) {
    if (index) return cb();
    if (loading) return;
    loading = true;
    fetch("search.json")
      .then(function (r) { return r.json(); })
      .then(function (data) { index = data; loading = false; cb(); })
      .catch(function () {
        loading = false;
        if (hint) hint.textContent = "搜索索引加载失败（直接双击打开本地文件时会被浏览器阻止，请用本地服务器访问）。";
      });
  }

  function item(post) {
    var tags = (post.tags || []).map(function (t) {
      return '<span class="chip">' + esc(t) + "</span>";
    }).join("");
    return '<li class="post-item"><a class="post-link" href="' + esc(post.url) + '">' +
      "<h2>" + esc(post.title) + "</h2></a>" +
      '<div class="post-meta"><time>' + esc(post.date) + "</time>" +
      (tags ? '<span>·</span><span class="chips">' + tags + "</span>" : "") +
      "</div></li>";
  }

  function run() {
    var q = input.value.trim().toLowerCase();
    if (!index) return;
    if (!q) {
      results.innerHTML = "";
      if (hint) hint.textContent = "共 " + index.length + " 篇文章，输入关键词开始筛选。";
      return;
    }
    var words = q.split(/\s+/).filter(Boolean);
    var hits = index.filter(function (p) {
      var hay = (p.title + " " + (p.tags || []).join(" ") + " " + p.text).toLowerCase();
      return words.every(function (w) { return hay.indexOf(w) !== -1; });
    });
    if (hint) hint.textContent = hits.length ? "找到 " + hits.length + " 篇" : "没有匹配的文章。";
    results.innerHTML = hits.map(item).join("");
  }

  input.addEventListener("input", function () { load(run); });
  load(run);
})();