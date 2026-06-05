"""
Schema base `AnuncioBase` — campos comunes a cualquier anuncio web,
independientemente del sector. Cada sector extiende esta clase.

Corresponde a la sección 5.3 del PLAN_PROYECTO_SCRAPING_BCRP.md.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EstadoAnuncio(str, Enum):
    """Estado del ciclo de vida del anuncio. Asignado por el historial."""

    NUEVO = "nuevo"
    REPETIDO = "repetido"
    DESAPARECIDO = "desaparecido"
    DADO_DE_BAJA = "dado de baja"


class RefAnuncio(BaseModel):
    """Referencia ligera a un anuncio descubierto en un listado.

    Separa el DESCUBRIMIENTO (barato: IDs/URLs visibles en la página de
    búsqueda) de la EXTRACCIÓN DE DETALLE (cara: una request por anuncio).
    Permite saltar el detalle de refs ya conocidas y solo pagar el costo por
    las nuevas. La construye `descubrir_listado` y la consume `extraer_detalle`
    (ver `core.contratos.PortalScraper`).
    """

    enlace: str                                  # URL del detalle (sin normalizar aún)
    fuente: str                                  # portal de origen
    id_externo: Optional[str] = None             # id del anuncio en el portal
    operacion: Optional[str] = None              # alcance consultado (región, tipo, etc.)

    model_config = {"frozen": True}


class AnuncioBase(BaseModel):
    """Campos presentes en cualquier anuncio web.

    Cada sector crea su subclase (p. ej. `AnuncioInmobiliario`,
    `AnuncioEmpleo`) que añade campos específicos y reglas propias.
    """

    # --- Identificación ---
    enlace: str                                  # URL canónica normalizada
    portal: str                                  # "urbania" | "computrabajo" | etc.
    sector: str                                  # "inmobiliario" | "empleo" | etc.
    id_portal: Optional[str] = None              # ID interno del portal si existe

    # --- Temporalidad ---
    fecha_publicacion: Optional[str] = None      # ISO 8601
    fecha_extraccion: str                        # ISO 8601, siempre presente

    # --- Estado del ciclo de vida (asignado por core.historial) ---
    estado_anuncio: Optional[EstadoAnuncio] = None
    ausencias_consecutivas: Optional[int] = Field(default=0, ge=0)

    # --- Metadatos de auditoría ---
    warnings: Optional[str] = None
    version_scraper: Optional[str] = None
    ejecutor: Optional[str] = None               # usuario que corrió el scraper

    model_config = {"use_enum_values": True}
