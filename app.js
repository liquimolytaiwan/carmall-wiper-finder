(function () {
  "use strict";
  var DATA = null;
  var elBrand = document.getElementById("sel-brand");
  var elModel = document.getElementById("sel-model");
  var elYear  = document.getElementById("sel-year");
  var elResult = document.getElementById("result");

  function opt(value, label) {
    var o = document.createElement("option");
    o.value = value; o.textContent = label;
    return o;
  }
  function clearSelect(sel, placeholder) {
    sel.innerHTML = "";
    sel.appendChild(opt("", placeholder));
  }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]; }); }

  // ---- load data ----
  fetch("data.json", { cache: "no-cache" })
    .then(function (r) { if(!r.ok) throw new Error("data load "+r.status); return r.json(); })
    .then(function (d) {
      DATA = d;
      clearSelect(elBrand, "請選擇車廠");
      d.brands.forEach(function (b) { elBrand.appendChild(opt(b.name, b.name)); });
      postHeight();
    })
    .catch(function (e) {
      elResult.hidden = false;
      elResult.innerHTML = '<div class="rc"><div class="state"><h3>查詢系統載入失敗</h3><p>請稍後重新整理頁面，或直接洽詢客服</p></div></div>';
      postHeight();
    });

  // ---- cascade ----
  elBrand.addEventListener("change", function () {
    elResult.hidden = true; elResult.innerHTML = "";
    clearSelect(elModel, "請選擇車款");
    clearSelect(elYear, "請先選擇車款");
    elYear.disabled = true;
    var b = findBrand(elBrand.value);
    if (!b) { elModel.disabled = true; postHeight(); return; }
    b.models.forEach(function (m) { elModel.appendChild(opt(m.name, m.name)); });
    elModel.disabled = false;
    postHeight();
  });

  elModel.addEventListener("change", function () {
    elResult.hidden = true; elResult.innerHTML = "";
    clearSelect(elYear, "請選擇年份 / 車型");
    var m = findModel(elBrand.value, elModel.value);
    if (!m) { elYear.disabled = true; postHeight(); return; }
    m.entries.forEach(function (e, i) { elYear.appendChild(opt(String(i), e.label)); });
    elYear.disabled = false;
    postHeight();
  });

  elYear.addEventListener("change", function () {
    var m = findModel(elBrand.value, elModel.value);
    if (!m || elYear.value === "") { elResult.hidden = true; postHeight(); return; }
    render(m.entries[parseInt(elYear.value, 10)], m.name);
  });

  function findBrand(n){ return DATA.brands.filter(function(b){return b.name===n;})[0]; }
  function findModel(bn, mn){ var b=findBrand(bn); return b ? b.models.filter(function(m){return m.name===mn;})[0] : null; }

  // ---- render result ----
  function render(e, modelName) {
    var brand = elBrand.value;
    var head = '<div class="rc-top"><div class="rc-veh">' + esc(brand + " " + modelName) +
      '<small>' + esc(e.label) + '</small></div></div>';

    if (e.fit === "dedicated") {
      elResult.innerHTML = '<div class="rc">' + head +
        '<div class="state">' + iconWrench() +
        '<h3>此車型前擋需使用「專用型雨刷」</h3>' +
        '<p>原廠通用型雨刷不適用於此車型。<br>專用型雨刷即將推出，或請洽客服協助選購</p>' +
        '</div></div>';
      elResult.hidden = false; postHeight(); return;
    }

    var sizesHtml = '<div class="sizes">' +
      sizeBox("駕駛座", e.driver) +
      sizeBox("乘客座", e.passenger) +
      '</div>';

    var body = sizesHtml + optionsHtml(e) + rearHtml(e);
    elResult.innerHTML = '<div class="rc">' + head + '<div class="rc-body">' + body + '</div></div>';
    elResult.hidden = false; postHeight();
  }

  function sizeBox(role, size) {
    return '<div class="size"><b>' + esc(size) + '<span class="unit">吋</span></b>' +
      '<span>' + role + '</span></div>';
  }

  function optionsHtml(e) {
    var opts = e.options || [];
    if (!opts.length) {
      return '<div class="note">' + iconAlert() +
        '<span>此車所需尺寸（' + e.driver + '吋 / ' + e.passenger +
        '吋）目前無現貨，請洽客服協助訂購</span></div>';
    }
    var cards = opts.map(function (o) { return optionCard(o, e); }).join("");
    return '<div class="opt-title">雨刷選擇　<span>共 ' + opts.length + ' 款，點選前往購買</span></div>' + cards;
  }

  function optionCard(o, e) {
    var matTag = '<span class="tag tag-mat">' + esc(o.material) + '</span>';
    var kindTag, sub;
    if (o.kind === "combo") {
      kindTag = '<span class="tag tag-combo">2支/組</span>';
      sub = '已配好 ' + e.driver + '吋＋' + e.passenger + '吋，一次購足';
    } else {
      kindTag = '<span class="tag tag-single">單支自選</span>';
      sub = o.driver + '吋 $' + o.driverPrice + '　＋　' + o.passenger + '吋 $' + o.passengerPrice + '（共 2 支）';
    }
    return '<a class="opt" href="' + esc(o.url) + '" target="_blank" rel="noopener">' +
      '<div class="opt-main"><div class="opt-name">' + esc(o.label) + matTag + kindTag + '</div>' +
      '<div class="opt-sub">' + sub + '</div></div>' +
      '<div class="opt-right"><div class="opt-price">$' + o.price + '</div>' + cart() + '</div></a>';
  }

  function rearHtml(e) {
    if (!e.rear) return "";
    return '<div class="note">' + iconInfo() +
      '<span>此車另有後擋雨刷（' + esc(e.rear) + '）。本商品為前擋通用型，後擋為專用規格，如需後擋雨刷請洽客服</span></div>';
  }

  // ---- icons ----
  function cart(){ return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.7 13.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6"/></svg>'; }
  function iconWrench(){ return '<svg class="ico" viewBox="0 0 24 24" fill="none" stroke="#2b2b6e" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.3 2.3-2.7-.7-.7-2.7z"/></svg>'; }
  function iconAlert(){ return '<svg viewBox="0 0 24 24" fill="none" stroke="#b9892b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;flex:0 0 auto;margin-top:1px"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12" y2="17"/></svg>'; }
  function iconInfo(){ return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="8"/></svg>'; }

  // ---- iframe auto-height ----
  function postHeight(){
    try {
      var h = document.documentElement.scrollHeight;
      parent.postMessage({ type: "carmallWiperHeight", height: h }, "*");
    } catch (e) {}
  }
  window.addEventListener("load", postHeight);
  if (window.ResizeObserver) { new ResizeObserver(postHeight).observe(document.body); }
})();
