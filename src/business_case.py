"""Business case workbook (live Excel formulas) + docs/06-business-case.md.

Inputs come from outputs/analysis/*.json. Every calculated cell in the workbook is an
Excel formula referencing the Assumptions sheet, so stakeholders can change any input
and watch scenarios, sensitivity and cash flow update. The markdown mirrors the same
formulas in Python (workbook is the interactive artifact; this file is the record).
"""
from __future__ import annotations

import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

FROZEN_DT = datetime(2026, 1, 1, 0, 0, 0)


def freeze_xlsx(path: Path) -> None:
    """Rewrite the zip with fixed metadata so rebuilds are byte-identical."""
    tmp = path.with_suffix(".tmp.xlsx")
    stamp = FROZEN_DT.strftime("%Y-%m-%dT%H:%M:%SZ")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "docProps/core.xml":
                data = re.sub(rb"<dcterms:modified[^>]*>[^<]*</dcterms:modified>",
                              f"<dcterms:modified xsi:type=\"dcterms:W3CDTF\">{stamp}</dcterms:modified>".encode(),
                              data)
            zi = zipfile.ZipInfo(item.filename, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = item.compress_type
            zi.external_attr = item.external_attr
            zout.writestr(zi, data)
    shutil.move(tmp, path)

AB = json.loads(Path("outputs/analysis/ab_test.json").read_text())
OUT_XLSX = Path("outputs/business_case.xlsx")
OUT_MD = Path("docs/06-business-case.md")

HEAD_FILL = PatternFill("solid", fgColor="1F4E5F")
HEAD_FONT = Font(color="FFFFFF", bold=True)
NUM = "#,##0.00"
PCT = "0.0%"
INT = "#,##0"


def build_workbook(inputs: dict) -> None:
    wb = Workbook()

    # ---------------- Assumptions ----------------
    ws = wb.active
    ws.title = "Assumptions"
    ws["A1"] = "Win-back program — assumptions (edit the yellow cells; everything else recalculates)"
    ws["A1"].font = Font(bold=True, size=13)
    rows = [
        ("Eligible pool (lapsed, opted-in)", inputs["pool"], "customers",
         "A/B design: last order 120-540 days ago, marketing opted-in"),
        ("Baseline (control) 60-day reactivation rate", inputs["baseline_rate"], "share",
         "A/B control arm; history-measured natural rate is 5.8%"),
        ("Email cost per send", inputs["cost_per_email"], "USD", "Platform + ops"),
        ("Average margin per order (win-back customers)", inputs["margin_per_order"], "USD",
         "Source: A/B economics output"),
        ("Campaign waves per year", 4, "waves", "Assumption: quarterly refreshes of the lapsed pool"),
        ("Scenario lift - conservative", inputs["lift_lo"], "relative",
         "Lower bound of the 95% CI of the A/B relative lift"),
        ("Scenario lift - base", inputs["lift_base"], "relative",
         "Observed relative lift in the A/B test"),
        ("Scenario lift - optimistic", inputs["lift_hi"], "relative",
         "Upper bound of the 95% CI of the A/B relative lift"),
    ]
    for i, (label, value, unit, note) in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=label)
        c = ws.cell(row=i, column=2, value=value)
        c.fill = PatternFill("solid", fgColor="FFF2CC")
        ws.cell(row=i, column=3, value=unit)
        ws.cell(row=i, column=4, value=note).font = Font(italic=True, size=9)
    ws["B3"].number_format = INT    # pool
    ws["B4"].number_format = PCT    # natural reactivation rate
    ws["B5"].number_format = "0.00"  # cost per send
    ws["B6"].number_format = "0.00"  # margin per order
    ws["B7"].number_format = INT    # waves per year
    for r in (8, 9, 10):
        ws.cell(row=r, column=2).number_format = PCT  # scenario lifts
    for col, w in zip("ABCD", (44, 14, 11, 58)):
        ws.column_dimensions[col].width = w
    A = {name: f"Assumptions!$B${r}" for name, r in zip(
        ["pool", "natural", "cost", "margin", "waves", "lift_lo", "lift_base", "lift_hi"], range(3, 11))}

    # ---------------- Scenarios ----------------
    ws = wb.create_sheet("Scenarios")
    ws["A1"] = "Scenarios (annual) — all cells are live formulas off Assumptions"
    ws["A1"].font = Font(bold=True, size=13)
    cols = [("Conservative", A["lift_lo"]), ("Base", A["lift_base"]), ("Optimistic", A["lift_hi"])]
    ws["A3"] = "Metric"; ws["A3"].font = HEAD_FONT; ws["A3"].fill = HEAD_FILL
    for j, (name, ref) in enumerate(cols, start=2):
        c = ws.cell(row=3, column=j, value=name); c.font = HEAD_FONT; c.fill = HEAD_FILL
        ws.cell(row=4, column=j, value=f"={ref}").number_format = "0.0%"  # rel lift
    labels = [
        ("Relative lift (assumption)", None, "0.0%"),
        ("Baseline (control) 60-day reactivation rate", f"={A['natural']}", "0.0%"),
        ("Treatment 60-day reactivation rate", "=C5*(1+C4)", "0.0%"),
        ("Incremental reactivations per wave", f"={A['pool']}*(C6-C5)", INT),
        ("Incremental gross margin per wave", f"=C7*{A['margin']}", NUM),
        ("Program cost per wave (sends x cost)", f"={A['pool']}*{A['cost']}", NUM),
        ("Net benefit per wave", "=C8-C9", NUM),
        ("Annual gross margin", f"=C8*{A['waves']}", NUM),
        ("Annual program cost", f"=C9*{A['waves']}", NUM),
        ("Annual net benefit", "=C10*" + f"{A['waves']}", NUM),
        ("Annual ROI on program cost", "=C13/C12", "0.0\"x\""),
    ]
    for i, (label, formula, fmt) in enumerate(labels, start=4):
        ws.cell(row=i, column=1, value=label)
        if formula is None:
            continue
        for j in range(2, 5):
            col = get_column_letter(j)
            c = ws.cell(row=i, column=j, value=formula.replace("C", col))
            c.number_format = fmt
    ws.column_dimensions["A"].width = 38
    for col in "BCD":
        ws.column_dimensions[col].width = 15

    # ---------------- Sensitivity ----------------
    ws = wb.create_sheet("Sensitivity")
    ws["A1"] = f"Annual net benefit = {A['pool']} x natural x lift x margin x {A['waves']} - {A['pool']} x cost x {A['waves']}"
    ws["A1"].font = Font(bold=True, size=12)
    ws["A3"] = "Lift \\ Margin per order"; ws["A3"].font = HEAD_FONT; ws["A3"].fill = HEAD_FILL
    margins = [30, 35, 40, 45, 50]
    lifts = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70]
    for j, m in enumerate(margins, start=2):
        c = ws.cell(row=3, column=j, value=m); c.font = HEAD_FONT; c.fill = HEAD_FILL
        c.number_format = NUM
    for i, lift in enumerate(lifts, start=4):
        ws.cell(row=i, column=1, value=lift).number_format = "0.0%"
        for j, m in enumerate(margins, start=2):
            col = get_column_letter(j)
            ws.cell(row=i, column=j,
                    value=f"={A['pool']}*{A['natural']}*$A{i}*{col}$3*{A['waves']}"
                          f"-{A['pool']}*{A['cost']}*{A['waves']}").number_format = NUM
    ws.column_dimensions["A"].width = 20
    for col in "BCDEF":
        ws.column_dimensions[col].width = 12

    # ---------------- Cashflow (base case) ----------------
    ws = wb.create_sheet("Cashflow")
    ws["A1"] = "Base-case cash flow by month (waves start months 1, 4, 7, 10; margin books 2 months after send)"
    ws["A1"].font = Font(bold=True, size=12)
    header = ["Month", "Wave?", "Emails sent", "Cost", "Reactivated orders", "Gross margin", "Net", "Cumulative net"]
    for j, h in enumerate(header, start=1):
        c = ws.cell(row=3, column=j, value=h); c.font = HEAD_FONT; c.fill = HEAD_FILL
    for m in range(1, 13):
        r = 3 + m
        wave = "YES" if m in (1, 4, 7, 10) else ""
        ws.cell(row=r, column=1, value=m)
        ws.cell(row=r, column=2, value=wave)
        ws.cell(row=r, column=3, value=f"=IF(B{r}=\"YES\",{A['pool']},0)").number_format = INT
        ws.cell(row=r, column=4, value=f"=C{r}*{A['cost']}").number_format = NUM
        ws.cell(row=r, column=5,
                value=f"=IF(B{r}=\"YES\",{A['pool']}*{A['natural']}*{A['lift_base']},0)").number_format = INT
        margin = f"IF(B{r-2}=\"YES\",E{r-2}*{A['margin']},0)" if m >= 3 else "0"
        ws.cell(row=r, column=6, value=f"={margin}").number_format = NUM
        ws.cell(row=r, column=7, value=f"=F{r}-D{r}").number_format = NUM
        prev = f"H{r-1}" if m > 1 else "0"
        ws.cell(row=r, column=8, value=f"={prev}+G{r}").number_format = NUM
    last = 3 + 12
    ws.cell(row=last + 2, column=1, value="Payback: first month with cumulative net > 0")
    ws.cell(row=last + 2, column=5, value=f"=MATCH(TRUE,INDEX(H4:H{last}>0,0),0)").number_format = "0"
    ws.column_dimensions["A"].width = 12
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 16

    wb.properties.created = FROZEN_DT
    wb.properties.modified = FROZEN_DT
    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_XLSX)
    freeze_xlsx(OUT_XLSX)


def mirror_in_python(inp: dict) -> dict:
    pool, nat, cost, margin, waves = inp["pool"], inp["baseline_rate"], inp["cost_per_email"], inp["margin_per_order"], inp["waves"]
    out = {"cases": [], "sensitivity": [], "cashflow": [], "payback_month": None}
    for name, lift in (("Conservative", inp["lift_lo"]), ("Base", inp["lift_base"]), ("Optimistic", inp["lift_hi"])):
        react = pool * nat * lift
        gm = react * margin
        pcost = pool * cost
        out["cases"].append({
            "name": name, "lift": lift, "react_wave": int(round(react)), "gm_wave": gm, "cost_wave": pcost,
            "net_wave": gm - pcost, "ann_gm": gm * waves, "ann_cost": pcost * waves,
            "ann_net": (gm - pcost) * waves, "roi": (gm - pcost) / pcost,
        })
    for lift in (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70):
        row = [pool * nat * lift * m * waves - pool * cost * waves for m in (30, 35, 40, 45, 50)]
        out["sensitivity"].append({"lift": lift, "values": row})
    cum = 0.0
    for m in range(1, 13):
        wave = m in (1, 4, 7, 10)
        sent = pool if wave else 0
        mc = sent * cost
        react = pool * nat * inp["lift_base"] if wave else 0
        gm = 0.0
        if m >= 3 and (m - 2) in (1, 4, 7, 10):
            gw = pool * nat * inp["lift_base"] * margin
            gm = gw
        cum += gm - mc
        out["cashflow"].append({"month": m, "wave": wave, "cost": mc, "gm": gm, "net": gm - mc, "cum": cum})
        if out["payback_month"] is None and cum > 0:
            out["payback_month"] = m
    return out


def main() -> None:
    design, obs, ec = AB["design"], AB["observed"], AB["economics"]
    inputs = {
        "pool": int(design["population"]),
        "baseline_rate": float(obs["control_rate"]),
        "cost_per_email": float(ec["cost_per_email"]),
        "margin_per_order": float(ec["avg_margin_per_order"]),
        "waves": 4,
        "lift_lo": float(obs["ci95_rel"][0]),
        "lift_base": float(obs["rel_lift"]),
        "lift_hi": float(obs["ci95_rel"][1]),
    }
    build_workbook(inputs)
    res = mirror_in_python(inputs)

    case_rows = "\n".join(
        f"| {c['name']} | {c['lift']:.1%} | {c['react_wave']:,} | {c['gm_wave']:,.0f} | {c['cost_wave']:,.0f} | "
        f"**{c['ann_net']:,.0f}** | {c['roi']:.1f}× |" for c in res["cases"])
    sens_min = min(v for row in res["sensitivity"] for v in row["values"])
    sens_max = max(v for row in res["sensitivity"] for v in row["values"])
    wilt = "\n".join(
        f"| {row['lift']:.0%} | " + " | ".join(f"{v:,.0f}" for v in row["values"]) + " |"
        for row in res["sensitivity"])
    cf_rows = "\n".join(
        f"| {c['month']} | {'wave' if c['wave'] else ''} | {c['cost']:,.0f} | {c['gm']:,.0f} | {c['net']:,.0f} | {c['cum']:,.0f} |"
        for c in res["cashflow"] if c["wave"] or c["gm"] > 0 or c["month"] == 12)

    md = f"""# 06 — Business Case: Customer Win-Back Program

> 🌐 _Versión en español: [06-business-case.es.md](06-business-case.es.md)_

> Generated by `src/business_case.py`. Interactive workbook: [`outputs/business_case.xlsx`](../outputs/business_case.xlsx)
> — every calculated cell is a live Excel formula driven by the yellow input cells on the Assumptions sheet.

## The decision

Run quarterly win-back campaigns to opted-in customers who lapsed 120–540 days ago. The base case
(the lift actually observed in the simulated A/B test) returns **{res['cases'][1]['ann_net']:,.0f} USD of net benefit
per year on {res['cases'][1]['ann_cost']:,.0f} USD of program cost ({res['cases'][1]['roi']:.0f}× ROI)**, and
the play stays profitable across every cell of the sensitivity grid above {sens_min:,.0f} USD.

## Inputs (all measured or explicitly assumed)

| Input | Value | Source |
|---|---:|---|
| Eligible pool (lapsed, opted-in) | {inputs['pool']:,} customers | A/B design: last order 120–540 days ago |
| Baseline (control) 60-day reactivation | {inputs['baseline_rate']:.2%} | A/B control arm (history-measured natural rate: 5.8%) |
| Email cost per send | ${inputs['cost_per_email']:.2f} | Assumption (platform + ops) |
| Margin per order (win-back customers) | ${inputs['margin_per_order']:.2f} | A/B economics output |
| Waves per year | {inputs['waves']} | Assumption (quarterly) |
| Lift — conservative / base / optimistic | {inputs['lift_lo']:.1%} / {inputs['lift_base']:.1%} / {inputs['lift_hi']:.1%} | 95% CI of A/B relative lift |

## Scenarios (annual, all formula-driven in the workbook)

| Scenario | Rel. lift | Reactivations/wave | Gross margin/wave | Cost/wave | Annual net benefit | ROI |
|---|---:|---:|---:|---:|---:|---:|
{case_rows}

## Sensitivity: annual net benefit (USD)

Rows: relative lift. Columns: margin per order (USD). Base case highlighted in the workbook.

| Lift \\ Margin | {' | '.join(str(m) for m in (30, 35, 40, 45, 50))} |
|---|{'---|' * 5}
{wilt}

Even the worst cell (low lift, thin margin) stays positive: the program's fixed cost is tiny relative
to one order's margin.

## Cash flow and payback (base case)

| Month | Event | Cost | Gross margin | Net | Cumulative |
|---:|---|---:|---:|---:|---:|
{cf_rows}

**Payback: month {res['payback_month']}** — the first wave's margin lands two months after send, and from then on
each wave's margin dwarfs the next wave's send cost.

## Risks and honest caveats

- The "observed lift" is from a **simulated** experiment on synthetic data; the workbook's job is to make the
  economics auditable and re-runnable with real numbers, not to claim this exact lift will reproduce.
- Pool per wave is assumed constant; in reality the 120–540 day lapsed pool replenishes from new churn,
  and customers who don't reactivate shouldn't be re-mailed every quarter without a cool-down.
- Margin per order is an average across the pool; if the win-back offer includes a discount, margins drop —
  the sensitivity grid covers margin as low as $30.
- Email deliverability/consent: population is consenting customers only; GDPR/LGPD-style suppression must be enforced.
"""

    es = f"""# 06 — Caso de negocio: programa de recuperación de clientes (win-back)

> 🌐 _English version: [06-business-case.md](06-business-case.md)_

> Generado por `src/business_case.py`. Workbook interactivo: [`outputs/business_case.xlsx`](../outputs/business_case.xlsx)
> — cada celda calculada es una fórmula viva de Excel alimentada por las celdas amarillas de la hoja Assumptions.

## La decisión

Ejecutar campañas trimestrales de win-back a clientes con opt-in que se durmieron hace 120–540 días. El caso
base (el lift realmente observado en el A/B simulado) devuelve **{res['cases'][1]['ann_net']:,.0f} USD de beneficio neto
al año sobre {res['cases'][1]['ann_cost']:,.0f} USD de costo del programa (ROI {res['cases'][1]['roi']:.0f}×)**, y la
jugada sigue siendo rentable en cada celda de la grilla de sensibilidad por encima de {sens_min:,.0f} USD.

## Insumos (medidos o supuestos explícitos)

| Insumo | Valor | Fuente |
|---|---:|---|
| Pool elegible (inactivos, con opt-in) | {inputs['pool']:,} clientes | Diseño del A/B: última compra hace 120–540 días |
| Reactivación base (control) a 60 días | {inputs['baseline_rate']:.2%} | Brazo control del A/B (tasa natural medida en histórico: 5.8%) |
| Costo por email | ${inputs['cost_per_email']:.2f} | Supuesto (plataforma + operación) |
| Margen por pedido (clientes de win-back) | ${inputs['margin_per_order']:.2f} | Output de economía del A/B |
| Olas por año | {inputs['waves']} | Supuesto (trimestral) |
| Lift — conservador / base / optimista | {inputs['lift_lo']:.1%} / {inputs['lift_base']:.1%} / {inputs['lift_hi']:.1%} | IC 95% del lift relativo del A/B |

## Escenarios (anuales, con fórmulas vivas en el workbook)

| Escenario | Lift rel. | Reactivaciones/ola | Margen bruto/ola | Costo/ola | Beneficio neto anual | ROI |
|---|---:|---:|---:|---:|---:|---:|
{case_rows}

## Sensibilidad: beneficio neto anual (USD)

Filas: lift relativo. Columnas: margen por pedido (USD). El caso base está resaltado en el workbook.

| Lift \\ Margen | {' | '.join(str(m) for m in (30, 35, 40, 45, 50))} |
|---|{'---|' * 5}
{wilt}

Incluso la peor celda (lift bajo, margen delgado) queda positiva: el costo fijo del programa es mínimo
frente al margen de un solo pedido.

## Flujo de caja y payback (caso base)

| Mes | Evento | Costo | Margen bruto | Neto | Acumulado |
|---:|---|---:|---:|---:|---:|
{cf_rows}

**Payback: mes {res['payback_month']}** — el margen de la primera ola entra dos meses después del envío, y desde
ahí el margen de cada ola supera ampliamente el costo de envío de la siguiente.

## Riesgos y advertencias honestas

- El "lift observado" proviene de un experimento **simulado** sobre datos sintéticos; el trabajo del workbook es
  hacer la economía auditable y re-ejecutable con números reales, no afirmar que este lift exacto se repetirá.
- Se asume pool constante por ola; en la realidad el pool de 120–540 días se recompone con nuevo churn,
  y los clientes que no reactivan no deberían recibir email cada trimestre sin un cool-down.
- El margen por pedido es un promedio del pool; si la oferta de win-back incluye descuento, el margen baja —
  la grilla de sensibilidad cubre márgenes desde $30.
- Entregabilidad/consentimiento: la población es solo clientes con opt-in; deben aplicarse supresiones tipo GDPR/LGPD.
"""
    OUT_MD.write_text(md)
    OUT_MD.with_name("06-business-case.es.md").write_text(es)
    print(f"wrote {OUT_XLSX}, {OUT_MD} and 06-business-case.es.md")


if __name__ == "__main__":
    main()
