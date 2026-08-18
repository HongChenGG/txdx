/**
 * profile.js — Fingerprint profile for jsdom.
 *
 * Captured from the REAL browser used for browser-path ticket issuance
 * (min_browser_pass.py Playwright + real Windows Chrome). This is the
 * critical alignment: the browser path PASSES on AppId 192037696, so jsdom
 * must reproduce THIS environment (Windows Chrome 151), not a macOS one.
 *
 * Source: capture/win_profile.json (capture_win_fp.py, 2026-08-09).
 */

"use strict";

const fs = require("fs");
const path = require("path");

function loadCanvasFp() {
  try {
    return fs.readFileSync(path.join(__dirname, "data", "canvas_fp.txt"), "utf8").trim();
  } catch (_) {
    return "";
  }
}

module.exports = {
  ua:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
    "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
  platform: "Win32",
  vendor: "Google Inc.",
  language: "zh-CN",
  languages: ["zh-CN", "zh"],
  hardwareConcurrency: 12,
  deviceMemory: 8, // Chrome hides deviceMemory on Windows; tdc falls back
  maxTouchPoints: 10,
  timezoneOffset: -480, // UTC+8
  timezoneName: "Asia/Shanghai",
  chromeVersion: 151,

  screen: {
    width: 1280,
    height: 900,
    availWidth: 1280,
    availHeight: 900,
    availLeft: 0,
    availTop: 0,
    colorDepth: 24,
    pixelDepth: 24,
    orientation: { type: "landscape-primary", angle: 0 },
  },

  viewport: {
    innerWidth: 1280,
    innerHeight: 900,
    outerWidth: 1296,
    outerHeight: 988,
    devicePixelRatio: 1,
  },

  // Real values from the actual ticketing browser (Windows Chrome 151, AMD GPU)。
  // 2026-08-15 evspec 实测（出票被接受的环境）：getParameter(37445/37446)：
  //   37445 UNMASKED_VENDOR_WEBGL   = "Google Inc. (AMD)"
  //   37446 UNMASKED_RENDERER_WEBGL = "ANGLE (AMD, AMD Radeon RX 5600 XT (0x0000731F) Direct3D11 vs_5_0 ps_5_0, D3D11)"
  // 旧值 SwiftShader = 软渲染/headless 特征，与 Chrome UA 矛盾 → ec=12 嫌疑。
  webgl: {
    vendor: "WebKit",
    renderer: "WebKit WebGL",
    version: "WebGL 1.0 (OpenGL ES 2.0 Chromium)",
    shadingLanguageVersion: "WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)",
    unmaskedVendor: "Google Inc. (AMD)",
    unmaskedRenderer:
      "ANGLE (AMD, AMD Radeon RX 5600 XT (0x0000731F) Direct3D11 vs_5_0 ps_5_0, D3D11)",
    // 2026-08-15 出票机实测（capture/webgl_exts_real.json，35 项）
    extensions: [
      "ANGLE_instanced_arrays",
      "EXT_blend_minmax",
      "EXT_clip_control",
      "EXT_color_buffer_half_float",
      "EXT_depth_clamp",
      "EXT_disjoint_timer_query",
      "EXT_float_blend",
      "EXT_frag_depth",
      "EXT_polygon_offset_clamp",
      "EXT_shader_texture_lod",
      "EXT_texture_compression_bptc",
      "EXT_texture_compression_rgtc",
      "EXT_texture_filter_anisotropic",
      "EXT_texture_mirror_clamp_to_edge",
      "EXT_sRGB",
      "KHR_parallel_shader_compile",
      "OES_element_index_uint",
      "OES_fbo_render_mipmap",
      "OES_standard_derivatives",
      "OES_texture_float",
      "OES_texture_float_linear",
      "OES_texture_half_float",
      "OES_texture_half_float_linear",
      "OES_vertex_array_object",
      "WEBGL_blend_func_extended",
      "WEBGL_color_buffer_float",
      "WEBGL_compressed_texture_s3tc",
      "WEBGL_compressed_texture_s3tc_srgb",
      "WEBGL_debug_renderer_info",
      "WEBGL_debug_shaders",
      "WEBGL_depth_texture",
      "WEBGL_draw_buffers",
      "WEBGL_lose_context",
      "WEBGL_multi_draw",
      "WEBGL_polygon_mode",
    ],
  },

  // Real Windows Chrome 151: 5 PDF plugins, 2 deduped mimeTypes.
  plugins: [
    {
      name: "PDF Viewer",
      filename: "internal-pdf-viewer",
      description: "Portable Document Format",
      mimes: [
        { type: "application/pdf", suffixes: "pdf" },
        { type: "text/pdf", suffixes: "pdf" },
      ],
    },
    {
      name: "Chrome PDF Viewer",
      filename: "internal-pdf-viewer",
      description: "Portable Document Format",
      mimes: [
        { type: "application/pdf", suffixes: "pdf" },
        { type: "text/pdf", suffixes: "pdf" },
      ],
    },
    {
      name: "Chromium PDF Viewer",
      filename: "internal-pdf-viewer",
      description: "Portable Document Format",
      mimes: [
        { type: "application/pdf", suffixes: "pdf" },
        { type: "text/pdf", suffixes: "pdf" },
      ],
    },
    {
      name: "Microsoft Edge PDF Viewer",
      filename: "internal-pdf-viewer",
      description: "Portable Document Format",
      mimes: [
        { type: "application/pdf", suffixes: "pdf" },
        { type: "text/pdf", suffixes: "pdf" },
      ],
    },
    {
      name: "WebKit built-in PDF",
      filename: "internal-pdf-viewer",
      description: "Portable Document Format",
      mimes: [
        { type: "application/pdf", suffixes: "pdf" },
        { type: "text/pdf", suffixes: "pdf" },
      ],
    },
  ],

  mimeTypes: [
    { type: "application/pdf", suffixes: "pdf" },
    { type: "text/pdf", suffixes: "pdf" },
  ],

  connection: {
    effectiveType: "4g",
    rtt: 0,
    downlink: 9.5,
    saveData: false,
  },

  // Real Windows Chrome: no runtime, loadTimes+csi+app present.
  chromeGlobal: {
    hasRuntime: false,
    hasLoadTimes: true,
    hasCsi: true,
    hasApp: true,
    appIsInstalled: false,
  },

  // Canvas fingerprint is the SAME painted sequence; data/canvas_fp.txt holds
  // the real render. Keep it (matches painting sequence in env_patch).
  canvasFingerprint: loadCanvasFp(),

  audio: {
    hashSample: 257.83077973115724,
    sampleAt5000: -0.3776991367340088,
  },
};