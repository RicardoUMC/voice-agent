# ODD plan: voice-agent
Status: MVP implementation complete; one external provider check remains intentionally skipped.
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

T1 | S1-S3 | Define architecture, adapter contracts, lifecycle/state model, security boundaries, and MVP acceptance criteria | plan | 552b6d5
T2 | S1-S3 | Implement daemon process, configuration, local control surface, and supervised lifecycle | implementation | ac93f9b, 560fa2e (b56f32b hygiene)
T3 | S1-S3 | Implement Pi RPC conversation adapter with dedicated-session serialization, streaming, cancellation, and recovery | implementation | a941bcc
T4 | S1-S2 | Implement audio/STT/TTS adapters with KittenTTS first and provider/model substitution points | implementation | 7b6084e, ccc7a06, e29f7ae
T5 | S1-S3 | Add multi-session model, observability, failure-path tests, and operational documentation | implementation | 15c83d1
T6 | S1-S4 | Verify MVP end to end and record unresolved platform/provider decisions | verification | e29f7ae plus final evidence; live generated-audio Deepgram path passed
T7 | S4 | Validate the KittenTTS model/runtime/weight license and Spanish voice quality before implementation lock-in | plan | research complete; runtime/quality validation pending

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

L7. Implementation evidence: commits `ac93f9b`, `7b6084e`, `a941bcc`, `b56f32b`, and `560fa2e` add the persistent session core, provider adapter boundaries, Pi RPC adapter, Python artifact hygiene, and local Unix-socket daemon service. Focused stdlib checks pass: daemon 11 tests, adapters 7 tests, conversation 4 tests, plus `compileall` and `python -m voice_agent --help`. Pytest is not installed.

L8. Integration evidence: `ccc7a06` adds injectable Deepgram streaming transport and `15c83d1` wires the cancellable voice pipeline into `voice_turn`, including persistent transcript/response storage, lifecycle events, redacted failures, and WAV-aware playback. Current checks pass: daemon 12 tests, adapters 9 tests, conversation 5 tests, voice pipeline 3 tests, `compileall`, and CLI help. Live provider validation is pending because `websocket-client` and `kittenml` were not installed at the time of this check; a project-local `.venv` installation is in progress.

L9. Final local provider evidence: `ea094b0` selects the installed KittenTTS `Spanish` voice after live validation rejected the previous `expr-voice-4-f` default. KittenTTS 2 `emb4` synthesis succeeded in the project `.venv`, producing a 24 kHz WAV with 81,120 frames. `websocket-client` 1.9.2, `kittenml` 0.9.4, VoiceDaemon provider wiring, all focused suites, compileall, CLI help, and Pi RPC readiness passed. A live Deepgram network/audio turn was intentionally not run; no external provider cost or credential use was added beyond local runtime setup.

L10. Authorized live STT evidence: `e29f7ae` fixes Deepgram WebSocket PCM metadata, streaming response shape, `Finalize`/`CloseStream` ordering, and realtime pacing. The full authorized path KittenTTS Spanish WAV -> ffmpeg 16 kHz mono PCM -> real Deepgram Nova-3 WebSocket returned non-empty Spanish text (`Hola, esta es una prueba real de la gente de voz.`). Recognition differed slightly from the source phrase (`agente`/`gente`), so this proves transport and provider operation, not word-perfect accuracy. Final focused checks pass: daemon 12, adapters 10, conversation 5, voice pipeline 3, compileall, CLI help, Pi readiness, and live TTS/STT.
