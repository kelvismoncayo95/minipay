// minipay — frontend sin frameworks, tipo "asistente": UNA pantalla a la vez,
// cada paso con una explicación corta, revisión antes de confirmar y tarjeta de resultado.
"use strict";

const app = document.getElementById("app");

// ---------- Formatos ----------
const pesosFmt = new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" });
const fmt = (cents) => pesosFmt.format(cents / 100);
/** Texto escrito por una persona → centavos. Acepta "4,80", "4.80", "1.000,50", "1000".
 *  Devuelve NaN si no es un monto válido (o tiene más de 2 decimales). */
function aCentavos(valor) {
  const t = String(valor).trim().replace(/\s|\$/g, "");
  let normal;
  if (/^\d{1,3}(\.\d{3})*(,\d{1,2})?$/.test(t) || /^\d+(,\d{1,2})?$/.test(t)) {
    normal = t.replace(/\./g, "").replace(",", "."); // coma decimal, puntos de miles
  } else if (/^\d+(\.\d{1,2})?$/.test(t)) {
    normal = t; // punto decimal: "4.80"
  } else {
    return NaN;
  }
  return Math.round(parseFloat(normal) * 100);
}
// hourCycle h23: algunos navegadores muestran "05:55" (sin a. m./p. m.) para las 17:55.
const fecha = (iso) =>
  new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short", hourCycle: "h23" });
const corto = (id) => String(id).slice(0, 8).toUpperCase();

const MAX_OPERACION = 500_000; // $5.000 (igual que la API)
const TIPOS = { balance_set: "Cambio de saldo", transfer: "Transferencia", payment: "Pago de cobro" };
const ESTADOS = { pending: "Pendiente", paid: "Pagado", rejected: "Rechazado" };

const USUARIOS = [
  { u: "ana", nombre: "Ana", icono: "👩", desc: "Persona: elige saldo, transfiere y paga cobros" },
  { u: "luis", nombre: "Luis", icono: "👨", desc: "Persona" },
  { u: "marta", nombre: "Marta", icono: "👩‍🦰", desc: "Persona" },
  { u: "pedro", nombre: "Pedro", icono: "🧑", desc: "Persona" },
  { u: "clinica-del-sur", nombre: "Clínica del Sur", icono: "🏥", desc: "Comercio: le cobra a las personas" },
  { u: "admin", nombre: "Admin", icono: "🛡️", desc: "Revisa que todo el dinero cuadre" },
];
const PERSONAS = USUARIOS.slice(0, 4);
const nombreDe = (username) => USUARIOS.find((x) => x.u === username)?.nombre || username;

let token = sessionStorage.getItem("token");
let yo = null;
let enInicio = false;

// ---------- Utilidades de DOM ----------
function h(tag, props = {}, ...hijos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (v === true) el.setAttribute(k, "");
    else if (v !== false && v != null) el.setAttribute(k, v);
  }
  for (const c of hijos.flat()) if (c != null && c !== false) el.append(c.nodeType ? c : String(c));
  return el;
}

const boton = (texto, onclick, clase = "") => h("button", { type: "button", class: clase, onclick }, texto);

const resumen = (filas) =>
  h("dl", { class: "resumen" }, filas.map(([k, v]) => h("div", {}, h("dt", {}, k), h("dd", {}, v))));

const opcion = ({ icono, titulo, desc, badge, onclick }) =>
  h("button", { type: "button", class: "opcion", onclick },
    h("span", { class: "icono" }, icono),
    h("span", {}, h("strong", {}, titulo), desc ? h("small", {}, desc) : null),
    badge ? h("span", { class: "badge" }, badge) : null);

/** Dibuja UNA pantalla (tarjeta) y reemplaza la anterior. */
function pantalla({ paso, total, titulo, explica, cuerpo = [], acciones = [], clase = "" }) {
  enInicio = false;
  const card = h("section", { class: `card ${clase}` },
    total ? h("div", { class: "pasos" }, Array.from({ length: total }, (_, i) => h("span", { class: i < paso ? "hecho" : "" }))) : null,
    total ? h("p", { class: "paso-texto" }, `Paso ${paso} de ${total}`) : null,
    h("h2", {}, titulo),
    explica ? h("p", { class: "explica" }, explica) : null,
    cuerpo,
    acciones.length ? h("div", { class: "acciones" }, acciones) : null);
  app.replaceChildren(card);
  window.scrollTo(0, 0);
  card.querySelector("input")?.focus();
  return card;
}

/** Tarjeta final: ✔ (salió bien) o ✘ (no salió), con el detalle. */
function resultado({ ok, titulo, explica, filas = [], motivo, referencia, acciones }) {
  const card = pantalla({
    clase: `resultado ${ok ? "ok" : "mal"}`,
    titulo,
    explica,
    cuerpo: [
      h("div", { class: "sello" }, ok ? "✔" : "✘"),
      referencia
        ? h("p", { class: "referencia" }, referencia.titulo, h("strong", {}, referencia.valor))
        : null,
      motivo ? h("div", { class: "motivo" }, motivo) : null,
      filas.length ? resumen(filas) : null,
    ],
    acciones,
  });
  card.prepend(card.querySelector(".sello")); // el ✔/✘ arriba de todo
  return card;
}

/** Pantalla de espera mientras la API valida y procesa. */
function procesando(titulo, pasos) {
  pantalla({
    clase: "procesando",
    titulo,
    explica: "No cierres esta pantalla.",
    cuerpo: [h("div", { class: "spinner", "aria-hidden": "true" }), h("ul", { class: "chequeos" }, pasos.map((p) => h("li", {}, p)))],
  });
}

/** Espera la respuesta de la API, pero muestra "Validando…" al menos un momento
 *  (si la API contesta en 50 ms, la pantalla parpadearía y no se llegaría a leer). */
async function conMinimo(promesa, ms = 900) {
  const [r] = await Promise.allSettled([promesa, new Promise((ok) => setTimeout(ok, ms))]);
  if (r.status === "rejected") throw r.reason;
  return r.value;
}

const ref = (prefijo, id) => ({ titulo: "N.º de referencia", valor: `${prefijo}-${corto(id)}` });
const refIntento = (clave) => ({ titulo: "Código del intento", valor: `INT-${corto(clave)}` });

/** Campo de monto en pesos con validación. */
function campoMonto(etiqueta, ayuda) {
  // type="text" + inputmode="decimal": teclado numérico CON coma en el celular.
  // (type="number" rechaza "4,80" en iPhone en español.)
  const input = h("input", { type: "text", inputmode: "decimal", autocomplete: "off", placeholder: "0,00" });
  const error = h("p", { class: "error-campo", hidden: true });
  const el = h("div", {}, h("label", {}, etiqueta, input), ayuda ? h("p", { class: "ayuda" }, ayuda) : null, error);
  return {
    el,
    input,
    leer() { return aCentavos(input.value); },
    error(texto) { error.textContent = texto; error.hidden = !texto; },
  };
}

// ---------- API ----------
async function api(method, path, body, extraHeaders = {}) {
  const headers = { ...extraHeaders };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  let r;
  try {
    r = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw Object.assign(new Error("Sin conexión. Revisá tu internet y probá de nuevo."), { red: true });
  }
  const data = await r.json().catch(() => null);
  if (!r.ok) {
    if (r.status === 401 && token && path !== "/auth/login") {
      salir();
      throw new Error("Tu sesión venció. Entrá de nuevo.");
    }
    throw Object.assign(new Error(mensajeDeError(data) || `Error ${r.status}`), { status: r.status });
  }
  return data;
}

function mensajeDeError(data) {
  if (!data || !data.detail) return null;
  if (typeof data.detail === "string") return data.detail;
  return data.detail.map((d) => d.msg).join(". "); // errores de validación (422)
}

// crypto.randomUUID solo existe en HTTPS o localhost. Por http (ej. desde el celular
// por Tailscale) se arma una clave aleatoria con getRandomValues, que sí existe.
function nuevaClave() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function ocupado(btn, fn) {
  btn.disabled = true;
  try {
    return await fn();
  } finally {
    btn.disabled = false;
  }
}

const saldoActual = async () => (await api("GET", "/me/balance")).balance_cents;

// ---------- Sesión ----------
function pantallaLogin(error) {
  document.getElementById("sesion").hidden = true;
  pantalla({
    titulo: "¿Quién querés ser?",
    explica: "Esto es una demo con dinero de mentira. Elegí un personaje para probarla. Entramos con la contraseña de la demo (demo1234).",
    cuerpo: [
      error ? h("p", { class: "error-campo" }, error) : null,
      h("div", { class: "opciones" },
        USUARIOS.map((x) => opcion({ icono: x.icono, titulo: x.nombre, desc: x.desc, onclick: (ev) => login(x.u, ev.currentTarget) }))),
    ],
  });
}

async function login(username, btn) {
  try {
    await ocupado(btn, async () => {
      const r = await api("POST", "/auth/login", { username, password: "demo1234" });
      token = r.access_token;
      sessionStorage.setItem("token", token);
      await entrar();
    });
  } catch (e) {
    pantallaLogin(e.message);
  }
}

function salir() {
  token = null;
  yo = null;
  sessionStorage.removeItem("token");
  pantallaLogin();
}

async function entrar() {
  yo = await api("GET", "/auth/me");
  document.getElementById("quien").textContent = yo.display_name;
  document.getElementById("sesion").hidden = false;
  await inicio();
}

document.getElementById("salir").addEventListener("click", salir);
document.getElementById("logo").addEventListener("click", () => (yo ? inicio() : pantallaLogin()));

// ---------- Inicio ----------
async function inicio() {
  if (yo.role === "admin") return pantallaAdmin();

  const [saldo, cobros] = await Promise.all([
    saldoActual(),
    yo.role === "user" ? api("GET", "/me/charges") : Promise.resolve([]),
  ]);
  const pendientes = cobros.filter((c) => c.status === "pending").length;
  const esPersona = yo.role === "user";

  const opciones = esPersona
    ? [
        { icono: "💰", titulo: "Elegir saldo", desc: "Cargá dinero de juguete a tu cuenta", onclick: () => saldoPaso1() },
        { icono: "➡️", titulo: "Transferir", desc: "Mandarle dinero a otra persona", onclick: () => transferirPaso1() },
        { icono: "🧾", titulo: "Cobros", desc: "Pagar o rechazar lo que te cobraron", badge: pendientes || null, onclick: () => cobrosLista() },
        { icono: "📜", titulo: "Movimientos", desc: "Todo lo que entró y salió de tu cuenta", onclick: () => movimientos() },
      ]
    : [
        { icono: "🧾", titulo: "Cobrar", desc: "Pedirle un pago a una persona", onclick: () => cobrarPaso1() },
        { icono: "📋", titulo: "Mis cobros", desc: "Ver si te pagaron", onclick: () => misCobros() },
        { icono: "📜", titulo: "Movimientos", desc: "Todo lo que entró a tu cuenta", onclick: () => movimientos() },
      ];

  pantalla({
    titulo: `Hola, ${yo.display_name}`,
    explica: esPersona
      ? "¿Qué querés hacer? Elegí una opción."
      : "Sos un comercio: le cobrás a las personas y ellas te pagan desde su cuenta.",
    cuerpo: [
      h("div", { class: "saldo" }, h("p", {}, "Tu saldo"), h("p", { class: "monto-grande", id: "saldo-num" }, fmt(saldo))),
      h("div", { class: "opciones" }, opciones.map(opcion)),
    ],
  });
  enInicio = true;
}

// Refresco automático del inicio cada 10 s (así Ana ve la plata que le mandó Marta).
async function refrescoSilencioso() {
  if (!token || !yo || document.hidden || !enInicio) return;
  try {
    if (yo.role === "admin") return;
    const num = document.getElementById("saldo-num");
    if (num) num.textContent = fmt(await saldoActual());
  } catch {
    /* si falla la red, se reintenta en el próximo ciclo */
  }
}
setInterval(refrescoSilencioso, 10_000);
document.addEventListener("visibilitychange", refrescoSilencioso);

const volverInicio = () => boton("Volver al inicio", () => inicio());

// ---------- Elegir saldo: 2 pasos + resultado ----------
function saldoPaso1() {
  const monto = campoMonto("Otro monto ($)", "Entre $1 y $5.000. Podés cambiarlo hasta 5 veces por hora.");
  const seguir = (cents) => {
    if (!(cents >= 100 && cents <= 500_000)) return monto.error("Elegí un monto entre $1 y $5.000.");
    saldoPaso2(cents);
  };
  pantalla({
    paso: 1, total: 2,
    titulo: "¿Cuánto saldo querés tener?",
    explica: "Es dinero de juguete. El monto que elijas reemplaza al que tenías.",
    cuerpo: [
      h("div", { class: "atajos" }, [10_000, 100_000, 500_000].map((c) => boton(fmt(c), () => seguir(c)))),
      monto.el,
    ],
    acciones: [boton("Cancelar", () => inicio()), boton("Seguir", () => seguir(monto.leer()), "primario")],
  });
}

async function saldoPaso2(nuevo) {
  const actual = await saldoActual();
  const confirmar = boton("Confirmar", (ev) => ocupado(ev.currentTarget, () => saldoEnviar(nuevo)), "primario");
  pantalla({
    paso: 2, total: 2,
    titulo: "Revisá antes de confirmar",
    explica: "Todavía no cambió nada. Si está bien, tocá Confirmar.",
    cuerpo: [resumen([["Saldo actual", fmt(actual)], ["Saldo nuevo", fmt(nuevo)]])],
    acciones: [boton("Volver", () => saldoPaso1()), confirmar],
  });
}

async function saldoEnviar(nuevo) {
  procesando("Cambiando tu saldo…", ["Revisando el monto", "Revisando el límite de cambios por hora"]);
  try {
    const r = await conMinimo(api("PUT", "/me/balance", { balance_cents: nuevo }));
    resultado({
      ok: true,
      titulo: "¡Listo! Tu saldo cambió",
      filas: [["Saldo nuevo", fmt(r.balance_cents)], ["Fecha", fecha(new Date().toISOString())]],
      acciones: [volverInicio()],
    });
  } catch (e) {
    resultado({
      ok: false,
      titulo: "No se pudo cambiar el saldo",
      explica: "Tu saldo quedó igual.",
      motivo: e.message,
      acciones: [boton("Intentar de nuevo", () => saldoPaso1()), volverInicio()],
    });
  }
}

// ---------- Transferir: 3 pasos + resultado ----------
function transferirPaso1() {
  pantalla({
    paso: 1, total: 3,
    titulo: "¿A quién le mandás dinero?",
    explica: "Elegí la persona que va a recibirlo.",
    cuerpo: [
      h("div", { class: "opciones" },
        PERSONAS.filter((p) => p.u !== yo.username).map((p) =>
          opcion({ icono: p.icono, titulo: p.nombre, onclick: () => transferirPaso2({ para: p.u }) }))),
    ],
    acciones: [boton("Cancelar", () => inicio())],
  });
}

async function transferirPaso2(t) {
  const saldo = await saldoActual();
  const monto = campoMonto(`Monto para ${nombreDe(t.para)} ($)`, "Máximo $5.000 por transferencia y $10.000 por día.");
  if (t.monto) monto.input.value = (t.monto / 100).toFixed(2).replace(".", ",");
  const seguir = () => {
    const c = monto.leer();
    if (!(c > 0)) return monto.error("Escribí un monto válido, por ejemplo 4,80.");
    if (c > MAX_OPERACION) return monto.error("El máximo por transferencia es $5.000.");
    if (c > saldo) return monto.error(`No te alcanza: tenés ${fmt(saldo)}.`);
    transferirPaso3({ ...t, monto: c, saldo, key: null });
  };
  pantalla({
    paso: 2, total: 3,
    titulo: `¿Cuánto le mandás a ${nombreDe(t.para)}?`,
    explica: `Tenés ${fmt(saldo)} disponibles.`,
    cuerpo: [monto.el],
    acciones: [boton("Volver", () => transferirPaso1()), boton("Seguir", seguir, "primario")],
  });
  monto.input.addEventListener("keydown", (ev) => ev.key === "Enter" && seguir());
}

function transferirPaso3(t) {
  // Una clave por transferencia: si se corta la red y reintentás, NO se manda dos veces.
  t.key ||= nuevaClave();
  const confirmar = boton("Confirmar", (ev) => ocupado(ev.currentTarget, () => transferirEnviar(t)), "primario");
  pantalla({
    paso: 3, total: 3,
    titulo: "Revisá la transferencia",
    explica: "Todavía no se movió el dinero. Si está todo bien, tocá Confirmar.",
    cuerpo: [resumen([
      ["De", yo.display_name],
      ["Para", nombreDe(t.para)],
      ["Monto", fmt(t.monto)],
      ["Tu saldo después", fmt(t.saldo - t.monto)],
    ])],
    acciones: [boton("Volver", () => transferirPaso2(t)), confirmar],
  });
}

async function transferirEnviar(t) {
  procesando("Validando la transferencia…", [
    "Verificando tu saldo",
    "Revisando los límites",
    `Enviando el dinero a ${nombreDe(t.para)}`,
  ]);
  try {
    const r = await conMinimo(
      api("POST", "/me/transfers", { to_username: t.para, amount_cents: t.monto }, { "Idempotency-Key": t.key })
    );
    resultado({
      ok: true,
      titulo: "Transferencia enviada",
      explica: `${nombreDe(t.para)} ya recibió el dinero.`,
      referencia: ref("TRF", r.transaction_id),
      filas: [
        ["Para", nombreDe(t.para)],
        ["Monto", fmt(r.amount_cents)],
        ["Tu saldo ahora", fmt(r.balance_cents)],
        ["Fecha", fecha(new Date().toISOString())],
      ],
      acciones: [boton("Hacer otra", () => transferirPaso1()), volverInicio()],
    });
  } catch (e) {
    const acciones = e.red
      ? [boton("Reintentar", () => transferirPaso3(t), "primario")] // misma clave
      : [boton("Corregir", () => transferirPaso2({ para: t.para, monto: t.monto }), "primario")];
    resultado({
      ok: false,
      titulo: "No se pudo transferir",
      explica: e.red ? "No sabemos si llegó. Reintentá: no se va a mandar dos veces." : "No se movió ningún dinero.",
      referencia: refIntento(t.key),
      motivo: e.message,
      acciones: [...acciones, volverInicio()],
    });
  }
}

// ---------- Cobros (persona): lista → confirmar → resultado ----------
async function cobrosLista() {
  const cobros = await api("GET", "/me/charges");
  const pendientes = cobros.filter((c) => c.status === "pending");
  const resueltos = cobros.filter((c) => c.status !== "pending");
  pantalla({
    paso: 1, total: 2,
    titulo: "Cobros que te hicieron",
    explica: "Un comercio te pidió que le pagues. Tocá un cobro pendiente para pagarlo o rechazarlo.",
    cuerpo: [
      pendientes.length
        ? h("div", { class: "opciones" }, pendientes.map((c) =>
            opcion({ icono: "🧾", titulo: `${c.description} · ${fmt(c.amount_cents)}`, desc: nombreDe(c.merchant_username), onclick: () => cobroDetalle(c) })))
        : h("p", { class: "explica" }, "No tenés cobros pendientes."),
      resueltos.length ? h("h3", {}, "Ya resueltos") : null,
      resueltos.length
        ? h("ul", { class: "lista" }, resueltos.map((c) =>
            h("li", {}, h("span", {}, c.description, h("br"), h("small", {}, `${nombreDe(c.merchant_username)} · ${fmt(c.amount_cents)}`)),
              h("span", { class: "estado" }, ESTADOS[c.status]))))
        : null,
    ],
    acciones: [volverInicio()],
  });
}

async function cobroDetalle(c) {
  const saldo = await saldoActual();
  c.key ||= nuevaClave();
  const pagar = boton("Pagar", (ev) => ocupado(ev.currentTarget, () => cobroResolver(c, "pay")), "primario");
  const rechazar = boton("Rechazar", (ev) => ocupado(ev.currentTarget, () => cobroResolver(c, "reject")));
  pantalla({
    paso: 2, total: 2,
    titulo: "¿Pagás este cobro?",
    explica: "Si lo pagás, el dinero pasa de tu cuenta a la del comercio. Si lo rechazás, no se mueve nada.",
    cuerpo: [resumen([
      ["Comercio", nombreDe(c.merchant_username)],
      ["Concepto", c.description],
      ["Monto", fmt(c.amount_cents)],
      ["Tu saldo después de pagar", fmt(saldo - c.amount_cents)],
    ])],
    acciones: [boton("Volver", () => cobrosLista()), rechazar, pagar],
  });
}

async function cobroResolver(c, accion) {
  procesando(accion === "pay" ? "Validando el pago…" : "Rechazando el cobro…",
    accion === "pay" ? ["Verificando tu saldo", "Revisando los límites", "Pagándole al comercio"] : ["Avisándole al comercio"]);
  try {
    const headers = accion === "pay" ? { "Idempotency-Key": c.key } : {};
    const r = await conMinimo(api("POST", `/me/charges/${c.id}/${accion}`, undefined, headers));
    resultado({
      ok: true,
      titulo: accion === "pay" ? "Cobro pagado" : "Cobro rechazado",
      explica: accion === "pay" ? `${nombreDe(c.merchant_username)} ya recibió el dinero.` : "No se movió dinero.",
      referencia: ref("COB", r.id),
      filas: [
        ["Comercio", nombreDe(r.merchant_username)],
        ["Concepto", r.description],
        ["Monto", fmt(r.amount_cents)],
        ["Estado", ESTADOS[r.status]],
        ["Fecha", fecha(r.resolved_at)],
      ],
      acciones: [boton("Ver cobros", () => cobrosLista()), volverInicio()],
    });
  } catch (e) {
    resultado({
      ok: false,
      titulo: "No se pudo resolver el cobro",
      explica: e.red ? "No sabemos si se pagó. Reintentá: no se va a cobrar dos veces." : "No se movió ningún dinero.",
      referencia: accion === "pay" ? refIntento(c.key) : ref("COB", c.id),
      motivo: e.message,
      acciones: [boton(e.red ? "Reintentar" : "Ver cobros", () => (e.red ? cobroDetalle(c) : cobrosLista()), "primario"), volverInicio()],
    });
  }
}

// ---------- Cobrar (comercio): 3 pasos + resultado ----------
function cobrarPaso1() {
  pantalla({
    paso: 1, total: 3,
    titulo: "¿A quién le cobrás?",
    explica: "Elegí la persona que tiene que pagarte.",
    cuerpo: [h("div", { class: "opciones" },
      PERSONAS.map((p) => opcion({ icono: p.icono, titulo: p.nombre, onclick: () => cobrarPaso2({ a: p.u }) })))],
    acciones: [boton("Cancelar", () => inicio())],
  });
}

function cobrarPaso2(c) {
  const monto = campoMonto("Monto ($)", "Máximo $5.000.");
  const concepto = h("input", { maxlength: "200", placeholder: "Ej.: Consulta general" });
  const errConcepto = h("p", { class: "error-campo", hidden: true });
  if (c.monto) monto.input.value = (c.monto / 100).toFixed(2).replace(".", ",");
  if (c.concepto) concepto.value = c.concepto;
  const seguir = () => {
    const cents = monto.leer();
    monto.error("");
    errConcepto.hidden = true;
    if (!(cents > 0 && cents <= MAX_OPERACION)) return monto.error("Elegí un monto entre $0,01 y $5.000.");
    if (!concepto.value.trim()) {
      errConcepto.textContent = "Escribí el concepto (para qué es el cobro).";
      errConcepto.hidden = false;
      return;
    }
    cobrarPaso3({ ...c, monto: cents, concepto: concepto.value.trim() });
  };
  pantalla({
    paso: 2, total: 3,
    titulo: `¿Cuánto le cobrás a ${nombreDe(c.a)}?`,
    explica: "Poné el monto y para qué es. La persona lo va a ver antes de pagar.",
    cuerpo: [monto.el, h("label", {}, "Concepto", concepto), errConcepto],
    acciones: [boton("Volver", () => cobrarPaso1()), boton("Seguir", seguir, "primario")],
  });
}

function cobrarPaso3(c) {
  const confirmar = boton("Enviar cobro", (ev) => ocupado(ev.currentTarget, () => cobrarEnviar(c)), "primario");
  pantalla({
    paso: 3, total: 3,
    titulo: "Revisá el cobro",
    explica: "Todavía no se envió. Cuando lo envíes, la persona decide si lo paga.",
    cuerpo: [resumen([["A", nombreDe(c.a)], ["Concepto", c.concepto], ["Monto", fmt(c.monto)]])],
    acciones: [boton("Volver", () => cobrarPaso2(c)), confirmar],
  });
}

async function cobrarEnviar(c) {
  try {
    procesando("Enviando el cobro…", ["Revisando el monto", `Avisándole a ${nombreDe(c.a)}`]);
    const r = await conMinimo(
      api("POST", "/merchant/charges", { payer_username: c.a, amount_cents: c.monto, description: c.concepto })
    );
    resultado({
      ok: true,
      titulo: "Cobro enviado",
      explica: `${nombreDe(c.a)} lo va a ver en "Cobros" y decide si lo paga.`,
      referencia: ref("COB", r.id),
      filas: [["A", nombreDe(r.payer_username)], ["Concepto", r.description], ["Monto", fmt(r.amount_cents)], ["Estado", ESTADOS[r.status]]],
      acciones: [boton("Cobrar otra vez", () => cobrarPaso1()), volverInicio()],
    });
  } catch (e) {
    resultado({
      ok: false,
      titulo: "No se pudo crear el cobro",
      motivo: e.message,
      acciones: [boton("Corregir", () => cobrarPaso2(c), "primario"), volverInicio()],
    });
  }
}

async function misCobros() {
  const cobros = await api("GET", "/merchant/charges");
  pantalla({
    titulo: "Mis cobros",
    explica: "Los cobros que enviaste y si ya te los pagaron.",
    cuerpo: [cobros.length
      ? h("ul", { class: "lista" }, cobros.map((c) =>
          h("li", {}, h("span", {}, c.description, h("br"), h("small", {}, `${nombreDe(c.payer_username)} · ${fmt(c.amount_cents)}`)),
            h("span", { class: "estado" }, ESTADOS[c.status]))))
      : h("p", { class: "explica" }, "Todavía no cobraste nada.")],
    acciones: [volverInicio()],
  });
}

// ---------- Movimientos ----------
async function movimientos() {
  const movs = await api("GET", "/me/movements");
  pantalla({
    titulo: "Movimientos",
    explica: "En verde lo que entró a tu cuenta, en rojo lo que salió.",
    cuerpo: [movs.length
      ? h("ul", { class: "lista" }, movs.map((m) =>
          h("li", {}, h("span", {}, TIPOS[m.kind] || m.kind, h("br"), h("small", {}, fecha(m.created_at))),
            h("span", { class: m.amount_cents < 0 ? "negativo" : "positivo" }, `${m.amount_cents > 0 ? "+" : ""}${fmt(m.amount_cents)}`))))
      : h("p", { class: "explica" }, "Todavía no hay movimientos.")],
    acciones: [volverInicio()],
  });
}

// ---------- Admin ----------
async function pantallaAdmin(run) {
  if (!run) {
    try {
      run = await api("GET", "/admin/reconciliation");
    } catch {
      run = null;
    }
  }
  const revisar = boton("Revisar ahora", (ev) =>
    ocupado(ev.currentTarget, async () => pantallaAdmin(await api("POST", "/admin/reconciliation"))), "primario");
  pantalla({
    clase: run ? `resultado ${run.ok ? "ok" : "mal"}` : "",
    titulo: "Conciliación del libro",
    explica: "El dinero solo pasa de una cuenta a otra, así que si sumás todo tiene que dar exactamente $0. Si no da 0, hay un error. El sistema lo revisa solo cada 15 minutos.",
    cuerpo: run
      ? [
          h("div", { class: "sello" }, run.ok ? "✔" : "✘"),
          resumen([
            ["Resultado", run.ok ? "Cuadra" : "¡Descuadre!"],
            ["Total", fmt(run.total_cents)],
            ["Renglones revisados", String(run.entries_count)],
            ["Última revisión", fecha(run.ran_at)],
          ]),
        ]
      : [h("p", { class: "explica" }, "Todavía no hay revisiones.")],
    acciones: [revisar],
  });
  const sello = app.querySelector(".sello");
  if (sello) app.querySelector(".card").prepend(sello);
}

// ---------- Inicio de la app ----------
if (token) entrar().catch(() => salir());
else pantallaLogin();
