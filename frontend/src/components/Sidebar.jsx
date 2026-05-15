function Sidebar({ chats, activeChatId, onNewChat, onSelectChat, onDeleteChat }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="sidebar-title">Chats</h1>
        <button className="btn-new-chat" onClick={onNewChat} title="Nuevo chat">
          +
        </button>
      </div>

      <div className="chat-list">
        {chats.length === 0 && (
          <p className="no-chats">No hay chats aún</p>
        )}
        {chats.map(chat => (
          <div
            key={chat.id}
            className={`chat-item ${activeChatId === chat.id ? 'active' : ''}`}
            onClick={() => onSelectChat(chat.id)}
          >
            <span className="chat-item-title">{chat.title}</span>
            <button
              className="btn-delete"
              onClick={(e) => {
                e.stopPropagation()
                onDeleteChat(chat.id)
              }}
              title="Eliminar chat"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </aside>
  )
}

export default Sidebar
