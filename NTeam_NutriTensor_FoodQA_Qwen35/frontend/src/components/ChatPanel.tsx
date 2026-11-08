import { useState } from "react";
import { ArrowUp, MessageCircle, Sparkles } from "lucide-react";
import { useWorkspace } from "../state/workspace";
import { errorMessage } from "../lib/export";
import { Button, ErrorNotice } from "./Primitives";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function ChatPanel({ analysisId }: { analysisId?: string }) {
  const { api } = useWorkspace();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const send = async (question: string) => {
    const text = question.trim();
    if (!text || pending) return;
    setInput("");
    setPending(true);
    setError(null);
    setMessages((current) => [...current, { role: "user", content: text }]);
    try {
      const reply = await api.chat(text, analysisId);
      setMessages((current) => [
        ...current,
        { role: "assistant", content: reply.answer },
      ]);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  };
  return (
    <section className="chat-panel">
      <div className="section-title">        
        <h3>Ask ntemma about this food</h3>
      </div>
      {messages.length === 0 && (
        <div className="chat-suggestions">
          {[
            "how much portein is in this food?",            
          ].map((text) => (
            <button key={text} onClick={() => void send(text)}>
              {text}              
            </button>
          ))}
        </div>
      )}
      <div className="chat-messages" aria-live="polite">
        {messages.map((message, index) => (
          <div key={index} className={`chat-message chat-${message.role}`}>
            <small>
              {message.role === "user"
                ? "You"
                : api.mode === "demo"
                  ? "Demo assistant"
                  : "ntemma"}
            </small>
            <p>{message.content}</p>
          </div>
        ))}
        {pending && (
          <p className="subtle">ntemma is checking the food-only scope and preparing an answer…</p>
        )}
      </div>
      {error && <ErrorNotice message={error} />}
      <form
        className="chat-input"
        onSubmit={(event) => {
          event.preventDefault();
          void send(input);
        }}
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          maxLength={2000}
          placeholder="have any question sir?"
          aria-label="Question about your meal"
        />
        <Button
          type="submit"
          disabled={!input.trim() || pending}
          aria-label="Send question"
        >          
        </Button>
      </form>
      <p className="fine-print">
        Food- and fruit-related questions only. Unrelated questions receive
        “Something wents wrong”. ntemma estimates,
        not measurements.
        <h3>Support Our Little SLM Research:</h3>
        Every contribution helps advance our little SLM research
        <h4>[Donate Now]</h4>
      </p>
    </section>
  );
}
