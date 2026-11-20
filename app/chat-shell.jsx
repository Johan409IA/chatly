"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  MessageCircle,
  MessagesSquare,
  RefreshCw,
  Search,
  Send,
  TriangleAlert,
} from "lucide-react";

const MAX_MESSAGE_LENGTH = 4000;

class ApiRequestError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  } catch {
    throw new Error("No se pudo conectar con el servidor. Comprueba tu conexión.");
  }

  let body = {};
  try {
    body = await response.json();
  } catch {
    if (response.ok) {
      throw new Error("El servidor devolvió una respuesta no válida.");
    }
  }

  if (!response.ok) {
    throw new ApiRequestError(
      body?.error?.message || "No se pudo completar la solicitud.",
      response.status,
    );
  }
  return body;
}

function initials(name = "") {
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0] || "")
      .join("")
      .toUpperCase() || "CH"
  );
}

function formatTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("es", { hour: "2-digit", minute: "2-digit" }).format(date);
}

function Avatar({ name, src, size = "2.75rem" }) {
  return (
    <span className="chatly-chat__avatar" style={{ width: size, height: size }}>
      {src ? (
        <img src={src} alt="" />
      ) : (
        <span className="chatly-chat__avatar-initials">{initials(name)}</span>
      )}
    </span>
  );
}

export default function ChatShell() {
  const router = useRouter();
  const [profile, setProfile] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [selected, setSelected] = useState(null);
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [listError, setListError] = useState("");
  const [messagesError, setMessagesError] = useState("");
  const [readError, setReadError] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);

  const filteredConversations = useMemo(() => {
    const filter = query.trim().toLocaleLowerCase("es");
    if (!filter) return conversations;
    return conversations.filter(
      (conversation) =>
        conversation.name?.toLocaleLowerCase("es").includes(filter) ||
        conversation.last_message_preview?.toLocaleLowerCase("es").includes(filter),
    );
  }, [conversations, query]);

  async function loadInbox() {
    setLoadingList(true);
    setListError("");
    try {
      const [me, inbox] = await Promise.all([
        request("/api/me"),
        request("/api/conversations"),
      ]);
      if (!Array.isArray(inbox.items)) {
        throw new Error("El servidor devolvió una lista de conversaciones no válida.");
      }
      setProfile(me);
      setConversations(inbox.items);
      setSelected((current) =>
        current ? inbox.items.find((item) => item.id === current.id) || null : null,
      );
    } catch (error) {
      if (error.status === 401) router.replace("/login");
      else setListError(error.message);
    } finally {
      setLoadingList(false);
    }
  }

  async function loadMessages(conversationId) {
    setLoadingMessages(true);
    setMessagesError("");
    setMessages([]);
    try {
      const result = await request(
        `/api/conversations/${encodeURIComponent(conversationId)}/messages?limit=50`,
      );
      if (!Array.isArray(result.items)) {
        throw new Error("El servidor devolvió un historial de mensajes no válido.");
      }
      setMessages(result.items);
      setReadError("");
      const lastMessage = result.items.at(-1);
      if (lastMessage && document.visibilityState === "visible") {
        try {
          await request(`/api/conversations/${encodeURIComponent(conversationId)}/read`, {
            method: "POST",
            body: JSON.stringify({ message_id: lastMessage.id }),
          });
          await loadInbox();
        } catch (error) {
          setReadError(error.message);
        }
      }
    } catch (error) {
      if (error.status === 401) router.replace("/login");
      else setMessagesError(error.message);
    } finally {
      setLoadingMessages(false);
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([request("/api/me"), request("/api/conversations")])
      .then(([me, inbox]) => {
        if (!Array.isArray(inbox.items)) {
          throw new Error("El servidor devolvió una lista de conversaciones no válida.");
        }
        if (active) {
          setProfile(me);
          setConversations(inbox.items);
        }
      })
      .catch((error) => {
        if (!active) return;
        if (error.status === 401) router.replace("/login");
        else setListError(error.message);
      })
      .finally(() => {
        if (active) setLoadingList(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  function openConversation(conversation) {
    setSelected(conversation);
    loadMessages(conversation.id);
  }

  async function sendMessage(event) {
    event.preventDefault();
    const content = draft.trim();
    if (!selected || !content || content.length > MAX_MESSAGE_LENGTH || sending) return;

    setSending(true);
    setMessagesError("");
    try {
      await request(`/api/conversations/${encodeURIComponent(selected.id)}/messages`, {
        method: "POST",
        body: JSON.stringify({
          content,
          client_message_id: crypto.randomUUID(),
          reply_to_message_id: null,
        }),
      });
      setDraft("");
      await loadMessages(selected.id);
    } catch (error) {
      if (error.status === 401) router.replace("/login");
      else setMessagesError(error.message);
    } finally {
      setSending(false);
    }
  }

  const totalUnread = conversations.reduce(
    (count, conversation) => count + (conversation.unread_count || 0),
    0,
  );

  return (
    <main className={`chatly-chat${selected ? " chatly-chat--conversation-open" : ""}`}>
      <aside className="chatly-chat__sidebar">
        <header className="chatly-chat__sidebar-brand">
          <span className="chatly-chat__brand-mark" aria-hidden="true">
            <MessagesSquare size={22} strokeWidth={2.2} />
          </span>
          <div>
            <div className="chatly-chat__brand-name">Chatly</div>
            <div className="chatly-chat__brand-caption">Tus conversaciones</div>
          </div>
          <span className="chatly-chat__total-unread">{totalUnread}</span>
        </header>

        <label className="chatly-chat__search">
          <Search size={17} aria-hidden="true" />
          <input
            aria-label="Buscar conversación"
            className="chatly-chat__search-input"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar conversación"
            value={query}
          />
        </label>

        <div className="chatly-chat__section-heading">
          <span className="chatly-chat__section-label">MENSAJES</span>
          <button
            aria-label="Actualizar conversaciones"
            className="chatly-chat__refresh"
            onClick={loadInbox}
            type="button"
          >
            <RefreshCw size={15} />
          </button>
        </div>

        {loadingList ? (
          <div className="chatly-chat__list-status" role="status">
            Cargando conversaciones…
          </div>
        ) : listError ? (
          <div className="chatly-chat__list-status">
            <p className="chatly-chat__error">
              <TriangleAlert size={16} /> {listError}
            </p>
            <button className="chatly-chat__retry" onClick={loadInbox} type="button">
              Intentar de nuevo
            </button>
          </div>
        ) : filteredConversations.length ? (
          <nav aria-label="Conversaciones" className="chatly-chat__conversation-list">
            {filteredConversations.map((conversation) => (
              <button
                aria-current={selected?.id === conversation.id ? "page" : undefined}
                className={`chatly-chat__conversation${
                  selected?.id === conversation.id
                    ? " chatly-chat__conversation--active"
                    : ""
                }`}
                key={conversation.id}
                onClick={() => openConversation(conversation)}
                type="button"
              >
                <Avatar
                  name={conversation.name || conversation.initials}
                  src={conversation.avatar_url}
                />
                <span className="chatly-chat__conversation-copy">
                  <span className="chatly-chat__conversation-topline">
                    <span className="chatly-chat__conversation-name">
                      {conversation.name || "Conversación"}
                    </span>
                    <span className="chatly-chat__conversation-time">
                      {formatTime(conversation.last_message_at)}
                    </span>
                  </span>
                  <span className="chatly-chat__conversation-preview">
                    {conversation.last_message_preview || "Sin mensajes aún"}
                  </span>
                </span>
                {conversation.unread_count > 0 && (
                  <span className="chatly-chat__unread-badge">
                    {conversation.unread_count}
                  </span>
                )}
              </button>
            ))}
          </nav>
        ) : (
          <div className="chatly-chat__list-status">
            <MessagesSquare size={26} />
            <p>{query ? "No encontramos coincidencias" : "Aún no tienes conversaciones"}</p>
            {!query && <small>Cuando inicies un chat, aparecerá aquí.</small>}
          </div>
        )}

        <footer className="chatly-chat__profile">
          <Avatar
            name={profile?.display_name || profile?.alias}
            src={profile?.avatar_url}
            size="2rem"
          />
          <span>
            <strong className="chatly-chat__profile-name">
              {profile?.display_name || "Tu cuenta"}
            </strong>
            <small className="chatly-chat__profile-caption">
              {profile?.alias ? `@${profile.alias}` : "Chatly"}
            </small>
          </span>
        </footer>
      </aside>

      <section className="chatly-chat__main">
        {selected ? (
          <div className="chatly-chat__conversation-panel">
            <header className="chatly-chat__conversation-header">
              <button
                aria-label="Volver a conversaciones"
                className="chatly-chat__back"
                onClick={() => setSelected(null)}
                type="button"
              >
                <ArrowLeft size={20} />
              </button>
              <Avatar
                name={selected.name || selected.initials}
                src={selected.avatar_url}
              />
              <div>
                <div className="chatly-chat__active-name">
                  {selected.name || "Conversación"}
                </div>
                <div className="chatly-chat__active-caption">
                  {selected.members_count
                    ? `${selected.members_count} integrantes`
                    : "Conversación de Chatly"}
                </div>
              </div>
            </header>

            {loadingMessages ? (
              <div className="chatly-chat__messages-status" role="status">
                Cargando mensajes…
              </div>
            ) : messagesError ? (
              <div className="chatly-chat__messages-status">
                <p className="chatly-chat__error">
                  <TriangleAlert size={16} /> {messagesError}
                </p>
                <button
                  className="chatly-chat__retry"
                  onClick={() => loadMessages(selected.id)}
                  type="button"
                >
                  Volver a intentar
                </button>
              </div>
            ) : messages.length ? (
              <div aria-live="polite" className="chatly-chat__messages">
                {messages.map((message) => {
                  const isOwn = message.author?.id === profile?.id;
                  const content = message.deleted
                    ? "Se eliminó un mensaje"
                    : message.type === "system"
                      ? "Actualización de la conversación"
                      : message.type === "poll"
                        ? message.poll?.question || "Encuesta compartida"
                        : message.content || "";
                  if (message.type === "system") {
                    return (
                      <div className="chatly-chat__message-row chatly-chat__message-row--system" key={message.id}>
                        <span className="chatly-chat__system-message">{content}</span>
                      </div>
                    );
                  }
                  return (
                    <div
                      className={`chatly-chat__message-row${
                        isOwn ? " chatly-chat__message-row--own" : ""
                      }`}
                      key={message.id}
                    >
                      <div
                        className={`chatly-chat__message-bubble${
                          isOwn ? " chatly-chat__message-bubble--own" : ""
                        }`}
                      >
                        {!isOwn && message.author?.alias && (
                          <span className="chatly-chat__message-author">
                            @{message.author.alias}
                          </span>
                        )}
                        <p className="chatly-chat__message-content">{content}</p>
                        <time className="chatly-chat__message-time" dateTime={message.created_at}>
                          {formatTime(message.created_at)}
                        </time>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="chatly-chat__messages-status">
                <MessageCircle size={24} />
                <p>Todavía no hay mensajes</p>
                <small>Envía el primero para iniciar la conversación.</small>
              </div>
            )}

            <form className="chatly-chat__composer-form" onSubmit={sendMessage}>
              {readError && (
                <p className="chatly-chat__read-error" role="status">
                  {readError}
                </p>
              )}
              <div className="chatly-chat__composer">
                <textarea
                  aria-label="Escribe un mensaje"
                  className="chatly-chat__composer-input"
                  maxLength={MAX_MESSAGE_LENGTH}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder="Escribe un mensaje…"
                  value={draft}
                />
                <button
                  aria-label="Enviar mensaje"
                  className="chatly-chat__send"
                  disabled={!draft.trim() || sending}
                  type="submit"
                >
                  <Send size={18} />
                </button>
              </div>
              <div className="chatly-chat__composer-hint">
                <span>Los mensajes se guardan en la conversación.</span>
                <span>{draft.length}/{MAX_MESSAGE_LENGTH}</span>
              </div>
            </form>
          </div>
        ) : (
          <div className="chatly-chat__welcome">
            <div className="chatly-chat__welcome-content">
              <span className="chatly-chat__welcome-icon">
                <MessagesSquare size={30} />
              </span>
              <h1>Tu espacio para conversar</h1>
              <p>Selecciona una conversación para ver los mensajes.</p>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
