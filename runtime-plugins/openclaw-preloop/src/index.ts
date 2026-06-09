#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";

type ControlConfig = {
  enabled?: boolean;
  protocol?: string;
  runtime?: string;
  control_ws_url?: string;
  bearer_token?: string;
  runtime_principal_id?: string;
  runtime_principal_name?: string;
  session_reference?: string;
};

type OpenClawRuntime = {
  sendPrompt?: (
    message: string,
    metadata?: Record<string, unknown>,
  ) => Promise<unknown>;
  sendVoiceTranscript?: (
    transcript: string,
    metadata?: Record<string, unknown>,
  ) => Promise<unknown>;
  interrupt?: (metadata?: Record<string, unknown>) => Promise<unknown>;
  subagent?: {
    run: (params: {
      sessionKey: string;
      message: string;
      deliver?: boolean;
      idempotencyKey?: string;
    }) => Promise<unknown>;
  };
};

type OperatorCommand = {
  message_id?: string;
  type?: string;
  name?: string;
  payload?: {
    text?: string;
    message?: string;
    input_mode?: string;
    metadata?: Record<string, unknown>;
    voice?: Record<string, unknown>;
    interrupt?: boolean;
    target_session_id?: string;
    session_reference?: string;
    runtime_session_id?: string;
  };
};

export class PreloopOpenClawPlugin {
  runtime = "openclaw";
  private controlConfig?: ControlConfig;
  private socket?: WebSocket;

  constructor(private readonly configPath?: string) {}

  configure(config: ControlConfig): void {
    this.controlConfig = config;
  }

  loadConfig(): ControlConfig {
    const resolvedPath = this.configPath ?? defaultConfigPath();
    const raw = JSON.parse(fs.readFileSync(resolvedPath, "utf8"));
    const config =
      raw.plugins?.entries?.["openclaw-plugin"]?.config ??
      raw.plugins?.entries?.["@preloop/openclaw-plugin"]?.config ??
      raw.preloop?.control ??
      raw.control ??
      raw;
    this.controlConfig = config;
    return config;
  }

  verify(): void {
    const config = this.loadConfig();
    if (config.runtime !== this.runtime) {
      throw new Error(
        `Expected OpenClaw runtime config, got ${String(config.runtime)}`,
      );
    }
    for (const key of [
      "control_ws_url",
      "bearer_token",
      "runtime_principal_id",
    ]) {
      if (!config[key as keyof ControlConfig]) {
        throw new Error(`preloop.control.${key} is required`);
      }
    }
  }

  async start(openclawRuntime?: OpenClawRuntime): Promise<void> {
    const config = this.controlConfig ?? this.loadConfig();
    const wsUrl = new URL(config.control_ws_url!);
    wsUrl.searchParams.set("token", config.bearer_token!);
    this.socket = new WebSocket(wsUrl);

    this.socket.addEventListener("open", () => {
      this.socket?.send(
        JSON.stringify({
          type: "presence",
          name: "capabilities",
          message_id: randomUUID(),
          payload: {
            status: "online",
            protocol: "preloop.agent_control.v1",
            runtime: this.runtime,
            capabilities: {
              new_session: true,
              existing_session: true,
              text: true,
              voice: true,
              interrupt: true,
            },
            runtime_principal_id: config.runtime_principal_id,
            runtime_principal_name: config.runtime_principal_name,
          },
        }),
      );
    });

    this.socket.addEventListener("message", async (event) => {
      const command = JSON.parse(String(event.data)) as OperatorCommand;
      try {
        const result = await this.dispatch(openclawRuntime, command);
        this.socket?.send(
          JSON.stringify({
            type: "status",
            name: "command_result",
            message_id: command.message_id,
            payload: {
              command_id: command.message_id,
              status: "completed",
              result,
              reply_text: this.resultToText(result),
            },
          }),
        );
      } catch (error) {
        this.socket?.send(
          JSON.stringify({
            type: "status",
            name: "command_error",
            message_id: command.message_id,
            payload: {
              command_id: command.message_id,
              status: "failed",
              error: error instanceof Error ? error.message : String(error),
            },
          }),
        );
      }
    });
  }

  stop(): void {
    this.socket?.close();
    this.socket = undefined;
  }

  async dispatch(
    openclawRuntime: OpenClawRuntime | undefined,
    command: OperatorCommand,
  ): Promise<unknown> {
    if (command.type !== "command" || command.name !== "send_message") {
      return undefined;
    }
    const payload = command.payload ?? {};
    const message = payload.text ?? payload.message ?? "";
    const metadata = payload.metadata ?? {};

    if (payload.interrupt) {
      if (!openclawRuntime?.interrupt) {
        throw new Error("OpenClaw interrupt hook is not available");
      }
      return openclawRuntime.interrupt(metadata);
    }

    if (payload.input_mode === "voice_transcript") {
      if (openclawRuntime?.sendVoiceTranscript) {
        return openclawRuntime.sendVoiceTranscript(message, metadata);
      }
      if (openclawRuntime?.sendPrompt) {
        return openclawRuntime.sendPrompt(message, metadata);
      }
      if (openclawRuntime?.subagent?.run) {
        return openclawRuntime.subagent.run({
          sessionKey: this.resolveSessionKey(payload, metadata),
          message,
          deliver: true,
          idempotencyKey: command.message_id,
        });
      }
      throw new Error("OpenClaw voice hook is not available");
    }

    if (openclawRuntime?.sendPrompt) {
      return openclawRuntime.sendPrompt(message, metadata);
    }
    if (openclawRuntime?.subagent?.run) {
      return openclawRuntime.subagent.run({
        sessionKey: this.resolveSessionKey(payload, metadata),
        message,
        deliver: true,
        idempotencyKey: command.message_id,
      });
    }
    throw new Error("OpenClaw sendPrompt hook is not available");
  }

  private resolveSessionKey(
    payload: NonNullable<OperatorCommand["payload"]>,
    metadata: Record<string, unknown>,
  ): string {
    const configured = this.controlConfig?.session_reference;
    for (const candidate of [
      payload.target_session_id,
      payload.session_reference,
      payload.runtime_session_id,
      metadata["session_key"],
      metadata["session_id"],
      metadata["runtime_session_id"],
      metadata["session_reference"],
      configured,
    ]) {
      if (typeof candidate === "string" && candidate.trim() !== "") {
        return candidate;
      }
    }
    return "preloop-agent-control";
  }

  private resultToText(result: unknown): string {
    if (typeof result === "string") return result;
    if (result && typeof result === "object") {
      const record = result as Record<string, unknown>;
      for (const key of ["reply_text", "text", "message", "output"]) {
        const value = record[key];
        if (typeof value === "string" && value.trim()) {
          return value;
        }
      }
    }
    return "";
  }
}

export const plugin = new PreloopOpenClawPlugin();

export const definition = {
  id: "openclaw-plugin",
  name: "Preloop",
  version: "0.1.0",
  description: "Expose OpenClaw to Preloop Agent Control.",
};

export function register(api: {
  pluginConfig?: Record<string, unknown>;
  runtime?: OpenClawRuntime;
  registrationMode?: string;
  logger?: {
    info?: (message: string) => void;
    warn?: (message: string) => void;
    error?: (message: string) => void;
  };
  on?: (
    hookName: "gateway_start" | "gateway_stop",
    handler: () => void | Promise<void>,
  ) => void;
}): void {
  const instance = new PreloopOpenClawPlugin();
  if (api.pluginConfig && Object.keys(api.pluginConfig).length > 0) {
    instance.configure(api.pluginConfig as ControlConfig);
  }
  let started = false;
  const start = (): void => {
    if (started) {
      return;
    }
    started = true;
    void instance.start(api.runtime).catch((error: unknown) => {
      started = false;
      const message = error instanceof Error ? error.message : String(error);
      api.logger?.error?.(`Preloop Agent Control failed to start: ${message}`);
    });
  };

  api.on?.("gateway_start", start);
  api.on?.("gateway_stop", () => {
    started = false;
    instance.stop();
  });
  if (process.argv.includes("gateway")) {
    start();
  }
  api.logger?.info?.("Preloop Agent Control plugin registered.");
}

function defaultConfigPath(): string {
  return path.join(process.env.HOME ?? ".", ".openclaw", "openclaw.json");
}

function parseArgs(): {
  command: string;
  configPath?: string;
} {
  const [, , command = "verify", ...rest] = process.argv;
  const configIndex = rest.indexOf("--config");
  return {
    command,
    configPath: configIndex >= 0 ? rest[configIndex + 1] : undefined,
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = parseArgs();
  const instance = new PreloopOpenClawPlugin(args.configPath);
  if (args.command === "verify") {
    instance.verify();
    console.log("@preloop/openclaw-plugin verified");
  } else if (args.command === "run") {
    void instance.start();
  } else {
    throw new Error(`Unknown command: ${args.command}`);
  }
}
