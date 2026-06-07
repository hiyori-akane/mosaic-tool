// JS↔Python ブリッジのラッパ。
// - pywebviewready を待って window.pywebview.api を解決（本番）。
// - 無ければ window.__DEV_API__（devserver の HTTP-RPC）へフォールバック（検証）。
// - onProgress / onJobDone / onError を window に定義し Python から呼ばれる口にする。

window.Bridge = (function () {
  let apiPromise = null;

  function resolveApi() {
    if (apiPromise) return apiPromise;
    apiPromise = new Promise((resolve) => {
      if (window.pywebview && window.pywebview.api) {
        resolve(window.pywebview.api);
        return;
      }
      let settled = false;
      const done = (api) => { if (!settled) { settled = true; resolve(api); } };
      window.addEventListener("pywebviewready", () => done(window.pywebview.api));
      // pywebview が無い環境（ブラウザ検証）では dev API を使う
      setTimeout(() => {
        if (window.pywebview && window.pywebview.api) done(window.pywebview.api);
        else if (window.__DEV_API__) done(window.__DEV_API__);
        else done(null); // API が無ければ null で解決し call() を即エラーにする
      }, 300);
    });
    return apiPromise;
  }

  async function call(method, ...args) {
    const api = await resolveApi();
    if (!api || typeof api[method] !== "function") {
      throw new Error("API未準備: " + method);
    }
    return api[method](...args);
  }

  // Python → JS のイベント口（job 進捗・完了・エラー）
  const handlers = { progress: [], done: [], error: [] };
  window.onProgress = (jobId, done, total, phase) =>
    handlers.progress.forEach((h) => h(jobId, done, total, phase));
  window.onJobDone = (jobId, result) =>
    handlers.done.forEach((h) => h(jobId, result));
  window.onError = (jobId, message) =>
    handlers.error.forEach((h) => h(jobId, message));

  return {
    call,
    ready: resolveApi,
    onProgress: (h) => handlers.progress.push(h),
    onJobDone: (h) => handlers.done.push(h),
    onError: (h) => handlers.error.push(h),
  };
})();
