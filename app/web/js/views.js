// ウィザード式フローの画面切替とイベント配線。
// 取り込み → 検出（自動） → 補正（1枚ずつ・前/次） → 書き出し → 次の取り込み
(function () {
  const $ = (id) => document.getElementById(id);
  const S = window.AppState;
  const STEPS = ["import", "detect", "review", "export"];

  function setStatus(msg) { $("status-line").textContent = msg || ""; }

  // -- ステップ切替 -------------------------------------------------------
  function showStep(name) {
    STEPS.forEach((s) => $("view-" + s).classList.toggle("hidden", s !== name));
    // ステッパー: 現在地を is-active、通過済みを is-done
    const idx = STEPS.indexOf(name);
    document.querySelectorAll(".step").forEach((el) => {
      const i = STEPS.indexOf(el.dataset.step);
      el.classList.toggle("is-active", i === idx);
      el.classList.toggle("is-done", i < idx);
    });
  }

  // Bridge 呼び出しの拒否を拾って UI を整える共通ラッパ
  async function guard(fn) {
    try {
      await fn();
    } catch (err) {
      setStatus("エラー: " + (err && err.message ? err.message : err));
    }
  }

  function setBarWidth(sel, pct) {
    const b = document.querySelector(sel);
    if (b) b.style.width = pct + "%";
  }
  const setDetectProgress = (pct) => setBarWidth("#detect-progress .bar", pct);
  const setExportProgress = (pct) => setBarWidth("#export-progress .bar", pct);

  // =====================================================================
  // Step 1: 取り込み
  // =====================================================================
  $("btn-pick-files").addEventListener("click", () => guard(async () => {
    const { paths } = await Bridge.call("pick_files");
    if (paths && paths.length) await loadBatch(paths);
  }));
  $("btn-pick-folder").addEventListener("click", () => guard(async () => {
    const { dir } = await Bridge.call("pick_folder");
    if (dir) await loadBatch([dir]);
  }));

  async function loadBatch(paths) {
    setStatus("読み込み中…");
    const { items } = await Bridge.call("load_batch", paths);
    startBatch(items);
  }

  // パスが取れない環境（ブラウザ検証など）向けに dataURL で取り込む
  async function loadBatchData(files) {
    setStatus("読み込み中…");
    const { items } = await Bridge.call("load_batch_data", files);
    startBatch(items);
  }

  // 取り込み後: 検出ステップへ進み、自動で全件検出を開始する
  function startBatch(items) {
    if (!items || !items.length) {
      setStatus("取り込める画像がありませんでした");
      showStep("import");
      return;
    }
    S.setItems(items);
    showStep("detect");
    $("detect-msg").textContent = "検出中…";
    $("detect-count").textContent = `0 / ${items.length}`;
    setDetectProgress(0);
    guard(async () => {
      const { job_id } = await Bridge.call("detect_all");
      S.jobs[job_id] = { kind: "detect" };
    });
  }

  function readAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve({ name: file.name, dataurl: r.result });
      r.onerror = () => reject(r.error);
      r.readAsDataURL(file);
    });
  }

  // ドラッグ&ドロップ
  const dz = $("dropzone");
  ["dragover", "dragenter"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
  dz.addEventListener("dragleave", (e) => { e.preventDefault(); dz.classList.remove("drag"); });
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("drag");
    const files = Array.from((e.dataTransfer && e.dataTransfer.files) || []);
    if (!files.length) return;
    guard(async () => {
      // pywebview ではネイティブパスが取れることがある。あればパス経由で取り込む。
      const paths = files.map((f) => f.path).filter(Boolean);
      if (paths.length === files.length) {
        await loadBatch(paths);
      } else {
        const data = await Promise.all(files.map(readAsDataUrl));
        await loadBatchData(data);
      }
    });
  });

  // =====================================================================
  // Step 3: 補正（1枚ずつ）
  // =====================================================================
  async function openReview(index) {
    if (index < 0 || index >= S.items.length) return;
    S.currentIndex = index;
    const it = S.items[index];
    S.currentId = it.id;
    showStep("review");
    const view = await Bridge.call("get_view", it.id);
    S.view = { scale: view.scale, dispW: view.disp_w, dispH: view.disp_h, blockPx: view.block_px };
    $("block-size").value = view.block_px;
    $("block-val").textContent = view.block_px;
    await CanvasEditor.load(view);
    updateReviewNav();
    setStatus(`補正中: ${it.name}`);
  }

  function updateReviewNav() {
    const i = S.currentIndex, n = S.items.length;
    $("review-pos").textContent = `画像 ${i + 1} / ${n} — ${S.items[i]?.name || ""}`;
    $("btn-prev").disabled = i <= 0;
    $("btn-next").textContent = i >= n - 1 ? "書き出しへ →" : "次へ →";
  }

  // 現在の補正（ブラシ + モザイク強度）をバックエンドに保存し、確認済みにする
  async function persistCurrent() {
    if (!S.currentId) return;
    const { add, remove } = CanvasEditor.exportBuffers();
    const params = { block_px: +$("block-size").value };
    await Bridge.call("apply_correction", S.currentId, add, remove, params);
    const res = await Bridge.call("set_reviewed", S.currentId, true);
    if (res && res.status) S.updateStatus(S.currentId, res.status);
  }

  document.querySelectorAll(".tool").forEach((b) =>
    b.addEventListener("click", () => {
      document.querySelectorAll(".tool").forEach((x) => x.classList.remove("is-active"));
      b.classList.add("is-active");
      CanvasEditor.setTool(b.dataset.tool);
    }));
  $("brush-size").addEventListener("input", (e) => CanvasEditor.setBrush(+e.target.value));
  $("block-size").addEventListener("input", (e) => { $("block-val").textContent = e.target.value; });
  $("btn-undo").addEventListener("click", () => CanvasEditor.undo());
  $("btn-redo").addEventListener("click", () => CanvasEditor.redo());
  $("btn-zoom-in").addEventListener("click", () => CanvasEditor.setZoom(CanvasEditor.getZoom() * 1.25));
  $("btn-zoom-out").addEventListener("click", () => CanvasEditor.setZoom(CanvasEditor.getZoom() / 1.25));

  $("btn-redetect").addEventListener("click", () => guard(async () => {
    const { job_id } = await Bridge.call("detect", S.currentId);
    S.jobs[job_id] = { kind: "detect", reopen: S.currentIndex };
    setStatus("再検出中…");
  }));

  // 補正 → 検出ステップへ戻る（全件を再検出。手動補正は保持される）
  $("btn-to-detect").addEventListener("click", () => guard(async () => {
    const back = S.currentIndex < 0 ? 0 : S.currentIndex;
    showStep("detect");
    $("detect-msg").textContent = "再検出中…";
    $("detect-count").textContent = `0 / ${S.items.length}`;
    setDetectProgress(0);
    const { job_id } = await Bridge.call("detect_all");
    S.jobs[job_id] = { kind: "detect", reopen: back };
  }));

  $("btn-apply").addEventListener("click", () => guard(async () => {
    const { add, remove } = CanvasEditor.exportBuffers();
    const params = { block_px: +$("block-size").value };
    setStatus("適用中…");
    const res = await Bridge.call("apply_correction", S.currentId, add, remove, params);
    if (res.error) { setStatus("エラー: " + res.error); return; }
    if (res.preview_dataurl) CanvasEditor.setPreview(res.preview_dataurl);
    setStatus("プレビューを更新しました");
  }));

  $("btn-prev").addEventListener("click", () => guard(async () => {
    if (S.currentIndex <= 0) return;
    await persistCurrent();
    await openReview(S.currentIndex - 1);
  }));

  $("btn-next").addEventListener("click", () => guard(async () => {
    await persistCurrent();
    if (S.currentIndex >= S.items.length - 1) {
      goExport();
    } else {
      await openReview(S.currentIndex + 1);
    }
  }));

  // =====================================================================
  // Step 4: 書き出し
  // =====================================================================
  function goExport() {
    showStep("export");
    $("out-dir").textContent = S.outDir || "out";
    $("export-result").textContent = "";
    $("done-row").classList.add("hidden");
    setStatus("書き出しの準備ができました");
  }

  $("btn-back-review").addEventListener("click", () =>
    openReview(Math.max(0, S.items.length - 1)));

  $("btn-out-dir").addEventListener("click", () => guard(async () => {
    const { dir } = await Bridge.call("pick_folder");
    if (dir) { S.outDir = dir; $("out-dir").textContent = dir; }
  }));

  $("btn-export").addEventListener("click", () => guard(async () => {
    const ids = S.ids();
    if (!ids.length) { setStatus("書き出す画像がありません"); return; }
    const options = { format: $("out-format").value, pattern: "{name}_mosaic" };
    $("export-progress").classList.remove("hidden");
    setExportProgress(0);
    const { job_id } = await Bridge.call("export", ids, S.outDir || "out", options);
    S.jobs[job_id] = { kind: "export" };
    setStatus("書き出し中…");
  }));

  $("btn-new-batch").addEventListener("click", () => {
    S.reset();
    $("export-result").textContent = "";
    $("done-row").classList.add("hidden");
    $("export-progress").classList.add("hidden");
    showStep("import");
    setStatus("");
  });

  // =====================================================================
  // Job イベント
  // =====================================================================
  Bridge.onProgress((jobId, done, total, phase) => {
    const pct = total ? Math.round((done / total) * 100) : 0;
    if (phase === "export") {
      setExportProgress(pct);
    } else {
      setDetectProgress(pct);
      $("detect-count").textContent = `${done} / ${total}`;
    }
    setStatus(`${phase}: ${done}/${total}`);
  });

  Bridge.onJobDone(async (jobId, result) => {
    const job = S.jobs[jobId] || {};
    delete S.jobs[jobId];
    if (job.kind === "detect") {
      const statuses = (result && result.statuses) || {};
      Object.keys(statuses).forEach((id) => S.updateStatus(id, statuses[id]));
      setStatus(`検出完了: ${result ? result.count : 0} 件`);
      if (typeof job.reopen === "number") {
        await openReview(job.reopen);   // 単体再検出: その画像を開き直す
      } else {
        await openReview(0);            // 全件検出の完了 → 1枚目の補正へ
      }
    } else if (job.kind === "export") {
      setExportProgress(100);
      $("export-progress").classList.add("hidden");
      $("export-result").textContent =
        `${result.count} 件を ${result.out_dir} に書き出しました`;
      $("done-row").classList.remove("hidden");
      setStatus("書き出し完了");
    }
  });

  Bridge.onError((jobId, message) => {
    const job = S.jobs[jobId] || {};
    delete S.jobs[jobId];
    if (job.kind === "detect") {
      // モデル未準備などで検出に失敗 → 手動補正のみで続行（元の位置へ）
      const idx = typeof job.reopen === "number" ? job.reopen : 0;
      setStatus("検出をスキップしました（手動補正のみ）: " + message);
      openReview(idx);
      return;
    }
    setStatus("エラー: " + message);
    console.error("job error", jobId, message);
  });

  // 起動
  Bridge.ready().then(async () => {
    try {
      const s = await Bridge.call("get_settings");
      if (s.detect_error) setStatus("検出エンジン未準備: 手動補正のみ可");
    } catch (e) { /* noop */ }
    CanvasEditor.init();
    showStep("import");
  });
})();
