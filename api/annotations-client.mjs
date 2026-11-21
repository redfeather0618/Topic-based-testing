/** 五碼標註統計用戶端；網址與權杖由執行時提供。 */
export function createAnnotationsClient(baseUrl, token) {
  const root = baseUrl.replace(/\/+$/, "");
  async function get(path, filters = {}, signal) {
    const query = new URLSearchParams(Object.entries(filters).filter(([,v]) => v != null));
    const response = await fetch(root + "/api/v1/annotations" + path + "?" + query,
      { headers: { Authorization: "Bearer " + token }, signal });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(data?.error?.message ?? "標註查詢失敗");
      Object.assign(error, {status: response.status, code: data?.error?.code, details: data?.error?.details});
      throw error;
    }
    if (data === null) throw new Error("服務未回傳JSON");
    return data;
  }
  return {
    current: signal => get("/datasets/current", {}, signal),
    overview: (filters, signal) => get("/stats/overview", filters, signal),
    rCodes: (filters, signal) => get("/stats/r-codes", filters, signal),
    categories: (filters, signal) => get("/stats/categories", filters, signal),
    cases: (filters, signal) => get("/cases", filters, signal),
    case: (id, filters, signal) => get("/cases/" + encodeURIComponent(id), filters, signal),
    async dashboard(filters = {}, signal) {
      // 先固定版本，避免匯入新版期間不同圖表混用資料。
      const version = filters.dataset_version ?? (await get("/datasets/current", {}, signal)).dataset_version;
      const fixed = {...filters, dataset_version: version};
      const [overview, rCodes, categories] = await Promise.all([
        get("/stats/overview", fixed, signal), get("/stats/r-codes", fixed, signal),
        get("/stats/categories", fixed, signal)
      ]);
      return {filters: fixed, overview, rCodes, categories};
    }
  };
}
