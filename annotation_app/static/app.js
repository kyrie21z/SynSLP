'use strict';

const $ = id => document.getElementById(id);

const state = {
  images: [],
  currentIndex: 0,
  currentImage: null,
  currentDoc: null,
  instances: [],
  selectedIndex: null,
  scale: 1,
  panX: 0,
  panY: 0,
  fit: true,
  pointer: null,
  drawMode: true,
  dirty: false,
  saveTimer: null,
  saving: null,
};

// API Helpers
async function fetchJson(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: '请求失败' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return await res.json();
}

// Coordinate & Origin Helpers
function getOrigin() {
  if (!state.currentImage) return [0, 0];
  const canvas = $('annotationCanvas');
  const ox = (canvas.width - state.currentImage.width * state.scale) / 2 + state.panX;
  const oy = (canvas.height - state.currentImage.height * state.scale) / 2 + state.panY;
  return [ox, oy];
}

function screenToImage(e, clamp = true) {
  if (!state.currentImage) return [0, 0];
  const canvas = $('annotationCanvas');
  const r = canvas.getBoundingClientRect();
  const [ox, oy] = getOrigin();
  let x = (e.clientX - r.left - ox) / state.scale;
  let y = (e.clientY - r.top - oy) / state.scale;

  if (clamp) {
    x = Math.max(0, Math.min(state.currentImage.width, x));
    y = Math.max(0, Math.min(state.currentImage.height, y));
  }
  return [Math.round(x), Math.round(y)];
}

function imageToScreen(ix, iy) {
  const [ox, oy] = getOrigin();
  return [ix * state.scale + ox, iy * state.scale + oy];
}

// Canvas Rendering
function draw() {
  const canvas = $('annotationCanvas');
  const viewport = $('viewport');
  if (!canvas || !viewport) return;

  canvas.width = viewport.clientWidth;
  canvas.height = viewport.clientHeight;
  const ctx = canvas.getContext('2d');

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!state.currentImage) {
    ctx.fillStyle = '#666';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('请选择或加载图像', canvas.width / 2, canvas.height / 2);
    return;
  }

  // Calculate fit scale if needed
  if (state.fit) {
    const scaleX = (canvas.width - 40) / state.currentImage.width;
    const scaleY = (canvas.height - 40) / state.currentImage.height;
    state.scale = Math.min(scaleX, scaleY, 6.0);
    state.panX = 0;
    state.panY = 0;
  }

  const [ox, oy] = getOrigin();
  const imgW = state.currentImage.width * state.scale;
  const imgH = state.currentImage.height * state.scale;

  // Draw image
  ctx.imageSmoothingEnabled = false; // Keep pixel sharpness for OCR/SLP crops
  ctx.drawImage(state.currentImage, ox, oy, imgW, imgH);

  // Draw image border
  ctx.strokeStyle = '#555';
  ctx.lineWidth = 1;
  ctx.strokeRect(ox, oy, imgW, imgH);

  // Update zoom display
  $('zoomLevelSpan').textContent = Math.round(state.scale * 100) + '%';

  // Draw annotated bounding boxes
  state.instances.forEach((inst, idx) => {
    const isSelected = idx === state.selectedIndex;
    const b = inst.bbox; // [x1, y1, x2, y2]
    const [sx1, sy1] = imageToScreen(b[0], b[1]);
    const [sx2, sy2] = imageToScreen(b[2], b[3]);
    const bw = sx2 - sx1;
    const bh = sy2 - sy1;

    // Fill and Stroke
    ctx.fillStyle = isSelected ? 'rgba(255, 214, 10, 0.25)' : 'rgba(76, 139, 245, 0.2)';
    ctx.fillRect(sx1, sy1, bw, bh);

    ctx.strokeStyle = isSelected ? '#ffd60a' : '#4c8bf5';
    ctx.lineWidth = isSelected ? 2 : 1.5;
    ctx.strokeRect(sx1, sy1, bw, bh);

    // Corner resize handles for selected box
    if (isSelected) {
      ctx.fillStyle = '#ffffff';
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 1;
      const corners = [
        [sx1, sy1],
        [sx2, sy1],
        [sx1, sy2],
        [sx2, sy2],
      ];
      for (const [cx, cy] of corners) {
        ctx.fillRect(cx - 3.5, cy - 3.5, 7, 7);
        ctx.strokeRect(cx - 3.5, cy - 3.5, 7, 7);
      }
    }

    // Label tag above box
    const labelText = `[${inst.order}] ${inst.text || '?'}`;
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'bottom';
    const tagPadding = 3;
    const tagW = ctx.measureText(labelText).width + tagPadding * 2;
    const tagH = 16;
    const tagX = sx1;
    const tagY = Math.max(tagH, sy1 - 2);

    ctx.fillStyle = isSelected ? '#ffd60a' : '#4c8bf5';
    ctx.fillRect(tagX, tagY - tagH, tagW, tagH);

    ctx.fillStyle = isSelected ? '#000' : '#fff';
    ctx.fillText(labelText, tagX + tagPadding, tagY - 2);
  });

  // Draw active drag box
  if (state.pointer && state.pointer.mode === 'draw') {
    const p1 = state.pointer.start;
    const p2 = state.pointer.end;
    const x1 = Math.min(p1[0], p2[0]);
    const y1 = Math.min(p1[1], p2[1]);
    const x2 = Math.max(p1[0], p2[0]);
    const y2 = Math.max(p1[1], p2[1]);

    const [sx1, sy1] = imageToScreen(x1, y1);
    const [sx2, sy2] = imageToScreen(x2, y2);

    ctx.fillStyle = 'rgba(52, 199, 89, 0.25)';
    ctx.fillRect(sx1, sy1, sx2 - sx1, sy2 - sy1);

    ctx.strokeStyle = '#34c759';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 3]);
    ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);
    ctx.setLineDash([]);
  }
}

// Mouse / Pointer Event Handling
function initPointerEvents() {
  const canvas = $('annotationCanvas');

  canvas.addEventListener('wheel', e => {
    if (!state.currentImage) return;
    e.preventDefault();
    const r = canvas.getBoundingClientRect();
    const cursorX = e.clientX - r.left;
    const cursorY = e.clientY - r.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    const newScale = Math.max(0.1, Math.min(15.0, state.scale * zoomFactor));

    const [ox, oy] = getOrigin();
    state.fit = false;
    $('zoomSelect').value = 'custom';

    state.panX = cursorX - (cursorX - ox) / state.scale * newScale - (canvas.width - state.currentImage.width * newScale) / 2;
    state.panY = cursorY - (cursorY - oy) / state.scale * newScale - (canvas.height - state.currentImage.height * newScale) / 2;
    state.scale = newScale;

    draw();
  }, { passive: false });

  canvas.addEventListener('pointerdown', e => {
    if (!state.currentImage || e.button !== 0) return;
    canvas.setPointerCapture(e.pointerId);

    const [ix, iy] = screenToImage(e, false);
    const [clampedX, clampedY] = screenToImage(e, true);

    // 1. Check if clicking a corner handle of the selected box
    if (state.selectedIndex !== null) {
      const selBox = state.instances[state.selectedIndex].bbox;
      const [sx1, sy1] = imageToScreen(selBox[0], selBox[1]);
      const [sx2, sy2] = imageToScreen(selBox[2], selBox[3]);
      const r = canvas.getBoundingClientRect();
      const cx = e.clientX - r.left;
      const cy = e.clientY - r.top;

      const corners = [
        [sx1, sy1], // 0: top-left
        [sx2, sy1], // 1: top-right
        [sx1, sy2], // 2: bottom-left
        [sx2, sy2], // 3: bottom-right
      ];
      const hitCorner = corners.findIndex(([hx, hy]) => Math.hypot(hx - cx, hy - cy) < 10);
      if (hitCorner >= 0) {
        state.pointer = {
          mode: 'resize',
          corner: hitCorner,
          start: [clampedX, clampedY],
          before: [...selBox],
        };
        return;
      }

      // 2. Check if clicking inside the selected box for moving (only in select mode)
      if (!state.drawMode && ix >= selBox[0] && ix <= selBox[2] && iy >= selBox[1] && iy <= selBox[3]) {
        state.pointer = {
          mode: 'move',
          start: [clampedX, clampedY],
          before: [...selBox],
        };
        return;
      }
    }

    // 2. In Draw Mode, dragging always creates a new box
    if (state.drawMode) {
      state.pointer = {
        mode: 'draw',
        start: [clampedX, clampedY],
        end: [clampedX, clampedY],
      };
      state.selectedIndex = null;
      renderEditor();
      renderList();
      draw();
      return;
    }

    // 3. In Select/Pan Mode, check if clicking any existing box to select/move it
    for (let i = state.instances.length - 1; i >= 0; i--) {
      const b = state.instances[i].bbox;
      if (ix >= b[0] && ix <= b[2] && iy >= b[1] && iy <= b[3]) {
        selectInstance(i);
        state.pointer = {
          mode: 'move',
          start: [clampedX, clampedY],
          before: [...b],
        };
        return;
      }
    }

    // 4. In Select/Pan Mode, clicking blank area pans the canvas
    state.pointer = {
      mode: 'pan',
      start: [e.clientX, e.clientY],
      beforePan: [state.panX, state.panY],
    };
    state.selectedIndex = null;
    renderEditor();
    renderList();
    draw();
  });

  canvas.addEventListener('pointermove', e => {
    if (!state.currentImage) return;
    const [ix, iy] = screenToImage(e, true);
    $('cursorPos').textContent = `光标: [${ix}, ${iy}]`;

    if (!state.pointer) return;

    if (state.pointer.mode === 'pan') {
      state.panX = state.pointer.beforePan[0] + (e.clientX - state.pointer.start[0]);
      state.panY = state.pointer.beforePan[1] + (e.clientY - state.pointer.start[1]);
      state.fit = false;
      $('zoomSelect').value = 'custom';
      draw();
      return;
    }

    if (state.pointer.mode === 'draw') {
      state.pointer.end = [ix, iy];
      draw();
      return;
    }

    if (state.pointer.mode === 'move') {
      const dx = ix - state.pointer.start[0];
      const dy = iy - state.pointer.start[1];
      const b = state.pointer.before;
      const w = b[2] - b[0];
      const h = b[3] - b[1];

      let newX1 = Math.max(0, Math.min(state.currentImage.width - w, b[0] + dx));
      let newY1 = Math.max(0, Math.min(state.currentImage.height - h, b[1] + dy));
      let newX2 = newX1 + w;
      let newY2 = newY1 + h;

      state.instances[state.selectedIndex].bbox = [newX1, newY1, newX2, newY2];
      renderEditorCoords();
      draw();
      return;
    }

    if (state.pointer.mode === 'resize') {
      const b = state.pointer.before;
      const c = state.pointer.corner;
      let [x1, y1, x2, y2] = b;

      if (c === 0) { // Top-left
        x1 = Math.min(b[2] - 1, ix);
        y1 = Math.min(b[3] - 1, iy);
      } else if (c === 1) { // Top-right
        x2 = Math.max(b[0] + 1, ix);
        y1 = Math.min(b[3] - 1, iy);
      } else if (c === 2) { // Bottom-left
        x1 = Math.min(b[2] - 1, ix);
        y2 = Math.max(b[1] + 1, iy);
      } else if (c === 3) { // Bottom-right
        x2 = Math.max(b[0] + 1, ix);
        y2 = Math.max(b[1] + 1, iy);
      }

      state.instances[state.selectedIndex].bbox = [x1, y1, x2, y2];
      renderEditorCoords();
      draw();
      return;
    }
  });

  const endGesture = () => {
    if (!state.pointer) return;
    const mode = state.pointer.mode;
    state.pointer = null;

    if (mode === 'draw') {
      const p1 = state.pointer?.start || [0, 0];
      const p2 = state.pointer?.end || [0, 0];
      // Handled via last event
    }
    draw();
  };

  canvas.addEventListener('pointerup', e => {
    if (!state.pointer) return;
    const p = state.pointer;
    state.pointer = null;

    if (p.mode === 'draw') {
      const [ix, iy] = screenToImage(e, true);
      const x1 = Math.min(p.start[0], ix);
      const y1 = Math.min(p.start[1], iy);
      const x2 = Math.max(p.start[0], ix);
      const y2 = Math.max(p.start[1], iy);

      if (x2 - x1 >= 2 && y2 - y1 >= 2) {
        // Calculate next order (highest current order + 1)
        const nextOrder = state.instances.length > 0
          ? Math.max(...state.instances.map(item => item.order)) + 1
          : 0;

        const newInst = {
          bbox: [x1, y1, x2, y2],
          text: '',
          order: nextOrder,
        };
        state.instances.push(newInst);
        state.selectedIndex = state.instances.length - 1;
        markDirty();
        renderList();
        renderEditor();

        // Focus text input immediately so user can type the character
        const textInput = $('charTextInput');
        if (textInput) {
          textInput.focus();
          textInput.select();
        }
      }
    } else if (p.mode === 'move' || p.mode === 'resize') {
      markDirty();
      renderList();
    }

    draw();
  });

  canvas.addEventListener('pointercancel', endGesture);
}

// Editor and List Sync
function selectInstance(idx) {
  if (idx < 0 || idx >= state.instances.length) {
    state.selectedIndex = null;
  } else {
    state.selectedIndex = idx;
  }
  renderList();
  renderEditor();
  draw();
}

function renderList() {
  const container = $('instanceList');
  $('charCountBadge').textContent = state.instances.length;

  if (state.instances.length === 0) {
    container.innerHTML = '<p class="empty-list-text">暂无标注字符</p>';
    return;
  }

  container.innerHTML = '';
  // Sort displayed list by order
  state.instances.forEach((inst, idx) => {
    const item = document.createElement('div');
    item.className = 'instance-item' + (idx === state.selectedIndex ? ' selected' : '');

    const orderSpan = document.createElement('span');
    orderSpan.className = 'item-order';
    orderSpan.textContent = `[${inst.order}]`;

    const textSpan = document.createElement('span');
    textSpan.className = 'item-text';
    textSpan.textContent = inst.text ? inst.text : '(空)';

    const coordsSpan = document.createElement('span');
    coordsSpan.className = 'item-coords';
    coordsSpan.textContent = `${inst.bbox[0]},${inst.bbox[1]},${inst.bbox[2]},${inst.bbox[3]}`;

    const delBtn = document.createElement('button');
    delBtn.className = 'item-delete-btn';
    delBtn.innerHTML = '&times;';
    delBtn.title = '删除此框';
    delBtn.onclick = ev => {
      ev.stopPropagation();
      deleteInstance(idx);
    };

    item.appendChild(orderSpan);
    item.appendChild(textSpan);
    item.appendChild(coordsSpan);
    item.appendChild(delBtn);

    item.onclick = () => selectInstance(idx);
    container.appendChild(item);
  });
}

function renderEditor() {
  const form = $('editForm');
  const placeholder = document.querySelector('.placeholder-text');

  if (state.selectedIndex === null || !state.instances[state.selectedIndex]) {
    form.hidden = true;
    placeholder.hidden = false;
    $('selectedBoxCoords').textContent = '未选中框';
    return;
  }

  form.hidden = false;
  placeholder.hidden = true;

  const inst = state.instances[state.selectedIndex];
  $('charTextInput').value = inst.text || '';
  $('charOrderInput').value = inst.order;
  renderEditorCoords();
}

function renderEditorCoords() {
  if (state.selectedIndex === null || !state.instances[state.selectedIndex]) return;
  const b = state.instances[state.selectedIndex].bbox;
  $('coordX1').value = b[0];
  $('coordY1').value = b[1];
  $('coordX2').value = b[2];
  $('coordY2').value = b[3];
  $('selectedBoxCoords').textContent = `选框 [${b[0]}, ${b[1]}, ${b[2]}, ${b[3]}] (${b[2] - b[0]}x${b[3] - b[1]})`;
}

function deleteInstance(idx) {
  if (idx < 0 || idx >= state.instances.length) return;
  state.instances.splice(idx, 1);
  if (state.selectedIndex === idx) {
    state.selectedIndex = state.instances.length > 0 ? Math.min(idx, state.instances.length - 1) : null;
  } else if (state.selectedIndex > idx) {
    state.selectedIndex--;
  }
  markDirty();
  renderList();
  renderEditor();
  draw();
}

// Persistence
function markDirty() {
  state.dirty = true;
  $('saveStatus').textContent = '待保存...';
  $('saveStatus').style.color = 'var(--text-secondary)';

  clearTimeout(state.saveTimer);
  state.saveTimer = setTimeout(() => {
    saveCurrentAnnotation().catch(err => {
      $('saveStatus').textContent = '保存失败: ' + err.message;
      $('saveStatus').style.color = 'var(--danger)';
    });
  }, 400);
}

async function saveCurrentAnnotation() {
  if (!state.currentDoc) return;
  clearTimeout(state.saveTimer);

  $('saveStatus').textContent = '保存中...';
  $('saveStatus').style.color = 'var(--accent)';

  const payload = {
    image: state.currentDoc.image,
    width: state.currentImage ? state.currentImage.width : state.currentDoc.width,
    height: state.currentImage ? state.currentImage.height : state.currentDoc.height,
    instances: state.instances,
  };

  const res = await fetchJson('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  state.dirty = false;
  $('saveStatus').textContent = '已保存 (JSONL)';
  $('saveStatus').style.color = 'var(--success)';

  // Update session list annotated badge
  if (state.images[state.currentIndex]) {
    state.images[state.currentIndex].annotated = state.instances.length > 0;
    state.images[state.currentIndex].instance_count = state.instances.length;
    updateSessionProgress();
  }
  return res;
}

// Navigation & Session Loading
async function loadSession() {
  $('saveStatus').textContent = '加载列表中...';
  const data = await fetchJson('/api/session');
  state.images = data.images || [];

  if (state.images.length === 0) {
    $('currentFilename').textContent = '无可用图像文件';
    $('saveStatus').textContent = '图像目录为空';
    return;
  }

  $('imgTotalSpan').textContent = `/ ${state.images.length}`;
  $('imgIndexInput').max = state.images.length;
  updateSessionProgress();

  await loadImageIndex(0);
}

function updateSessionProgress() {
  const annotatedCount = state.images.filter(img => img.annotated).length;
  $('progressStatus').textContent = `图像 ${annotatedCount} / ${state.images.length} 已标注`;
}

async function loadImageIndex(index) {
  if (index < 0 || index >= state.images.length) return;

  // Flush pending changes before navigating away
  if (state.dirty) {
    await saveCurrentAnnotation();
  }

  state.currentIndex = index;
  $('imgIndexInput').value = index + 1;
  $('prevBtn').disabled = index === 0;
  $('nextBtn').disabled = index === state.images.length - 1;

  const item = state.images[index];
  $('currentFilename').textContent = item.filename;

  // Fetch annotation data and load image concurrently
  const [doc, image] = await Promise.all([
    fetchJson('/api/annotation?path=' + encodeURIComponent(item.path)),
    new Promise((resolve, reject) => {
      const im = new Image();
      im.onload = () => resolve(im);
      im.onerror = () => reject(new Error('图像加载失败'));
      im.src = '/api/image?path=' + encodeURIComponent(item.path);
    }),
  ]);

  state.currentDoc = doc;
  state.currentImage = image;
  state.instances = (doc.instances || []).map(inst => ({ ...inst }));
  state.selectedIndex = state.instances.length > 0 ? 0 : null;
  state.dirty = false;
  state.fit = true;
  state.panX = 0;
  state.panY = 0;

  $('imgDimensions').textContent = `[${image.width} x ${image.height}]`;
  $('zoomSelect').value = 'fit';
  $('saveStatus').textContent = doc.instances?.length > 0 ? '已就绪 (已载入)' : '就绪 (未标注)';
  $('saveStatus').style.color = 'var(--success)';

  renderList();
  renderEditor();
  draw();
}

// Wire UI Listeners
function initUI() {
  $('prevBtn').onclick = () => loadImageIndex(state.currentIndex - 1);
  $('nextBtn').onclick = () => loadImageIndex(state.currentIndex + 1);

  $('imgIndexInput').onchange = () => {
    const val = parseInt($('imgIndexInput').value, 10);
    if (!isNaN(val)) loadImageIndex(val - 1);
  };

  $('zoomSelect').onchange = e => {
    const v = e.target.value;
    if (v === 'fit') {
      state.fit = true;
      state.panX = 0;
      state.panY = 0;
    } else if (v !== 'custom') {
      state.fit = false;
      state.scale = parseFloat(v);
    }
    draw();
  };

  $('resetViewBtn').onclick = () => {
    state.fit = true;
    state.panX = 0;
    state.panY = 0;
    $('zoomSelect').value = 'fit';
    draw();
  };

  function updateDrawModeUI() {
    $('drawModeBtn').classList.toggle('active', state.drawMode);
    $('drawModeBtn').textContent = state.drawMode ? '画框模式: 开 (D)' : '画框模式: 关 (移动/浏览)';
  }

  $('drawModeBtn').onclick = () => {
    state.drawMode = !state.drawMode;
    updateDrawModeUI();
  };

  $('deleteSelectedBtn').onclick = () => {
    if (state.selectedIndex !== null) deleteInstance(state.selectedIndex);
  };

  $('clearAllBtn').onclick = () => {
    if (state.instances.length === 0) return;
    if (confirm('确认清空当前图像的所有标注框？')) {
      state.instances = [];
      state.selectedIndex = null;
      markDirty();
      renderList();
      renderEditor();
      draw();
    }
  };

  // Character inputs
  $('charTextInput').addEventListener('input', e => {
    if (state.selectedIndex === null) return;
    state.instances[state.selectedIndex].text = e.target.value;
    renderList();
    draw();
    markDirty();
  });

  // Handle Enter key in character input: advance to next box or confirm
  $('charTextInput').addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      e.preventDefault();
      // If there is a next instance, select it and focus text input
      if (state.selectedIndex !== null && state.selectedIndex < state.instances.length - 1) {
        selectInstance(state.selectedIndex + 1);
        $('charTextInput').focus();
        $('charTextInput').select();
      } else {
        $('charTextInput').blur();
      }
    }
  });

  $('charOrderInput').addEventListener('change', e => {
    if (state.selectedIndex === null) return;
    const val = parseInt(e.target.value, 10);
    if (!isNaN(val)) {
      state.instances[state.selectedIndex].order = val;
      state.instances.sort((a, b) => a.order - b.order);
      state.selectedIndex = state.instances.findIndex(inst => inst.order === val);
      renderList();
      draw();
      markDirty();
    }
  });

  ['coordX1', 'coordY1', 'coordX2', 'coordY2'].forEach((id, i) => {
    $(id).addEventListener('change', () => {
      if (state.selectedIndex === null) return;
      const b = state.instances[state.selectedIndex].bbox;
      const val = parseInt($(id).value, 10);
      if (!isNaN(val)) {
        b[i] = val;
        // Keep order x1 < x2, y1 < y2
        b[0] = Math.min(b[0], b[2]);
        b[2] = Math.max(b[0], b[2]);
        b[1] = Math.min(b[1], b[3]);
        b[3] = Math.max(b[1], b[3]);
        renderEditorCoords();
        draw();
        markDirty();
      }
    });
  });

  // Global Keyboard Shortcuts
  window.addEventListener('keydown', e => {
    // If typing in input or textarea, only allow Escape / Enter
    const isTyping = ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName);

    if (e.key === 'Escape') {
      state.selectedIndex = null;
      renderEditor();
      renderList();
      draw();
      return;
    }

    if (!isTyping) {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        if (state.selectedIndex !== null) deleteInstance(state.selectedIndex);
      } else if (e.key === 'PageUp' || (e.key === 'ArrowLeft' && e.altKey)) {
        e.preventDefault();
        if (state.currentIndex > 0) loadImageIndex(state.currentIndex - 1);
      } else if (e.key === 'PageDown' || (e.key === 'ArrowRight' && e.altKey)) {
        e.preventDefault();
        if (state.currentIndex < state.images.length - 1) loadImageIndex(state.currentIndex + 1);
      } else if (e.key === 'd' || e.key === 'D') {
        state.drawMode = !state.drawMode;
        updateDrawModeUI();
      }
    }

    // Ctrl+S / Command+S manual save
    if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) {
      e.preventDefault();
      saveCurrentAnnotation();
    }
  });

  // Help Modal
  $('helpBtn').onclick = () => $('helpModal').showModal();
  $('closeHelpBtn').onclick = () => $('helpModal').close();

  window.addEventListener('resize', () => draw());
}

// Boot
window.addEventListener('DOMContentLoaded', () => {
  initPointerEvents();
  initUI();
  loadSession().catch(err => {
    $('saveStatus').textContent = '初始化失败: ' + err.message;
    $('saveStatus').style.color = 'var(--danger)';
  });
});
