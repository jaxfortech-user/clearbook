"use client";

import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Trash2 } from "lucide-react";
import { sendChatMessage, ChatMessage } from "@/lib/api";

export function FloatingChat() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (open && messages.length === 0) {
      // focus textarea when opened
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [open]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    const newMessages: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(newMessages);
    setInput("");
    setLoading(true);
    setError(null);

    // reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    try {
      const res = await sendChatMessage(newMessages);
      setMessages([...newMessages, { role: "assistant", content: res.reply }]);
    } catch (e) {
      setError("Failed to get response. Please try again.");
      setMessages(newMessages);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 100) + "px";
  };

  const chips = [
    "What is UAE Corporate Tax?",
    "VAT filing deadlines 2024",
    "Free zone tax benefits",
    "Transfer pricing rules UAE",
  ];

  return (
    <>
      {/* Floating panel */}
      {open && (
        <div
          style={{
            position: "fixed",
            bottom: "80px",
            right: "24px",
            width: "380px",
            height: "520px",
            background: "#ffffff",
            border: "1px solid #ebebeb",
            borderRadius: "16px",
            boxShadow: "0 8px 32px rgba(0,0,0,0.12)",
            display: "flex",
            flexDirection: "column",
            zIndex: 1000,
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "14px 16px",
              borderBottom: "1px solid #ebebeb",
              display: "flex",
              alignItems: "center",
              gap: "10px",
              background: "#ffffff",
            }}
          >
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "#5266eb",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <MessageSquare size={16} color="#ffffff" />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: "14px", fontWeight: 600, color: "#111" }}>
                CA Assistant
              </div>
              <div style={{ fontSize: "11px", color: "#888" }}>UAE Tax & Compliance</div>
            </div>
            {messages.length > 0 && (
              <button
                onClick={() => { setMessages([]); setError(null); }}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "#aaa",
                  padding: "4px",
                  borderRadius: "6px",
                  display: "flex",
                  alignItems: "center",
                }}
                title="Clear chat"
              >
                <Trash2 size={14} />
              </button>
            )}
            <button
              onClick={() => setOpen(false)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "#aaa",
                padding: "4px",
                borderRadius: "6px",
                display: "flex",
                alignItems: "center",
              }}
            >
              <X size={16} />
            </button>
          </div>

          {/* Messages */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "12px",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
            }}
          >
            {messages.length === 0 && (
              <div style={{ marginTop: "8px" }}>
                <p style={{ fontSize: "13px", color: "#666", marginBottom: "12px", lineHeight: 1.5 }}>
                  Ask me anything about UAE tax, VAT, corporate tax, or accounting compliance.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {chips.map((chip) => (
                    <button
                      key={chip}
                      onClick={() => { setInput(chip); textareaRef.current?.focus(); }}
                      style={{
                        background: "#fafafa",
                        border: "1px solid #ebebeb",
                        borderRadius: "8px",
                        padding: "7px 11px",
                        fontSize: "12px",
                        color: "#444",
                        cursor: "pointer",
                        textAlign: "left",
                        transition: "background 0.15s",
                      }}
                    >
                      {chip}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "85%",
                    padding: "9px 12px",
                    borderRadius: msg.role === "user" ? "12px 12px 2px 12px" : "12px 12px 12px 2px",
                    background: msg.role === "user" ? "#5266eb" : "#fafafa",
                    border: msg.role === "assistant" ? "1px solid #ebebeb" : "none",
                    color: msg.role === "user" ? "#ffffff" : "#111",
                    fontSize: "13px",
                    lineHeight: 1.5,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {msg.content}
                </div>
              </div>
            ))}

            {loading && (
              <div style={{ display: "flex", justifyContent: "flex-start" }}>
                <div
                  style={{
                    padding: "10px 14px",
                    borderRadius: "12px 12px 12px 2px",
                    background: "#fafafa",
                    border: "1px solid #ebebeb",
                    display: "flex",
                    gap: "5px",
                    alignItems: "center",
                  }}
                >
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: "#5266eb",
                        display: "inline-block",
                        animation: "bounce 1.2s infinite",
                        animationDelay: `${i * 0.2}s`,
                      }}
                    />
                  ))}
                </div>
              </div>
            )}

            {error && (
              <div
                style={{
                  background: "#fff5f5",
                  border: "1px solid #fecaca",
                  borderRadius: "8px",
                  padding: "8px 12px",
                  fontSize: "12px",
                  color: "#dc2626",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                {error}
                <button
                  onClick={() => setError(null)}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "#dc2626" }}
                >
                  <X size={12} />
                </button>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div
            style={{
              borderTop: "1px solid #ebebeb",
              padding: "10px 12px",
              display: "flex",
              gap: "8px",
              alignItems: "flex-end",
              background: "#ffffff",
            }}
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask about UAE tax..."
              rows={1}
              style={{
                flex: 1,
                resize: "none",
                border: "1px solid #ebebeb",
                borderRadius: "10px",
                padding: "8px 11px",
                fontSize: "13px",
                fontFamily: "inherit",
                outline: "none",
                lineHeight: 1.5,
                maxHeight: "100px",
                overflowY: "auto",
                background: "#fafafa",
              }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || loading}
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "10px",
                background: input.trim() && !loading ? "#5266eb" : "#e5e7eb",
                border: "none",
                cursor: input.trim() && !loading ? "pointer" : "not-allowed",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                transition: "background 0.15s",
              }}
            >
              <Send size={15} color={input.trim() && !loading ? "#ffffff" : "#9ca3af"} />
            </button>
          </div>

          {/* Disclaimer */}
          <div
            style={{
              padding: "6px 12px 8px",
              fontSize: "10px",
              color: "#aaa",
              textAlign: "center",
              background: "#ffffff",
            }}
          >
            For guidance only — verify with FTA regulations
          </div>
        </div>
      )}

      {/* Bounce animation */}
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40% { transform: translateY(-6px); }
        }
      `}</style>

      {/* Floating button */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          width: "52px",
          height: "52px",
          borderRadius: "50%",
          background: "#5266eb",
          border: "none",
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 4px 16px rgba(82,102,235,0.4)",
          zIndex: 1001,
          transition: "transform 0.15s, box-shadow 0.15s",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = "scale(1.08)";
          (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 6px 20px rgba(82,102,235,0.5)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)";
          (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 4px 16px rgba(82,102,235,0.4)";
        }}
        title="AI CA Assistant"
      >
        {open ? <X size={22} color="#ffffff" /> : <MessageSquare size={22} color="#ffffff" />}
      </button>
    </>
  );
}