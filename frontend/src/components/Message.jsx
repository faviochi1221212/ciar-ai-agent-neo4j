function Message({ message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`message ${isUser ? 'user' : 'assistant'}`}>
      <div className="bubble">
        {message.content}
      </div>
    </div>
  )
}

export default Message
