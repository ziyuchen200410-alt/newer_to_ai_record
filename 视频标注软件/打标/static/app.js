const datasetPathInput = document.querySelector("#datasetPathInput");
const loadBtn = document.querySelector("#loadBtn");
const refVideo = document.querySelector("#refVideo");
const srcVideo = document.querySelector("#srcVideo");
const refPathNode = document.querySelector("#refPath");
const srcPathNode = document.querySelector("#srcPath");
const goodBtn = document.querySelector("#goodBtn");
const badBtn = document.querySelector("#badBtn");
const sampleCounter = document.querySelector("#sampleCounter");
const statusNode = document.querySelector("#status");
const playbackState = document.querySelector("#playbackState");
const timeInfo = document.querySelector("#timeInfo");
const syncInfo = document.querySelector("#syncInfo");
const instructionList = document.querySelector("#instructionList");
const tagBadge = document.querySelector("#tagBadge");
const speedButtons = document.querySelectorAll(".speed");
const goodSizeRow = document.querySelector("#goodSizeRow");
const largeBtn = document.querySelector("#largeBtn");
const smallBtn = document.querySelector("#smallBtn");

const videos = [refVideo, srcVideo];
const PATH_STORAGE_KEY = "absolute_label_dataset_path";
const SYNC_TOLERANCE_SECONDS = 0.04;
const maskImage = document.querySelector("#maskImage");
const maskFallback = document.querySelector("#maskFallback");

const state = {
  datasetPath: "",
  outputPath: "",
  goodPath: "",
  goodWithSizePath: "",
  scriptPath: "",
  selectedObjectSize: "",
  items: [],
  index: 0,
  apiBase: "",
  lastApiUrl: "",
  playbackRate: 1,
  isPlaying: false,
  loadingToken: 0,
  isInternalSeek: false,
  rafId: 0,
};

function basePath() {
  const p = window.location.pathname || "/";
  if (p.endsWith("/")) {
    return p;
  }
  const idx = p.lastIndexOf("/");
  return idx >= 0 ? p.slice(0, idx + 1) : "/";
}

function normalizedBase(base) {
  let value = base || "/";
  if (!value.endsWith("/")) {
    value += "/";
  }
  return `${window.location.origin}${value}`;
}

function candidateApiBases() {
  const candidates = new Set();
  candidates.add(normalizedBase(basePath()));
  candidates.add(normalizedBase("/"));
  return Array.from(candidates);
}

async function discoverApiBase() {
  const tried = [];
  for (const base of candidateApiBases()) {
    const url = `${base}api/health`;
    tried.push(url);
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) {
        continue;
      }
      const text = await response.text();
      if (!text) {
        continue;
      }
      const payload = JSON.parse(text);
      if (payload && payload.ok === true) {
        return base;
      }
    } catch {
      // continue to next candidate
    }
  }
  throw new Error(`无法探测可用 API 基址。已尝试: ${tried.join(" , ")}`);
}

function apiUrl(path) {
  const normalized = path.startsWith("/") ? path.slice(1) : path;
  const base = state.apiBase || normalizedBase(basePath());
  return `${base}${normalized}`;
}

async function fetchJson(url, options) {
  state.lastApiUrl = url;
  const response = await fetch(url, options);
  const text = await response.text();
  let payload = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { raw_text: text };
    }
  }
  if (!response.ok) {
    const detail = payload.error || payload.message || (typeof payload.raw_text === "string" ? payload.raw_text.slice(0, 220) : "");
    throw new Error(`请求失败(${response.status}): ${detail || "服务端未返回错误详情"}`);
  }
  return payload;
}

function currentItem() {
  return state.items[state.index] || null;
}

function setStatus(text) {
  statusNode.textContent = text;
}

function renderVideoPaths(refPath, srcPath) {
  if (refPathNode) {
    refPathNode.textContent = refPath || "-";
    refPathNode.title = refPath || "";
  }
  if (srcPathNode) {
    srcPathNode.textContent = srcPath || "-";
    srcPathNode.title = srcPath || "";
  }
}

function normalizeObjectSize(value) {
  if (!value) {
    return "";
  }
  const text = String(value).trim().toLowerCase();
  if (["large", "big", "大", "大物体"].includes(text)) {
    return "large";
  }
  if (["small", "tiny", "小", "小物体"].includes(text)) {
    return "small";
  }
  return "";
}

function renderObjectSizeControls(item) {
  const required = !!item?.requires_good_size_tag;
  if (!goodSizeRow) {
    return;
  }

  if (!required) {
    goodSizeRow.classList.add("hidden");
    state.selectedObjectSize = normalizeObjectSize(item?.object_size);
    return;
  }

  goodSizeRow.classList.remove("hidden");
  const fromItem = normalizeObjectSize(item?.object_size);
  if (fromItem) {
    state.selectedObjectSize = fromItem;
  }
  if (!fromItem && !["large", "small"].includes(state.selectedObjectSize)) {
    state.selectedObjectSize = "";
  }

  const isLarge = state.selectedObjectSize === "large";
  const isSmall = state.selectedObjectSize === "small";
  largeBtn?.classList.toggle("active", isLarge);
  smallBtn?.classList.toggle("active", isSmall);
}

function formatSpeed(speed) {
  return Number.isInteger(speed) ? `${speed}x` : `${speed.toFixed(1)}x`;
}

function applyRate(speed) {
  state.playbackRate = speed;
  for (const video of videos) {
    video.playbackRate = speed;
    video.defaultPlaybackRate = speed;
  }
  for (const btn of speedButtons) {
    const active = Number(btn.dataset.speed) === speed;
    btn.classList.toggle("active", active);
  }
  updatePlaybackInfo();
}

function renderInstructions(list) {
  instructionList.innerHTML = "";
  const values = Array.isArray(list) ? list : [];
  values.slice(0, 4).forEach((text, idx) => {
    const li = document.createElement("li");
    li.textContent = `${idx + 1}. ${text}`;
    instructionList.append(li);
  });
  if (!values.length) {
    const li = document.createElement("li");
    li.textContent = "该样本没有可展示的指令字段。";
    instructionList.append(li);
  }
}

function renderTag(tag, objectSize = "") {
  tagBadge.className = "badge";
  if (tag === "good" || tag === "bad") {
    tagBadge.classList.add(tag);
    if (tag === "good") {
      const size = normalizeObjectSize(objectSize);
      if (size === "large") {
        tagBadge.textContent = "GOOD · 大物体";
        return;
      }
      if (size === "small") {
        tagBadge.textContent = "GOOD · 小物体";
        return;
      }
    }
    tagBadge.textContent = tag.toUpperCase();
    return;
  }
  tagBadge.classList.add("pending");
  tagBadge.textContent = "未标注";
}

function resetVideos() {
  state.isPlaying = false;
  for (const video of videos) {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
  updatePlaybackInfo();
}

function waitReady(video, token) {
  return new Promise((resolve, reject) => {
    if (token !== state.loadingToken) {
      reject(new Error("样本已切换，取消当前加载"));
      return;
    }
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
      resolve();
      return;
    }

    const cleanup = () => {
      video.removeEventListener("loadeddata", onReady);
      video.removeEventListener("canplay", onReady);
      video.removeEventListener("error", onError);
    };

    const onReady = () => {
      cleanup();
      resolve();
    };

    const onError = () => {
      cleanup();
      reject(new Error(`视频加载失败: ${video.currentSrc || video.src}`));
    };

    video.addEventListener("loadeddata", onReady, { once: true });
    video.addEventListener("canplay", onReady, { once: true });
    video.addEventListener("error", onError, { once: true });
  });
}

function syncVideoTimes(master = refVideo) {
  if (state.isInternalSeek) {
    return;
  }
  state.isInternalSeek = true;
  const target = master.currentTime || 0;
  for (const video of videos) {
    if (video === master) {
      continue;
    }
    if (Math.abs((video.currentTime || 0) - target) > SYNC_TOLERANCE_SECONDS) {
      video.currentTime = target;
    }
    if (video.playbackRate !== state.playbackRate) {
      video.playbackRate = state.playbackRate;
    }
  }
  state.isInternalSeek = false;
}

function updatePlaybackInfo() {
  const current = Number.isFinite(refVideo.currentTime) ? refVideo.currentTime : 0;
  const duration = Number.isFinite(refVideo.duration) ? refVideo.duration : 0;
  const deltaMs = Math.round(Math.abs((refVideo.currentTime || 0) - (srcVideo.currentTime || 0)) * 1000);
  playbackState.textContent = state.isPlaying ? "播放中" : "暂停";
  timeInfo.textContent = `${current.toFixed(2)}s / ${duration.toFixed(2)}s · ${formatSpeed(state.playbackRate)}`;
  syncInfo.textContent = `对齐偏差 ${deltaMs} ms`;
}

async function renderCurrentItem() {
  const item = currentItem();
  if (!item) {
    sampleCounter.textContent = "样本 0 / 0";
    setStatus("没有可用样本");
    instructionList.innerHTML = "";
    renderTag("", "");
    renderVideoPaths("", "");
    renderObjectSizeControls(null);
    resetVideos();
    return;
  }

  const token = ++state.loadingToken;
  resetVideos();
  sampleCounter.textContent = `样本 ${state.index + 1} / ${state.items.length}`;
  renderInstructions(item.instructions || item.text || []);
  renderTag(item.tag, item.object_size);
  renderObjectSizeControls(item);
  renderVideoPaths(item.ref_video_path || "", item.src_video_path || "");
  // --- 新增：渲染掩码图 ---
  if (item.mask_exists) {
    maskImage.src = item.mask_url;
    maskImage.classList.remove("hidden");
    maskFallback.classList.add("hidden");
  } else {
    maskImage.src = "";
    maskImage.classList.add("hidden");
    maskFallback.classList.remove("hidden");
  }
  // ------------------------
  const loadingGoodHint = state.goodPath ? ` | Good文件: ${state.goodPath}` : "";
  setStatus(`加载中... 结果文件: ${state.outputPath}${loadingGoodHint}`);

  if (!item.ref_video_exists) {
    throw new Error(`Ref 视频不存在: ${item.ref_video_path}`);
  }
  if (!item.src_video_exists) {
    throw new Error(`Src 视频不存在: ${item.src_video_path}`);
  }

  refVideo.src = item.ref_video_url;
  srcVideo.src = item.src_video_url;
  refVideo.load();
  srcVideo.load();
  await Promise.all(videos.map((v) => waitReady(v, token)));
  if (token !== state.loadingToken) {
    return;
  }
  applyRate(state.playbackRate);
  syncVideoTimes(refVideo);
  const loadedGoodHint = state.goodPath ? ` | Good文件: ${state.goodPath}` : "";
  setStatus(`结果文件: ${state.outputPath}${loadedGoodHint}`);
}

async function loadDataset(pathText) {
  const payload = await fetchJson(apiUrl(`api/dataset?path=${encodeURIComponent(pathText)}`));
  state.datasetPath = payload.dataset_path;
  state.outputPath = payload.output_path;
  state.goodPath = payload.good_path || "";
  state.goodWithSizePath = payload.good_with_size_path || "";
  state.scriptPath = payload.script_path || "";
  state.items = payload.items || [];
  state.index = Math.min(payload.next_index || 0, Math.max((payload.total || 1) - 1, 0));

  datasetPathInput.value = state.datasetPath;
  try {
    localStorage.setItem(PATH_STORAGE_KEY, state.datasetPath);
  } catch {
    // ignore
  }

  await renderCurrentItem();
}

async function loadFromInput() {
  const text = (datasetPathInput.value || "").trim();
  if (!text) {
    throw new Error("请输入 JSON 绝对路径");
  }
  await loadDataset(text);
}

async function saveLabel(tag, objectSizeOverride = "") {
  const item = currentItem();
  if (!item) {
    return;
  }
  const requiresSize = !!item.requires_good_size_tag;
  const resolvedObjectSize = normalizeObjectSize(objectSizeOverride || state.selectedObjectSize || item.object_size);
  if (tag === "good" && requiresSize && !resolvedObjectSize) {
    throw new Error("当前是添加/移除任务，标注 good 时必须选择“大物体”或“小物体”");
  }

  const oldTag = item.tag;
  const oldObjectSize = item.object_size;
  item.tag = tag;
  if (tag === "good" && resolvedObjectSize) {
    item.object_size = resolvedObjectSize;
    state.selectedObjectSize = resolvedObjectSize;
  }
  if (tag === "bad") {
    delete item.object_size;
  }
  renderTag(item.tag, item.object_size);
  renderObjectSizeControls(item);
  setStatus("保存中...");

  try {
    const requestPayload = {
      dataset_path: state.datasetPath,
      index: state.index,
      tag,
    };
    if (tag === "good" && resolvedObjectSize) {
      requestPayload.object_size = resolvedObjectSize;
    }

    const payload = await fetchJson(apiUrl("api/save-label"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload),
    });
    state.outputPath = payload.output_path || state.outputPath;
    state.goodPath = payload.good_path || state.goodPath;
    state.goodWithSizePath = payload.good_with_size_path || state.goodWithSizePath;
    state.scriptPath = payload.script_path || state.scriptPath;
    const savedGoodHint = state.goodPath ? ` | Good文件: ${state.goodPath}` : "";
    setStatus(`已保存 ${payload.completed} / ${state.items.length} · ${state.outputPath}${savedGoodHint}`);
    if (state.index < state.items.length - 1) {
      state.index += 1;
      await renderCurrentItem();
    }
  } catch (err) {
    item.tag = oldTag;
    if (oldObjectSize === undefined) {
      delete item.object_size;
    } else {
      item.object_size = oldObjectSize;
    }
    state.selectedObjectSize = normalizeObjectSize(oldObjectSize);
    renderTag(item.tag, item.object_size);
    renderObjectSizeControls(item);
    throw err;
  }
}

async function switchSample(delta) {
  if (!state.items.length) {
    return;
  }
  const next = Math.max(0, Math.min(state.items.length - 1, state.index + delta));
  if (next === state.index) {
    return;
  }
  state.index = next;
  await renderCurrentItem();
}

async function togglePlayback() {
  if (state.isPlaying) {
    videos.forEach((video) => video.pause());
    state.isPlaying = false;
    updatePlaybackInfo();
    return;
  }
  try {
    await Promise.all(videos.map((v) => waitReady(v, state.loadingToken)));
    applyRate(state.playbackRate);
    syncVideoTimes(refVideo);
    await Promise.all(videos.map((v) => v.play()));
    state.isPlaying = true;
    updatePlaybackInfo();
  } catch (err) {
    state.isPlaying = false;
    throw err;
  }
}

function showError(err) {
  const msg = err?.message || String(err);
  const urlHint = state.lastApiUrl ? ` | API: ${state.lastApiUrl}` : "";
  setStatus(`错误: ${msg}${urlHint}`);
  console.error(err);
}

function setupVideoEvents() {
  for (const video of videos) {
    video.muted = true;
    video.playsInline = true;
    video.preload = "auto";
    video.addEventListener("seeking", () => syncVideoTimes(video));
    video.addEventListener("timeupdate", () => {
      if (state.isPlaying) {
        syncVideoTimes(video);
      }
      updatePlaybackInfo();
    });
    video.addEventListener("ended", () => {
      videos.forEach((v) => v.pause());
      state.isPlaying = false;
      updatePlaybackInfo();
    });
    video.addEventListener("error", () => {
      showError(new Error(`视频播放失败: ${video.currentSrc || video.src}`));
    });
  }

  cancelAnimationFrame(state.rafId);
  const tick = () => {
    if (state.isPlaying) {
      const delta = Math.abs((refVideo.currentTime || 0) - (srcVideo.currentTime || 0));
      if (delta > SYNC_TOLERANCE_SECONDS) {
        syncVideoTimes(refVideo);
      }
    }
    updatePlaybackInfo();
    state.rafId = requestAnimationFrame(tick);
  };
  tick();
}

function setupKeyboard() {
  window.addEventListener("keydown", async (event) => {
    const tagName = document.activeElement?.tagName?.toLowerCase();
    if (tagName === "input" || tagName === "textarea") {
      return;
    }

    if (event.code === "Space") {
      event.preventDefault();
      togglePlayback().catch(showError);
      return;
    }
    if (event.code === "ArrowLeft") {
      event.preventDefault();
      switchSample(-1).catch(showError);
      return;
    }
    if (event.code === "ArrowRight") {
      event.preventDefault();
      switchSample(1).catch(showError);
      return;
    }

    const key = event.key.toLowerCase();
    if (key === "g") {
      event.preventDefault();
      saveLabel("good").catch(showError);
      return;
    }
    if (key === "b") {
      event.preventDefault();
      saveLabel("bad").catch(showError);
      return;
    }
    if (key === "l") {
      event.preventDefault();
      saveLabel("good", "large").catch(showError);
      return;
    }
    if (key === "s") {
      event.preventDefault();
      saveLabel("good", "small").catch(showError);
      return;
    }
    if (key === "1") {
      event.preventDefault();
      applyRate(1);
      return;
    }
    if (key === "2") {
      event.preventDefault();
      applyRate(2);
      return;
    }
    if (key === "3") {
      event.preventDefault();
      applyRate(3);
      return;
    }
    if (key === "0") {
      event.preventDefault();
      applyRate(0.5);
    }
  });
}

function setupActions() {
  loadBtn.addEventListener("click", () => loadFromInput().catch(showError));
  datasetPathInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      loadFromInput().catch(showError);
    }
  });
  goodBtn.addEventListener("click", () => saveLabel("good").catch(showError));
  badBtn.addEventListener("click", () => saveLabel("bad").catch(showError));
  largeBtn?.addEventListener("click", () => saveLabel("good", "large").catch(showError));
  smallBtn?.addEventListener("click", () => saveLabel("good", "small").catch(showError));
  speedButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      applyRate(Number(btn.dataset.speed));
    });
  });
}

async function init() {
  try {
    state.apiBase = await discoverApiBase();
  } catch (err) {
    showError(err);
    return;
  }

  setupVideoEvents();
  setupKeyboard();
  setupActions();
  applyRate(1);

  let remembered = "";
  try {
    remembered = localStorage.getItem(PATH_STORAGE_KEY) || "";
  } catch {
    remembered = "";
  }
  if (remembered) {
    datasetPathInput.value = remembered;
  }
  setStatus(`就绪。API基址: ${state.apiBase}`);
}

init();
