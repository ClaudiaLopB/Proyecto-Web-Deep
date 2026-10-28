"""Tests del modo sin IA y de las herramientas deterministas. Ejecutar con: python -m unittest"""

import json
import tempfile
import unittest
from pathlib import Path

from agente import datos
from agente.__main__ import main
from agente.automatico import automatic_operations, automatic_spec
from agente.dashboard import build_dashboard, validate_spec

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "datos" / "accidentes_urbanos.csv"


class CleaningTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = datos.load_csv(CSV)
        datos.detect_issues(cls.session)
        datos.apply_operations(cls.session, automatic_operations(cls.session))

    def test_detects_known_problems(self):
        problems = {(i["columna"], i["propuesta"]["op"]) for i in self.session.issues if i["propuesta"]}
        self.assertIn(("velocidad_estimada_kmh", "a_nulo"), problems)
        self.assertIn(("tipo_accidente", "normalizar_categorias"), problems)
        self.assertIn(("con_lesiones", "normalizar_categorias"), problems)
        self.assertIn(("alumbrado", "a_nulo"), problems)
        self.assertIn(("edad_conductor", "rango_valido"), problems)

    def test_categories_are_unified(self):
        data = self.session.data
        self.assertEqual(data["tipo_accidente"].nunique(), 5)
        self.assertEqual(set(data["con_lesiones"].dropna()), {"sí", "no"})
        self.assertNotIn("N/D", set(data["alumbrado"].dropna()))

    def test_sentinels_and_impossible_values_become_null(self):
        data = self.session.data
        self.assertGreaterEqual(data["velocidad_estimada_kmh"].min(), 0)
        self.assertEqual(int(data["velocidad_estimada_kmh"].isna().sum()), 518)
        self.assertLessEqual(data["edad_conductor"].max(), 100)
        self.assertEqual(len(data), 9200)

    def test_query_rate(self):
        result = datos.query(self.session, ["implicado_vulnerable"], "tasa", "con_lesiones", "sí")
        rates = {r["implicado_vulnerable"]: r["tasa_%"] for r in result["filas"]}
        self.assertGreater(rates["sí"], rates["no"])

    def test_query_bins_keep_order(self):
        result = datos.query(self.session, ["velocidad_estimada_kmh"], "conteo",
                             bins={"velocidad_estimada_kmh": [0, 50, 100, 200]})
        self.assertEqual([r["velocidad_estimada_kmh"] for r in result["filas"]], ["0–50", "50–100", "100–200"])


class MapTest(unittest.TestCase):
    CSV_COORDS = ROOT / "tests" / "datos" / "actividades_con_coordenadas.csv"

    def test_detects_coordinates(self):
        session = datos.load_csv(self.CSV_COORDS)
        self.assertEqual(datos.detect_coordinates(session.raw), {"lat": "latitud", "lon": "longitud"})

    def test_no_coordinates_in_accidents(self):
        self.assertIsNone(datos.detect_coordinates(datos.load_csv(CSV).raw))

    def test_automatic_spec_adds_map(self):
        session = datos.load_csv(self.CSV_COORDS)
        datos.detect_issues(session)
        datos.apply_operations(session, automatic_operations(session))
        spec = automatic_spec(session)
        self.assertEqual(spec["graficos"][0]["tipo"], "mapa")
        self.assertEqual(validate_spec(session, spec), [])
        with tempfile.TemporaryDirectory() as tmp:
            html = build_dashboard(session, spec, Path(tmp) / "d.html").read_text(encoding="utf-8")
        # Las coordenadas no se redondean al guardarlas en la página
        self.assertIn(str(session.data["latitud"].iloc[0]), html)

    def test_map_needs_valid_coordinates(self):
        session = datos.load_csv(CSV)
        datos.apply_operations(session, [])
        errors = validate_spec(session, {"graficos": [{"tipo": "mapa", "titulo": "m", "lat": "edad_conductor", "lon": "hora"}]})
        self.assertTrue(any("no son grados" in e for e in errors))


class DashboardTest(unittest.TestCase):
    def test_automatic_spec_is_valid_and_builds(self):
        session = datos.load_csv(CSV)
        datos.detect_issues(session)
        datos.apply_operations(session, automatic_operations(session))
        spec = automatic_spec(session)
        self.assertEqual(validate_spec(session, spec), [])
        with tempfile.TemporaryDirectory() as tmp:
            html = build_dashboard(session, spec, Path(tmp) / "d.html").read_text(encoding="utf-8")
        self.assertIn("plotly", html)
        self.assertNotIn("__DATA__", html)

    def test_invalid_spec_reports_errors(self):
        session = datos.load_csv(CSV)
        errors = validate_spec(session, {"graficos": [{"tipo": "tarta", "x": "no_existe"}]})
        self.assertTrue(any("tipo desconocido" in e for e in errors))
        self.assertTrue(any("no_existe" in e for e in errors))

    def test_example_plan_builds_from_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "d.html"
            code = main([str(CSV), "--spec", str(ROOT / "ejemplos" / "accidentes_plan.json"), "--salida", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())

    def test_example_plan_is_valid_json(self):
        plan = json.loads((ROOT / "ejemplos" / "accidentes_plan.json").read_text(encoding="utf-8"))
        self.assertIn("limpieza", plan)
        self.assertIn("dashboard", plan)


if __name__ == "__main__":
    unittest.main()
