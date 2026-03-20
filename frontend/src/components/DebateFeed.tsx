import type { Message } from '../types/models'

interface DebateFeedProps {
  messages: Message[]
}

export function DebateFeed({ messages }: DebateFeedProps) {
  return (
    <div className="debate-feed" aria-live="polite">
      {messages.map((message) => (
        <article key={message.id} className={`message-card role-${message.role}`}>
          <div className="message-topline">
            <div className="persona-nameplate">
              <span className="persona-avatar" aria-hidden="true">
                {message.avatar_emoji}
              </span>
              <div>
                <p className="eyebrow">
                  round {message.round_index} {message.cue ? `• ${message.cue}` : ''}
                </p>
                <h4>{message.author_name}</h4>
              </div>
            </div>
            {message.confidence !== null && message.stance !== null ? (
              <span className="metric-pill">
                {message.stance > 0 ? '+' : ''}
                {message.stance.toFixed(2)}
              </span>
            ) : null}
          </div>
          <p>{message.content}</p>
        </article>
      ))}
    </div>
  )
}

