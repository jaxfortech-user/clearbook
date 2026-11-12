"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Bot, User, Sparkles, AlertCircle } from "lucide-react";
import { sendChatMessage, type ChatMessage } from "@/lib/api";

const SUGGESTIONS = [
  "What documents are needed for VAT filing in UAE?",
  "Explain reverse charge mechanism for imports",
  "What is the VAT treatment for exports?",
  "How to calculate corporate tax for FY 2024?",
  "What are the FTA audit requirements?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(text?: string) {
    const content = (text ?? input).trim();
    if (!content || loading) return;

    const userMsg: ChatMessage = { role: "user", content };
    const next = [...messages, userMsg];
    setMessages(next);
    setInput("");
    setError("");
    setLoading(true);

    try {
      const { reply } = await sendChatMessage(next);
      setMessages(prev => [...prev, { role: "assistant", content: reply }]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to get a response. Please try again.");
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const isEmpty = messages.length === 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#fafafa" }}>

      {/* Header */}
      <div style={{ flexShrink: 0, padding: "0 28px", height: "56px", display: "flex", alignItems: "center", justifyContent: "space-between", background: "#ffffff", borderBottom: "1px solid #ebebeb" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{ width: "28px", height: "28px", borderRadius: "8px", background: "#eef0fd", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Sparkles size={14} color="#5266eb" />
          </div>
          <div>
            <div style={{ fontSize: "13.5px", fontWeight: 650, color: "#0a0a0a", letterSpacing: "-0.2px" }}>AI CA Assistant</div>
            <div style={{ fontSize: "11px", color: "#a3a3a3", marginTop: "1px" }}>UAE Tax & Compliance Expert</div>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => { setMessages([]); setError(""); }}
            style={{ fontSize: "12px", color: "#a3a3a3", background: "none", border: "none", cursor: "pointer", fontFamily: "var(--font-family-sans)", padding: "4px 8px", borderRadius: "6px" }}
            onMouseEnter={e => { e.currentTarget.style.background = "#f5f5f5"; e.currentTarget.style.color = "#525252"; }}
            onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "#a3a3a3"; }}
          >
            Clear chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px", display: "flex", flexDirection: "column", gap: "16px" }}>

        {isEmpty ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "20px", paddingBottom: "60px" }}>
            <div style={{ width: "52px", height: "52px", borderRadius: "14px", background: "#eef0fd", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <Sparkles size={22} color="#5266eb" />
            </div>
            <div style={{ textAlign: "center" }}>
              <p style={{ fontSize: "16px", fontWeight: 650, color: "#0a0a0a", letterSpacing: "-0.3px", margin: 0 }}>How can I help you today?</p>
              <p style={{ fontSize: "13px", color: "#a3a3a3", marginTop: "6px" }}>Ask me anything about UAE tax, VAT, corporate tax, or compliance.</p>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px", width: "100%", maxWidth: "520px" }}>
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => handleSend(s)}
                  style={{ padding: "10px 16px", background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "10px", fontSize: "13px", color: "#525252", cursor: "pointer", textAlign: "left", fontFamily: "var(--font-family-sans)", transition: "all 0.1s" }}
                  onMouseEnter={e => { e.currentTarget.style.background = "#fafafa"; e.currentTarget.style.borderColor = "#5266eb"; e.currentTarget.style.color = "#5266eb"; }}
                  onMouseLeave={e => { e.currentTarget.style.background = "#ffffff"; e.currentTarget.style.borderColor = "#ebebeb"; e.currentTarget.style.color = "#525252"; }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, i) => (
              <div key={i} style={{ display: "flex", gap: "10px", alignItems: "flex-start", flexDirection: msg.role === "user" ? "row-reverse" : "row" }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: msg.role === "user" ? "#5266eb" : "#eef0fd", marginTop: "2px" }}>
                  {msg.role === "user" ? <User size={13} color="#fff" /> : <Bot size={13} color="#5266eb" />}
                </div>
                <div style={{
                  maxWidth: "72%",
                  padding: "10px 14px",
                  borderRadius: msg.role === "user" ? "14px 4px 14px 14px" : "4px 14px 14px 14px",
                  background: msg.role === "user" ? "#5266eb" : "#ffffff",
                  border: msg.role === "user" ? "none" : "1px solid #ebebeb",
                  boxShadow: msg.role === "assistant" ? "0 1px 3px rgba(0,0,0,0.05)" : "none",
                  fontSize: "13px",
                  lineHeight: "1.6",
                  color: msg.role === "user" ? "#ffffff" : "#0a0a0a",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}>
                  {msg.content}
                </div>
              </div>
            ))}

            {loading && (
              <div style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#eef0fd", marginTop: "2px" }}>
                  <Bot size={13} color="#5266eb" />
                </div>
                <div style={{ padding: "12px 16px", background: "#ffffff", border: "1px solid #ebebeb", borderRadius: "4px 14px 14px 14px", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", display: "flex", alignItems: "center", gap: "5px" }}>
                  {[0, 1, 2].map(d => (
                    <div key={d} style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#5266eb", animation: `bounce 1.2s ease-in-out ${d * 0.2}s infinite` }} />
                  ))}
                </div>
              </div>
            )}

            {error && (
              <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "10px 14px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "10px", fontSize: "12.5px", color: "#dc2626" }}>
                <AlertCircle size={13} />
                {error}
                <button onClick={() => setError("")} style={{ marginLeft: "auto", fontSize: "11px", color: "#dc2626", background: "none", border: "none", cursor: "pointer", textDecoration: "underline", fontFamily: "var(--font-family-sans)" }}>Dismiss</button>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div style={{ flexShrink: 0, padding: "14px 28px 20px", background: "#ffffff", borderTop: "1px solid #ebebeb" }}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: "10px", maxWidth: "800px", margin: "0 auto" }}>
          <div style={{ flex: 1, display: "flex", alignItems: "flex-end", background: "#fafafa", border: "1px solid #e0e0e0", borderRadius: "12px", padding: "10px 14px", gap: "8px", transition: "border-color 0.15s", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}
            onFocusCapture={e => (e.currentTarget.style.borderColor = "#5266eb")}
            onBlurCapture={e => (e.currentTarget.style.borderColor = "#e0e0e0")}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about UAE tax, VAT, compliance…"
              rows={1}
              style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontSize: "13px", color: "#0a0a0a", fontFamily: "var(--font-family-sans)", resize: "none", lineHeight: "1.5", maxHeight: "120px", overflowY: "auto" }}
              onInput={e => {
                const t = e.currentTarget;
                t.style.height = "auto";
                t.style.height = Math.min(t.scrollHeight, 120) + "px";
              }}
            />
          </div>
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || loading}
            style={{ width: "38px", height: "38px", flexShrink: 0, borderRadius: "10px", background: input.trim() && !loading ? "#5266eb" : "#e5e5e5", border: "none", cursor: input.trim() && !loading ? "pointer" : "not-allowed", display: "flex", alignItems: "center", justifyContent: "center", transition: "background 0.15s" }}
            onMouseEnter={e => { if (input.trim() && !loading) e.currentTarget.style.background = "#4254d4"; }}
            onMouseLeave={e => { if (input.trim() && !loading) e.currentTarget.style.background = "#5266eb"; }}
          >
            <Send size={15} color={input.trim() && !loading ? "#fff" : "#a3a3a3"} />
          </button>
        </div>
        <p style={{ textAlign: "center", fontSize: "11px", color: "#c0c0c0", marginTop: "8px" }}>
          AI responses are for guidance only. Always verify with FTA regulations.
        </p>
      </div>

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}