# 08 — Historias de usuario y criterios de aceptación

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
  (objetivo $2.01 en el caso base).

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
  recompra a 90 días de Colombia se recupera hacia la base pre-incidente de 31.1%.

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
- **Dado** el artefacto del modelo (AUC test 0.64),
  **cuando** corre el batch semanal, **entonces** cada cliente con primera compra en los últimos 30 días recibe
  un score y un decil, escritos al CRM con timestamp de ejecución y versión del modelo.
- **Dado** que los scores están en el CRM, **cuando** un cliente cae en el decil inferior, **entonces** queda
  en cola para un toque de servicio (no un descuento) dentro de 7 días.

## Definition of Done (todas las historias)

- El movimiento de métricas se mide contra un holdout o base pre-período, documentado en `outputs/analysis/`.
- Los artefactos del pipeline se regeneran con `make all`; ningún spreadsheet manual sale del proceso.
- Privacidad: procesamiento limitado a clientes con opt-in; listas de supresión respetadas antes de cada envío.
