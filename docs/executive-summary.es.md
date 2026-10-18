# Resumen ejecutivo — Diagnóstico de retención de Altiplano Goods

> 🌐 _English version: [executive-summary.md](executive-summary.md)_

**Elaborado a partir de:** dataset sintético a nivel de pedido, ene 2024 – dic 2025 (79 mil pedidos, 20 mil clientes).
Todas las cifras provienen del pipeline del repositorio y se reproducen con `make all`.

## El problema

La tasa de recompra a 90 días cayó de **35.3%** (S1 2024) a
**26.8%** (T3 2025) — **-8.5 pp** (-24% relativo).
Como los clientes recurrentes generan **83%** del ingreso, es un problema de
ingresos, no una métrica de vanidad: el decil superior concentra **53%** de las ventas.

## Qué lo está impulsando

1. **Cambio de mix hacia adquisición de baja recompra.** Paid social (recompra 22.7%) e
   influencer crecieron mientras referral/orgánico/email (recompra 44.0%–38.6%)
   se redujeron. Descomposición: **7.1 pp de la caída de 8.5 pp es mix**;
   1.3 pp es comportamiento intra-segmento.
2. **El descuento profundo envenena la retención.** Las primeras compras con descuento alto recompran
   **22.4%** vs **37.4%** a precio pleno, y su
   margen a 12 meses es **$126 vs $248**.
3. **Las fallas logísticas están concentradas.** Colombia: demora de primera entrega
   1.7 → 6.4 días,
   recompra 31.1% → 19.1%.
4. **Un modelo puede priorizar clientes.** Modelo logístico (AUC test 0.64); el decil superior
   recompra 1.5× la tasa base — los compradores que merecen trato preferente
   se identifican desde el día 0.
5. **La maniobra de win-back funciona.** Sobre 5,057 clientes inactivos con opt-in, el email elevó
   la reactivación a 60 días de 5.1% → 7.5%
   (p=0.0003); economía: **ROI 19×, payback dentro de la primera ola**.

## Recomendaciones (priorizadas en docs/07-roadmap.es.md)

1. **Lanzar el programa trimestral de win-back** (beneficio neto caso base ≈ $19k USD/año con el pool actual; escala con el pool).
2. **Arreglar el courier de Colombia y pausar la escala de paid social allí** hasta que la demora sea < 3 días.
3. **Limitar los descuentos de adquisición a bandas light/medium**; reemplazar profundidad por incentivos de referral y email.
4. **Proteger a los champions (21% de los clientes, 71% del ingreso)** con
   niveles de servicio VIP, no con descuentos.
5. **Desplegar el triaje por score de churn** para derivar los primeros pedidos en riesgo a soporte antes de que se pierdan en silencio.

## Advertencias

Datos sintéticos; el entregable es el pipeline, el método y la lógica de decisión. Los efectos son
direccionales, estimados con intervalos de confianza donde importa, y cada número se regenera con `make all`.
