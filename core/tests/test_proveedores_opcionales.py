"""Pruebas de los dos proveedores opcionales: Nano Banana y ElevenLabs.

Lo que se comprueba no es que llamen a internet (eso no se puede probar sin clave
ni red), sino las tres cosas que sí importan cuando alguien instala esto:

  1 · Sin clave, el mensaje es claro y NO se hace ninguna petición de red.
  2 · `/health` solo anuncia lo que de verdad está disponible.
  3 · Un error del proveedor (401, 429, sin red) se convierte en un mensaje
     legible, nunca en un volcado técnico ni en la clave.
"""

import importlib
import os
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "service"))

from service import proveedores_externos as ext  # noqa: E402


@pytest.fixture(autouse=True)
def sin_claves(monkeypatch):
    """Cada prueba arranca sin claves: el estado por defecto de una instalación nueva."""
    for nombre in ("VE_GEMINI_KEY", "VE_ELEVEN_KEY"):
        monkeypatch.delenv(nombre, raising=False)
    yield


# ── 1 · sin clave ─────────────────────────────────────────────────────────


def test_gemini_sin_clave_avisa_y_no_llama_a_la_red(tmp_path, monkeypatch):
    llamadas = []
    monkeypatch.setattr(ext.urllib.request, "urlopen", lambda *a, **k: llamadas.append(1))

    with pytest.raises(ext.ProveedorNoConfigurado) as fallo:
        ext.generar_imagen_gemini("un gato", tmp_path / "x.png")

    assert "VE_GEMINI_KEY" in str(fallo.value)
    assert llamadas == [], "sin clave no se debe ni intentar la petición"


def test_eleven_sin_clave_avisa_y_no_llama_a_la_red(tmp_path, monkeypatch):
    llamadas = []
    monkeypatch.setattr(ext.urllib.request, "urlopen", lambda *a, **k: llamadas.append(1))

    with pytest.raises(ext.ProveedorNoConfigurado) as fallo:
        ext.generar_voz_eleven("hola", tmp_path / "x.mp3")

    assert "VE_ELEVEN_KEY" in str(fallo.value)
    assert llamadas == []


def test_disponibilidad_refleja_las_claves(monkeypatch):
    assert ext.gemini_disponible() is False
    assert ext.eleven_disponible() is False

    monkeypatch.setenv("VE_GEMINI_KEY", "una-clave-cualquiera")
    assert ext.gemini_disponible() is True
    assert ext.eleven_disponible() is False


# ── 2 · /health ───────────────────────────────────────────────────────────


def test_health_solo_anuncia_lo_que_existe(monkeypatch):
    monkeypatch.delenv("VE_PROVIDER_IMAGE_URL", raising=False)
    monkeypatch.delenv("VE_PROVIDER_MUSIC_URL", raising=False)

    generar = importlib.reload(importlib.import_module("service.generate"))
    estado = generar.provider_status()

    assert estado["providerModes"]["image"]["local"] is True, "local siempre está"
    assert estado["providerModes"]["image"]["gemini"] is False, "sin clave no se anuncia"
    assert estado["providerModes"]["voice"]["eleven"] is False

    monkeypatch.setenv("VE_GEMINI_KEY", "k")
    monkeypatch.setenv("VE_ELEVEN_KEY", "k")
    estado = generar.provider_status()
    assert estado["providerModes"]["image"]["gemini"] is True
    assert estado["providerModes"]["voice"]["eleven"] is True


# ── 3 · errores legibles ──────────────────────────────────────────────────


def test_un_401_dice_que_la_clave_fue_rechazada(tmp_path, monkeypatch):
    import urllib.error

    monkeypatch.setenv("VE_GEMINI_KEY", "clave-mala")

    def urlopen(*a, **k):
        raise urllib.error.HTTPError("u", 401, "no", {}, None)

    monkeypatch.setattr(ext.urllib.request, "urlopen", urlopen)

    with pytest.raises(RuntimeError) as fallo:
        ext.generar_imagen_gemini("x", tmp_path / "y.png")

    mensaje = str(fallo.value)
    assert "rechazó la clave" in mensaje
    assert "clave-mala" not in mensaje, "la clave nunca aparece en el mensaje"


def test_sin_red_el_mensaje_es_humano(tmp_path, monkeypatch):
    import urllib.error

    monkeypatch.setenv("VE_ELEVEN_KEY", "k")

    def urlopen(*a, **k):
        raise urllib.error.URLError("sin ruta al host")

    monkeypatch.setattr(ext.urllib.request, "urlopen", urlopen)

    with pytest.raises(RuntimeError) as fallo:
        ext.generar_voz_eleven("x", tmp_path / "y.mp3")

    assert "sin red o tardó demasiado" in str(fallo.value)
