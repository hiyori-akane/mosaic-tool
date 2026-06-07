// 補正キャンバス（描画/ブラシ/ズーム/マスク書き出し）。
// 表示解像度で動作し、「適用」時のみ add/remove バッファを PNG dataURL で送る（仕様 §8）。
window.CanvasEditor = (function () {
  const imageCanvas = () => document.getElementById("canvas-image");
  const overlayCanvas = () => document.getElementById("canvas-overlay");

  let dispW = 0, dispH = 0, zoom = 1;
  let tool = "add", brush = 32, drawing = false;

  // 編集バッファ（表示解像度）: 追加 / 削除 を別々に保持
  let addBuf, removeBuf, modelMaskImg;
  // Undo/Redo: バッファのスナップショット
  const undoStack = [], redoStack = [];

  function newBuf() {
    const c = document.createElement("canvas");
    c.width = dispW; c.height = dispH;
    return c;
  }

  async function load(view) {
    dispW = view.disp_w; dispH = view.disp_h; zoom = 1;
    [imageCanvas(), overlayCanvas()].forEach((c) => { c.width = dispW; c.height = dispH; });
    addBuf = newBuf(); removeBuf = newBuf();
    undoStack.length = 0; redoStack.length = 0;

    // 背景画像
    await drawDataUrl(imageCanvas(), view.image_dataurl);
    // 検出マスク（オーバーレイ表示用に保持）
    modelMaskImg = await loadImage(view.mask_dataurl);
    applyZoom();
    redrawOverlay();
    updateCursor();
  }

  function setPreview(dataurl) {
    drawDataUrl(imageCanvas(), dataurl);
  }

  function loadImage(src) {
    return new Promise((res) => {
      const img = new Image();
      img.onload = () => res(img);
      img.src = src;
    });
  }

  async function drawDataUrl(canvas, src) {
    const img = await loadImage(src);
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  }

  function redrawOverlay() {
    const ctx = overlayCanvas().getContext("2d");
    ctx.clearRect(0, 0, dispW, dispH);
    // 検出マスク（白）を半透明シアンで
    if (modelMaskImg) {
      ctx.globalAlpha = 0.35;
      ctx.globalCompositeOperation = "source-over";
      tintAndDraw(ctx, modelMaskImg, [56, 189, 248]);  // シアン
    }
    // 追加ブラシ = マゼンタ / 削除ブラシ = 赤
    ctx.globalAlpha = 0.5;
    ctx.drawImage(addBuf, 0, 0);
    ctx.drawImage(removeBuf, 0, 0);
    ctx.globalAlpha = 1;
  }

  // 白黒マスク画像を指定色で塗ってオフスクリーン経由で描く。
  // マスク PNG は背景=黒(不透明)・前景=白なので、輝度をアルファに変換して
  // 前景だけを着色する（黒背景まで塗って全面が単色になるのを防ぐ）。
  // 着色済みキャンバスをキャッシュする。tintAndDraw はブラシ描画中
  // （pointermove → redrawOverlay）に高頻度で呼ばれるため、マスク画像が
  // 変わらない限り getImageData / ピクセルループ / putImageData を再実行しない。
  let _tintCanvas;
  let _tintKey;
  function tintAndDraw(ctx, img, rgb) {
    const [r, g, b] = rgb;
    const key = `${img.src}|${dispW}x${dispH}|${r},${g},${b}`;
    if (!_tintCanvas || _tintKey !== key) {
      _tintKey = key;
      if (!_tintCanvas) _tintCanvas = document.createElement("canvas");
      _tintCanvas.width = dispW; _tintCanvas.height = dispH;
      const tctx = _tintCanvas.getContext("2d");
      tctx.clearRect(0, 0, dispW, dispH);
      tctx.drawImage(img, 0, 0, dispW, dispH);
      const id = tctx.getImageData(0, 0, dispW, dispH);
      const d = id.data;
      for (let i = 0; i < d.length; i += 4) {
        const lum = d[i];            // グレースケール（R=G=B）
        d[i] = r; d[i + 1] = g; d[i + 2] = b;
        d[i + 3] = lum;              // アルファ = マスク輝度（黒=透明 / 白=不透明）
      }
      tctx.putImageData(id, 0, 0);
    }
    ctx.drawImage(_tintCanvas, 0, 0);
  }

  function applyZoom() {
    [imageCanvas(), overlayCanvas()].forEach((c) => {
      c.style.transform = `scale(${zoom})`;
    });
  }

  // ブラシ用カーソル: 実サイズの円 + 中央プラス（SVG）。
  // 画面上の見かけ径はズーム倍率込み（brush * zoom）。色はツールに合わせる。
  function brushCursorCss() {
    const screen = Math.max(8, Math.min(120, brush * zoom)); // 直径(px)・上限はカーソルサイズ制限
    const s = Math.ceil(screen) + 6;        // 余白込みのカーソル画像サイズ
    const c = Math.floor(s / 2);            // 中心（ホットスポット）
    const r = screen / 2;
    // 追加=ピンクの実線円＋「＋」 / 削除=赤の破線円＋「−」 で明確に区別する
    const isAdd = tool === "add";
    const col = isAdd ? "#ec4899" : "#ef4444";
    const dash = isAdd ? "" : " stroke-dasharray='4 3'";
    const arm = 5;
    const hLine =
      `<line x1='${c - arm}' y1='${c}' x2='${c + arm}' y2='${c}' stroke='${col}' stroke-width='2'/>`;
    const vLine =
      `<line x1='${c}' y1='${c - arm}' x2='${c}' y2='${c + arm}' stroke='${col}' stroke-width='2'/>`;
    const glyph = isAdd ? hLine + vLine : hLine; // ＋ か −
    const svg =
      `<svg xmlns='http://www.w3.org/2000/svg' width='${s}' height='${s}' viewBox='0 0 ${s} ${s}'>` +
      `<circle cx='${c}' cy='${c}' r='${r}' fill='none' stroke='${col}' stroke-width='1.5'${dash}/>` +
      glyph +
      `</svg>`;
    return `url("data:image/svg+xml,${encodeURIComponent(svg)}") ${c} ${c}, crosshair`;
  }
  function updateCursor() {
    overlayCanvas().style.cursor = brushCursorCss();
  }

  // -- 入力 ---------------------------------------------------------------
  function pos(e) {
    const r = overlayCanvas().getBoundingClientRect();
    return { x: (e.clientX - r.left) / zoom, y: (e.clientY - r.top) / zoom };
  }
  function snapshot() {
    undoStack.push({
      add: copyBuf(addBuf), remove: copyBuf(removeBuf),
    });
    if (undoStack.length > 30) undoStack.shift();
    redoStack.length = 0;
  }
  function copyBuf(buf) {
    const c = newBuf();
    c.getContext("2d").drawImage(buf, 0, 0);
    return c;
  }
  function paint(p) {
    const buf = tool === "add" ? addBuf : removeBuf;
    const other = tool === "add" ? removeBuf : addBuf;
    const ctx = buf.getContext("2d");
    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = tool === "add" ? "#ec4899" : "#ef4444";
    ctx.beginPath();
    ctx.arc(p.x, p.y, brush / 2, 0, Math.PI * 2);
    ctx.fill();
    // 反対のブラシ跡を同じ場所から消す（最後の操作を優先＝塗り直しで上書きできる）
    const octx = other.getContext("2d");
    octx.save();
    octx.globalCompositeOperation = "destination-out";
    octx.fillStyle = "#000";
    octx.beginPath();
    octx.arc(p.x, p.y, brush / 2, 0, Math.PI * 2);
    octx.fill();
    octx.restore();
    redrawOverlay();
  }

  function bind() {
    const ov = overlayCanvas();
    ov.addEventListener("pointerdown", (e) => {
      drawing = true; snapshot(); paint(pos(e)); ov.setPointerCapture(e.pointerId);
    });
    ov.addEventListener("pointermove", (e) => { if (drawing) paint(pos(e)); });
    ov.addEventListener("pointerup", () => (drawing = false));
    ov.addEventListener("pointerleave", () => (drawing = false));
    updateCursor();
  }

  // -- API ----------------------------------------------------------------
  return {
    init: bind,
    load,
    setPreview,
    setTool: (t) => { tool = t; updateCursor(); },
    setBrush: (b) => { brush = b; updateCursor(); },
    setZoom: (z) => { zoom = Math.max(0.2, Math.min(5, z)); applyZoom(); updateCursor(); },
    getZoom: () => zoom,
    undo() {
      if (!undoStack.length) return;
      redoStack.push({ add: copyBuf(addBuf), remove: copyBuf(removeBuf) });
      const s = undoStack.pop();
      addBuf = s.add; removeBuf = s.remove; redrawOverlay();
    },
    redo() {
      if (!redoStack.length) return;
      undoStack.push({ add: copyBuf(addBuf), remove: copyBuf(removeBuf) });
      const s = redoStack.pop();
      addBuf = s.add; removeBuf = s.remove; redrawOverlay();
    },
    // 表示解像度の PNG dataURL（空なら null）
    exportBuffers() {
      return {
        add: isEmpty(addBuf) ? null : toMaskDataUrl(addBuf),
        remove: isEmpty(removeBuf) ? null : toMaskDataUrl(removeBuf),
      };
    },
  };

  function isEmpty(buf) {
    const d = buf.getContext("2d").getImageData(0, 0, dispW, dispH).data;
    for (let i = 3; i < d.length; i += 4) if (d[i] !== 0) return false;
    return true;
  }
  // カラーバッファを白黒マスク PNG に変換
  function toMaskDataUrl(buf) {
    const c = newBuf();
    const ctx = c.getContext("2d");
    ctx.fillStyle = "#000"; ctx.fillRect(0, 0, dispW, dispH);
    const src = buf.getContext("2d").getImageData(0, 0, dispW, dispH);
    const out = ctx.getImageData(0, 0, dispW, dispH);
    for (let i = 0; i < src.data.length; i += 4) {
      const on = src.data[i + 3] > 0;
      out.data[i] = out.data[i + 1] = out.data[i + 2] = on ? 255 : 0;
      out.data[i + 3] = 255;
    }
    ctx.putImageData(out, 0, 0);
    return c.toDataURL("image/png");
  }
})();
