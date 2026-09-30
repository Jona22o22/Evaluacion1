const API = "/api";
const ATRIBUTOS = {  // atributos variables por categoría
  Teclados: [["conexion", "Conexión (USB, Bluetooth...)"], ["distribucion", "Distribución (ES, US...)"]],
  Pantallas: [["pulgadas", "Pulgadas"], ["resolucion", "Resolución (1920x1080...)"]],
  Televisores: [["pulgadas", "Pulgadas"], ["resolucion", "Resolución (3840x2160...)"]],
};
const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => "Bs " + Number(n).toLocaleString("es-BO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(path, opts) {
  const r = await fetch(API + path, opts);
  let body = null;
  try { body = await r.json(); } catch (_) {}
  return { status: r.status, ok: r.ok, body, instancia: r.headers.get("X-Instance-Id") };
}

function nav() {
  const h = location.hash || "#/catalogo";
  document.querySelectorAll("nav a").forEach((a) => a.classList.toggle("activo", h.startsWith(a.getAttribute("href"))));
}

async function vistaCatalogo() {
  $("#vista").innerHTML = "<p>Cargando catálogo…</p>";
  const r = await api("/productos");
  if (!r.ok) { $("#vista").innerHTML = `<div class="msg ko">No se pudo cargar el catálogo (HTTP ${r.status}): ${esc(r.body?.error)} [paso: ${esc(r.body?.paso)}]</div>`; return; }
  if (!r.body.length) { $("#vista").innerHTML = "<p>No hay productos publicados.</p>"; return; }
  $("#vista").innerHTML = `<p><b>${r.body.length}</b> productos publicados · atendido por <code>${esc(r.instancia)}</code></p><div class="grid">` +
    r.body.map((p) => `<div class="card" onclick="location.hash='#/detalle/${p.producto_id}'">
      <img loading="lazy" src="${esc(p.miniatura_url)}" alt="${esc(p.nombre)}">
      <div class="cuerpo"><h3>${esc(p.nombre)}</h3><span class="chip">${esc(p.categoria)}</span>
      <p class="precio">${money(p.precio)}</p></div></div>`).join("") + "</div>";
}

async function vistaDetalle(id) {
  const r = await api("/productos/" + id);
  if (!r.ok) { $("#vista").innerHTML = `<div class="msg ko">HTTP ${r.status}: ${esc(r.body?.error)}</div>`; return; }
  const p = r.body;
  const attrs = Object.entries(p.atributos || {}).map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join("");
  $("#vista").innerHTML = `<div class="panel"><div class="detalle">
    <div>${p.miniatura_url ? `<img src="${esc(p.miniatura_url)}" alt="">` : "<p>Sin fotografía disponible</p>"}</div>
    <div><h2>${esc(p.nombre)}</h2><span class="chip">${esc(p.categoria)}</span> <span class="chip">${esc(p.estado)}</span>
    <p class="precio">${money(p.precio)}</p><p>${esc(p.descripcion)}</p>
    <p><small>producto_id: <b>${p.producto_id}</b> · código: ${esc(p.codigo)} · atendido por ${esc(r.instancia)}</small></p>
    <h3>Atributos</h3><table>${attrs || "<tr><td>Sin atributos</td></tr>"}</table>
    <button class="sec" onclick="location.hash='#/catalogo'">← Volver</button></div></div></div>`;
}

let cats = [];
async function vistaRegistrar() {
  const r = await api("/categorias");
  if (!r.ok) { $("#vista").innerHTML = `<div class="msg ko">No se pudieron cargar categorías (HTTP ${r.status}): ${esc(r.body?.error)}</div>`; return; }
  cats = r.body;
  $("#vista").innerHTML = `<form id="f" novalidate><h2>Registrar producto</h2>
   <div class="fila"><div><label>Código</label><input id="codigo" maxlength="50"><div class="err" id="e-codigo"></div></div>
   <div><label>Nombre</label><input id="nombre" maxlength="150"><div class="err" id="e-nombre"></div></div></div>
   <label>Descripción</label><textarea id="descripcion" rows="3"></textarea><div class="err" id="e-descripcion"></div>
   <div class="fila"><div><label>Precio</label><input id="precio" type="number" step="0.01" min="0"><div class="err" id="e-precio"></div></div>
   <div><label>Categoría</label><select id="categoria"><option value="">Seleccione…</option>${cats.map((c) => `<option value="${c.categoria_id}">${esc(c.nombre)}</option>`).join("")}</select><div class="err" id="e-categoria"></div></div></div>
   <div id="attrs"></div>
   <label>Fotografía (JPEG o PNG, máx. 5 MB)</label><input id="foto" type="file" accept="image/jpeg,image/png"><div class="err" id="e-foto"></div>
   <button type="submit" id="enviar">Registrar</button><button type="button" class="sec" id="reintentar" style="display:none">Reintentar imagen</button>
   <div id="estado"></div></form>`;
  $("#categoria").onchange = pintarAttrs;
  $("#f").onsubmit = enviar;
  $("#reintentar").onclick = reintentar;
}

function pintarAttrs() {
  const c = cats.find((x) => String(x.categoria_id) === $("#categoria").value);
  $("#attrs").innerHTML = c ? `<h3>Atributos de ${esc(c.nombre)}</h3><div class="fila">` +
    (ATRIBUTOS[c.nombre] || []).map(([k, l]) => `<div><label>${l}</label><input data-attr="${k}"><div class="err" id="e-${k}"></div></div>`).join("") + "</div>" : "";
}

function marcar(id, msg) { const e = $("#e-" + id); if (e) e.textContent = msg || ""; const i = $("#" + id); if (i) i.classList.toggle("mal", !!msg); }
function estado(cls, txt) { $("#estado").innerHTML = `<div class="msg ${cls}">${esc(txt)}</div>`; }

let pendiente = null; // {producto_id, archivo}
function validar() {
  let ok = true;
  ["codigo", "nombre", "descripcion", "precio", "categoria", "foto"].forEach((k) => marcar(k, ""));
  const req = (k, m) => { if (!$("#" + k).value.trim()) { marcar(k, m); ok = false; } };
  req("codigo", "Obligatorio"); req("nombre", "Obligatorio"); req("descripcion", "Obligatorio"); req("categoria", "Seleccione una categoría");
  const pr = $("#precio").value;
  if (pr === "" || Number(pr) < 0) { marcar("precio", "Precio requerido y no negativo"); ok = false; }
  document.querySelectorAll("[data-attr]").forEach((i) => { const m = i.value.trim() ? "" : "Obligatorio"; marcar_attr(i, m); if (m) ok = false; });
  const f = $("#foto").files[0];
  if (!f) { marcar("foto", "Seleccione una fotografía"); ok = false; }
  else if (!["image/jpeg", "image/png"].includes(f.type)) { marcar("foto", "Solo JPEG o PNG"); ok = false; }
  else if (f.size > 5 * 1024 * 1024) { marcar("foto", "Máximo 5 MB"); ok = false; }
  return ok;
}
function marcar_attr(i, m) { i.classList.toggle("mal", !!m); const e = $("#e-" + i.dataset.attr); if (e) e.textContent = m; }

async function subirImagen(id, archivo) {
  const fd = new FormData(); fd.append("imagen", archivo);
  return api(`/productos/${id}/imagen`, { method: "POST", body: fd });
}

function mostrarResultadoImagen(r, id) {
  if (r.ok) {
    pendiente = null; $("#reintentar").style.display = "none";
    estado("ok", `Producto ${id} PUBLICADO (HTTP ${r.status}, instancia ${r.instancia}).`);
    $("#estado").innerHTML += `<button type="button" onclick="location.hash='#/detalle/${id}'">Ver detalle</button>`;
  } else {
    $("#reintentar").style.display = "inline-block";
    estado("ko", `El producto ${id} quedó PENDIENTE (HTTP ${r.status}). Paso fallido: ${r.body?.paso}. ${r.body?.error}`);
  }
}

async function enviar(ev) {
  ev.preventDefault();
  if (!validar()) { estado("ko", "Corrija los campos marcados."); return; }
  $("#enviar").disabled = true; estado("info", "Registrando…");
  const atributos = {}; document.querySelectorAll("[data-attr]").forEach((i) => { atributos[i.dataset.attr] = i.value.trim(); });
  const body = { codigo: $("#codigo").value, nombre: $("#nombre").value, descripcion: $("#descripcion").value,
                 precio: Number($("#precio").value), categoria_id: Number($("#categoria").value), atributos };
  const archivo = $("#foto").files[0];
  const r = await api("/productos", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  $("#enviar").disabled = false;
  if (r.status === 201) {
    pendiente = { producto_id: r.body.producto_id, archivo };
    estado("info", `Producto ${r.body.producto_id} registrado como PENDIENTE. Subiendo imagen…`);
    mostrarResultadoImagen(await subirImagen(r.body.producto_id, archivo), r.body.producto_id);
  } else if (r.status === 409) {
    marcar("codigo", "Código duplicado");
    estado("ko", `HTTP 409: ${r.body.error}. Producto existente ${r.body.producto_id} (${r.body.estado}). No se creó un producto nuevo.`);
  } else {
    estado("ko", `HTTP ${r.status} [paso: ${r.body?.paso}]: ${r.body?.error}` + (r.body?.producto_id ? ` (producto ${r.body.producto_id} PENDIENTE)` : ""));
  }
}

async function reintentar() {
  if (!pendiente) return;
  estado("info", "Reintentando imagen…");
  mostrarResultadoImagen(await subirImagen(pendiente.producto_id, pendiente.archivo), pendiente.producto_id);
}

function ruta() {
  nav();
  const h = location.hash || "#/catalogo";
  if (h.startsWith("#/detalle/")) return vistaDetalle(h.split("/")[2]);
  if (h.startsWith("#/registrar")) return vistaRegistrar();
  return vistaCatalogo();
}
window.addEventListener("hashchange", ruta);
ruta();
