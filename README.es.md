# Análisis de Retención E-commerce — Altiplano Goods (caso sintético)

[![ci](https://github.com/Vaxilium/ba-ecommerce-retention-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/Vaxilium/ba-ecommerce-retention-analysis/actions/workflows/ci.yml)

**Proyecto de portafolio de Business Analyst:** diagnóstico completo de por qué cae la recompra en una
marca ficticia de e-commerce latinoamericana — desde el planteamiento del problema y la calidad de datos
hasta el modelado SQL, el análisis estadístico y una recomendación con costos, todo reproducible con `make all`.

> ⚠️ **Datos sintéticos.** Altiplano Goods no existe. El dataset (79,084 pedidos, 20,000 clientes,
> ene 2024 – dic 2025) se genera con código semillado e incluye suciedad deliberada (duplicados, nulos,
> timestamps con zona horaria rota) para que la capa de calidad tenga trabajo real. El entregable es el
> *método y la toma de decisiones*, no los números específicos.

## Resultados principales (calculados por este pipeline)

| Hallazgo | Evidencia |
|---|---|
| La tasa de recompra a 90 días cayó **35.3% → 26.8%** (-8.5 pp, -24% rel.) | `sql/32`, matriz de cohortes |
| La caída es principalmente **mix de canales**, no peores clientes: **7.1 pp mix** vs 1.3 pp intra-grupo | Descomposición conjunta canal×descuento (`sql/40`) |
| Descuentos profundos predicen churn: primera compra con descuento alto recompra **22.4%** vs **37.4%** sin descuento | `sql/34`, modelo (docs/05) |
| Paid social trae volumen, no lealtad: recompra **22.7%** vs referral **44.0%** | `sql/36`, `sql/41` |
| Incidente logístico en Colombia: demora 1.7 → **6.4 días**, recompra 31.1% → **19.1%** | `sql/38` |
| Modelo de churn: AUC test **0.636**, decil superior recompra **1.5×** | `src/model_churn.py` |
| Email de win-back validado: 5.1% → 7.5% (+2.5 pp, p=0.0003), **ROI 19×** | `src/ab_test_winback.py`, `outputs/business_case.xlsx` |
| Ingresos concentrados: decil superior = **53%**; champions = **71%** del ingreso | `sql/39`, RFM (`sql/31`) |

## Entregables

| Artefacto | Qué es |
|---|---|
| 📊 **[Dashboard interactivo](https://vaxilium.github.io/ba-ecommerce-retention-analysis/dashboard.html)** | Reporte plotly en vivo (también autocontenido en `docs/dashboard.html` — abrir localmente) |
| 📄 **[Resumen ejecutivo](docs/executive-summary.md)** | Lectura de una página para stakeholders |
| 💰 **[Caso de negocio](docs/06-business-case.md)** + **[Excel](outputs/business_case.xlsx)** | Escenarios con fórmulas vivas, sensibilidad, payback |
| 🗺️ **[Roadmap RICE](docs/07-roadmap.md)** · **[Historias de usuario](docs/08-user-stories.md)** | Iniciativas priorizadas con criterios de aceptación |
| 🔍 **[Planteamiento](docs/01-problem-framing.md)** · **[Modelo de datos](docs/02-data-model.md)** · **[Calidad](docs/03-data-quality.md)** | Fundamentos BA |
| 🧮 **[Hallazgos SQL](docs/04-sql-findings.md)** · **[Análisis](docs/05-analytics.md)** | Análisis completo, métodos y limitaciones |

## Cómo funciona el pipeline

```
generate_data.py  →  build_warehouse.py   →  run_sql_analysis.py  →  model_churn.py / rfm_segments.py /
(CSV crudos,         (staging → calidad →     (sql/30–41, KPI,        ab_test_winback.py / business_case.py /
 semillado)           marts, duckdb)           descomposición)         build_dashboard.py / build_roadmap.py / README
```

`make all` ejecuta toda la cadena (generación → warehouse → análisis SQL → analítica Python → docs → tests).
Semillado de punta a punta: la misma semilla ⇒ datos byte-idénticos y los mismos números en cada documento.

## Inicio rápido

```bash
git clone https://github.com/Vaxilium/ba-ecommerce-retention-analysis
cd ba-ecommerce-retention-analysis
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
make all        # reconstrucción completa (~1–2 min) + tests
open docs/dashboard.html
```

## Notas de método (honestidad primero)

- La capa SQL de calidad **detecta y repara** duplicados, timestamps desviados y nulos de join (16/16 checks
  post-limpieza; ver docs/03).
- La caída de retención se descompone en mix/rate con cohortes conjuntas: "paid social crece" no se confunde
  con "los clientes empeoraron".
- La tasa control del A/B está **anclada a la reactivación natural medida**, no asumida; potencia e
  intervalos se calculan desde primeros principios (sin cajas negras).
- El modelo es regresión logística con IC de Wald — elegido por interpretabilidad, honesto con su AUC 0.64.
- El "Impact" del RICE es margen USD medido; Confianza/Esfuerzo son supuestos declarados.

## Autor

Franco Tilleria Centurion — Business Analyst.
[GitHub](https://github.com/Vaxilium) · [LinkedIn](https://www.linkedin.com/in/franco-tilleria-centurion)

_Licencia: MIT. Datos sintéticos; no se usa información real de clientes._ · [Read in English](README.md)
