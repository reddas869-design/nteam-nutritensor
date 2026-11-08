export interface ServerEvent {
  id?: string;
  event: string;
  data: string;
}

export class EventParser {
  private buffer = "";
  private previousWasCR = false;

  push(chunk: string): ServerEvent[] {
    // CRLF may straddle network chunks. Normalize lone CR and CRLF exactly once.
    for (const character of chunk) {
      if (character === "\n" && this.previousWasCR) {
        this.previousWasCR = false;
        continue;
      }
      this.previousWasCR = character === "\r";
      this.buffer += this.previousWasCR ? "\n" : character;
    }
    if (this.buffer.length > 1_000_000)
      throw new Error("Event stream exceeded its buffer limit");
    const events: ServerEvent[] = [];
    let separator = this.buffer.indexOf("\n\n");
    while (separator >= 0) {
      const block = this.buffer.slice(0, separator);
      this.buffer = this.buffer.slice(separator + 2);
      let id: string | undefined;
      let event = "message";
      const lines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith(":")) continue;
        const colon = line.indexOf(":");
        const field = colon < 0 ? line : line.slice(0, colon);
        const value = colon < 0 ? "" : line.slice(colon + 1).replace(/^ /, "");
        if (field === "id" && !value.includes("\0")) id = value;
        if (field === "event") event = value;
        if (field === "data") lines.push(value);
      }
      if (lines.length) events.push({ id, event, data: lines.join("\n") });
      separator = this.buffer.indexOf("\n\n");
    }
    return events;
  }
}

export async function consumeEvents(
  response: Response,
  listener: (event: ServerEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  if (!response.ok || !response.body)
    throw new Error(`Event connection failed (${response.status})`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new EventParser();
  try {
    while (!signal.aborted) {
      const next = await reader.read();
      if (next.done) break;
      for (const event of parser.push(
        decoder.decode(next.value, { stream: true }),
      ))
        listener(event);
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
