# Preloop Runtime Plugins

This directory contains standalone, open-source runtime plugins for external
agents. These are not Preloop EE server plugins and should not live under the
top-level `plugins/` directory.

Runtime plugins are responsible for the agent-side Preloop exposure contract:

- read the CLI-written `preloop.control` configuration
- keep the Agent Control WebSocket connected
- advertise runtime capabilities and presence
- route operator text or voice-transcript turns into the native agent runtime
- emit command results and status events back to Preloop

The packages here are intentionally structured so they can be published from
this repository first, then split into dedicated standalone repositories later
without changing their package names.
