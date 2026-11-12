"""Pruebas del motor cinematico: que el skill este puesto y que el seam no mienta.

Lo que se fija aqui:
  * el skill viaja DENTRO del repo, no en una ruta de la maquina del autor;
  * los tres scripts que el pipeline necesita existen de verdad;
  * un nombre de proyecto no puede escapar de la raiz (``../`` y amigos);
  * ``crear_proyecto`` produce la carpeta con los archivos del skill;
  * ``estado`` dice la verdad cuando no hay nada renderizado.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service import cinematic  # noqa: E402


class SkillVendoreadoTests(unittest.TestCase):
    def test_el_skill_vive_dentro_del_repo(self) -> None:
        # Si esto falla, alguien movio el skill fuera y el plugin deja de ser portable.
        self.assertTrue(cinematic.CINEMATIC_ROOT.is_dir(), cinematic.CINEMATIC_ROOT)
        repo = Path(__file__).resolve().parents[2]
        self.assertIn(repo, cinematic.CINEMATIC_ROOT.parents)

    def test_los_tres_scripts_del_pipeline_existen(self) -> None:
        for script in ("new_project.py", "build_narration.py", "render.py"):
            self.assertTrue((cinematic.SCRIPTS / script).is_file(), script)

    def test_disponible_dice_la_verdad(self) -> None:
        info = cinematic.disponible()
        self.assertTrue(info["disponible"])
        self.assertEqual(info["faltan"], [])
        self.assertGreaterEqual(info["scripts"], 10)

    def test_la_licencia_va_con_el_skill(self) -> None:
        # El skill no es nuestro: si se redistribuye, la licencia viaja al lado.
        self.assertTrue((cinematic.CINEMATIC_ROOT / "LICENSE").is_file())


class NombresTests(unittest.TestCase):
    def test_rechaza_escaparse_de_la_raiz(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for malo in ("../fuera", "a/b", "", "con espacio", ".oculto"):
                with self.assertRaises(ValueError, msg=malo):
                    cinematic._carpeta(base, malo)

    def test_acepta_un_nombre_normal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            destino = cinematic._carpeta(base, "mi-pelicula")
            self.assertEqual(destino.name, "mi-pelicula")
            self.assertEqual(destino.parent.resolve(), base.resolve())


class CrearProyectoTests(unittest.TestCase):
    def test_crear_proyecto_andamia_la_carpeta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "cine"
            info = cinematic.crear_proyecto(base, "prueba-uno", "Prueba Uno")
            carpeta = Path(info["carpeta"])
            self.assertTrue(carpeta.is_dir())
            # El skill deja script.json y scene.py; sin ellos el render no arranca.
            self.assertIn("script.json", info["archivos"])
            self.assertIn("scene.py", info["archivos"])

    def test_no_pisa_un_proyecto_existente(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "cine"
            cinematic.crear_proyecto(base, "repetido", "Uno")
            with self.assertRaises(ValueError):
                cinematic.crear_proyecto(base, "repetido", "Dos")


class EstadoTests(unittest.TestCase):
    def test_sin_nada_renderizado_lo_dice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "cine"
            cinematic.crear_proyecto(base, "vacio", "Vacio")
            info = cinematic.estado(base / "vacio")
            self.assertTrue(info["existe"])
            self.assertFalse(info["terminado"])
            self.assertFalse(info["corriendo"])
            self.assertIsNone(info["salida"])

    def test_carpeta_inexistente_no_explota(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            info = cinematic.estado(Path(tmp) / "no-existe")
            self.assertFalse(info["existe"])
            self.assertFalse(info["corriendo"])


if __name__ == "__main__":
    unittest.main()
