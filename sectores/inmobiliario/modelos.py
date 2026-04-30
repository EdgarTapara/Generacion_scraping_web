"""
Schema del sector inmobiliario — extiende `core.modelos.AnuncioBase`.

Migrado de v1/modelos.py. Los campos específicos del sector (tipo_inmueble,
precio, area, distrito, etc.) se declaran aquí. Los campos comunes a
cualquier anuncio web (enlace, portal, fecha_extraccion, warnings, etc.)
los hereda de AnuncioBase.
"""

from typing import Optional

from pydantic import Field, field_validator

from core.modelos import AnuncioBase


class AnuncioInmobiliario(AnuncioBase):
    """Anuncio inmobiliario: un departamento, casa, terreno, etc. de un portal."""

    # `sector` viene con default (contrasta con AnuncioBase que lo exige).
    sector: str = "inmobiliario"

    # Específico del sector
    tipo_operacion: str                                 # "alquiler" | "venta"
    posting_id: Optional[str] = None
    publicacion_id: Optional[str] = None

    # --- Precio ---
    precio_raw: Optional[str] = None
    precio: Optional[float] = None
    moneda: Optional[str] = Field(None, pattern=r"^(PEN|USD)$")
    precio_secundario: Optional[float] = None
    moneda_secundaria: Optional[str] = Field(None, pattern=r"^(PEN|USD)$")
    mantenimiento_raw: Optional[str] = None
    mantenimiento: Optional[float] = None

    # --- Texto ---
    fecha_publicacion_raw: Optional[str] = None
    titulo: Optional[str] = None
    tipo_inmueble: Optional[str] = None
    descripcion: Optional[str] = None

    # --- Ubicación ---
    distrito: Optional[str] = None
    zone_name: Optional[str] = None
    address_name: Optional[str] = None
    ubicacion: Optional[str] = None  # referencia urbana Av./Calle/Urb.

    # --- Características físicas ---
    caracteristicas_raw: Optional[str] = None
    area_total_m2: Optional[float] = Field(None, ge=1, le=100000)
    area_construida_m2: Optional[float] = Field(None, ge=1, le=100000)
    dormitorios: Optional[int] = Field(None, ge=0, le=50)
    banos: Optional[int] = Field(None, ge=0, le=30)
    medio_banos: Optional[int] = Field(None, ge=0, le=10)
    estacionamientos: Optional[int] = Field(None, ge=0, le=20)
    pisos: Optional[int] = Field(None, ge=1, le=60)
    antiguedad_anos: Optional[int] = Field(None, ge=0, le=200)

    # --- Anunciante y derivados ---
    anunciante: Optional[str] = None
    precio_por_m2: Optional[float] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None

    @field_validator("precio", "precio_secundario", "mantenimiento")
    @classmethod
    def precio_positivo(cls, v):
        if v is not None and v < 0:
            raise ValueError(f"Valor monetario debe ser no negativo: {v}")
        return v


# --- Catálogo de distritos de Arequipa metropolitana ---
DISTRITOS_AREQUIPA = [
    "Arequipa", "Alto Selva Alegre", "Cayma", "Cerro Colorado",
    "Characato", "Chiguata", "Hunter", "Jacobo Hunter",
    "Jose Luis Bustamante y Rivero", "J.L.B. y Rivero",
    "La Joya", "Mariano Melgar", "Miraflores", "Mollebaya",
    "Paucarpata", "Pocsi", "Polobaya", "Quequeña",
    "Sabandia", "Sabandía", "Sachaca", "San Juan de Siguas",
    "San Juan de Tarucani", "Santa Isabel de Siguas",
    "Santa Rita de Siguas", "Socabaya", "Tiabaya",
    "Uchumayo", "Vitor", "Yanahuara", "Yarabamba", "Yura",
]

DISTRITOS_NORM = {d.lower().strip() for d in DISTRITOS_AREQUIPA}

# --- Rangos razonables por operación y moneda ---
RANGOS_PRECIOS = {
    "alquiler": {"PEN": (150, 80000), "USD": (40, 25000)},
    "venta": {"PEN": (30000, 80000000), "USD": (8000, 25000000)},
}


def validar_anuncio(anuncio: AnuncioInmobiliario) -> list[str]:
    """Aplica reglas de negocio inmobiliario. Retorna lista de warnings."""
    warnings: list[str] = []

    if anuncio.precio and anuncio.moneda:
        rango = RANGOS_PRECIOS.get(anuncio.tipo_operacion, {}).get(anuncio.moneda)
        if rango and not (rango[0] <= anuncio.precio <= rango[1]):
            warnings.append(
                f"Precio {anuncio.precio} {anuncio.moneda} fuera de rango "
                f"{rango} para {anuncio.tipo_operacion}"
            )

    if anuncio.distrito and anuncio.distrito.lower().strip() not in DISTRITOS_NORM:
        warnings.append(f"Distrito no reconocido: '{anuncio.distrito}'")

    if anuncio.area_total_m2 and anuncio.area_construida_m2:
        if anuncio.area_construida_m2 > anuncio.area_total_m2 * 1.1:
            warnings.append(
                f"Area construida ({anuncio.area_construida_m2}) > "
                f"area total ({anuncio.area_total_m2})"
            )

    if not anuncio.titulo:
        warnings.append("Titulo no generable (faltan campos base)")

    return warnings
