import { useState, useEffect, useRef } from 'react'
import { getMessages, sendMessage } from '../api'
import Message from './Message'

function Chat({ chatId, onTitleUpdate }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    loadMessages()
  }, [chatId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const loadMessages = async () => {
    try {
      const res = await getMessages(chatId)
      setMessages(res.data)
    } catch (e) {
      console.error('Error cargando mensajes:', e)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const question = input.trim()
    setInput('')
    setLoading(true)

    // Mostrar mensaje del usuario de inmediato
    const tempUserMsg = { id: Date.now(), role: 'user', content: question }
    setMessages(prev => [...prev, tempUserMsg])

    try {
      const res = await sendMessage(chatId, question)
      // Recargar todos los mensajes para tener los IDs reales
      const allMsgs = await getMessages(chatId)
      setMessages(allMsgs.data)

      // Actualizar título del chat si es el primer mensaje
      if (messages.length === 0) {
        onTitleUpdate(chatId, question.slice(0, 60))
      }
    } catch (e) {
      console.error('Error enviando mensaje:', e)
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Error al procesar tu pregunta. Intenta de nuevo.'
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat">
      <div className="messages">
        {messages.length === 0 && !loading && (
          <div className="chat-hint">
            <p>Ejemplos de preguntas:</p>
            <ul>
              <li>¿Qué publicaciones hay sobre NLP?</li>
              <li>¿Cuáles son los autores más productivos?</li>
              <li>¿Qué publicaciones hay del 2024?</li>
              <li>¿Cuántas publicaciones hay por área de IA?</li>
            </ul>
          </div>
        )}
        {messages.map(msg => (
          <Message key={msg.id} message={msg} />
        ))}
        {loading && (
          <div className="message assistant">
            <div className="bubble thinking">
              <span className="dot" /><span className="dot" /><span className="dot" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Escribe tu pregunta sobre publicaciones de IA..."
          rows={1}
          disabled={loading}
        />
        <button
          className="btn-send"
          onClick={handleSend}
          disabled={!input.trim() || loading}
        >
          {loading ? '...' : '↑'}
        </button>
      </div>
    </div>
  )
}

export default Chat
