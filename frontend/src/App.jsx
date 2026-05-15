import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Chat from './components/Chat'
import { getChats, createChat, deleteChat } from './api'
import './App.css'

function App() {
  const [chats, setChats] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)

  useEffect(() => {
    loadChats()
  }, [])

  const loadChats = async () => {
    try {
      const res = await getChats()
      setChats(res.data)
    } catch (e) {
      console.error('Error cargando chats:', e)
    }
  }

  const handleNewChat = async () => {
    try {
      const res = await createChat('Nuevo chat')
      setChats(prev => [res.data, ...prev])
      setActiveChatId(res.data.id)
    } catch (e) {
      console.error('Error creando chat:', e)
    }
  }

  const handleSelectChat = (chatId) => {
    setActiveChatId(chatId)
  }

  const handleDeleteChat = async (chatId) => {
    try {
      await deleteChat(chatId)
      setChats(prev => prev.filter(c => c.id !== chatId))
      if (activeChatId === chatId) setActiveChatId(null)
    } catch (e) {
      console.error('Error eliminando chat:', e)
    }
  }

  const handleChatTitleUpdate = (chatId, newTitle) => {
    setChats(prev => prev.map(c => c.id === chatId ? { ...c, title: newTitle } : c))
  }

  return (
    <div className="app">
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
      />
      <main className="main">
        {activeChatId ? (
          <Chat
            chatId={activeChatId}
            onTitleUpdate={handleChatTitleUpdate}
          />
        ) : (
          <div className="empty-state">
            <div className="empty-icon">🤖</div>
            <h2>Agente de Publicaciones IA</h2>
            <p>Haz preguntas sobre publicaciones académicas de inteligencia artificial</p>
            <button className="btn-new" onClick={handleNewChat}>
              Iniciar nuevo chat
            </button>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
