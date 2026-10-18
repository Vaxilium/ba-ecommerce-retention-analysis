# 06 — Caso de negocio: programa de recuperación de clientes (win-back)

> 🌐 _English version: [06-business-case.md](06-business-case.md)_

> Generado por `src/business_case.py`. Workbook interactivo: [`outputs/business_case.xlsx`](../outputs/business_case.xlsx)
> — cada celda calculada es una fórmula viva de Excel alimentada por las celdas amarillas de la hoja Assumptions.

## La decisión

Ejecutar campañas trimestrales de win-back a clientes con opt-in que se durmieron hace 120–540 días. El caso
base (el lift realmente observado en el A/B simulado) devuelve **19,287 USD de beneficio neto
al año sobre 1,011 USD de costo del programa (ROI 19×)**, y la
jugada sigue siendo rentable en cada celda de la grilla de sensibilidad por encima de 2,059 USD.

## Insumos (medidos o supuestos explícitos)

| Insumo | Valor | Fuente |
|---|---:|---|
| Pool elegible (inactivos, con opt-in) | 5,057 clientes | Diseño del A/B: última compra hace 120–540 días |
| Reactivación base (control) a 60 días | 5.06% | Brazo control del A/B (tasa natural medida en histórico: 5.8%) |
| Costo por email | $0.05 | Supuesto (plataforma + operación) |
| Margen por pedido (clientes de win-back) | $40.34 | Output de economía del A/B |
| Olas por año | 4 | Supuesto (trimestral) |
| Lift — conservador / base / optimista | 22.7% / 49.2% / 75.6% | IC 95% del lift relativo del A/B |

## Escenarios (anuales, con fórmulas vivas en el workbook)

| Escenario | Lift rel. | Reactivaciones/ola | Margen bruto/ola | Costo/ola | Beneficio neto anual | ROI |
|---|---:|---:|---:|---:|---:|---:|
| Conservative | 22.7% | 58 | 2,346 | 253 | **8,374** | 8.3× |
| Base | 49.2% | 126 | 5,074 | 253 | **19,287** | 19.1× |
| Optimistic | 75.6% | 193 | 7,803 | 253 | **30,199** | 29.9× |

## Sensibilidad: beneficio neto anual (USD)

Filas: lift relativo. Columnas: margen por pedido (USD). El caso base está resaltado en el workbook.

| Lift \ Margen | 30 | 35 | 40 | 45 | 50 |
|---|---|---|---|---|---|
| 10% | 2,059 | 2,571 | 3,083 | 3,595 | 4,106 |
| 20% | 5,130 | 6,153 | 7,177 | 8,200 | 9,224 |
| 30% | 8,200 | 9,736 | 11,271 | 12,806 | 14,342 |
| 40% | 11,271 | 13,318 | 15,365 | 17,412 | 19,459 |
| 50% | 14,342 | 16,900 | 19,459 | 22,018 | 24,577 |
| 60% | 17,412 | 20,483 | 23,553 | 26,624 | 29,695 |
| 70% | 20,483 | 24,065 | 27,648 | 31,230 | 34,812 |

Incluso la peor celda (lift bajo, margen delgado) queda positiva: el costo fijo del programa es mínimo
frente al margen de un solo pedido.

## Flujo de caja y payback (caso base)

| Mes | Evento | Costo | Margen bruto | Neto | Acumulado |
|---:|---|---:|---:|---:|---:|
| 1 | wave | 253 | 0 | -253 | -253 |
| 3 |  | 0 | 5,074 | 5,074 | 4,822 |
| 4 | wave | 253 | 0 | -253 | 4,569 |
| 6 |  | 0 | 5,074 | 5,074 | 9,643 |
| 7 | wave | 253 | 0 | -253 | 9,390 |
| 9 |  | 0 | 5,074 | 5,074 | 14,465 |
| 10 | wave | 253 | 0 | -253 | 14,212 |
| 12 |  | 0 | 5,074 | 5,074 | 19,287 |

**Payback: mes 3** — el margen de la primera ola entra dos meses después del envío, y desde
ahí el margen de cada ola supera ampliamente el costo de envío de la siguiente.

## Riesgos y advertencias honestas

- El "lift observado" proviene de un experimento **simulado** sobre datos sintéticos; el trabajo del workbook es
  hacer la economía auditable y re-ejecutable con números reales, no afirmar que este lift exacto se repetirá.
- Se asume pool constante por ola; en la realidad el pool de 120–540 días se recompone con nuevo churn,
  y los clientes que no reactivan no deberían recibir email cada trimestre sin un cool-down.
- El margen por pedido es un promedio del pool; si la oferta de win-back incluye descuento, el margen baja —
  la grilla de sensibilidad cubre márgenes desde $30.
- Entregabilidad/consentimiento: la población es solo clientes con opt-in; deben aplicarse supresiones tipo GDPR/LGPD.
