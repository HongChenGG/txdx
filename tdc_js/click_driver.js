/**
 * click_driver.js v2 — 滑块极简驱动骨架 + 真实验证码 DOM 复刻。
 *
 * 重放证据表明 tdc.js 会采集 DOM 相对坐标；因此驱动必须恢复真实 rect、
 * elementFromPoint、offsetX/Y 与 ClickEl mark 几何。服务端错误码语义不是公开契约，
 * 此处不再把 12/50 硬解释成某个单一失败原因。
 *
 * 本驱动：把已封装的真实验证码 DOM（data/click_dom_real.json）原样注入
 * jsdom，按捕获顺序给每个元素恢复真实 getBoundingClientRect，stub
 * elementFromPoint 做命中测试，事件派发到命中元素（target 与真实浏览器一致）。
 *
 * 输入(stdin JSON): {tdc_url, ua, sid, entry_url, clicks:[{x,y}...]}（页面级显示坐标）
 * 输出(stdout JSON): {collect(已decode), eks, tokenid, events}
 */
"use strict";

const fs = require("fs");
const path = require("path");
const { JSDOM } = require("jsdom");

// 完整 Chrome 环境指纹补丁（canvas 真指纹 + WebGL + plugins + fonts）
const envPatch = require("./env_patch");

const DOM_JSON = path.join(__dirname, "data", "click_dom_real.json");

// 滑块驱动同款 module70 50 项 feature 自算 ft
function computeFtJS() {
  function el(tag) { return document.createElement(tag); }
  function hist() { return "history" in window && "pushState" in history; }
  const f = [
    function () { return "matches" in el("div"); },
    function () { return "msMatchesSelector" in el("div"); },
    function () { return "webkitMatchesSelector" in el("div"); },
    function () { return !!(window.matchMedia && window.matchMedia("(min-width: 400px)") && window.matchMedia("(min-width: 400px)").matches); },
    function () { return !!(window.CSS && CSS.supports && CSS.supports("display", "block")); },
    function () { return !!document.createRange; },
    function () { return "CustomEvent" in window; },
    function () { return "scrollIntoView" in el("div"); },
    function () { return "getUserMedia" in navigator; },
    function () { return !!window.IntersectionObserver; },
    function () { return "ontouchstart" in el("div"); },
    function () { return "performance" in window; },
    function () { return !!window.performance && window.performance.timing; },
    function () { return "MediaSource" in window; },
    function () { return "onpageshow" in window; },
    function () { return "onhashchange" in window; },
    function () { return !!(window.requestFileSystem || window.webkitRequestFileSystem); },
    function () { return !!window.screen.orientation; },
    function () { return "WebSocket" in window; },
    function () { return true; },
    function () { return "FileReader" in window; },
    function () { return !!window.atob; },
    function () { return !!(window.JSON && JSON.parse); },
    function () { return "postMessage" in window; },
    function () { return "EventSource" in window; },
    function () { return "vibrate" in navigator; },
    function () { return "Promise" in window; },
    function () { return "setImmediate" in window; },
    function () { return "isInfinite" in Number; },
    function () { return "indexedDB" in window; },
    function () { return "Proxy" in window; },
    function () { return "serviceWorker" in navigator; },
    function () { return "postMessage" in window; },
    function () { return "Crypto" in window; },
    function () { return "openDatabase" in window; },
    function () { return "Notification" in window; },
    function () { return "currentScript" in document; },
    function () { var flag = false; if (typeof window.screenX === "number") { ["webkit", "moz", "ms", "o", ""].forEach(function (p) { var key = "".concat(p + (p ? "H" : "h"), "idden"); if (!flag && document[key] !== undefined) flag = true; }); } return flag; },
    function () { var b = false; try { b = "localStorage" in window && "setItem" in localStorage; } catch (e) { } return b; },
    function () { var b = false; try { b = "sessionStorage" in window && "setItem" in sessionStorage; } catch (e) { } return b; },
    function () { return "console" in window; },
    function () { return "requestAnimationFrame" in window; },
    function () { return "geolocation" in navigator; },
    function () { return "webkitSpeechRecognition" in window; },
    hist,
    function () { return "TextEncoder" in window; },
    hist,
    hist,
    function () { var b = false; try { new URL("/", "https://sv.aq.qq.com/").href === "https://sv.aq.qq.com/" && (b = true); } catch (e) { } return b; },
    function () { try { "a".localeCompare("b", "i"); } catch (e) { return "RangeError" === e.name; } return false; },
  ];
  const res = [];
  for (let i = 0; i < f.length; i++) res.push(f[i]());
  const bits = [];
  for (let k = 0; k < f.length; k++) { if (res[k]) { bits[Math.floor(k / 6)] = (bits[Math.floor(k / 6)] || 0) ^ (1 << (k % 6)); } }
  const A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
  const chars = [];
  for (let j = 0; j < bits.length; j++) chars[j] = A.charAt(bits[j] || 0);
  return chars.join("");
}

async function main() {
  let input = "";
  for await (const chunk of process.stdin) input += chunk;
  const {
    tdc_url, ua, sid, entry_url, clicks, debug, replay, tdc_local,
    debug_collectors, skip_events, collector_overrides,
  } = JSON.parse(input);

  // debug 模式：hook JSON.stringify 抓 mGetData 的明文源头 {cd, od, sd}（反汇编 fn34 实证）
  // ★ VMDUMP: stringify 时刻在 VM 运行内部 → __TENCENT_CHAOS_STACK 栈上有活引用，
  //   递归扫描栈槽抓全部 ≥16 字符的字符串（= cd 明文片段/采集器输出），供与真实浏览器 diff。
  let dbgStringify = null;
  if (debug) {
    dbgStringify = window => {
      const orig = window.JSON.stringify;
      window.JSON.stringify = function (v, r, s) {
        try {
          if (v && typeof v === "object" && "cd" in v && "sd" in v) {
            process.stderr.write("COLLECT_PLAIN:" + orig.call(window.JSON, v) + "\n");
            const S = window.__TENCENT_CHAOS_STACK;
            const found = [];
            const seen = new Set();
            const walk = (o, p, d) => {
              if (!o || d > 4 || seen.has(o) || found.length > 400) return;
              seen.add(o);
              if (typeof o === "string") { if (o.length >= 16) found.push(p + " => " + o.slice(0, 300)); return; }
              if (Array.isArray(o)) { for (let i = 0; i < Math.min(o.length, 200); i++) walk(o[i], p + "[" + i + "]", d + 1); return; }
              if (typeof o === "object") {
                for (const k of Object.getOwnPropertyNames(o).slice(0, 40)) {
                  try { walk(o[k], p + "." + k, d + 1); } catch (e) { }
                }
              }
            };
            try {
              process.stderr.write("VMSTACKLEN:" + (S ? S.length : -1) + "\n");
              for (let i = 0; i < S.length; i++) {
                try { walk(S[i], "S" + i, 0); } catch (e) { }
                try { walk(S[i][0], "S" + i + "[0]", 0); } catch (e) { }
              }
            } catch (e) { }
            process.stderr.write("VMDUMP:" + JSON.stringify(found) + "\n");
          }
        } catch (_) { }
        return orig.call(window.JSON, v, r, s);
      };
    };
  }

  if (!tdc_local || !fs.existsSync(tdc_local)) {
    throw new Error("tdc_local is required; Python must download TDC with the request proxy");
  }
  let code = fs.readFileSync(tdc_local, "utf8");
  if (debug_collectors) {
    const marker = /function __TENCENT_CHAOS_VM\(([^)]*)\)\{/;
    if (!marker.test(code)) throw new Error("TDC VM marker not found");
    code = code.replace(
      marker,
      (match, params) => `function __TENCENT_CHAOS_VM(${params}){try{(window.__vmEntries||(window.__vmEntries=[])).push(arguments[0])}catch(_){ }`
    );
  }

  // ★ 真实流程 tdc.js 跑在【业务页】里（TJCaptcha 2.0 无 iframe，直接注入主文档），
  // collect 内嵌 location = 业务页 origin。服务器用它交叉校验 entry_url/白名单域名。
  // jsdom 之前用 qcloud origin → collect location 与 entry_url 矛盾 → ec=12。
  const pageUrl = entry_url || "https://sssjz.guaishouyiyou.cn/#/pages/index";
  // referrer 留空：真实用户直开业务页，document.referrer=""（env_dump 实测）。
  const dom = new JSDOM("<!DOCTYPE html><html><head></head><body></body></html>", {
    url: pageUrl,
    contentType: "text/html", runScripts: "outside-only", pretendToBeVisual: true,
  });
  const { window } = dom;
  const { document } = window;

  // —— 环境补丁：完整 Chrome 指纹（canvas/webgl/plugins/fonts/mimeTypes）——
  // 真实合成出票 collect=1368 vs 极简 jsdom 1144，差值即环境指纹数据。
  envPatch.apply(window);

  // —— 对齐出票浏览器真实环境（capture/env_dump.json 2026-08-15 实测，覆盖 env_patch 差异）——
  Object.defineProperty(window.navigator, "userAgent", { get: () => ua, configurable: true });
  Object.defineProperty(window.navigator, "platform", { get: () => "Win32", configurable: true });
  Object.defineProperty(window.navigator, "language", { get: () => "zh-CN", configurable: true });
  Object.defineProperty(window.navigator, "languages", { get: () => ["zh-CN", "zh"], configurable: true });
  Object.defineProperty(window.navigator, "hardwareConcurrency", { get: () => 12, configurable: true });
  Object.defineProperty(window.navigator, "deviceMemory", { get: () => null, configurable: true }); // 真实 Chrome http 页 = null
  Object.defineProperty(window.navigator, "maxTouchPoints", { get: () => 10, configurable: true });
  Object.defineProperty(window.navigator, "vendor", { get: () => "Google Inc.", configurable: true });
  Object.defineProperty(window.navigator, "onLine", { get: () => true, configurable: true });
  Object.defineProperty(window, "screenX", { get: () => 10, configurable: true });
  Object.defineProperty(window, "screenY", { get: () => 10, configurable: true });
  // 真实 Chrome：Notification 存在且 permission="denied"（env_dump 实测）
  if (!window.Notification) {
    function Notification(title, opts) { void title; void opts; }
    Notification.permission = "denied";
    Notification.requestPermission = () => Promise.resolve("denied");
    Notification.maxActions = 2;
    window.Notification = Notification;
  }
  // document.hasFocus → true（jsdom 默认 false，"全程未聚焦"= 可疑信号，env_dump 实测真实=true）
  try { document.hasFocus = () => true; } catch (e) { }
  Object.defineProperty(window, "innerWidth", { get: () => 1280 });
  Object.defineProperty(window, "innerHeight", { get: () => 900 });
  Object.defineProperty(window, "outerWidth", { get: () => 1296 });
  Object.defineProperty(window, "outerHeight", { get: () => 988 });
  Object.defineProperty(window, "devicePixelRatio", { get: () => 1 });
  Object.defineProperty(window.screen, "width", { get: () => 1280 });
  Object.defineProperty(window.screen, "height", { get: () => 900 });
  Object.defineProperty(window.screen, "availWidth", { get: () => 1280 });
  Object.defineProperty(window.screen, "availHeight", { get: () => 900 });
  Object.defineProperty(window.screen, "colorDepth", { get: () => 24 });
  // ★ 2.0 主文档流实测（2026-08-15 出票页验证）：window.name=""，
  //   TCaptchaSid / TCaptchaReferrer / TCaptchaIframeClientPos 全部 UNDEFINED。
  //   注入这些 1.0 iframe 时代全局会让 tdc 走 iframe 分支，collect 出现服务器
  //   明知不该有的字段 → ec=12。（滑块能过是因其校验宽松，不代表这些该设。）
  try { window.name = ""; } catch (e) { }

  // ★ 栈洗白（生产必备）：模块59(fn281) init 时故意 throw "errr" 自测，把自身调用栈
  //   (fn285 处理: 去at/换行, 切100字符) 嵌进 collect。Chrome 栈帧 =
  //   "at fn (https://turing.captcha.qcloud.com/tdc.js:2:12345)"；jsdom window.eval 的
  //   V8 栈帧泄露本机文件路径 → 服务器直接识破。V8 的 Error.prepareStackTrace 在
  //   .stack 读取时触发 → 把所有帧统一重写成 tdc.js URL 格式。
  const TDC_SRC = "https://turing.captcha.qcloud.com/tdc.js";
  const sanitizeStack = (e, frames) => {
    const lines = frames.map((f) => {
      let fn = "", ln = 2, col = 1;
      try { fn = f.getFunctionName() || ""; } catch (_) { }
      try { ln = f.getLineNumber() || 2; } catch (_) { }
      try { col = f.getColumnNumber() || 1; } catch (_) { }
      return "    at " + (fn ? fn + " (" : "(") + TDC_SRC + ":" + ln + ":" + col + ")" + (fn ? "" : "");
    });
    return (e && e.name ? e.name + ": " : "") + (e || "") + "\n" + lines.join("\n");
  };
  Error.prepareStackTrace = sanitizeStack;

  // debug_collectors: mInit 会把带 get() 的采集器 push 进内部列表。
  // 在初始化边界用 Proxy 包住 get()，直接记录 mGetData 加密前的每个 cd 片段。
  // Proxy 的 Function#toString 仍呈 native-code 形态；TDC 就绪后立即恢复 Array#push。
  const collectorCalls = [];
  const collectorRegs = [];
  let restoreArrayPush = null;
  if (debug_collectors) {
    const originalPush = window.Array.prototype.push;
    const wrapped = new WeakMap();
    let nextCollectorId = 0;
    const snapshot = (value, depth = 0, seen = new WeakSet()) => {
      if (value === undefined) return { __type: "undefined" };
      if (value === null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") return value;
      if (typeof value === "function") return { __type: "function", name: value.name || "" };
      if (depth >= 5) return { __type: "depth-limit" };
      if (typeof value === "object") {
        if (seen.has(value)) return { __type: "circular" };
        seen.add(value);
        if (Array.isArray(value)) return value.map((v) => snapshot(v, depth + 1, seen));
        const out = {};
        for (const k of Object.getOwnPropertyNames(value).slice(0, 60)) {
          try { out[k] = snapshot(value[k], depth + 1, seen); }
          catch (e) { out[k] = { __type: "error", message: String(e && e.message || e) }; }
        }
        return out;
      }
      return String(value);
    };
    const pushProxy = new Proxy(originalPush, {
      apply(target, thisArg, args) {
        for (const item of args) {
          if (!item || typeof item !== "object" || typeof item.get !== "function" || wrapped.has(item)) continue;
          const id = nextCollectorId++;
          const originalGet = item.get;
          const getProxy = new Proxy(originalGet, {
            apply(getTarget, getThis, getArgs) {
              const entries = window.__vmEntries || [];
              const entryStart = entries.length;
              const actual = Reflect.apply(getTarget, getThis, getArgs);
              const override = collector_overrides && Object.prototype.hasOwnProperty.call(collector_overrides, String(id))
                ? collector_overrides[String(id)]
                : actual;
              collectorCalls.push({
                id,
                entries: entries.slice(entryStart),
                actual: snapshot(actual),
                value: snapshot(override),
              });
              return override;
            },
          });
          try {
            Object.defineProperty(item, "get", { value: getProxy, writable: true, configurable: true });
            wrapped.set(item, id);
            collectorRegs.push({
              id,
              keys: Object.getOwnPropertyNames(item),
              hasOn: typeof item.on === "function",
              hasReset: typeof item.reset === "function",
              getName: originalGet.name || "",
              getLength: originalGet.length,
              getSource: String(originalGet).slice(0, 500),
              onSource: typeof item.on === "function" ? String(item.on).slice(0, 500) : "",
            });
          } catch (_) {}
        }
        return Reflect.apply(target, thisArg, args);
      },
    });
    window.Array.prototype.push = pushProxy;
    restoreArrayPush = () => { window.Array.prototype.push = originalPush; };
  }

  // ★ 时序修复（2026-08-15 JSVMP 反汇编实证 sfn39970）：
  //   tdc.js eval 时 mInit → on() 选绑定目标：
  //     inIframe() ? document
  //     : (getElementById("tCaptchaDyContent") || document)   ← 弹窗存在则绑弹窗!
  //   真实浏览器：tdc.js 随页面加载先 eval（弹窗未创建）→ 绑定 document，
  //   全页 mousemove（含 mask-layer 热身）都被采集（COLLECT_SPEC §2 铁证：
  //   "tdc.js 自己挂 document 级监听"）。
  //   旧版先注 DOM 后 eval → 绑到 tCaptchaDyContent → 弹窗外 ambient 移动全丢。
  // 故：先 eval（绑定 document），再注入弹窗 DOM（真实顺序）。
  // The real widget injects tdc.js asynchronously after the host page has
  // already completed its load event. If jsdom evaluates it while still
  // loading, TDC observes jsdom's pending load and records a synthetic delay.
  if (document.readyState !== "complete") {
    await new Promise((resolve) => window.addEventListener("load", resolve, { once: true }));
  }
  if (dbgStringify) dbgStringify(window);
  window.eval(code);
  if (restoreArrayPush) restoreArrayPush();
  if (!window.TDC) { process.stderr.write("NO TDC"); process.exit(1); }

  // —— 注入真实验证码 DOM + 恢复每个元素的真实 rect（eval 之后 = 弹窗后创建）——
  const cap = JSON.parse(fs.readFileSync(DOM_JSON, "utf-8"));
  document.body.innerHTML = cap.html;

  // 按捕获时的同序遍历（body 下 captcha 相关子级 × [self + descendants]）配对 rect
  const kids = [...document.body.children].filter((e) => {
    const s = (e.className || "") + " " + (e.id || "");
    return /captcha|tcap|turing/i.test(s);
  });
  const els = [];
  for (const k of kids) for (const e of [k, ...k.querySelectorAll("*")]) els.push(e);

  const rectMap = new Map();
  const rectList = [];
  els.forEach((e, i) => {
    const r = cap.rects[i];
    if (!r) return;
    const rect = {
      x: r.rect.x, y: r.rect.y, width: r.rect.w, height: r.rect.h,
      top: r.rect.top, left: r.rect.left, right: r.rect.right, bottom: r.rect.bottom,
      toJSON() { return { ...this, toJSON: undefined }; },
    };
    rectMap.set(e, rect);
    if (r.rect.w > 0 && r.rect.h > 0) rectList.push({ el: e, rect });
  });

  // 全元素 getBoundingClientRect → 真实捕获值（父类原型打补丁，未捕获元素回退全 0）
  const ElemProto = window.Element.prototype;
  ElemProto.getBoundingClientRect = function () {
    const r = rectMap.get(this);
    if (r) return r;
    return { x: 0, y: 0, width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0, toJSON: function () { return this; } };
  };

  // ★ clientWidth/clientHeight：sfn25087 反编译实证 —— 主文档流采集器读
  //   getElementById("tCaptchaDyContent").clientWidth/clientHeight 进 collect。
  //   jsdom 无布局恒 0 → cd 内弹窗尺寸字段与真实 Chrome(360×401) 矛盾。
  Object.defineProperty(ElemProto, "clientWidth", {
    get() { const r = rectMap.get(this); return r ? Math.round(r.width) : 0; }, configurable: true,
  });
  Object.defineProperty(ElemProto, "clientHeight", {
    get() { const r = rectMap.get(this); return r ? Math.round(r.height) : 0; }, configurable: true,
  });

  // elementFromPoint：DOM 序最后命中（无定位弹窗的绘制顺序 = DOM 顺序，后者在上层）。
  // 实测真实点击 target = verify-bg-img DIV（图像区最后绘制的元素）。
  document.elementFromPoint = function (x, y) {
    let best = null;
    for (const { el, rect } of rectList) {
      if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
        best = el; // 覆盖式：取最后一个 = 最上层
      }
    }
    return best;
  };

  // ★ 核心修复：tdc 行为采集读 e.offsetX/e.offsetY（相对 e.target 的坐标）。
  // 真实浏览器：offsetX = clientX - target.rect.left（如点击(597,372)→122,77）。
  // jsdom 默认 offsetX=clientX（不减 target 位置）→ 坐标偏差 475/295 → ec=12。
  const ME = window.MouseEvent.prototype;
  Object.defineProperty(ME, "offsetX", {
    get() {
      const t = this.target;
      const r = t && rectMap.get(t);
      const x = typeof this.__pointerX === "number" ? this.__pointerX : this.clientX;
      return Math.round(x - (r ? r.left : 0));
    },
    configurable: true,
  });
  Object.defineProperty(ME, "offsetY", {
    get() {
      const t = this.target;
      const r = t && rectMap.get(t);
      const y = typeof this.__pointerY === "number" ? this.__pointerY : this.clientY;
      return Math.round(y - (r ? r.top : 0));
    },
    configurable: true,
  });

  // —— 事件派发器：目标元素直发（target 与真实浏览器一致），bubbles 冒泡到 document ——
  // 对齐真实出票样本 capture/evspec/pass_*：screenX=x+18, screenY=y+97（窗口偏移）。
  // tgJCap ClickEl.addNewMark：markSize=32，显示尺寸=markSize*getRate()；
  // getRate()=targetWidth/360，因此当前 330px 背景上的 mark 是 29.333px。
  // 后续 mousemove 命中 mark 时，TDC 会记录 mark-local offsetX/Y。
  const markSize = 32;
  const renderedMarkSize = markSize * Math.min(1, 330 / 360);
  const addMark = (x, y) => {
    const m = document.createElement("div");
    m.className = "tencent-captcha-dy__click-mark";
    document.body.appendChild(m);
    const left = x - renderedMarkSize / 2;
    const top = y - renderedMarkSize / 2;
    const rect = {
      x: left, y: top, width: renderedMarkSize, height: renderedMarkSize,
      top, left, right: left + renderedMarkSize, bottom: top + renderedMarkSize,
      toJSON() { return { ...this, toJSON: undefined }; },
    };
    rectMap.set(m, rect);
    rectList.push({ el: m, rect });
  };

  const dispatchedEvents = [];
  const fire = (type, x, y, ts) => {
    // Chromium quantizes Playwright mouse coordinates to integer clientX/Y.
    const pointerX = x;
    const pointerY = y;
    x = Math.round(x);
    y = Math.round(y);
    const target = document.elementFromPoint(pointerX, pointerY) || document;
    const evt = new window.MouseEvent(type, {
      clientX: x, clientY: y, bubbles: true, cancelable: true, composed: true,
      view: window, button: 0, buttons: type === "mousedown" ? 1 : 0,
      screenX: x + 18, screenY: y + 97,
    });
    // Preserve the subpixel pointer for Chrome-like offsetX/Y quantization.
    try { Object.defineProperty(evt, "__pointerX", { value: pointerX }); } catch (e) { }
    try { Object.defineProperty(evt, "__pointerY", { value: pointerY }); } catch (e) { }
    // jsdom 忽略 init 字典的 timeStamp（返回墙钟时间）；真实 Chrome = 页面年龄高精度值。
    try { Object.defineProperty(evt, "timeStamp", { value: ts }); } catch (e) { }
    target.dispatchEvent(evt);
    dispatchedEvents.push({
      type, x, y,
      offsetX: evt.offsetX,
      offsetY: evt.offsetY,
      target: target === document ? "#document" : String(target.className || target.tagName || ""),
    });
  };

  // —— tdc 生命周期：真实页面加载后数秒才交互。立即开打 = 时间轴异常。 ——
  await new Promise((r) => setTimeout(r, 1200 + Math.floor(Math.random() * 800)));

  // ★ debug 探针：反编译实证 mouseMoveEvent 记录每个点调 Math.max(0, offsetX/offsetY)，
  //   hook 之 = 直接看到 tdc 实际记录的 (x,y) 序列（offsetX/Y 相对 e.target）。
  let maxLog = null;
  if (debug) {
    maxLog = [];
    const omax = window.Math.max;
    window.Math.max = function () {
      if (arguments.length === 2 && arguments[0] === 0 && typeof arguments[1] === "number") {
        maxLog.push([arguments[1], Date.now()]);
      }
      return omax.apply(window.Math, arguments);
    };
    // ★ 错误通道探针：模块59(fn275/fn285) 把采集器异常的 e.stack(切100字符)嵌进 collect。
    //   包一层日志再委托给洗白器（保持生产栈格式一致）。
    const errLog = [];
    const sanit = Error.prepareStackTrace;
    Error.prepareStackTrace = (e, frames) => {
      try {
        errLog.push(String(e && e.message || e).slice(0, 120) + " @@ " +
          (frames[1] ? String(frames[1].getFunctionName() || frames[1].getFileName()) : "?"));
      } catch (_) { }
      return sanit(e, frames);
    };
    process.on("exit", () => {
      if (errLog.length) process.stderr.write("ERRLOG:" + JSON.stringify(errLog.slice(0, 40)) + "\n");
    });
  }

  // —— replay 模式：原样回放真实浏览器抓到的事件流（evspec events.json）——
  // 行为段与真实出票逐字节一致 → 消除轨迹形状变量，隔离环境差异。
  if (skip_events) {
    // Collector-only fixed vector: keep behavior stream empty.
  } else if (replay && replay.length) {
    let prevTs = replay[0].ts;
    for (let ri = 0; ri < replay.length; ri++) {
      const ev = replay[ri];
      const dt = Math.max(0, ev.ts - prevTs);
      prevTs = ev.ts;
      if (dt > 0) await new Promise((r) => setTimeout(r, Math.min(dt, 2500)));
      fire(ev.t, ev.x, ev.y, ev.ts);
      // 非最后一位 click = 字点击 → 注入 mark（真实 widget 行为）
      if (ev.t === "click" && replay.some((e2, j2) => j2 > ri && e2.t === "click")) {
        addMark(ev.x, ev.y);
      }
    }
  } else {

  // —— ambient：读题热身（真实样本：4+ 个 mask 层 mousemove 进入弹窗）——
  // timeStamp 基准 = 真实 performance.now()：真实浏览器 e.timeStamp ≈ 派发时刻的
  // performance.now()（页面年龄）。伪造固定值会与 tdc 自身时钟矛盾。
  let t = window.performance.now();
  let ambientX = 99, ambientY = 69;
  {
    for (let i = 0; i < 4; i++) {
      ambientX += 90 + Math.floor(Math.random() * 30);
      ambientY += 60 + Math.floor(Math.random() * 20);
      fire("mousemove", ambientX, ambientY, t);
      t += 6 + Math.floor(Math.random() * 4);
      await new Promise((r) => setTimeout(r, 6));
    }
  }

  // —— 事件流 ——
  let cx = ambientX, cy = ambientY;

  for (let ci = 0; ci < clicks.length; ci++) {
    const c = clicks[ci];
    const tx = Math.round(c.x * 10) / 10, ty = Math.round(c.y * 10) / 10;
    const steps = ci === 0 ? 6 : (ci === clicks.length - 1 ? 4 : 3);
    for (let i = 1; i <= steps; i++) {
      const p = i / steps;
      t += 6;
      fire("mousemove", Math.round(cx + (tx - cx) * p), Math.round(cy + (ty - cy) * p), t);
      await new Promise((r) => setTimeout(r, 6));
    }
    cx = tx; cy = ty;
    t += 170;
    await new Promise((r) => setTimeout(r, 170));
    fire("mousedown", tx, ty, t);
    t += 60 + Math.floor(Math.random() * 60); // 按住 60-120ms（真实 95-125）
    await new Promise((r) => setTimeout(r, 70));
    fire("mouseup", tx, ty, t);
    fire("click", tx, ty, t);
    if (ci !== clicks.length - 1) {
      addMark(tx, ty); // 字点击后渲染 mark（最后一位是确认键，无 mark）
      t += 180 + Math.floor(Math.random() * 240); // 真实样本约 180–420ms
      await new Promise((r) => setTimeout(r, 300));
    }
  }

  } // end else (非 replay)

  // —— ft 注入 + getData（真实流程顺序）——
  // 真实出票流程 setData 全量 = [{"ft":"6X_7Pb__H"}]（真 Chrome 位图，evspec 实测）。
  // jsdom 自算 ft 描述的是 jsdom 缺失环境，与 Chrome UA 矛盾 → ec=12。
  try { window.TDC.setData({ ft: "6X_7Pb__H" }); } catch (e) { }

  const raw = window.TDC.getData(true) || "";
  const collect = decodeURIComponent(raw);
  if (maxLog && maxLog.length) {
    process.stderr.write("MAXLOG:" + JSON.stringify(maxLog) + "\n");
  }
  const info = window.TDC.getInfo() || {};
  process.stdout.write(JSON.stringify({
    collect, eks: info.info || "", tokenid: String(info.tokenid || ""),
    collectors: debug_collectors ? collectorCalls : undefined,
    collector_regs: debug_collectors ? collectorRegs : undefined,
    events: dispatchedEvents,
  }));
  window.close();
}

main().catch((e) => { process.stderr.write(String(e && e.stack || e)); process.exit(1); });
