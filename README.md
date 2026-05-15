Agente de IA sobre Neo4j – Publicaciones Académicas
Agente conversacional que permite realizar consultas en lenguaje natural sobre una base de datos grafo Neo4j con publicaciones académicas de inteligencia artificial. Construido con FastAPI, LangChain, Groq (Llama 3.3), SQLite y React.

Modelo de Grafo
Diagrama
(Autor)-[:ESCRIBIO {orden}]->(Publicacion)
(Autor)-[:PERTENECE_A]----->(Institucion)
(Publicacion)-[:PERTENECE_A]-->(AreaIA)
(Publicacion)-[:PUBLICADA_EN]->(Venue)
Nodos y propiedades
NodoPropiedadesPublicacionid_publicacion, titulo, anio, numero_citas, palabra_claveAutornombre_autorInstitucionnombre_institucion, paisAreaIAnombreVenuenombre, tipo (Revista / Conferencia)
Relaciones y cardinalidades
RelaciónCardinalidadPropiedades(Autor)-[:ESCRIBIO]->(Publicacion)N:Morden (orden de autoría)(Autor)-[:PERTENECE_A]->(Institucion)N:1—(Publicacion)-[:PERTENECE_A]->(AreaIA)N:1—(Publicacion)-[:PUBLICADA_EN]->(Venue)N:1—
Justificación del modelo
El CSV viene denormalizado (una fila por autor-publicación). El modelo grafo permite:

Consultar coautorías de forma natural con MATCH (a1)-[:ESCRIBIO]->(p)<-[:ESCRIBIO]-(a2)
Filtrar por área, año, venue o institución combinando relaciones sin JOINs complejos
El orden en ESCRIBIO preserva el orden de autoría de cada publicación
palabra_clave se almacena como propiedad de Publicacion (no como nodo) porque cada publicación tiene exactamente una y no aporta valor modelarla como entidad separada

Datos cargados

100 publicaciones, 64 autores, 21 instituciones, 6 áreas de IA, 24 venues
345 relaciones ESCRIBIO, 100 PERTENECE_A (pub→área), 100 PUBLICADA_EN, 64 PERTENECE_A (autor→inst)


Stack tecnológico
CapaTecnologíaBase de datos grafoNeo4j AuraDB FreeAgente de IALangChain + Groq (Llama 3.3-70b-versatile)Backend APIFastAPI + UvicornPersistencia de chatsSQLite + SQLAlchemyFrontendReact + Vite + Axios

Setup paso a paso
Requisitos previos

Python 3.10+
Node.js 18+
Cuenta en Neo4j AuraDB Free
API Key de Groq (gratis)

1. Clonar el repositorio
bashgit clone https://github.com/faviochi1221212/ciar-ai-agent-neo4j.git
cd ciar-ai-agent-neo4j
2. Cargar los datos en Neo4j

Crea una instancia gratuita en Neo4j AuraDB
Sube publicaciones_ia.csv a un repositorio público de GitHub y copia la URL raw
En AuraDB ve a Query y ejecuta el script load_data.cypher reemplazando la URL del CSV

3. Configurar el backend
bashcd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
Crea el archivo .env copiando el ejemplo:
bashcp .env.example .env
Edita .env con tus credenciales reales (ver sección Variables de entorno).
Levanta el servidor:
bashuvicorn main:app --reload --port 8000
Verifica en http://localhost:8000/health → debe devolver {"status":"ok"}
4. Configurar el frontend
bashcd frontend
npm install --legacy-peer-deps
npm run dev
Abre http://localhost:5173 en el navegador.

Variables de entorno
Crea backend/.env con estas variables (sin credenciales reales):
env# Neo4j AuraDB
NEO4J_URI=bolt+ssc://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=xxxxxxxx
NEO4J_PASSWORD=tu_password_aqui
NEO4J_DATABASE=xxxxxxxx

# Groq API Key — obtén la tuya gratis en https://console.groq.com
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx

# SQLite
DATABASE_URL=sqlite:///./chats.db

Nota sobre la URI: Neo4j AuraDB Free puede requerir bolt+ssc:// en lugar de neo4j+s:// dependiendo de la configuración de red. Si hay problemas de SSL, usa bolt+ssc:// que omite la verificación del certificado.


Arquitectura del agente
Usuario
  │
  ▼
Frontend React (localhost:5173)
  │  HTTP (axios)
  ▼
FastAPI (localhost:8000)
  │
  ├── SQLite ──── guarda/recupera chats y mensajes
  │
  └── Agente LangChain
        │
        ├── 1. Recibe pregunta + historial completo
        ├── 2. LLM (Groq Llama 3.3) genera query Cypher
        ├── 3. Guardrail: bloquea queries destructivos
        ├── 4. Ejecuta Cypher en Neo4j AuraDB
        ├── 5. Si falla: auto-corrección y reintento
        └── 6. LLM genera respuesta en lenguaje natural
Memoria de sesión
El historial completo de la conversación se re-inyecta en cada llamada al agente. Esto permite referencias contextuales como:

"¿Qué publicaciones hay sobre NLP?" → encuentra 17
"¿Y de esas, cuáles son del 2024?" → filtra correctamente usando el contexto anterior

Guardrails implementados

Queries destructivos bloqueados: CREATE, MERGE, DELETE, DETACH DELETE, SET, REMOVE, DROP, LOAD CSV
Preguntas fuera del dominio: el agente responde con un mensaje genérico sin inventar información
Auto-corrección: si Neo4j devuelve un error, el agente reintenta con el mensaje de error como contexto


Endpoints de la API
MétodoEndpointDescripciónGET/chatsLista todos los chatsPOST/chatsCrea un nuevo chatDELETE/chats/{id}Elimina un chatGET/chats/{id}/messagesObtiene mensajes de un chatPOST/chats/{id}/messagesEnvía pregunta al agenteGET/healthHealth check
Documentación interactiva disponible en http://localhost:8000/docs

Qué quedó fuera y por qué
FeatureEstadoMotivoExtra 2: Manejo ventana de contextoNo implementadoCon 24h de tiempo límite se priorizó el flujo end-to-end funcional. El historial completo funciona bien para conversaciones cortas.Validación semántica del Cypher contra el esquemaParcialEl esquema se pasa en el system prompt; no hay validación explícita pre-ejecución, pero el auto-retry compensa errores.Tests automatizadosNo implementadoPrioridad al flujo funcional.

Decisiones de diseño
¿Por qué Groq sobre OpenAI?
Tier gratuito generoso, latencia muy baja (importante para demo en vivo), y el modelo Llama 3.3-70b genera Cypher de alta calidad.
¿Por qué FastAPI sobre Flask?
Genera documentación interactiva automática (/docs), tipado con Pydantic, y código más limpio para APIs REST.
¿Por qué SQLite sobre PostgreSQL?
Setup cero, sin dependencias externas, suficiente para el volumen de datos de la prueba. PostgreSQL sería la elección para producción.
¿Por qué bolt+ssc:// en vez de neo4j+s://?
neo4j+s:// usa routing (para clusters) que no es compatible con AuraDB Free en todas las redes. bolt+ssc:// usa conexión directa con SSL sin verificación de certificado, más confiable en este contexto.