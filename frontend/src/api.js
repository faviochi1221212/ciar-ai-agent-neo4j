import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000',
})

export const getChats = () => api.get('/chats')
export const createChat = (title = 'Nuevo chat') => api.post('/chats', { title })
export const deleteChat = (chatId) => api.delete(`/chats/${chatId}`)
export const getMessages = (chatId) => api.get(`/chats/${chatId}/messages`)
export const sendMessage = (chatId, question) =>
  api.post(`/chats/${chatId}/messages`, { question })
