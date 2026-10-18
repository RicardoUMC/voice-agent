# ODD plan: voice-agent
Status: planning; source implementation is intentionally not authorized yet.
Scope: external persistent voice conversation daemon integrated with Pi through RPC.

## Specs

S1. User objective (verbatim):
> Objetivo: diseñar e implementar un daemon de conversación por voz que funcione independientemente de la interfaz de Pi. Debe conectar micrófono/STT → Pi mediante RPC → TTS → altavoces, seguir funcionando aunque se cierre la TUI y permitir cambiar proveedores o modelos sin rehacer la arquitectura.

S2. Initial architectural decisions (verbatim):
> - Usar un proceso externo persistente, no una extensión acoplada a Pi.
> - Usar Pi RPC como primer backend conversacional.
> - Usar KittenTTS como primer proveedor TTS.
> - Encapsular STT, TTS, audio y conversación detrás de adaptadores.
> - Empezar con una sesión de voz dedicada para evitar escrituras concurrentes sobre una misma sesión.
> - Diseñar desde el inicio para múltiples sesiones.
> - No usar MCP como dependencia central.
> - Priorizar configuración, seguridad local, cancelación, interrupciones y recuperación ante fallos.

S3. Planning gate (verbatim):
> No implementes hasta cerrar ese plan.

S4. Follow-up decisions and preferences (verbatim):
> Yo creo que sí, las sesiones sí deberían de sobrevivir a los reinicios del demon, y que además yo creo que para la plataforma de audio y backend inicial, usemos la que ahorita tenemos configurada dentro de Pi, que es la que ahorita yo he tenido más comodidad, más facilidad de uso, entonces estoy ya familiarizado con ella, me gusta. Yo creo que es la que vamos a estar utilizando inicialmente.
> 
> El runtime, modelo y licencia en no sé, yo creo que seguiré una recomendación que tú me des realmente,
> 
> ¿Y podríamos utilizar ahorita un único cliente local? No creo utilizarla en algún otro lado, a lo mejor desde el celular poder hacer puede ser que, si tú ves conveniente, ir preparando una API. Ya para poder utilizarlo desde varios clientes. Pero lo dejo a tu consideración, cualquiera de los 2 días me gusta. Siento que la API a lo mejor daría un poquito más de libertad, pero realmente lo dejo a tu consideración.

## Tasks

T1 | S1-S3 | Define architecture, adapter contracts, lifecycle/state model, security boundaries, and MVP acceptance criteria | plan | TBD
T2 | S1-S3 | Implement daemon process, configuration, local control surface, and supervised lifecycle | implementation | TBD
T3 | S1-S3 | Implement Pi RPC conversation adapter with dedicated-session serialization, streaming, cancellation, and recovery | implementation | TBD
T4 | S1-S2 | Implement audio/STT/TTS adapters with KittenTTS first and provider/model substitution points | implementation | TBD
T5 | S1-S3 | Add multi-session model, observability, failure-path tests, and operational documentation | implementation | TBD
T6 | S1-S4 | Verify MVP end to end and record unresolved platform/provider decisions | verification | TBD
T7 | S4 | Validate the KittenTTS model/runtime/weight license and Spanish voice quality before implementation lock-in | plan | TBD

## Log

L1. User request (verbatim):
> Estamos retomando el proyecto voice-agent.
> 
> Primero recuperá el contexto desde Engram y revisá el repositorio actual. No escribas código todavía.
> 
> Objetivo: diseñar e implementar un daemon de conversación por voz que funcione independientemente de la interfaz de Pi. Debe conectar micrófono/STT → Pi mediante RPC → TTS
> → altavoces, seguir funcionando aunque se cierre la TUI y permitir cambiar proveedores o modelos sin rehacer la arquitectura.
> 
> Decisiones iniciales:
> - Usar un proceso externo persistente, no una extensión acoplada a Pi.
> - Usar Pi RPC como primer backend conversacional.
> - Usar KittenTTS como primer proveedor TTS.
> - Encapsular STT, TTS, audio y conversación detrás de adaptadores.
> - Empezar con una sesión de voz dedicada para evitar escrituras concurrentes sobre una misma sesión.
> - Diseñar desde el inicio para múltiples sesiones.
> - No usar MCP como dependencia central.
> - Priorizar configuración, seguridad local, cancelación, interrupciones y recuperación ante fallos.
> 
> Leé primero toda la documentación relevante de Pi y verificá el estado del repositorio. Después creá o reconciliá el documento de planificación ODD y presentame la
> arquitectura, los límites del MVP y las decisiones que todavía requieren confirmación. No implementes hasta cerrar ese plan.

L2. Product decision recorded: `Allowlist explícita` — habilitar únicamente herramientas/extensiones definidas en configuración; diseñar y validar esa allowlist antes de implementar.

L3. User follow-up (verbatim):
> Yo creo que sí, las sesiones sí deberían de sobrevivir a los reinicios del demon, y que además yo creo que para la plataforma de audio y backend inicial, usemos la que ahorita tenemos configurada dentro de Pi, que es la que ahorita yo he tenido más comodidad, más facilidad de uso, entonces estoy ya familiarizado con ella, me gusta. Yo creo que es la que vamos a estar utilizando inicialmente. El runtime, modelo y licencia en no sé, yo creo que seguiré una recomendación que tú me des realmente, ¿Y podríamos utilizar ahorita un único cliente local? No creo utilizarla en algún otro lado, a lo mejor desde el celular poder hacer puede ser que, si tú ves conveniente, ir preparando una API. Ya para poder utilizarlo desde varios clientes. Pero lo dejo a tu consideración, cualquiera de los 2 días me gusta. Siento que la API a lo mejor daría un poquito más de libertad, pero realmente lo dejo a tu consideración.

L4. Architecture recommendation recorded: implement a session-addressed local API from the start, bind it only to a Unix socket for the MVP, and keep the protocol transport-neutral so a future authenticated phone client can be added without redesigning the daemon. Deploy and test only one local client initially.

L5. Environment evidence: the current Pi dictation package uses Deepgram Nova-3 streaming with 16 kHz mono PCM captured through `rec`/SoX; this host has `rec`, `sox`, PipeWire capture/playback tools, and active microphone/sink devices. The daemon should reuse Deepgram as the initial STT backend while isolating capture/playback behind adapters.

L6. Product confirmation recorded: KittenTTS 2 with `emb4` CPU weights is accepted for the personal/non-commercial MVP, subject to validating Spanish voice quality and documenting the separate model license.
