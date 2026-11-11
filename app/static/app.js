// minipay — frontend sin frameworks. Habla con la API del mismo servidor.
"use strict";

const $ = (sel) => document.querySelector(sel);
const pesos = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" });
const fmt = (cents) => pesos.format(cents / 100);
const aCentavos = (valor) => Math.round(parseFloat(valor) * 100);
// hourCycle h23: algunos navegadores muestran "05:55" (sin a. m./p. m.) para las 17:55.
const fecha = (iso) =>
  new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short", hourCycle: "h23" });
const nombres = {
  balance_set: "Cambio de saldo",
  transfer: "Transferencia",
  payment: "Pago de cobro",
};
const estados = { pending: "Pendiente", paid: "Pagado", rejected: "Rechazado" };

let token = sessionStorage.getItem("token");
let yo = null;

// ---------- API ----------
async function api(method, path, body, extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = r.status === 204 ? null : await r.json().catch(() => null);
  if (!r.ok) {
    if (r.status === 401 && token) salir();
    throw new Error(mensajeDeError(data) || `Error ${r.status}`);
  }
  return data;
}

function mensajeDeError(data) {
  if (!data || !data.detail) return null;
  if (typeof data.detail === "string") return data.detail;
  return data.detail.map((d) => d.msg).join(". "); // errores de validación (422)
}

// Clave de idempotencia por envío de formulario.
// Si se corta la red, el reintento usa LA MISMA clave → no se cobra dos veces.
function claveDe(form) {
  if (!form.dataset.key) form.dataset.key = nuevaClave();
  return form.dataset.key;
}

// crypto.randomUUID solo existe en HTTPS o localhost. Por http (ej. desde el celular
// por Tailscale) se arma una clave aleatoria con getRandomValues, que sí existe.
function nuevaClave() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// ---------- UI ----------
let timer;
function avisar(texto, tipo = "") {
  const m = $("#mensaje");
  m.textContent = texto;
  m.className = `mensaje ${tipo}`;
  m.hidden = false;
  clearTimeout(timer);
  timer = setTimeout(() => (m.hidden = true), 3500);
}

async function conBoton(boton, fn) {
  boton.disabled = true;
  try {
    await fn();
  } catch (e) {
    avisar(e.message === "Failed to fetch" ? "Sin conexión. Probá de nuevo." : e.message, "error");
  } finally {
    boton.disabled = false;
  }
}

function li(html) {
  const el = document.createElement("li");
  el.innerHTML = html;
  return el;
}

function escapar(texto) {
  const d = document.createElement("div");
  d.textContent = texto;
  return d.innerHTML;
}

function vacio(lista, texto) {
  lista.replaceChildren(li(texto));
  lista.firstChild.className = "vacio";
}

// ---------- LOGIN ----------
document.querySelectorAll("[data-user]").forEach((b) =>
  b.addEventListener("click", () => {
    $("#form-login").username.value = b.dataset.user;
    $("#form-login").requestSubmit();
  })
);

$("#form-login").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  conBoton(f.querySelector("button"), async () => {
    const r = await api("POST", "/auth/login", { username: f.username.value, password: f.password.value });
    token = r.access_token;
    sessionStorage.setItem("token", token);
    await entrar();
  });
});

$("#salir").addEventListener("click", salir);

function salir() {
  token = null;
  yo = null;
  sessionStorage.removeItem("token");
  $("#sesion").hidden = true;
  $("#vista-cuenta").hidden = true;
  $("#vista-admin").hidden = true;
  $("#vista-login").hidden = false;
}

async function entrar() {
  yo = await api("GET", "/auth/me");
  $("#quien").textContent = `${yo.display_name}`;
  $("#sesion").hidden = false;
  $("#vista-login").hidden = true;

  if (yo.role === "admin") {
    $("#vista-admin").hidden = false;
    await cargarConciliacion();
    return;
  }
  const persona = yo.role === "user";
  $("#vista-cuenta").hidden = false;
  $("#bloque-elegir").hidden = !persona;
  $("#bloque-transferir").hidden = !persona;
  $("#bloque-cobros").hidden = !persona;
  $("#bloque-cobrar").hidden = persona;
  // No mostrarse a uno mismo como destino.
  document.querySelectorAll("select option").forEach((o) => (o.hidden = o.value === yo.username));
  const sel = $("#form-transferir").to_username;
  if (sel.selectedOptions[0]?.hidden) sel.value = [...sel.options].find((o) => !o.hidden).value;
  await refrescar();
}

// ---------- CUENTA ----------
async function refrescar() {
  const tareas = [cargarSaldo(), cargarMovimientos()];
  if (yo.role === "user") tareas.push(cargarCobros());
  if (yo.role === "merchant") tareas.push(cargarCobrosComercio());
  await Promise.all(tareas);
}

async function cargarSaldo() {
  const r = await api("GET", "/me/balance");
  $("#saldo").textContent = fmt(r.balance_cents);
}

async function cargarMovimientos() {
  const lista = $("#lista-movimientos");
  const movs = await api("GET", "/me/movements");
  if (!movs.length) return vacio(lista, "Todavía no hay movimientos.");
  lista.replaceChildren(
    ...movs.map((m) =>
      li(`<span>${nombres[m.kind] || m.kind}<br><small class="muted">${fecha(m.created_at)}</small></span>
          <span class="${m.amount_cents < 0 ? "negativo" : "positivo"}">${m.amount_cents > 0 ? "+" : ""}${fmt(m.amount_cents)}</span>`)
    )
  );
}

async function elegirSaldo(cents, boton) {
  await conBoton(boton, async () => {
    await api("PUT", "/me/balance", { balance_cents: cents });
    avisar(`Saldo: ${fmt(cents)}`, "ok");
    await refrescar();
  });
}

document.querySelectorAll("[data-saldo]").forEach((b) =>
  b.addEventListener("click", () => elegirSaldo(Number(b.dataset.saldo), b))
);

$("#form-saldo").addEventListener("submit", (ev) => {
  ev.preventDefault();
  elegirSaldo(aCentavos(ev.target.monto.value), ev.target.querySelector("button")).then(() => ev.target.reset());
});

$("#form-transferir").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  conBoton(f.querySelector("button"), async () => {
    const key = claveDe(f);
    try {
      const r = await api(
        "POST",
        "/me/transfers",
        { to_username: f.to_username.value, amount_cents: aCentavos(f.monto.value) },
        { "Idempotency-Key": key }
      );
      delete f.dataset.key;
      f.monto.value = "";
      avisar(`Transferiste ${fmt(r.amount_cents)}`, "ok");
      await refrescar();
    } catch (e) {
      if (e.message !== "Failed to fetch") delete f.dataset.key; // la API respondió: clave nueva la próxima
      throw e;
    }
  });
});

// ---------- COBROS (persona) ----------
async function cargarCobros() {
  const lista = $("#lista-cobros");
  const cobros = await api("GET", "/me/charges");
  if (!cobros.length) return vacio(lista, "No tenés cobros.");
  lista.replaceChildren(
    ...cobros.map((c) => {
      const el = li(`<span><strong>${escapar(c.description)}</strong><br><small class="muted">${escapar(c.merchant_username)} · ${fmt(c.amount_cents)}</small></span>`);
      if (c.status === "pending") {
        const acciones = document.createElement("span");
        acciones.className = "acciones";
        const pagar = document.createElement("button");
        pagar.className = "primario";
        pagar.textContent = "Pagar";
        pagar.onclick = () =>
          conBoton(pagar, async () => {
            pagar.dataset.key ||= nuevaClave();
            await api("POST", `/me/charges/${c.id}/pay`, undefined, { "Idempotency-Key": pagar.dataset.key });
            avisar("Cobro pagado", "ok");
            await refrescar();
          });
        const rechazar = document.createElement("button");
        rechazar.textContent = "Rechazar";
        rechazar.onclick = () =>
          conBoton(rechazar, async () => {
            await api("POST", `/me/charges/${c.id}/reject`);
            avisar("Cobro rechazado");
            await refrescar();
          });
        acciones.append(pagar, rechazar);
        el.append(acciones);
      } else {
        el.insertAdjacentHTML("beforeend", `<span class="estado">${estados[c.status]}</span>`);
      }
      return el;
    })
  );
}

// ---------- COBROS (comercio) ----------
async function cargarCobrosComercio() {
  const lista = $("#lista-cobros-comercio");
  const cobros = await api("GET", "/merchant/charges");
  if (!cobros.length) return vacio(lista, "Todavía no cobraste nada.");
  lista.replaceChildren(
    ...cobros.map((c) =>
      li(`<span><strong>${escapar(c.description)}</strong><br><small class="muted">${escapar(c.payer_username)} · ${fmt(c.amount_cents)}</small></span>
          <span class="estado">${estados[c.status]}</span>`)
    )
  );
}

$("#form-cobrar").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const f = ev.target;
  conBoton(f.querySelector("button"), async () => {
    await api("POST", "/merchant/charges", {
      payer_username: f.payer_username.value,
      amount_cents: aCentavos(f.monto.value),
      description: f.description.value,
    });
    f.reset();
    avisar("Cobro creado", "ok");
    await refrescar();
  });
});

// ---------- ADMIN ----------
function mostrarConciliacion(r) {
  $("#conciliacion").innerHTML = r.ok
    ? `<span class="positivo">✔ Cuadra: total ${fmt(r.total_cents)}</span><br><small class="muted">${r.entries_count} renglones · ${fecha(r.ran_at)}</small>`
    : `<span class="negativo">✘ Descuadre: ${fmt(r.total_cents)}</span>`;
}

async function cargarConciliacion() {
  try {
    mostrarConciliacion(await api("GET", "/admin/reconciliation"));
  } catch {
    $("#conciliacion").textContent = "Todavía no hay conciliaciones.";
  }
}

$("#conciliar").addEventListener("click", (ev) =>
  conBoton(ev.target, async () => mostrarConciliacion(await api("POST", "/admin/reconciliation")))
);

// ---------- REFRESCO AUTOMÁTICO ----------
// Cada 10 s (solo con la pestaña visible), y al volver a la pestaña.
// Así Ana ve la transferencia de Marta sin recargar la página.
function refrescoSilencioso() {
  if (!token || !yo || document.hidden) return;
  const tarea = yo.role === "admin" ? cargarConciliacion() : refrescar();
  tarea.catch(() => {}); // si falla la red, se reintenta en el próximo ciclo
}
setInterval(refrescoSilencioso, 10_000);
document.addEventListener("visibilitychange", refrescoSilencioso);

// ---------- INICIO ----------
if (token) entrar().catch(salir);
