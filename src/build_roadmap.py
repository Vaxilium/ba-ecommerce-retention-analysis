"""Build docs/07-roadmap.md (RICE, computed) and docs/08-user-stories.md.
Dollar impacts are estimated from measured outputs; confidence and effort are explicit
assumptions shown in the table (documented as such)."""
from __future__ import annotations

import json
from pathlib import Path

SUM = json.loads(Path("outputs/analysis/summary.json").read_text())
RFM = json.loads(Path("outputs/analysis/rfm_segments.json").read_text())
AB = json.loads(Path("outputs/analysis/ab_test.json").read_text())
BC_CASES = {"base_annual_gm": 0.0}  # filled below from A/B (no dependency on workbook)

pool = AB["design"]["population"]
control = AB["observed"]["control_rate"]
lift = AB["observed"]["rel_lift"]
margin = AB["economics"]["avg_margin_per_order"]
waves = 4

winback_gm_yr = pool * control * lift * margin * waves
winback_cost_yr = pool * AB["economics"]["cost_per_email"] * waves

col = next(r for r in SUM["region_period"] if r["country"] == "Colombia" and r["period"] == "from_2025H2")
col_pre = next(r for r in SUM["region_period"] if r["country"] == "Colombia" and r["period"] == "pre_2025H2")
col_gap = col_pre["repeat_rate_90d"] - col["repeat_rate_90d"]

heavy = next(r for r in SUM["clv"]["by_band"] if r["first_order_discount_band"] == "heavy")
light = next(r for r in SUM["clv"]["by_band"] if r["first_order_discount_band"] == "light")
ps = next(r for r in SUM["clv"]["by_channel"] if r["acquisition_channel"] == "paid_social")
ref = next(r for r in SUM["clv"]["by_channel"] if r["acquisition_channel"] == "referral")
heavy_count = next(r for r in SUM["discount"] if r["first_order_discount_band"] == "heavy")["customers"]

delay_bad = sum(r["customers"] for r in SUM["delay_bucket"] if r["delay_bucket"] in ("4_six_to_10d", "5_over_10d"))
delay_gap = next(r for r in SUM["delay_bucket"] if r["delay_bucket"] == "2_one_to_3d")["repeat_rate_90d"] - \
            next(r for r in SUM["delay_bucket"] if r["delay_bucket"] == "4_six_to_10d")["repeat_rate_90d"]

needs_att = next(r for r in RFM["profiles"] if r["segment"] == "needs_attention")

INITIATIVES = [
    dict(
        name="Win-back program (quarterly waves)",
        name_es="Programa de win-back (olas trimestrales)",
        story="US-1", owner="CRM / Lifecycle", owner_es="CRM / Ciclo de vida",
        reach=pool * waves,
        impact=winback_gm_yr - winback_cost_yr,
        confidence=0.80, effort=3,
        basis=f"A/B-validated: {lift:.0%} rel lift, p={AB['observed']['p_value']:.4f}",
        basis_es=f"Validado con A/B: lift relativo {lift:.0%}, p={AB['observed']['p_value']:.4f}",
        risk="Pool assumed constant/quarter; cool-down rules needed to avoid over-mailing",
        risk_es="Se asume pool constante por trimestre; hacen falta reglas de cool-down para no sobremailar",
    ),
    dict(
        name="Cap first-order discounts (no 'heavy' tier)",
        name_es="Limitar descuentos de primera compra (sin tramo 'heavy')",
        story="US-2", owner="Growth / Pricing", owner_es="Growth / Precios",
        reach=heavy_count,
        impact=heavy_count * 0.2 * (light["avg_margin_12m"] - heavy["avg_margin_12m"]),
        confidence=0.30, effort=4,
        basis=f"12-mo margin gap light vs heavy band: ${light['avg_margin_12m']:.0f} vs ${heavy['avg_margin_12m']:.0f}; assume 20% of heavy recruits shift to light",
        basis_es=f"Brecha de margen a 12 meses banda light vs heavy: ${light['avg_margin_12m']:.0f} vs ${heavy['avg_margin_12m']:.0f}; se asume que 20% de los reclutas heavy migra a light",
        risk="Volume loss from removing deep discounts is NOT modelled — directional estimate only",
        risk_es="La pérdida de volumen al eliminar descuentos profundos NO está modelada — estimación direccional",
    ),
    dict(
        name="Fix Colombia courier delays",
        name_es="Arreglar demoras del courier en Colombia",
        story="US-3", owner="Operations", owner_es="Operaciones",
        reach=col["customers"] * 4,
        impact=col["customers"] * col_gap * margin * 4,
        confidence=0.55, effort=6,
        basis=f"Colombia repeat fell {col_pre['repeat_rate_90d']:.1%} -> {col['repeat_rate_90d']:.1%} while delay hit {SUM['delay_colombia']['from_2025h2']:.1f} days",
        basis_es=f"La recompra en Colombia cayó {col_pre['repeat_rate_90d']:.1%} -> {col['repeat_rate_90d']:.1%} mientras la demora llegó a {SUM['delay_colombia']['from_2025h2']:.1f} días",
        risk="Observational link; seasonal/postal factors could share the blame",
        risk_es="Vínculo observacional; factores estacionales/postales podrían compartir la culpa",
    ),
    dict(
        name="Delay-aware send suppression",
        name_es="Supresión de envíos por demora de entrega",
        story="US-4", owner="CRM / Ops integration", owner_es="CRM / Integración con Ops",
        reach=delay_bad * 4,
        impact=delay_bad * delay_gap * margin * 4,
        confidence=0.45, effort=2,
        basis=f"Customers with 6+ day delays repeat {delay_gap:.1%} below the 1-3d baseline ({delay_bad} customers/yr)",
        basis_es=f"Clientes con demoras de 6+ días recompran {delay_gap:.1%} por debajo de la base de 1-3 días ({delay_bad} clientes/año)",
        risk="Suppression costs some short-term email revenue; retention gain is the bet",
        risk_es="La supresión cuesta algo de ingreso de email de corto plazo; la apuesta es la retención",
    ),
    dict(
        name="Shift paid-social budget to referral / email",
        name_es="Mover presupuesto de paid social a referral / email",
        story="US-5", owner="Growth", owner_es="Growth",
        reach=ps["customers"],
        impact=ps["customers"] * 0.15 * (ref["avg_margin_12m"] - ps["avg_margin_12m"]),
        confidence=0.35, effort=8,
        basis=f"12-mo margin per customer: referral ${ref['avg_margin_12m']:.0f} vs paid social ${ps['avg_margin_12m']:.0f}; assume 15% volume shift",
        basis_es=f"Margen a 12 meses por cliente: referral ${ref['avg_margin_12m']:.0f} vs paid social ${ps['avg_margin_12m']:.0f}; se asume 15% de migración de volumen",
        risk="Channel capacity is not infinite; CAC differences not modelled here",
        risk_es="La capacidad de cada canal no es infinita; las diferencias de CAC no están modeladas aquí",
    ),
    dict(
        name="RFM-triggered lifecycle nudges (needs_attention)",
        name_es="Nudges de ciclo de vida por RFM (needs_attention)",
        story="US-1", owner="CRM / Lifecycle", owner_es="CRM / Ciclo de vida",
        reach=needs_att["customers"],
        impact=needs_att["customers"] * control * lift * margin,
        confidence=0.35, effort=3,
        basis=f"{needs_att['customers']:,} customers, {needs_att['avg_frequency']:.1f} orders avg, {needs_att['avg_monetary']:.0f} USD spend; assume half the win-back lift applies",
        basis_es=f"{needs_att['customers']:,} clientes, {needs_att['avg_frequency']:.1f} pedidos promedio, {needs_att['avg_monetary']:.0f} USD de gasto; se asume la mitad del lift de win-back",
        risk="Segment overlaps win-back pool — count once to avoid double-dipping",
        risk_es="El segmento se solapa con el pool de win-back — contar una sola vez para evitar doble conteo",
    ),
]

for i in INITIATIVES:
    if i["name"].startswith("RFM-triggered"):
        i["impact"] *= 0.5
    i["score"] = i["impact"] * i["confidence"] / i["effort"]

ranked = sorted(INITIATIVES, key=lambda i: -i["score"])
now = ranked[:2]
next_ = ranked[2:4]
later = ranked[4:]


def table(items, lang: str = "en") -> str:
    key = "name" if lang == "en" else "name_es"
    okey = "owner" if lang == "en" else "owner_es"
    rows = "\n".join(
        f"| {i[key]} | {i['story']} | {i[okey]} | {i['reach']:,} | {i['impact']:,.0f} | "
        f"{i['confidence']:.2f} | {i['effort']} | **{i['score']:,.0f}** |" for i in items)
    if lang == "en":
        return ("| Initiative | Story | Owner | Reach/yr | Impact (USD/yr) | Conf. | Effort (wks) | Score (USD/wk) |\n"
                "|---|---|---|---:|---:|---:|---:|---:|\n" + rows)
    return ("| Iniciativa | Historia | Dueño | Alcance/año | Impacto (USD/año) | Conf. | Esfuerzo (sem) | Score (USD/sem) |\n"
            "|---|---|---|---:|---:|---:|---:|---:|\n" + rows)


def basis_list(items, lang: str = "en") -> str:
    if lang == "en":
        return "\n".join(f"- **{i['name']}** — basis: {i['basis']}. Risk: {i['risk']}." for i in items)
    return "\n".join(f"- **{i['name_es']}** — base: {i['basis_es']}. Riesgo: {i['risk_es']}." for i in items)


md7 = f"""# 07 — Prioritised Roadmap (RICE)

> 🌐 _Versión en español: [07-roadmap.es.md](07-roadmap.es.md)_

> Generated by `src/build_roadmap.py`. **Score = Impact × Confidence ÷ Effort** — risk-adjusted USD of
> annual margin per week of effort, so scores read directly in business terms (plain RICE would double-count
> reach right back into the score because Impact is already a total in USD). Confidence and Effort are
> explicit analyst assumptions; reach and impact derive from measured outputs.

## Ranked initiatives

{table(ranked)}

## Sequencing

- **Now (this quarter):** {", ".join(i['name'] for i in now)} — within Now, ship the **win-back program first**:
  it is the only initiative validated with an experiment, so it is the safest immediate win.
- **Next (next quarter):** {", ".join(i['name'] for i in next_)}.
- **Later (when capacity allows):** {", ".join(i['name'] for i in later)}.

## Evidence behind the estimates

{basis_list(ranked)}

## How these scores can move

RICE is a conversation tool: if operations commits to the Colombia fix, confidence rises and it jumps the
queue; if a discount A/B shows no volume loss, the discount-cap estimate firms up. Re-run `make all`
after new data to refresh every figure.
"""

md7_es = f"""# 07 — Roadmap priorizado (RICE)

> 🌐 _English version: [07-roadmap.md](07-roadmap.md)_

> Generado por `src/build_roadmap.py`. **Score = Impacto × Confianza ÷ Esfuerzo** — USD de margen anual
> ajustado por riesgo por semana de esfuerzo, para que los scores se lean directamente en términos de negocio
> (el RICE clásico volvería a multiplicar el alcance dentro del score porque el Impacto ya es un total en USD).
> Confianza y Esfuerzo son supuestos explícitos del analista; alcance e impacto derivan de outputs medidos.

## Iniciativas rankeadas

{table(ranked, 'es')}

## Secuenciación

- **Ahora (este trimestre):** {", ".join(i['name_es'] for i in now)} — dentro de Ahora, lanzar primero el
  **programa de win-back**: es la única iniciativa validada con un experimento, la victoria inmediata más segura.
- **Siguiente (próximo trimestre):** {", ".join(i['name_es'] for i in next_)}.
- **Más adelante (cuando haya capacidad):** {", ".join(i['name_es'] for i in later)}.

## Evidencia detrás de las estimaciones

{basis_list(ranked, 'es')}

## Cómo pueden moverse estos scores

RICE es una herramienta de conversación: si Operaciones se compromete con el arreglo de Colombia, la
confianza sube y salta la cola; si un A/B de descuentos muestra que no hay pérdida de volumen, la estimación
del límite de descuentos se consolida. Re-ejecutar `make all` con datos nuevos refresca cada cifra.
"""

md8 = f"""# 08 — User Stories and Acceptance Criteria

> 🌐 _Versión en español: [08-user-stories.es.md](08-user-stories.es.md)_

> Generated by `src/build_roadmap.py` from the same computed outputs as docs/07.
> Stories follow the analytics-to-delivery handoff pattern: data contract → trigger → acceptance test.

## US-1 — Win-back campaign to lapsed customers
*As a CRM manager, I want a quarterly win-back send to opted-in customers lapsed 120–540 days, so that
dormant revenue is recovered at low cost.*

- Story points: 5 · Linked initiative: win-back program / lifecycle nudges
- **Given** a customer's last order was 120–540 days ago **and** they are marketing opted-in
  **and** they received no win-back email in the last 90 days (cool-down),
  **when** the quarterly wave runs, **then** they receive exactly one win-back email and are tracked
  in the campaign table with a randomized control holdout.
- **Given** a customer purchased in the last 90 days, **when** the wave runs, **then** they are excluded.
- Metric guardrails: 60-day reactivation rate per arm, unsubscribe rate < 1%, send cost per reactivation
  (${AB['economics']['program_cost'] / max(AB['economics']['incremental_conversions'], 1):.2f} target at base case).

## US-2 — Discount depth caps in acquisition
*As a growth lead, I want first-order discount depth capped at the light tier for self-serve channels, so
that we stop buying retention-negative volume.*

- Story points: 8 · Linked initiative: discount cap
- **Given** a new customer at checkout on paid social/paid search,
  **when** cart value is below the qualification threshold, **then** the maximum offered discount is the
  light band (≤15%) and the offer shown is logged for audit.
- **Given** the cap is live, **when** the monthly readout runs, **then** conversion rate, AOV, and 90-day
  repeat rate by band are reported vs. the pre-cap baseline.

## US-3 — Colombia delivery SLA
*As an operations manager, I want a courier SLA dashboard for Colombia with a 3-day p90 target, so delays
stop destroying repeat rates.*

- Story points: 8 · Linked initiative: fix Colombia courier
- **Given** daily order data, **when** first-delivery delay exceeds 3 days for a Colombian order,
  **then** the order is flagged in the Ops queue and included in the weekly SLA report.
- **Given** the fix is live for 90 days, **when** the cohort readout runs, **then** Colombia 90-day repeat
  rate recovers toward the {col_pre['repeat_rate_90d']:.1%} pre-incident baseline.

## US-4 — Delay-aware send suppression
*As a CRM manager, I want promotional sends suppressed for customers with an open delayed delivery, so that
we don't ask for another order while the first one is late.*

- Story points: 3 · Linked initiative: delay-aware suppression
- **Given** a customer has an in-transit order past its promised date, **when** a promotional campaign
  executes, **then** the customer is suppressed until delivery (or resolution) plus 2 days.
- **Given** suppression is active, **when** the monthly report runs, **then** suppressed volume and the
  repeat-rate delta for suppressed vs. matched control are reported.

## US-5 — Churn-risk scoring batch + CRM routing
*As a lifecycle analyst, I want weekly churn scores for new customers so the first 90 days get the right
level of care.*

- Story points: 5 · Linked initiative: churn-score triage (feeds US-1 audience selection)
- **Given** the model artifact (test AUC {json.loads(Path('outputs/analysis/churn_model.json').read_text())['auc_test']:.2f}),
  **when** the weekly batch runs, **then** every customer with a first order in the last 30 days receives a
  score and a decile, written to the CRM with run timestamp and model version.
- **Given** scores are in the CRM, **when** a customer lands in the bottom decile, **then** they are queued
  for a service touch (not a discount) within 7 days.

## Definition of Done (all stories)

- Metric movement measured against a holdout or pre-period baseline, documented in `outputs/analysis/`.
- Pipeline artifacts regenerate via `make all`; no manual spreadsheet leaves the building.
- Privacy: processing limited to opted-in customers; suppression lists honoured before every send.
"""

md8_es = f"""# 08 — Historias de usuario y criterios de aceptación

> 🌐 _English version: [08-user-stories.md](08-user-stories.md)_

> Generado por `src/build_roadmap.py` a partir de los mismos outputs calculados que docs/07.
> Las historias siguen el patrón de traspaso analytics→entrega: contrato de datos → disparador → test de aceptación.

## US-1 — Campaña de win-back a clientes inactivos
*Como responsable de CRM, quiero un envío trimestral de win-back a clientes con opt-in inactivos hace 120–540 días,
para recuperar ingreso dormido a bajo costo.*

- Story points: 5 · Iniciativa vinculada: programa de win-back / nudges de ciclo de vida
- **Dado** un cliente cuya última compra fue hace 120–540 días **y** con opt-in de marketing
  **y** que no recibió email de win-back en los últimos 90 días (cool-down),
  **cuando** corre la ola trimestral, **entonces** recibe exactamente un email de win-back y queda registrado
  en la tabla de campaña con un holdout control aleatorizado.
- **Dado** un cliente que compró en los últimos 90 días, **cuando** corre la ola, **entonces** queda excluido.
- Guardrails de métricas: reactivación a 60 días por brazo, tasa de baja < 1%, costo por reactivación
  (objetivo ${AB['economics']['program_cost'] / max(AB['economics']['incremental_conversions'], 1):.2f} en el caso base).

## US-2 — Límites de profundidad de descuento en adquisición
*Como líder de growth, quiero limitar el descuento de primera compra al tramo light en canales self-serve,
para dejar de comprar volumen con retención negativa.*

- Story points: 8 · Iniciativa vinculada: límite de descuentos
- **Dado** un cliente nuevo en el checkout de paid social/paid search,
  **cuando** el valor del carrito está por debajo del umbral de calificación, **entonces** el descuento máximo
  ofrecido es la banda light (≤15%) y la oferta mostrada queda registrada para auditoría.
- **Dado** que el límite está activo, **cuando** corre el readout mensual, **entonces** se reportan tasa de
  conversión, AOV y recompra a 90 días por banda vs. la base pre-límite.

## US-3 — SLA de entregas en Colombia
*Como gerente de operaciones, quiero un tablero de SLA del courier para Colombia con objetivo p90 de 3 días,
para que las demoras dejen de destruir la recompra.*

- Story points: 8 · Iniciativa vinculada: arreglo del courier de Colombia
- **Dado** el dato diario de pedidos, **cuando** la demora de primera entrega supera 3 días en un pedido
  colombiano, **entonces** el pedido se marca en la cola de Operaciones y se incluye en el reporte semanal de SLA.
- **Dado** que el arreglo lleva 90 días activo, **cuando** corre el readout de cohortes, **entonces** la
  recompra a 90 días de Colombia se recupera hacia la base pre-incidente de {col_pre['repeat_rate_90d']:.1%}.

## US-4 — Supresión de envíos por demora
*Como responsable de CRM, quiero suprimir envíos promocionales a clientes con una entrega demorada abierta,
para no pedir otra compra mientras la primera llega tarde.*

- Story points: 3 · Iniciativa vinculada: supresión por demora
- **Dado** un cliente con un pedido en tránsito pasado de fecha prometida, **cuando** se ejecuta una campaña
  promocional, **entonces** el cliente queda suprimido hasta la entrega (o resolución) más 2 días.
- **Dado** que la supresión está activa, **cuando** corre el reporte mensual, **entonces** se reportan el
  volumen suprimido y el delta de recompra entre suprimidos y un control pareado.

## US-5 — Batch de score de churn + ruteo en CRM
*Como analista de ciclo de vida, quiero scores de churn semanales para clientes nuevos, para que los
primeros 90 días reciban el nivel de cuidado correcto.*

- Story points: 5 · Iniciativa vinculada: triaje por score de churn (alimenta la selección de audiencia de US-1)
- **Dado** el artefacto del modelo (AUC test {json.loads(Path('outputs/analysis/churn_model.json').read_text())['auc_test']:.2f}),
  **cuando** corre el batch semanal, **entonces** cada cliente con primera compra en los últimos 30 días recibe
  un score y un decil, escritos al CRM con timestamp de ejecución y versión del modelo.
- **Dado** que los scores están en el CRM, **cuando** un cliente cae en el decil inferior, **entonces** queda
  en cola para un toque de servicio (no un descuento) dentro de 7 días.

## Definition of Done (todas las historias)

- El movimiento de métricas se mide contra un holdout o base pre-período, documentado en `outputs/analysis/`.
- Los artefactos del pipeline se regeneran con `make all`; ningún spreadsheet manual sale del proceso.
- Privacidad: procesamiento limitado a clientes con opt-in; listas de supresión respetadas antes de cada envío.
"""

Path("docs/07-roadmap.md").write_text(md7)
Path("docs/07-roadmap.es.md").write_text(md7_es)
Path("docs/08-user-stories.md").write_text(md8)
Path("docs/08-user-stories.es.md").write_text(md8_es)
print("wrote docs/07-roadmap(.es).md and docs/08-user-stories(.es).md")
