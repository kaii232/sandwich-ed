export function recordWellbeingCheckpoint() {
  const key = "wb_cp_count";
  const count = Number(localStorage.getItem(key) || 0) + 1;
  localStorage.setItem(key, String(count));
  // let listeners (the modal) know a checkpoint happened
  window.dispatchEvent(new CustomEvent("wb:checkpoint", { detail: { count } }));
}
