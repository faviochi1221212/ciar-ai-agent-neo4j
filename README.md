# Agente de IA sobre Neo4j – Publicaciones Académicas

Agente conversacional que permite realizar consultas en **lenguaje natural** sobre una base de datos grafo Neo4j con publicaciones académicas de inteligencia artificial. Construido con FastAPI, LangChain, Groq (Llama 3.3), SQLite y React.

---

## Modelo de Grafo

### Diagrama

```
(Autor)-[:ESCRIBIO {orden}]---->(Publicacion)   N:M
(Autor)-[:PERTENECE_A]-------->( Institucion)   N:1
(Publicacion)-[:PERTENECE_A]-->(AreaIA)         N:1
(Publicacion)-[:PUBLICADA_EN]->(Venue)          N:1
```

### Nodos y propiedades

| Nodo | Propiedades |
|------|-------------|
| `Publicacion` | `id_publicacion`, `titulo`, `anio`, `numero_citas`, `palabra_clave` |
| `Autor` | `nombre_autor` |
| `Institucion` | `nombre_institucion`, `pais` |
| `AreaIA` | `nombre` |
| `Venue` | `nombre`, `tipo` (Revista / Conferencia) |

### Justificación del modelo

El CSV viene denormalizado (una fila por autor-publicación). El modelo grafo permite:

- Consultar coautorías naturalmente: `MATCH (a1)-[:ESCRIBIO]->(p)<-[:ESCRIBIO]-(a2)`
- Filtrar por área, año, venue o institución combinando relaciones sin JOINs complejos
- El `orden` en `ESCRIBIO` preserva el orden de autoría de cada publicación
- `palabra_clave` se almacena como propiedad de `Publicacion` porque cada publicación tiene exactamente una

### Datos cargados

- 100 publicaciones, 64 autores, 21 instituciones, 6 áreas de IA, 24 venues
- 345 relaciones ESCRIBIO, 100 PERTENECE_A (pub→área), 100 PUBLICADA_EN, 64 PERTENECE_A (autor→inst)

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Base de datos grafo | Neo4j AuraDB Free |
| Agente de IA | LangChain + Groq (Llama 3.3-70b-versatile) |
| Backend API | FastAPI + Uvicorn |
| Persistencia de chats | SQLite + SQLAlchemy |
| Frontend | React + Vite + Axios |

---

## Setup paso a paso

### Requisitos previos

- Python 3.10+
- Node.js 18+
- Cuenta en [Neo4j AuraDB Free](https://neo4j.com/cloud/aura-free/)
- API Key de [Groq](https://console.groq.com) (gratis)

### 1. Clonar el repositorio

```bash
git clone https://github.com/faviochi1221212/ciar-ai-agent-neo4j.git
cd ciar-ai-agent-neo4j
```

### 2. Cargar los datos en Neo4j

1. Crea una instancia gratuita en [Neo4j AuraDB](https://neo4j.com/cloud/aura-free/)
2. Sube `publicaciones_ia.csv` a GitHub y copia la URL raw
3. En AuraDB ve a **Query** y ejecuta el script `load_data.cypher` reemplazando la URL del CSV
4. Verifica: `MATCH (n) RETURN labels(n), count(n)` debe mostrar 215 nodos

### 3. Configurar el backend

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edita .env con tus credenciales
```

Levanta el servidor:

```bash
uvicorn main:app --reload --port 8000
```

Verifica en `http://localhost:8000/health` → debe devolver `{"status":"ok"}`

### 4. Configurar el frontend

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Abre `http://localhost:5173` en el navegador.

---

## Variables de entorno

Crea `backend/.env` basándote en `backend/.env.example`:

```env
NEO4J_URI=bolt+ssc://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=xxxxxxxx
NEO4J_PASSWORD=tu_password_aqui
NEO4J_DATABASE=xxxxxxxx
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
DATABASE_URL=sqlite:///./chats.db
```

> **Nota:** Usar `bolt+ssc://` en lugar de `neo4j+s://` porque AuraDB Free en algunas redes bloquea el routing protocol. `bolt+ssc://` usa conexión directa con SSL sin verificación de certificado.

---

## Arquitectura del agente

```
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
        ├── 1. Guardrail: detecta prompt injection
        ├── 2. Sliding window: trunca historial a 10 msgs
        ├── 3. LLM genera query Cypher
        ├── 4. Guardrail: bloquea queries destructivos
        ├── 5. Validación sintáctica del Cypher
        ├── 6. Validación semántica contra esquema del grafo
        ├── 7. Ejecuta Cypher en Neo4j AuraDB
        ├── 8. Auto-corrección si falla (reintento)
        └── 9. LLM genera respuesta en lenguaje natural
```

---

## Extras implementados

### Extra 1 — Guardrails de seguridad

**Queries destructivos bloqueados:** CREATE, MERGE, DELETE, DETACH DELETE, SET, REMOVE, DROP, LOAD CSV, CALL {, SELECT.

**Prompt injection detectado** con lista de patrones: `ignora`, `olvida`, `actua como`, `jailbreak`, `DAN`, `sin restricciones`, `ignore the rules`, entre otros. Cuando se detecta, responde con mensaje genérico sin procesar la solicitud.

### Extra 2 — Sliding Window

**Estrategia elegida:** Sliding window de los últimos 10 mensajes.

**Justificación:** Se eligió sliding window sobre summary memory porque:
- Es más simple de implementar y predecible en comportamiento
- Para consultas sobre publicaciones académicas, el contexto reciente (últimos 10 turnos) es suficiente para entender referencias como "esas" o "los anteriores"
- No consume tokens adicionales del LLM para generar resúmenes
- Summary memory requeriría una llamada extra al LLM por cada truncado, aumentando latencia y consumo de tokens

Cuando el historial supera 10 mensajes, se truncan los más antiguos manteniendo los más recientes.

### Extra 3 — Flujo de agente mejorado

El flujo implementado va más allá del básico (pregunta → Cypher → resultado):

1. **Validación sintáctica:** Verifica que el Cypher tenga estructura válida (paréntesis balanceados, contiene RETURN, empieza con MATCH/RETURN/WITH) antes de enviarlo a Neo4j. Si falla, el LLM recibe el error y corrige.

2. **Validación semántica:** Consulta los labels reales del grafo (`CALL db.labels()`) y verifica que el Cypher no use labels inexistentes. Previene errores por alucinaciones del LLM.

3. **Auto-corrección con reintento:** Si Neo4j devuelve un error de ejecución, el mensaje de error se pasa al LLM como contexto para que genere un query corregido. Máximo 1 reintento.

**¿Por qué estas mejoras?** El LLM ocasionalmente genera Cypher con errores sintácticos menores o usa labels que no existen. Sin validación previa, estos errores llegan directamente a Neo4j y el usuario ve un mensaje de error genérico. Con el flujo mejorado, se corrigen automáticamente antes de llegar al usuario.

---

## Endpoints de la API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/chats` | Lista todos los chats |
| POST | `/chats` | Crea un nuevo chat |
| DELETE | `/chats/{id}` | Elimina un chat |
| GET | `/chats/{id}/messages` | Obtiene mensajes de un chat |
| POST | `/chats/{id}/messages` | Envía pregunta al agente |
| GET | `/health` | Health check |

Documentación interactiva en `http://localhost:8000/docs`

---

## Qué quedó fuera y por qué

| Feature | Estado | Motivo |
|---------|--------|--------|
| Summary memory | No implementado | Se eligió sliding window por ser más eficiente en tokens y suficiente para el dominio |
| Tests automatizados | No implementado | Con 24h de límite se priorizó el flujo end-to-end funcional |
| Streaming de respuestas | No implementado | Complejidad adicional no requerida por el enunciado |

---

## Decisiones de diseño

**¿Por qué Groq sobre OpenAI?**
Tier gratuito generoso (100k tokens/día), latencia muy baja importante para demo en vivo, y Llama 3.3-70b genera Cypher de alta calidad.

**¿Por qué FastAPI sobre Flask?**
Genera documentación interactiva automática (`/docs`), tipado con Pydantic, y código más limpio para APIs REST.

**¿Por qué SQLite sobre PostgreSQL?**
Setup cero, sin dependencias externas, suficiente para el volumen de datos de la prueba.

**¿Por qué `bolt+ssc://` en vez de `neo4j+s://`?**
`neo4j+s://` usa routing (para clusters) que no es compatible con AuraDB Free en todas las redes. `bolt+ssc://` usa conexión directa con SSL, más confiable en este contexto.

**¿Por qué LangChain sobre LangGraph?**
Para este caso de uso (pregunta → Cypher → respuesta) el flujo es lineal y no requiere un grafo de estados. LangChain es más simple y suficiente.
