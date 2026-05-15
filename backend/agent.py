import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, AIMessage, SystemMessage

load_dotenv()

# ---------- Conexion Neo4j ----------

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

try:
    driver.verify_connectivity()
    print("✅ Conexion a Neo4j exitosa")
except Exception as e:
    print(f"❌ Error conectando a Neo4j: {e}")


def get_schema() -> str:
    return """
Nodos y propiedades:
- Publicacion: id_publicacion, titulo, anio, numero_citas, palabra_clave
- Autor: nombre_autor
- Institucion: nombre_institucion, pais
- AreaIA: nombre
- Venue: nombre, tipo (Revista o Conferencia)

Relaciones:
- (Autor)-[:ESCRIBIO {orden}]->(Publicacion)
- (Autor)-[:PERTENECE_A]->(Institucion)
- (Publicacion)-[:PERTENECE_A]->(AreaIA)
- (Publicacion)-[:PUBLICADA_EN]->(Venue)

Valores exactos de AreaIA.nombre: 'NLP', 'Machine Learning', 'IA Generativa', 'Vision Computacional', 'Sistemas de Recomendacion', 'Robotica'
Valores exactos de Venue.tipo: 'Revista', 'Conferencia'
Anios disponibles: 2020, 2021, 2022, 2023, 2024, 2025
""".strip()


def execute_cypher(query: str) -> list:
    with driver.session(database=os.getenv("NEO4J_DATABASE", "580ee8e5")) as session:
        result = session.run(query)
        return [dict(record) for record in result]


DESTRUCTIVE_KEYWORDS = [
    "CREATE", "MERGE", "DELETE", "DETACH", "SET",
    "REMOVE", "DROP", "LOAD CSV", "CALL {"
]


def is_destructive(query: str) -> bool:
    return any(kw in query.upper() for kw in DESTRUCTIVE_KEYWORDS)


llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY")
)

SYSTEM_PROMPT = f"""Eres un asistente experto en consultar una base de datos Neo4j sobre publicaciones academicas de inteligencia artificial.

ESQUEMA DEL GRAFO:
{get_schema()}

TU FLUJO DE TRABAJO:
1. Analiza la pregunta del usuario (y el historial si existe).
2. Si la pregunta es sobre publicaciones, autores, instituciones, areas o venues, genera UN SOLO query Cypher valido entre etiquetas <cypher> y </cypher>.
3. Recibiras los resultados y debes responder en lenguaje natural, claro y conciso, en español.
4. Si la pregunta NO esta relacionada con la base de datos, responde EXACTAMENTE: "Solo puedo responder preguntas sobre las publicaciones academicas de IA en la base de datos."

REGLAS:
- SOLO queries de lectura (MATCH, RETURN, WHERE, ORDER BY, LIMIT).
- NUNCA uses CREATE, MERGE, DELETE, SET, REMOVE, DROP.
- Usa toLower() y CONTAINS para busquedas flexibles.
- Si el usuario dice "esas", "esos", "los anteriores", usa el historial.
- Nunca inventes datos. Si no hay resultados, dilo.
- Siempre usa LIMIT 20.

EJEMPLOS:
- MATCH (p:Publicacion)-[:PERTENECE_A]->(a:AreaIA) WHERE toLower(a.nombre) CONTAINS 'nlp' RETURN p.titulo, p.anio LIMIT 20
- MATCH (a:Autor)-[:ESCRIBIO]->(p:Publicacion) RETURN a.nombre_autor, count(p) AS total ORDER BY total DESC LIMIT 10
- MATCH (p:Publicacion) WHERE p.anio = 2024 RETURN p.titulo, p.numero_citas ORDER BY p.numero_citas DESC LIMIT 20
"""


def build_messages(history: list, user_question: str) -> list:
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_question))
    return messages


def extract_cypher(text: str):
    if "<cypher>" in text and "</cypher>" in text:
        start = text.index("<cypher>") + len("<cypher>")
        end = text.index("</cypher>")
        return text[start:end].strip()
    return None


def run_agent(user_question: str, history: list = []) -> str:
    messages = build_messages(history, user_question)
    response = llm.invoke(messages)
    llm_output = response.content

    if "Solo puedo responder preguntas" in llm_output:
        return llm_output

    cypher_query = extract_cypher(llm_output)

    if not cypher_query:
        return "No pude generar una consulta valida. Puedes reformular tu pregunta?"

    if is_destructive(cypher_query):
        return "No puedo ejecutar operaciones de escritura sobre la base de datos."

    try:
        results = execute_cypher(cypher_query)
    except Exception as e:
        print(f"❌ Error Cypher: {e}\nQuery: {cypher_query}")
        correction_prompt = f"""El query fallo con este error:
{str(e)}

Query fallido:
{cypher_query}

Genera un query corregido entre etiquetas <cypher> y </cypher>."""
        messages.append(AIMessage(content=llm_output))
        messages.append(HumanMessage(content=correction_prompt))
        retry = llm.invoke(messages)
        cypher_query = extract_cypher(retry.content)
        if not cypher_query:
            return f"No pude ejecutar la consulta. Error: {str(e)}"
        try:
            results = execute_cypher(cypher_query)
        except Exception as e2:
            return f"No pude ejecutar la consulta tras corregirla. Error: {str(e2)}"

    if not results:
        return "No encontre resultados para tu consulta en la base de datos."

    final_prompt = f"""El usuario pregunto: "{user_question}"

Query ejecutado:
{cypher_query}

Resultados:
{str(results[:20])}

Responde en español de forma clara y concisa, basandote SOLO en estos resultados."""

    messages.append(AIMessage(content=llm_output))
    messages.append(HumanMessage(content=final_prompt))
    final_response = llm.invoke(messages)
    return final_response.content