# 07 — Roadmap priorizado (RICE)

> 🌐 _English version: [07-roadmap.md](07-roadmap.md)_

> Generado por `src/build_roadmap.py`. **Score = Impacto × Confianza ÷ Esfuerzo** — USD de margen anual
> ajustado por riesgo por semana de esfuerzo, para que los scores se lean directamente en términos de negocio
> (el RICE clásico volvería a multiplicar el alcance dentro del score porque el Impacto ya es un total en USD).
> Confianza y Esfuerzo son supuestos explícitos del analista; alcance e impacto derivan de outputs medidos.

## Iniciativas rankeadas

| Iniciativa | Historia | Dueño | Alcance/año | Impacto (USD/año) | Conf. | Esfuerzo (sem) | Score (USD/sem) |
|---|---|---|---:|---:|---:|---:|---:|
| Limitar descuentos de primera compra (sin tramo 'heavy') | US-2 | Growth / Precios | 5,620 | 125,315 | 0.30 | 4 | **9,399** |
| Programa de win-back (olas trimestrales) | US-1 | CRM / Ciclo de vida | 20,228 | 19,287 | 0.80 | 3 | **5,143** |
| Supresión de envíos por demora de entrega | US-4 | CRM / Integración con Ops | 3,100 | 8,666 | 0.45 | 2 | **1,950** |
| Mover presupuesto de paid social a referral / email | US-5 | Growth | 2,698 | 39,272 | 0.35 | 8 | **1,718** |
| Arreglar demoras del courier en Colombia | US-3 | Operaciones | 1,764 | 8,568 | 0.55 | 6 | **785** |
| Nudges de ciclo de vida por RFM (needs_attention) | US-1 | CRM / Ciclo de vida | 2,061 | 1,034 | 0.35 | 3 | **121** |

## Secuenciación

- **Ahora (este trimestre):** Limitar descuentos de primera compra (sin tramo 'heavy'), Programa de win-back (olas trimestrales) — dentro de Ahora, lanzar primero el
  **programa de win-back**: es la única iniciativa validada con un experimento, la victoria inmediata más segura.
- **Siguiente (próximo trimestre):** Supresión de envíos por demora de entrega, Mover presupuesto de paid social a referral / email.
- **Más adelante (cuando haya capacidad):** Arreglar demoras del courier en Colombia, Nudges de ciclo de vida por RFM (needs_attention).

## Evidencia detrás de las estimaciones

- **Limitar descuentos de primera compra (sin tramo 'heavy')** — base: Brecha de margen a 12 meses banda light vs heavy: $238 vs $126; se asume que 20% de los reclutas heavy migra a light. Riesgo: La pérdida de volumen al eliminar descuentos profundos NO está modelada — estimación direccional.
- **Programa de win-back (olas trimestrales)** — base: Validado con A/B: lift relativo 49%, p=0.0003. Riesgo: Se asume pool constante por trimestre; hacen falta reglas de cool-down para no sobremailar.
- **Supresión de envíos por demora de entrega** — base: Clientes con demoras de 6+ días recompran 6.9% por debajo de la base de 1-3 días (775 clientes/año). Riesgo: La supresión cuesta algo de ingreso de email de corto plazo; la apuesta es la retención.
- **Mover presupuesto de paid social a referral / email** — base: Margen a 12 meses por cliente: referral $256 vs paid social $158; se asume 15% de migración de volumen. Riesgo: La capacidad de cada canal no es infinita; las diferencias de CAC no están modeladas aquí.
- **Arreglar demoras del courier en Colombia** — base: La recompra en Colombia cayó 31.1% -> 19.1% mientras la demora llegó a 6.4 días. Riesgo: Vínculo observacional; factores estacionales/postales podrían compartir la culpa.
- **Nudges de ciclo de vida por RFM (needs_attention)** — base: 2,061 clientes, 3.5 pedidos promedio, 477 USD de gasto; se asume la mitad del lift de win-back. Riesgo: El segmento se solapa con el pool de win-back — contar una sola vez para evitar doble conteo.

## Cómo pueden moverse estos scores

RICE es una herramienta de conversación: si Operaciones se compromete con el arreglo de Colombia, la
confianza sube y salta la cola; si un A/B de descuentos muestra que no hay pérdida de volumen, la estimación
del límite de descuentos se consolida. Re-ejecutar `make all` con datos nuevos refresca cada cifra.
