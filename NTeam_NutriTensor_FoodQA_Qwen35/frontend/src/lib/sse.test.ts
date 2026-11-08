import { describe, expect, it } from "vitest";
import { EventParser, consumeEvents, type ServerEvent } from "./sse";

describe("incremental SSE parsing", () => {
  it("reassembles every possible split of a CRLF event", () => {
    const source =
      'id: 42\r\nevent: progress\r\ndata: {"stage":"review"}\r\n\r\n';
    for (let index = 0; index <= source.length; index++) {
      const parser = new EventParser();
      const result = [
        ...parser.push(source.slice(0, index)),
        ...parser.push(source.slice(index)),
      ];
      expect(result).toEqual([
        { id: "42", event: "progress", data: '{"stage":"review"}' },
      ]);
    }
  });

  it("supports lone CR, comments, multiline data and multiple events", () => {
    const parser = new EventParser();
    expect(
      parser.push(": heartbeat\r\rdata: one\rdata: two\r\rdata: three\r\r"),
    ).toEqual([
      { id: undefined, event: "message", data: "one\ntwo" },
      { id: undefined, event: "message", data: "three" },
    ]);
  });

  it("waits for a complete event and ignores unsafe identifiers", () => {
    const parser = new EventParser();
    expect(parser.push("id: unsafe\0id\ndata: {")).toEqual([]);
    expect(parser.push("}\n\n")).toEqual([
      { id: undefined, event: "message", data: "{}" },
    ]);
  });

  it("bounds malformed or never-terminated streams", () => {
    const parser = new EventParser();
    expect(() => parser.push("x".repeat(1_000_001))).toThrow(/buffer limit/);
  });

  it("decodes Unicode split inside a UTF-8 character", async () => {
    const bytes = new TextEncoder().encode("data: ভাত\n\n");
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
        controller.close();
      },
    });
    const events: ServerEvent[] = [];
    await consumeEvents(
      new Response(body),
      (event) => events.push(event),
      new AbortController().signal,
    );
    expect(events[0].data).toBe("ভাত");
  });

  it("surfaces an authentication failure before reading events", async () => {
    await expect(
      consumeEvents(
        new Response(null, { status: 401 }),
        () => undefined,
        new AbortController().signal,
      ),
    ).rejects.toThrow("401");
  });
});
