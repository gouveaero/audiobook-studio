/* Ajudante compartilhado: token de sessão e escritas autenticadas. */
(function (global) {
  const KEY = "studioToken";
  const q = new URLSearchParams(location.search);
  if (q.has("token")) {
    try { sessionStorage.setItem(KEY, q.get("token")); } catch (e) {}
  }

  function token() {
    try { return sessionStorage.getItem(KEY) || ""; } catch (e) { return ""; }
  }

  function href(path) {
    const t = token();
    if (!t) return path;
    const u = new URL(path, location.href);
    u.searchParams.set("token", t);
    return u.pathname + u.search + (u.hash || "");
  }

  async function studioFetch(path, opts) {
    opts = opts || {};
    const method = (opts.method || "GET").toUpperCase();
    const headers = Object.assign({}, opts.headers || {});
    if (method !== "GET" && method !== "HEAD") {
      headers["X-Studio-Token"] = token();
    }
    return fetch(path, Object.assign({}, opts, { method: method, headers: headers }));
  }

  async function studioWrite(path, body, method, headers) {
    method = method || "POST";
    headers = headers || {};
    const r = await studioFetch(path, { method: method, body: body, headers: headers });
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || "erro");
    return j;
  }

  // Resposta crua (áudio binário ou JSON de erro). Cabeçalhos extras e corpo Blob/ArrayBuffer ok.
  async function studioWriteRaw(path, body, method, headers) {
    method = method || "POST";
    headers = headers || {};
    const r = await studioFetch(path, { method: method, body: body, headers: headers });
    if (!r.ok) {
      let msg = "erro";
      try { const j = await r.json(); msg = j.error || msg; } catch (e) {}
      throw new Error(msg);
    }
    return r;
  }

  global.studio = {
    token: token,
    href: href,
    fetch: studioFetch,
    write: studioWrite,
    writeRaw: studioWriteRaw,
    post: function (path, body, headers) { return studioWrite(path, body, "POST", headers || {}); },
    postRaw: function (path, body, headers) { return studioWriteRaw(path, body, "POST", headers || {}); },
    put: function (path, body, headers) { return studioWrite(path, body, "PUT", headers || {}); },
    del: function (path, body, headers) { return studioWrite(path, body, "DELETE", headers || {}); }
  };
})(window);
