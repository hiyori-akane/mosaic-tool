// アプリのフロント状態（単純なシングルトン）。
window.AppState = {
  items: [],          // {id, name, w, h, thumb_dataurl, status}
  byId: {},
  currentIndex: -1,   // 補正中の画像のインデックス（items 内の位置）
  currentId: null,    // 補正中の画像ID
  view: {             // get_view の戻り（補正中）
    scale: 1, dispW: 0, dispH: 0, blockPx: 10,
  },
  outDir: "out",      // 既定の出力先（書き出し時に変更可）
  jobs: {},           // job_id -> {kind, ...}

  setItems(items) {
    this.items = items;
    this.byId = {};
    items.forEach((it) => (this.byId[it.id] = it));
    this.currentIndex = -1;
    this.currentId = null;
  },
  updateStatus(id, status) {
    if (this.byId[id]) this.byId[id].status = status;
  },
  ids() {
    return this.items.map((i) => i.id);
  },
  reset() {
    this.items = [];
    this.byId = {};
    this.currentIndex = -1;
    this.currentId = null;
    this.jobs = {};
  },
};
