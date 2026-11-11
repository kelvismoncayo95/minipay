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

### 3.1 `users` — decidido 2026-11-11

| Columna | Tipo | Reglas | Para qué |
|---|---|---|---|
| `id` | `UUID` | clave primaria | identificador (2.3) |
| `username` | `TEXT` | `NOT NULL`, `UNIQUE` | nombre para entrar: `ana`, `clinica-del-sur` |
| `display_name` | `TEXT` | `NOT NULL` | nombre en pantalla: `Ana`, `Clínica del Sur (demo)` |
| `role` | `TEXT` | `NOT NULL`, `CHECK (role IN ('user','merchant','admin'))` | qué puede hacer |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, default `now()` | cuándo se creó |
| `password_hash` | `TEXT` | puede ser `NULL` | hash bcrypt de la contraseña (paso 4). `NULL` = no puede entrar |

**Notas:**
- `username` es único porque identifica a **una** persona al entrar. `display_name` se puede repetir (puede haber muchas "Ana").
- `password_hash` se agregó en el paso 4 con la migración `c090afa7b211`. Nunca se guarda la contraseña, solo su hash.
- `CHECK` en vez de `ENUM`: más fácil de cambiar después.

### 3.2 `accounts` — decidido 2026-11-11

| Columna | Tipo | Reglas | Para qué |
|---|---|---|---|
| `id` | `UUID` | clave primaria | identificador |
| `user_id` | `UUID` | clave foránea a `users.id`, `UNIQUE`, puede ser `NULL` | dueño de la cuenta |
| `kind` | `TEXT` | `NOT NULL`, `CHECK (kind IN ('user','system'))` | cuenta de persona o del sistema |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, default `now()` | cuándo se creó |

**Regla entre columnas:** `CHECK ((kind = 'system' AND user_id IS NULL) OR (kind = 'user' AND user_id IS NOT NULL))`.

**Notas:**
- Una cuenta por usuario en v1 (`UNIQUE` en `user_id`).
- **No hay columna de saldo:** se calcula sumando las líneas (sección 1).
- "Las personas no pueden quedar en negativo" **no se puede expresar como `CHECK`** (depende de una suma). La controla el código al transferir, bloqueando la cuenta mientras calcula.

### 3.3 `ledger_transactions` (el movimiento) — decidido 2026-11-11

| Columna | Tipo | Reglas | Para qué |
|---|---|---|---|
| `id` | `UUID` | clave primaria | identificador |
| `seq` | `BIGINT` | `NOT NULL`, `IDENTITY`, `UNIQUE` | orden interno 1, 2, 3… (paso 5). No se muestra en la API |
| `kind` | `TEXT` | `NOT NULL`, `CHECK (kind IN ('balance_set','transfer'))` | tipo de movimiento |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, default `now()` | cuándo pasó |

- `balance_set`: cambio de saldo entre el Banco de juguete y una persona.
- `transfer`: transferencia entre dos personas.
- Cobros y reembolsos se agregan a `kind` en sus pasos.
- **Por qué `seq`:** `now()` en PostgreSQL devuelve la hora de inicio de la transacción, así que dos movimientos pueden tener el mismo `created_at`. El historial se ordena por `seq`, que nunca empata. Migración `5db1b39c3d48`.

### 3.4 `ledger_entries` (los renglones) — decidido 2026-11-11

| Columna | Tipo | Reglas | Para qué |
|---|---|---|---|
| `id` | `UUID` | clave primaria | identificador |
| `transaction_id` | `UUID` | `NOT NULL`, clave foránea a `ledger_transactions.id` | a qué movimiento pertenece |
| `account_id` | `UUID` | `NOT NULL`, clave foránea a `accounts.id`, **con índice** | qué cuenta se mueve |
| `amount` | `BIGINT` | `NOT NULL`, `CHECK (amount <> 0)` | centavos: negativo sale, positivo entra |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, default `now()` | cuándo se anotó |

**Notas:**
- Una sola columna con signo en vez de debe/haber: misma idea, más simple.
- El índice en `account_id` hace rápido el cálculo del saldo (`SUM(amount) WHERE account_id = ...`).
- **"Suma cero"** no se puede expresar como `CHECK` (son varias filas). En v1: el código crea el movimiento y sus renglones juntos en **una sola transacción de base de datos**, y un test lo verifica. Mejora futura: un trigger en PostgreSQL.

### 3.5 `idempotency_keys` (pedidos ya procesados) — decidido 2026-11-11 (paso 7)

| Columna | Tipo | Reglas | Para qué |
|---|---|---|---|
| `id` | `UUID` | clave primaria | identificador |
| `user_id` | `UUID` | `NOT NULL`, clave foránea a `users.id` | quién mandó el pedido |
| `key` | `TEXT` | `NOT NULL` | la clave del header `Idempotency-Key` (8 a 100 caracteres) |
| `request_hash` | `TEXT` | `NOT NULL` | huella SHA-256 del pedido (tipo + destino + monto) |
| `transaction_id` | `UUID` | clave foránea a `ledger_transactions.id`, puede ser `NULL` | el movimiento que produjo |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, default `now()` | cuándo llegó |

**Regla:** `UNIQUE (user_id, key)` (`uq_idempotency_keys_user_key`): la clave es única **por usuario**.

**Notas:**
- Se inserta con `INSERT ... ON CONFLICT DO NOTHING`: si dos pedidos con la misma clave llegan a la vez, PostgreSQL hace esperar al segundo hasta que el primero termine.
- Misma clave + mismo pedido → se devuelve el movimiento guardado. Misma clave + otro pedido → error.
- Si la operación falla (ej. saldo insuficiente), la clave **no** queda guardada (savepoint): se puede reintentar.
- Migración `eb426c5d4173`.

### 3.6 `charges` (cobros de comercios) — decidido 2026-11-11 (paso 9)

| Columna | Tipo | Reglas | Para qué |
|---|---|---|---|
| `id` | `UUID` | clave primaria | identificador |
| `merchant_id` | `UUID` | `NOT NULL`, FK `users.id`, índice | comercio que cobra |
| `payer_id` | `UUID` | `NOT NULL`, FK `users.id`, índice | persona que paga |
| `amount` | `BIGINT` | `NOT NULL`, `CHECK (amount > 0)` | centavos |
| `description` | `TEXT` | `NOT NULL` (1–200 caracteres, validado en la API) | concepto |
| `status` | `TEXT` | `CHECK (status IN ('pending','paid','rejected'))`, default `pending` | estado |
| `transaction_id` | `UUID` | FK `ledger_transactions.id`, puede ser `NULL` | el pago en el libro |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, default `now()` | cuándo se creó |
| `resolved_at` | `TIMESTAMPTZ` | puede ser `NULL` | cuándo se pagó o rechazó |

**Regla entre columnas:** `ck_charges_paid_has_transaction`: `paid` ⇔ tiene `transaction_id`.

**Notas:**
- `ledger_transactions.kind` ahora acepta `payment` (cambio de `CHECK` hecho a mano: autogenerate no lo detecta). Migración `f6de89137503`.
- Pagar bloquea primero el cobro (`FOR UPDATE`) y después las cuentas. El estado `pending` se revisa con el cobro bloqueado.
- Los pagos cuentan para el límite diario, igual que las transferencias.

---

## 4. Regla de oro: solo agregar (append-only)

- Los renglones (`ledger_entries`) y los movimientos (`ledger_transactions`) **nunca se modifican ni se borran**.
- Si hubo un error, se agrega un movimiento nuevo que lo compensa.
- Así siempre queda la historia completa y nadie hace desaparecer dinero sin dejar rastro.
