"""
Historial SQLite genérico multi-sector.

Generaliza v1/historial.py. El schema es evolutivo: si un nuevo sector
declara columnas snapshot u operación distintas, la tabla se expande sin
romper los datos existentes. La identidad del anuncio se maneja con una
clave sintética por alcance lógico (sector + portal + operación + enlace),
de modo que una misma URL no colisione entre sectores o portales.

El ciclo de vida (nuevo / repetido / desaparecido / dado de baja) es
idéntico al de v1 porque es la metodología validada en producción.
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta

import pandas as pd

from core.utils import normalizar_enlace as _normalizar_enlace

logger = logging.getLogger("scraping")

_COLUMNAS_BASE_ANUNCIOS: dict[str, str] = {
    "id": "INTEGER",
    "clave_registro": "TEXT",
    "enlace": "TEXT",
    "sector": "TEXT",
    "portal": "TEXT",
    "primera_vez_visto": "TEXT",
    "ultima_vez_visto": "TEXT",
    "ausencias_consecutivas": "INTEGER",
    "activo": "INTEGER",
    "fecha_baja": "TEXT",
}

_COLUMNAS_BASE_CORRIDAS: dict[str, str] = {
    "id": "INTEGER",
    "fecha": "TEXT",
    "sector": "TEXT",
    "portal": "TEXT",
    "id_fuente": "TEXT",
    "n_total": "INTEGER",
    "n_nuevos": "INTEGER",
    "n_repetidos": "INTEGER",
    "n_desaparecidos": "INTEGER",
    "listado_completo": "INTEGER",
    "estado_calidad": "TEXT",
}


def _quote_ident(nombre: str) -> str:
    return f'"{nombre.replace(chr(34), chr(34) * 2)}"'


def _clave_registro(
    sector: str,
    portal: str,
    enlace: str,
    campo_operacion: str | None = None,
    operacion: str | None = None,
) -> str:
    """Clave estable por alcance lógico del anuncio."""
    partes = [
        str(sector or "").strip(),
        str(portal or "").strip(),
        str(campo_operacion or "").strip(),
        str(operacion or "").strip(),
        _normalizar_enlace(enlace),
    ]
    return "|".join(partes)


def _valor(row, campo):
    """Extrae valor del row tolerando NaN de pandas."""
    v = row.get(campo)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


class HistorialSQLite:
    """Historial acumulativo con columnas snapshot parametrizadas.

    Parámetros:
        ruta_db: path al archivo .db (se crea si no existe).
        sector: nombre del sector (guardado en la columna `sector`).
        campos_snapshot: lista de (nombre_columna, tipo_sql_opcional). Si el
            tipo es None se usa TEXT. Estos son los campos que se guardan
            en cada registro y se actualizan cuando el anuncio es repetido.
        umbral_ausencias: corridas consecutivas sin aparecer antes de marcar
            un anuncio como dado de baja.
        campo_operacion: nombre del campo que agrupa corridas (para
            inmobiliario es `tipo_operacion`; para empleo puede ser
            `rubro` o similar). None si el sector no tiene operaciones.
        fraccion_colapso: guarda anti-colapso. Si una corrida que se declara
            COMPLETA trae menos de esta fracción de los activos previos
            presentes, NO se dan de baja los ausentes esa corrida (evita que
            un listado encogido por un hipo del portal/API borre historial
            válido). Solo aplica si la base supera `min_base_colapso`.
        min_base_colapso: número mínimo de activos previos para que la guarda
            anti-colapso pueda dispararse (con pocos activos el porcentaje no
            es confiable).
        dias_vejez: retiro por vejez para listados PARCIALES. En portales con
            tope de páginas el mecanismo normal de bajas no puede correr
            (no se conoce el universo). Si `dias_vejez > 0`, en corridas con
            `listado_completo=False` se dan de baja los avisos del alcance no
            vistos en más de N días. 0 = desactivado (default seguro).
    """

    def __init__(
        self,
        ruta_db: str,
        sector: str,
        campos_snapshot: list[tuple[str, str | None]],
        umbral_ausencias: int = 3,
        campo_operacion: str | None = None,
        fraccion_colapso: float = 0.4,
        min_base_colapso: int = 20,
        dias_vejez: int = 0,
    ):
        self.ruta_db = ruta_db
        self.sector = sector
        self.umbral_ausencias = umbral_ausencias
        self.campo_operacion = campo_operacion
        self.fraccion_colapso = fraccion_colapso
        self.min_base_colapso = min_base_colapso
        self.dias_vejez = dias_vejez

        # Normalizar a pares (nombre, tipo_sql)
        self._snapshot: list[tuple[str, str]] = [
            (nombre, tipo or "TEXT") for nombre, tipo in campos_snapshot
        ]
        os.makedirs(os.path.dirname(ruta_db) or ".", exist_ok=True)

    # -----------------------------
    # Schema
    # -----------------------------

    def _columnas_requeridas_anuncios(self) -> dict[str, str]:
        columnas = dict(_COLUMNAS_BASE_ANUNCIOS)
        if self.campo_operacion:
            columnas[self.campo_operacion] = "TEXT"
        for nombre, tipo in self._snapshot:
            columnas[nombre] = tipo
        return columnas

    def _columnas_requeridas_corridas(self) -> dict[str, str]:
        columnas = dict(_COLUMNAS_BASE_CORRIDAS)
        if self.campo_operacion:
            columnas[self.campo_operacion] = "TEXT"
        return columnas

    def _tabla_existe(self, conn: sqlite3.Connection, tabla: str) -> bool:
        fila = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (tabla,),
        ).fetchone()
        return fila is not None

    def _columnas_tabla(self, conn: sqlite3.Connection, tabla: str) -> list[dict]:
        filas = conn.execute(f"PRAGMA table_info({_quote_ident(tabla)})").fetchall()
        return [
            {
                "cid": fila[0],
                "name": fila[1],
                "type": fila[2] or "TEXT",
                "notnull": bool(fila[3]),
                "default": fila[4],
                "pk": fila[5],
            }
            for fila in filas
        ]

    def _crear_tabla_anuncios(self, conn: sqlite3.Connection) -> None:
        defs = [
            '"id" INTEGER PRIMARY KEY AUTOINCREMENT',
            '"clave_registro" TEXT NOT NULL',
            '"enlace" TEXT NOT NULL',
            '"sector" TEXT NOT NULL',
            '"portal" TEXT NOT NULL',
        ]
        if self.campo_operacion:
            defs.append(f"{_quote_ident(self.campo_operacion)} TEXT")
        defs.extend(
            f"{_quote_ident(nombre)} {tipo}" for nombre, tipo in self._snapshot
        )
        defs.extend([
            '"primera_vez_visto" TEXT NOT NULL',
            '"ultima_vez_visto" TEXT NOT NULL',
            '"ausencias_consecutivas" INTEGER DEFAULT 0',
            '"activo" INTEGER DEFAULT 1',
            '"fecha_baja" TEXT',
        ])
        conn.execute(f'CREATE TABLE IF NOT EXISTS "anuncios" ({", ".join(defs)})')

    def _crear_tabla_corridas(self, conn: sqlite3.Connection) -> None:
        defs = [
            '"id" INTEGER PRIMARY KEY AUTOINCREMENT',
            '"fecha" TEXT NOT NULL',
            '"sector" TEXT NOT NULL',
            '"portal" TEXT NOT NULL',
        ]
        if self.campo_operacion:
            defs.append(f"{_quote_ident(self.campo_operacion)} TEXT")
        defs.extend([
            '"n_total" INTEGER',
            '"n_nuevos" INTEGER',
            '"n_repetidos" INTEGER',
            '"n_desaparecidos" INTEGER',
            '"listado_completo" INTEGER DEFAULT 1',
            '"estado_calidad" TEXT DEFAULT \'ok\'',
        ])
        conn.execute(f'CREATE TABLE IF NOT EXISTS "corridas" ({", ".join(defs)})')

    def _asegurar_columnas(
        self,
        conn: sqlite3.Connection,
        tabla: str,
        columnas_requeridas: dict[str, str],
    ) -> None:
        existentes = {c["name"] for c in self._columnas_tabla(conn, tabla)}
        for nombre, tipo in columnas_requeridas.items():
            if nombre in existentes or nombre == "id":
                continue
            conn.execute(
                f'ALTER TABLE {_quote_ident(tabla)} ADD COLUMN {_quote_ident(nombre)} {tipo}'
            )

    def _necesita_migracion_anuncios(self, conn: sqlite3.Connection) -> bool:
        info = self._columnas_tabla(conn, "anuncios")
        columnas = {c["name"]: c for c in info}
        if "id" not in columnas or "clave_registro" not in columnas:
            return True
        return columnas.get("enlace", {}).get("pk", 0) == 1

    def _migrar_tabla_anuncios_legacy(self, conn: sqlite3.Connection) -> None:
        info = self._columnas_tabla(conn, "anuncios")
        columnas_existentes = [c["name"] for c in info]
        tipos_existentes = {c["name"]: c["type"] or "TEXT" for c in info}
        columnas_requeridas = self._columnas_requeridas_anuncios()

        columnas_preservadas = [
            c for c in columnas_existentes if c not in {"id", "clave_registro"}
        ]
        for nombre, tipo in columnas_requeridas.items():
            if nombre in {"id", "clave_registro"} or nombre in columnas_preservadas:
                continue
            columnas_preservadas.append(nombre)
            tipos_existentes[nombre] = tipo

        tabla_tmp = "anuncios_migracion_tmp"
        conn.execute(f'DROP TABLE IF EXISTS {_quote_ident(tabla_tmp)}')

        defs = [
            '"id" INTEGER PRIMARY KEY AUTOINCREMENT',
            '"clave_registro" TEXT NOT NULL',
        ]
        defs.extend(
            f"{_quote_ident(nombre)} {tipos_existentes.get(nombre, 'TEXT')}"
            for nombre in columnas_preservadas
        )
        conn.execute(f'CREATE TABLE {_quote_ident(tabla_tmp)} ({", ".join(defs)})')

        if columnas_existentes:
            consulta = ", ".join(_quote_ident(c) for c in columnas_existentes)
            filas = conn.execute(
                f'SELECT {consulta} FROM {_quote_ident("anuncios")}'
            ).fetchall()
            placeholders = ", ".join("?" for _ in range(len(columnas_preservadas) + 1))
            columnas_insert = ["clave_registro", *columnas_preservadas]
            consulta_insert = ", ".join(_quote_ident(c) for c in columnas_insert)

            for fila in filas:
                data = dict(zip(columnas_existentes, fila))
                enlace = _normalizar_enlace(data.get("enlace"))
                data["enlace"] = enlace
                op_actual = data.get(self.campo_operacion) if self.campo_operacion else None
                data["clave_registro"] = _clave_registro(
                    sector=data.get("sector", self.sector),
                    portal=data.get("portal", ""),
                    enlace=enlace,
                    campo_operacion=self.campo_operacion,
                    operacion=op_actual,
                )
                valores = [data.get("clave_registro")]
                valores.extend(data.get(c) for c in columnas_preservadas)
                conn.execute(
                    f'INSERT INTO {_quote_ident(tabla_tmp)} ({consulta_insert}) '
                    f"VALUES ({placeholders})",
                    valores,
                )

        conn.execute('DROP TABLE "anuncios"')
        conn.execute(
            f'ALTER TABLE {_quote_ident(tabla_tmp)} RENAME TO {_quote_ident("anuncios")}'
        )

    def _crear_indices(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS "idx_anuncios_clave_registro" '
            'ON "anuncios" ("clave_registro")'
        )
        if self.campo_operacion:
            conn.execute(
                f'CREATE INDEX IF NOT EXISTS "idx_anuncios_scope_activo_{self.campo_operacion}" '
                f'ON "anuncios" ("sector", "portal", {_quote_ident(self.campo_operacion)}, "activo")'
            )
        else:
            conn.execute(
                'CREATE INDEX IF NOT EXISTS "idx_anuncios_scope_activo" '
                'ON "anuncios" ("sector", "portal", "activo")'
            )

    def _inicializar(self, conn: sqlite3.Connection) -> None:
        if not self._tabla_existe(conn, "anuncios"):
            self._crear_tabla_anuncios(conn)
        elif self._necesita_migracion_anuncios(conn):
            self._migrar_tabla_anuncios_legacy(conn)

        self._asegurar_columnas(conn, "anuncios", self._columnas_requeridas_anuncios())
        self._crear_indices(conn)

        self._crear_tabla_corridas(conn)
        self._asegurar_columnas(conn, "corridas", self._columnas_requeridas_corridas())
        columnas_corridas = {c["name"] for c in self._columnas_tabla(conn, "corridas")}
        if "listado_completo" in columnas_corridas:
            conn.execute(
                'UPDATE "corridas" SET "listado_completo" = 1 '
                'WHERE "listado_completo" IS NULL'
            )

    def asegurar_esquema(self) -> None:
        """Crea/actualiza tablas e índices sin registrar una corrida.

        Útil para migrar/inspeccionar la base (p. ej. en scripts de
        mantenimiento) sin necesidad de pasar un DataFrame.
        """
        with sqlite3.connect(self.ruta_db) as conn:
            self._inicializar(conn)

    def _preparar_corrida(self, df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        df = df.copy()
        df["enlace"] = df["enlace"].apply(_normalizar_enlace)
        df = df[df["enlace"] != ""].reset_index(drop=True)

        antes = len(df)
        df = df.drop_duplicates(subset=["enlace"], keep="last").reset_index(drop=True)
        descartados = antes - len(df)
        if descartados > 0:
            logger.warning(
                f"HistorialSQLite: se descartaron {descartados} enlaces duplicados "
                "dentro de la misma corrida."
            )
        return df, descartados

    # -----------------------------
    # API principal
    # -----------------------------

    def registrar_corrida(
        self,
        df: pd.DataFrame,
        portal: str,
        operacion: str | None = None,
        estado_calidad: str = "ok",
        id_fuente: str | None = None,
        permitir_rerun: bool = False,
        mutar_desaparecidos: bool | None = None,
        listado_completo: bool = True,
    ) -> tuple[pd.DataFrame, dict]:
        """Registra una corrida y marca estados en el DataFrame.

        Args:
            listado_completo: True si el listado capturó el universo completo
                del alcance consultado. Si es False (p. ej. se alcanzó un tope
                de páginas con indicios de más resultados), NO se marcan
                ausencias ni bajas por el mecanismo normal — un listado parcial
                no prueba que un aviso desapareció. Si además
                `self.dias_vejez > 0`, se aplica retiro por vejez.

        Retorna:
            (df con columna `estado_anuncio` agregada, dict de stats).
        """
        hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df, duplicados_descartados = self._preparar_corrida(df)
        estado_norm = str(estado_calidad or "").strip().lower()
        if mutar_desaparecidos is None:
            mutar_desaparecidos = estado_norm not in {"degradado", "degradada"}

        estados: list[str] = []
        nuevos = 0
        repetidos = 0

        with sqlite3.connect(self.ruta_db) as conn:
            self._inicializar(conn)
            cur = conn.cursor()

            es_rerun_fuente = False
            if id_fuente:
                where_rerun = '"sector" = ? AND "portal" = ? AND "id_fuente" = ?'
                params_rerun: list = [self.sector, portal, id_fuente]
                if self.campo_operacion:
                    where_rerun += f" AND {_quote_ident(self.campo_operacion)} IS ?"
                    params_rerun.append(operacion)
                cur.execute(
                    f'SELECT "id" FROM "corridas" WHERE {where_rerun} LIMIT 1',
                    params_rerun,
                )
                es_rerun_fuente = cur.fetchone() is not None

            if es_rerun_fuente and not permitir_rerun:
                df["estado_anuncio"] = ["ya_registrado"] * len(df)
                stats = {
                    "nuevos": 0,
                    "repetidos": 0,
                    "desaparecidos": 0,
                    "dados_de_baja": 0,
                    "duplicados_descartados": duplicados_descartados,
                    "omitido_por_rerun": True,
                    "mutacion_desaparecidos": False,
                    "id_fuente": id_fuente,
                }
                logger.warning(
                    "HistorialSQLite: corrida fuente ya registrada (%s/%s/%s). "
                    "No se muta SQLite. Usa permitir_rerun=True si corresponde.",
                    self.sector,
                    portal,
                    id_fuente,
                )
                return df, stats

            nombres_snapshot = [n for n, _ in self._snapshot]

            # Un solo pase: calcular claves y recolectar datos por fila
            rows_data: list[tuple] = []
            for _, row in df.iterrows():
                enlace = row["enlace"]
                clave = _clave_registro(
                    sector=self.sector,
                    portal=portal,
                    enlace=enlace,
                    campo_operacion=self.campo_operacion,
                    operacion=operacion,
                )
                rows_data.append((clave, enlace, row))

            claves_corrida = {clave for clave, _, _ in rows_data}

            # Batch SELECT — un query en lugar de N individuales
            if claves_corrida:
                ph_in = ",".join(["?"] * len(claves_corrida))
                cur.execute(
                    f'SELECT "clave_registro" FROM "anuncios" '
                    f'WHERE "clave_registro" IN ({ph_in})',
                    list(claves_corrida),
                )
                existentes = {r[0] for r in cur.fetchall()}
            else:
                existentes = set()

            # Templates SQL pre-computados (schema constante por instancia)
            campos_ins = ["clave_registro", "enlace", "sector", "portal"]
            if self.campo_operacion:
                campos_ins.append(self.campo_operacion)
            campos_ins.extend(nombres_snapshot)
            campos_ins.extend(["primera_vez_visto", "ultima_vez_visto", "ausencias_consecutivas", "activo"])
            sql_ins = (
                f'INSERT INTO "anuncios" ({",".join(_quote_ident(c) for c in campos_ins)}) '
                f'VALUES ({",".join(["?"] * len(campos_ins))})'
            )

            set_clauses_upd = [f"{_quote_ident(c)} = ?" for c in nombres_snapshot] + [
                '"ultima_vez_visto" = ?',
                '"ausencias_consecutivas" = 0',
                '"activo" = 1',
                '"fecha_baja" = NULL',
            ]
            sql_upd = (
                f'UPDATE "anuncios" SET {", ".join(set_clauses_upd)} '
                'WHERE "clave_registro" = ?'
            )

            batch_ins: list[tuple] = []
            batch_upd: list[tuple] = []

            for clave, enlace, row in rows_data:
                snapshot = {c: _valor(row, c) for c in nombres_snapshot}
                if clave not in existentes:
                    vals: list = [clave, enlace, self.sector, portal]
                    if self.campo_operacion:
                        vals.append(operacion)
                    vals.extend(snapshot[c] for c in nombres_snapshot)
                    vals.extend([hoy, hoy, 0, 1])
                    batch_ins.append(tuple(vals))
                    estados.append("nuevo")
                    nuevos += 1
                else:
                    vals = [snapshot[c] for c in nombres_snapshot] + [hoy, clave]
                    batch_upd.append(tuple(vals))
                    estados.append("repetido")
                    repetidos += 1

            if batch_ins:
                cur.executemany(sql_ins, batch_ins)
            if batch_upd:
                cur.executemany(sql_upd, batch_upd)

            desaparecidos = 0
            dados_de_baja = 0
            colapso_listado = False
            puede_mutar_ausencias = bool(mutar_desaparecidos) and not es_rerun_fuente

            where_scope = '"sector" = ? AND "portal" = ? AND "activo" = 1'
            params_scope: list = [self.sector, portal]
            if self.campo_operacion and operacion is not None:
                where_scope += f" AND {_quote_ident(self.campo_operacion)} = ?"
                params_scope.append(operacion)

            if puede_mutar_ausencias and listado_completo:
                # Bajas normales: solo cuando el listado representa el universo
                # completo del alcance consultado.
                cur.execute(
                    f'SELECT "clave_registro", "ausencias_consecutivas" '
                    f'FROM "anuncios" WHERE {where_scope}',
                    params_scope,
                )
                activos_db = cur.fetchall()

                # Guarda anti-colapso: si una corrida "completa" trae muchos
                # menos activos presentes que los conocidos, se OMITEN las bajas
                # esta vez para no perder historial válido por un hipo del portal.
                base = len(activos_db)
                presentes = sum(1 for clave_db, _ in activos_db if clave_db in claves_corrida)
                if base >= self.min_base_colapso and presentes < self.fraccion_colapso * base:
                    colapso_listado = True
                    logger.warning(
                        "Posible colapso de listado [%s/%s]: solo %d de %d activos "
                        "presentes (< %.0f%%). Se OMITEN bajas esta corrida para no "
                        "perder historial valido; revisar el portal.",
                        portal, operacion, presentes, base, self.fraccion_colapso * 100,
                    )
                    activos_db = []

                fecha_baja = datetime.now().strftime("%Y-%m-%d")

                batch_baja: list[tuple] = []
                batch_ausencia: list[tuple] = []
                for clave_db, ausencias in activos_db:
                    if clave_db in claves_corrida:
                        continue
                    desaparecidos += 1
                    nuevas_ausencias = (ausencias or 0) + 1
                    if nuevas_ausencias >= self.umbral_ausencias:
                        batch_baja.append((nuevas_ausencias, fecha_baja, clave_db))
                        dados_de_baja += 1
                    else:
                        batch_ausencia.append((nuevas_ausencias, clave_db))

                if batch_baja:
                    cur.executemany(
                        'UPDATE "anuncios" SET "ausencias_consecutivas" = ?, '
                        '"activo" = 0, "fecha_baja" = ? WHERE "clave_registro" = ?',
                        batch_baja,
                    )
                if batch_ausencia:
                    cur.executemany(
                        'UPDATE "anuncios" SET "ausencias_consecutivas" = ? '
                        'WHERE "clave_registro" = ?',
                        batch_ausencia,
                    )
            elif puede_mutar_ausencias and not listado_completo and self.dias_vejez > 0:
                # Listado PARCIAL (tope de páginas): no se puede saber qué
                # desapareció, pero sí retirar lo no visto en > N días. Los
                # avisos presentes acaban de refrescar `ultima_vez_visto`, así
                # que solo caen los realmente añejos. Se auto-sana al reaparecer.
                umbral_fecha = (
                    datetime.now() - timedelta(days=self.dias_vejez)
                ).strftime("%Y-%m-%d %H:%M:%S")
                where_vejez = where_scope + ' AND "ultima_vez_visto" < ?'
                params_vejez = [*params_scope, umbral_fecha]
                n_vejez = cur.execute(
                    f'SELECT COUNT(*) FROM "anuncios" WHERE {where_vejez}', params_vejez
                ).fetchone()[0]
                if n_vejez:
                    fecha_baja = datetime.now().strftime("%Y-%m-%d")
                    cur.execute(
                        f'UPDATE "anuncios" SET "activo" = 0, "fecha_baja" = ? '
                        f'WHERE {where_vejez}',
                        [fecha_baja, *params_vejez],
                    )
                    desaparecidos += n_vejez
                    dados_de_baja += n_vejez
                    logger.info(
                        "Retiro por vejez [%s/%s]: %d avisos no vistos en >%d dias.",
                        portal, operacion, n_vejez, self.dias_vejez,
                    )

            # Bitácora de corrida
            cols_ins = ["fecha", "sector", "portal", "id_fuente"]
            vals_ins: list = [hoy, self.sector, portal, id_fuente]
            if self.campo_operacion:
                cols_ins.append(self.campo_operacion)
                vals_ins.append(operacion)
            cols_ins.extend([
                "n_total",
                "n_nuevos",
                "n_repetidos",
                "n_desaparecidos",
                "listado_completo",
                "estado_calidad",
            ])
            vals_ins.extend([
                len(df), nuevos, repetidos, desaparecidos,
                int(listado_completo), estado_calidad,
            ])
            placeholders = ",".join(["?"] * len(cols_ins))
            cur.execute(
                f'INSERT INTO "corridas" ({",".join(_quote_ident(c) for c in cols_ins)}) '
                f"VALUES ({placeholders})",
                vals_ins,
            )

        df["estado_anuncio"] = estados

        stats = {
            "nuevos": nuevos,
            "repetidos": repetidos,
            "desaparecidos": desaparecidos,
            "dados_de_baja": dados_de_baja,
            "duplicados_descartados": duplicados_descartados,
            "omitido_por_rerun": False,
            "mutacion_desaparecidos": puede_mutar_ausencias,
            "listado_completo": listado_completo,
            "colapso_listado": colapso_listado,
            "id_fuente": id_fuente,
        }
        return df, stats

    def obtener_bitacora(self) -> pd.DataFrame:
        """Lee la tabla `corridas` completa como DataFrame."""
        with sqlite3.connect(self.ruta_db) as conn:
            try:
                return pd.read_sql_query(
                    'SELECT * FROM "corridas" ORDER BY "id" DESC', conn
                )
            except Exception:
                return pd.DataFrame()
