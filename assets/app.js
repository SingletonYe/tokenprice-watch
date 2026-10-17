/* TokenPrice Watch — client-side table, filters, calculator.
   Progressive enhancement only: every page is fully readable without JS. */
(function () {
  "use strict";

  var raw = document.getElementById("models-data");
  var data = null;
  if (raw) {
    try { data = JSON.parse(raw.textContent); } catch (e) { data = null; }
  }

  function fmtUSD(v, allowZero) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    if (v === 0) return allowZero ? "Free" : "$0";
    if (v < 0.01) return "$" + v.toFixed(4);
    if (v < 1) return "$" + v.toFixed(3);
    if (v < 100) return "$" + v.toFixed(2);
    if (v < 10000) return "$" + v.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return "$" + Math.round(v).toLocaleString();
  }
  function fmtCtx(n) {
    if (!n) return "—";
    if (n >= 1000000 && n % 1000000 === 0) return (n / 1000000) + "M";
    if (n >= 1000) return Math.round(n / 1000) + "K";
    return String(n);
  }
  function esc(s) {
    return String(s === null || s === undefined ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function modelUrl(m) {
    if (m.u) return m.u;
    return "/model/" + encodeURIComponent(m.v) + "/" + encodeURIComponent(
      String(m.i).split(":")[0].split("/").slice(1).join("/").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
    ) + "/";
  }

  /* ---------------- mega table (/#models) ---------------- */
  var rowsEl = document.getElementById("rows");
  if (rowsEl && data) {
    var q = document.getElementById("q");
    var fFree = document.getElementById("f-free");
    var fVision = document.getElementById("f-vision");
    var fReason = document.getElementById("f-reason");
    var fLong = document.getElementById("f-long");
    var countEl = document.getElementById("count");
    var sortKey = "b", sortDir = 1;

    function view() {
      var term = (q && q.value || "").trim().toLowerCase();
      return data.filter(function (m) {
        if (fFree && fFree.checked && !(m.a === 0 && m.o === 0)) return false;
        if (fVision && fVision.checked && String(m.x || "").indexOf("image") === -1) return false;
        if (fReason && fReason.checked && !m.r) return false;
        if (fLong && fLong.checked && !(m.c >= 128000)) return false;
        if (!term) return true;
        return (m.n + " " + m.v + " " + m.i).toLowerCase().indexOf(term) !== -1;
      }).sort(function (a, b) {
        var x = a[sortKey], y = b[sortKey];
        if (typeof x === "string" || typeof y === "string") {
          return String(x || "").localeCompare(String(y || "")) * sortDir;
        }
        if (x === null || x === undefined) return 1;
        if (y === null || y === undefined) return -1;
        return (x - y) * sortDir;
      });
    }

    function render() {
      var list = view();
      var html = "";
      for (var k = 0; k < list.length; k++) {
        var m = list[k];
        var badges = "";
        if (m.a === 0 && m.o === 0) badges += '<span class="badge free">free</span>';
        if (m.r) badges += '<span class="badge">reasoning</span>';
        if (m.c >= 1000000) badges += '<span class="badge">1M ctx</span>';
        html += "<tr>" +
          '<td><a href="' + modelUrl(m) + '">' + esc(m.n) + "</a>" + badges + "</td>" +
          "<td>" + esc(m.v) + "</td>" +
          '<td class="num">' + fmtUSD(m.a, true) + "</td>" +
          '<td class="num">' + fmtUSD(m.o, true) + "</td>" +
          '<td class="num strong">' + fmtUSD(m.b, true) + "</td>" +
          '<td class="num">' + fmtCtx(m.c) + "</td>" +
          '<td class="num">' + (m.q || "—") + "</td>" +
          "</tr>";
      }
      rowsEl.innerHTML = html || '<tr><td colspan="7" class="muted">No models match those filters.</td></tr>';
      if (countEl) countEl.textContent = list.length + " of " + data.length + " models";
    }

    var heads = document.querySelectorAll("#allmodels th[data-sort]");
    Array.prototype.forEach.call(heads, function (th) {
      th.addEventListener("click", function () {
        var key = th.getAttribute("data-sort");
        if (sortKey === key) { sortDir = -sortDir; } else { sortKey = key; sortDir = 1; }
        Array.prototype.forEach.call(heads, function (o) { o.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", sortDir === 1 ? "ascending" : "descending");
        render();
      });
    });
    ["input", "change"].forEach(function (ev) {
      [q, fFree, fVision, fReason, fLong].forEach(function (el) {
        if (el) el.addEventListener(ev, render);
      });
    });
    render();
  }

  /* ---------------- cost calculator ---------------- */
  var calcRows = document.getElementById("calcrows");
  if (calcRows && data) {
    var elCalls = document.getElementById("calls");
    var elIn = document.getElementById("tin");
    var elOut = document.getElementById("tout");
    var elCache = document.getElementById("cache");
    var elDays = document.getElementById("days");
    var out = document.getElementById("calcout");

    function num(el, fallback) {
      var v = parseFloat(el && el.value);
      return isNaN(v) || v < 0 ? fallback : v;
    }

    function compute() {
      var calls = num(elCalls, 0), tin = num(elIn, 0), tout = num(elOut, 0);
      var cachePct = Math.min(num(elCache, 0), 95) / 100, days = num(elDays, 30) || 30;
      var inTok = calls * tin * days;
      var outTok = calls * tout * days;
      var rows = data.map(function (m) {
        var a = m.a === null || m.a === undefined ? null : m.a;
        var o = m.o === null || m.o === undefined ? null : m.o;
        if (a === null || o === null) return { m: m, cost: null };
        var cacheRate = (m.c === null || m.c === undefined) ? a : m.c;
        var cost = (inTok * (1 - cachePct) * a + inTok * cachePct * cacheRate + outTok * o) / 1e6;
        return { m: m, cost: cost };
      }).filter(function (r) { return r.cost !== null && isFinite(r.cost); })
        .sort(function (x, y) { return x.cost - y.cost; });

      var html = "";
      var top = rows.slice(0, 30);
      for (var i = 0; i < top.length; i++) {
        var r = top[i], m = r.m;
        html += "<tr>" +
          '<td class="num rank">' + (i + 1) + "</td>" +
          '<td><a href="' + modelUrl(m) + '">' + esc(m.n) + "</a></td>" +
          "<td>" + esc(m.v) + "</td>" +
          '<td class="num">' + fmtUSD(m.a, true) + "</td>" +
          '<td class="num">' + fmtUSD(m.o, true) + "</td>" +
          '<td class="num strong">' + fmtUSD(r.cost) + "</td>" +
          '<td class="num">' + (m.q || "—") + "</td>" +
          "</tr>";
      }
      calcRows.innerHTML = html || '<tr><td colspan="7" class="muted">Enter a volume above to see costs.</td></tr>';

      var cheapest = rows[0];
      var median = rows.length ? rows[Math.floor(rows.length / 2)] : null;
      var dearest = rows.length ? rows[rows.length - 1] : null;
      var monthlyTokens = inTok + outTok;
      if (out) {
        out.innerHTML = "Monthly volume: <strong>" + monthlyTokens.toLocaleString() +
          "</strong> tokens (" + Math.round(inTok).toLocaleString() + " in / " +
          Math.round(outTok).toLocaleString() + " out). Cheapest tracked option: <strong>" +
          (cheapest ? fmtUSD(cheapest.cost) : "—") + "</strong> with " +
          (cheapest ? esc(cheapest.m.n) : "—") + " · median model: <strong>" +
          (median ? fmtUSD(median.cost) : "—") + "</strong> · most expensive: <strong>" +
          (dearest ? fmtUSD(dearest.cost) : "—") + "</strong>.";
      }
    }
    [elCalls, elIn, elOut, elCache, elDays].forEach(function (el) {
      if (el) el.addEventListener("input", compute);
    });
    compute();
  }

  /* ---------------- ticker: cheapest model + biggest mover ---------------- */
  var ticker = document.getElementById("ticker");
  if (ticker && data) {
    var paid = data.filter(function (m) { return m.b && m.b > 0; });
    if (paid.length) {
      var cheap = paid.slice().sort(function (a, b) { return a.b - b.b; })[0];
      var best = data.filter(function (m) { return m.q; }).sort(function (a, b) { return b.q - a.q; })[0];
      ticker.innerHTML += ' · Cheapest blended: <strong>' + esc(cheap.n) + "</strong> at " +
        fmtUSD(cheap.b) + "/1M" +
        (best ? " · Highest published intelligence index: <strong>" + esc(best.n) + "</strong> (" + best.q + ")" : "");
    }
  }
})();
