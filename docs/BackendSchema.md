# BackendSchema — minipay

> Diseño de la base de datos. Se escribe **antes** del código: acá se decide el qué y el por qué.
> Crece por pasos: cada tabla se agrega cuando llega el paso que la necesita.

**Última actualización:** 2026-11-11

---

## 1. Principio central: libro contable de doble entrada

- Cada movimiento de dinero se anota **dos veces**: sale de una cuenta y entra en otra.
- Las líneas (entries) de cada movimiento **siempre suman cero**.
- El saldo de una cuenta **se calcula** sumando sus líneas. No se guarda un número que se va pisando.
- El dinero nunca aparece ni desaparece de la nada.

---

## 2. Decisiones

### 2.1 Cómo se guarda el dinero — decidido 2026-11-11

**Decisión:** `BIGINT` en **centavos**.

| Valor en pantalla | Valor en la base |
|---|---|
| $12,50 | `1250` |
| $5.000 (máximo por operación) | `500000` |
| $10.000 (límite diario) | `1000000` |

**Por qué:**
- `FLOAT` tiene errores de redondeo (`0.1 + 0.2 = 0.30000000000000004`). Descartado.
- `NUMERIC` es exacto, pero obliga a usar `Decimal` en todo el código Python.
- Los enteros son exactos y rápidos. Es lo que usan la mayoría de los sistemas de pagos.
- Los pesos con coma solo aparecen al **mostrar** el número.

### 2.2 De dónde sale el dinero de juguete — decidido 2026-11-11

**Decisión:** una **cuenta del sistema** llamada **"Banco de juguete"**, que no pertenece a ninguna persona.

- Cuando alguien elige o cambia su saldo, se registra un movimiento entre el Banco de juguete y su cuenta.
- Ejemplo: Ana elige $1.000 → Banco **−100000**, Ana **+100000** (suma 0).
- Ejemplo: Ana baja a $300 → Ana **−70000**, Banco **+70000** (suma 0).
- **Solo el Banco de juguete puede quedar en negativo.** Las cuentas de personas nunca.

**Por qué:**
- En doble entrada el dinero no puede aparecer de la nada: necesita una cuenta de origen.
- Se llama cuenta de emisión o contrapartida (*contra account*).

**Control:** la suma de **todas** las cuentas (Banco incluido) siempre tiene que dar **0**. Si no da 0, hay un bug.

### 2.3 Tipo de ID de las tablas — decidido 2026-11-11

**Decisión:** **UUID versión 4** (aleatorio) en todas las tablas. Tipo `UUID` nativo de PostgreSQL. Se genera en Python con `uuid.uuid4()`.

**Por qué:**
- minipay es una demo pública. Con IDs `1, 2, 3` se filtra cuántos registros hay.
- Evita el **ataque de enumeración**: probar `/transactions/56`, `/55`… para ver datos ajenos.
- El UUID **no reemplaza** los permisos: la API igual verifica que el dato sea del usuario. Es una segunda capa.

---

## 3. Tablas del paso 2 (libro contable)

_(se completan cuando estén cerradas las decisiones de la sección 2)_

- `users`
- `accounts`
- `ledger_transactions`
- `ledger_entries`
