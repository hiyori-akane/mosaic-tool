// 検証用フォールバックAPI（?dev=1 のときだけ有効）。
// devserver.py の HTTP-RPC を fetch で呼び、本物の Python Api を実行する。
// job 系メソッドは同期実行され、サーバが返す events を再生する（onProgress/onJobDone）。
(function () {
  const isDev = new URLSearchParams(location.search).has("dev");
  if (!isDev) return;

  const JOB_METHODS = new Set(["detect", "detect_all", "export"]);

  async function rpc(method, args) {
    const res = await fetch("/rpc", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ method, args }),
    });
    if (!res.ok) throw new Error(`rpc ${method} failed: HTTP ${res.status}`);
    const data = await res.json();
    // サーバが捕捉したイベントをフロントへ再生
    if (Array.isArray(data.events)) {
      for (const [fn, fnArgs] of data.events) {
        if (typeof window[fn] === "function") window[fn](...fnArgs);
      }
    }
    if (data.error) throw new Error(data.error);
    return data.result;
  }

  // window.pywebview.api と同じ形のプロキシ
  const handler = {
    get(_t, method) {
      return (...args) => rpc(method, args);
    },
  };
  window.__DEV_API__ = new Proxy({}, handler);
  console.info("[dev] HTTP-RPC スタブAPIを有効化しました");
})();
