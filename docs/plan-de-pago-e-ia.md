# Plan de pago e IA: asistente del reglamento y entrenador de swing

> **Estado: aparcado** (26 oct 2026). No es para ahora: para cobrar hay que darse de alta como autónomo y queda mucho trabajo por delante. Este documento recoge lo decidido y lo estimado para retomarlo sin rehacer nada.
>
> Issues: épica [RyderCupAM#676](https://github.com/agustinEDev/RyderCupAM/issues/676) (asistente, con el modelo de rentabilidad en un comentario) y sus hijas #677–#680 y [RyderCupWeb#977](https://github.com/agustinEDev/RyderCupWeb/issues/977); entrenador de swing en [RyderCupWeb#937](https://github.com/agustinEDev/RyderCupWeb/issues/937).
>
> Sustituye al plan de diciembre de 2025: [RAG_IMPLEMENTATION.md](RAG_IMPLEMENTATION.md), [ADR-022](architecture/decisions/ADR-022-rag-golf-rules-assistant.md) y la v2.2.0 del [ROADMAP](../ROADMAP.md).

Las cifras son estimaciones del 26 oct 2026 con precios consultados ese día, no presupuestos. La cuota de autónomo, la gestoría y la comisión de Stripe están por confirmar.

## 1. Asistente del reglamento

**Qué es.** Una hoja «¿Qué dice el reglamento?» en la anotación (torneo y partida rápida) y en la ficha de la competición. Contesta en español o inglés, **siempre cita la fuente** (una regla de la app, una norma local del organizador o el número de una Regla de Golf con enlace a la RFEG) y **se niega** si nuestros textos no respaldan la respuesta. Es orientativo: la reglamentación oficial es la de la RFEG y el comité u organizador tiene la última palabra.

**Con qué contesta (solo textos nuestros).**
1. El **reglamento de la app**, escrito a partir del dominio: modalidades, concesión, retirada en el fourball, raya = doble bogey neto, partidos sin terminar o no jugados, no presentado y retirado en stroke play, mejor tarjeta o acumulado, apertura y cierre automáticos. Hoy no está escrito: vive en el código y en las decisiones de producto.
2. Una **guía de las Reglas de Golf explicada en sencillo, escrita por nosotros**: por situaciones, con ejemplos, el número de la regla y un enlace a la regla oficial en la RFEG.
3. Las **normas locales** que pegue cada organizador.

**Por qué no el texto oficial.** Las Reglas de Golf (edición 2023 y el libro en español de la RFEG) son © R&A Rules Limited y USGA, y los términos de randa.org solo permiten uso personal y no comercial. Meter el texto oficial en una base de datos y citarlo en un producto de pago exige permiso por escrito. Los derechos de autor protegen la redacción, no las ideas, así que **lo explicamos con nuestras palabras, con nuestra estructura (no regla por regla), citando el número y enlazando a la RFEG**. Sin logos de la R&A ni de la RFEG y sin presentarlo como oficial. Antes de meterlo en un plan de pago, una revisión legal ligera del aviso y de unas cuantas explicaciones. Pedir el texto literal a la R&A a través de la RFEG queda como opcional (#680).

**Arquitectura** (ver la épica para el detalle):
- Vectores en el **Postgres de Render que ya tenemos** con pgvector (~10–25 MB).
- Embeddings con Voyage `voyage-3.5-lite`.
- Respuesta con Claude: `claude-sonnet-5-5` en el plan de pago y `claude-haiku-5-5` en el gratuito y para reformular la pregunta. Caché de prompts para las instrucciones y las reglas básicas.
- Un módulo `ai` con puertos y adaptadores, `POST /api/v1/ai/rules/query`, cupos en Postgres (no hay Redis), registros 90 días sin datos personales, y un juego de 80–120 preguntas reales para evaluarlo antes de cada release.

**Fases:**

| Fase | Issue | Esfuerzo |
|---|---|---|
| 0. Escribir el reglamento de la app y la guía de reglas (ES/EN), publicados como página | #677 | S–M, 2–3 semanas (sirve sin IA) |
| 1. Backend: módulo `ai`, pgvector, ingesta, consulta, cupos, evaluación | #678 | M, 2–3 semanas |
| 2. Front: la hoja en la anotación, la competición y la partida rápida | RyderCupWeb#977 | S–M, 1–2 semanas |
| 3. Normas locales del organizador | #679 | M, 2 semanas |
| Opcional: permiso para el texto oficial | #680 | — |

**Qué ha quedado viejo del plan de diciembre:** OpenAI, Pinecone, Redis y LangChain no están instalados ni hacen falta; `temperature` ya no se acepta en los modelos actuales; el corpus oficial está bloqueado por la licencia; y no solo en competiciones en juego, también en partida rápida. Sigue valiendo: RAG y no fine-tuning, el módulo con puertos y adaptadores, preguntas frecuentes, cupos por niveles y citas.

## 2. Entrenador de swing

Inspirado en GolfFix: grabar o importar un swing, esqueleto, fases, tempo y fallos típicos, y después consejos y ejercicios. El análisis corre **en el móvil** con MediaPipe (gratis, sin carga en Render); los vídeos **no se suben** (solo métricas y fotogramas clave). Fases y riesgos en [RyderCupWeb#937](https://github.com/agustinEDev/RyderCupWeb/issues/937); precios corregidos en su comentario del 26 oct.

Referencias de precio: GolfFix 17,99 €/mes o 99,99 €/año (App Store España), Sportsbox ~15,99 $/mes, V1 Golf 9,99 $/mes. Hudl Technique ya no existe.

## 3. Costes

**Construcción.** Con nuestro flujo de agentes: el tiempo de Agustín y menos de 30 $ de API en pruebas (asistente: 5–7 semanas; swing fases 0–1: 6–8 semanas). Subcontratado (50–80 €/h): asistente 11–26 k€; swing fases 0–1 12–27 k€, fase 2 12–32 k€ más contenido.

**Funcionamiento al mes** (3–4 preguntas por usuario; el 20 % hace 8 análisis de swing):

| Usuarios | Asistente con Sonnet | Asistente con Haiku | Swing con Sonnet |
|---|---|---|---|
| 30 | ~2 $ | ~0,1 $ | ~0,5 $ |
| 500 | ~24 $ | ~1,2 $ | ~8 $ |
| 2.200 | ~106 $ | ~5 $ | ~35 $ |

**Costes fijos técnicos al mes:** hoy ~16 € (Render). Con 2.200 jugadores, ~135 €: Render ~60 €, un plan de pago de Mailgun ~35 € (hoy se comparte el cupo gratis de 100 correos al día con el Kind), Sentry ~25 €, dominio y otros ~5 €, IA del plan gratuito ~10 €.

## 4. Precio y rentabilidad (decidido el 26 oct 2026)

- **Gratis:** asistente con Haiku (~10 preguntas al mes), visor de swing y 3 análisis al mes.
- **De pago: 4,99 €/mes o 39,99 €/año**, el asistente y el entrenador juntos.
- **Tope de IA:** Sonnet hasta ~40 preguntas al mes y después Haiku. Así un suscriptor cuesta como mucho ~1 €/mes de IA.
- Al ser una PWA no hay comisión de las tiendas de apps, solo la de Stripe.

**Lo que queda por suscriptor al mes**, después del 21 % de IVA, Stripe (~1,5 % + 0,25 € por cobro) y el uso medio de IA: mensual ~3,50 €, anual ~2,40 €; mitad y mitad, **~2,95 €**.

**Para cobrar hay que darse de alta como autónomo:** tarifa plana ~80 €/mes el primer año, después ~230 € o más, y una gestoría (~50 €/mes). Al vender a particulares de otros países de la UE, el IVA se declara por la ventanilla única (OSS).

| Usuarios | Fijos con autónomo, 1.er año | Suscriptores para no perder | Fijos con autónomo, después | Suscriptores |
|---|---|---|---|---|
| 30 | ~150 € | 51 (más que usuarios) | ~300 € | 102 |
| 500 | ~180 € | 61 (12 %) | ~330 € | 112 (22 %) |
| 2.200 | ~265 € | **90 (4 %)** | ~415 € | **141 (6,4 %)** |

**Conclusión.** La IA y la infraestructura son baratas; lo que pesa es poder facturar. Solo con suscripciones de jugadores se cubren costes hacia los 2.200 usuarios, y en el límite alto de lo habitual (suele pagar entre el 2 y el 5 %). **Siguiente paso a estudiar antes de cobrar:** cobrar también al organizador o al club (por competición grande o con un plan de club), que equivale a decenas de suscripciones de jugador.

## 5. Antes de retomarlo

1. Darse de alta como autónomo y hablar con una gestoría (cuota, IVA, OSS).
2. Estudiar el plan de organizador o de club.
3. Fase 0 del asistente (#677): sirve aunque no haya IA.
4. Spike de una semana del entrenador de swing (fase 0 + esqueleto con MediaPipe en el iPhone).
