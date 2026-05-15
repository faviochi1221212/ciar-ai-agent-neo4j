import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage, AIMessage, SystemMessage

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "580ee8e5")

driver = GraphDatabase.driver(
    NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD)
)

try:
    driver.verify_connectivity()
    print(f"✅ Conexion a Neo4j exitosa — DB: {NEO4J_DATABASE}")
except Exception as e:
    print(f"❌ Error conectando a Neo4j: {e}")


# ============================================================
# EXTRA 1: Guardrails
# ============================================================

DESTRUCTIVE_KEYWORDS = [
    "CREATE", "MERGE", "DELETE", "DETACH", "SET",
    "REMOVE", "DROP", "LOAD CSV", "CALL {", "SELECT"
]

INJECTION_PATTERNS = [
    "ignora", "ignore", "olvida", "forget", "bypass",
    "jailbreak", "prompt", "instruccion", "instruction",
    "sistema", "system", "eres ahora", "you are now",
    "nuevo rol", "new role", "actua como", "act as",
    "DAN", "modo desarrollador", "developer mode",
    "sin restricciones", "no restrictions",
    "ignora las reglas", "ignore the rules",
    "pretend", "imagina que eres", "imagine you are"
]


def is_destructive(query: str) -> bool:
    return any(kw in query.upper() for kw in DESTRUCTIVE_KEYWORDS)


def is_injection(text: str) -> bool:
    text_lower = text.lower()
    return any(pattern.lower() in text_lower for pattern in INJECTION_PATTERNS)


# ============================================================
# EXTRA 2: Sliding window para manejo de contexto
# ============================================================

MAX_HISTORY_MESSAGES = 10  # maximo de mensajes en el historial


def apply_sliding_window(history: list) -> list:
    """
    Sliding window: mantiene solo los ultimos MAX_HISTORY_MESSAGES mensajes.
    Esto evita que el contexto crezca demasiado y supere el limite de tokens.
    Si el historial es mayor, se trunca desde el inicio manteniendo los mas recientes.
    """
    if len(history) <= MAX_HISTORY_MESSAGES:
        return history
    print(f"⚠️ Sliding window: truncando historial de {len(history)} a {MAX_HISTORY_MESSAGES} mensajes")
    return history[-MAX_HISTORY_MESSAGES:]


# ============================================================
# Schema y conexion Neo4j
# ============================================================

def get_schema() -> str:
    return """
Nodos y propiedades:
- Publicacion: id_publicacion, titulo, anio (entero), numero_citas (entero), palabra_clave
- Autor: nombre_autor
- Institucion: nombre_institucion, pais
- AreaIA: nombre
- Venue: nombre, tipo (Revista o Conferencia)

Relaciones:
- (Autor)-[:ESCRIBIO {orden}]->(Publicacion)
- (Autor)-[:PERTENECE_A]->(Institucion)
- (Publicacion)-[:PERTENECE_A]->(AreaIA)
- (Publicacion)-[:PUBLICADA_EN]->(Venue)

Valores EXACTOS de AreaIA.nombre:
- 'NLP'
- 'Machine Learning'
- 'IA Generativa'
- 'Visión Computacional'
- 'Sistemas de Recomendación'
- 'Robótica'

Valores exactos de Venue.tipo: 'Revista', 'Conferencia'
Anios disponibles: 2020, 2021, 2022, 2023, 2024, 2025
Paises: España, Estados Unidos, Argentina, Perú, Colombia, Chile, Suiza, Alemania, México, Reino Unido, Brasil, Canadá
""".strip()


def get_graph_schema_labels() -> dict:
    """
    EXTRA 3: Obtiene labels y propiedades reales del grafo para validacion semantica.
    """
    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            labels = [r["label"] for r in session.run("CALL db.labels() YIELD label RETURN label")]
            rel_types = [r["relationshipType"] for r in session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]
            return {"labels": labels, "relationships": rel_types}
    except Exception as e:
        print(f"⚠️ No se pudo obtener schema del grafo: {e}")
        return {"labels": [], "relationships": []}


def execute_cypher(query: str) -> list:
    print(f"🔍 Query: {query}")
    with driver.session(database=NEO4J_DATABASE) as session:
        result = session.run(query)
        return [dict(record) for record in result]


# ============================================================
# EXTRA 3: Validacion sintatica y semantica del Cypher
# ============================================================

def validate_cypher_syntax(query: str) -> tuple[bool, str]:
    """
    Validacion sintatica basica: verifica que el query tenga
    estructura minima valida antes de enviarlo a Neo4j.
    """
    query_upper = query.upper().strip()

    if not query_upper:
        return False, "Query vacio"

    if not any(query_upper.startswith(kw) for kw in ["MATCH", "RETURN", "WITH", "CALL", "UNWIND"]):
        return False, "El query debe comenzar con MATCH, RETURN, WITH, CALL o UNWIND"

    if "RETURN" not in query_upper:
        return False, "El query debe contener RETURN"

    open_parens = query.count("(")
    close_parens = query.count(")")
    if open_parens != close_parens:
        return False, f"Parentesis desbalanceados: {open_parens} abiertos, {close_parens} cerrados"

    open_brackets = query.count("[")
    close_brackets = query.count("]")
    if open_brackets != close_brackets:
        return False, f"Corchetes desbalanceados"

    return True, "OK"


def validate_cypher_semantic(query: str, schema: dict) -> tuple[bool, str]:
    """
    EXTRA 3: Validacion semantica: verifica que los labels usados
    en el query existan realmente en el grafo.
    """
    if not schema["labels"]:
        return True, "OK"  # si no hay schema, omitir validacion

    import re
    used_labels = re.findall(r'\([\w]*:([\w]+)\)', query)

    for label in used_labels:
        if label not in schema["labels"]:
            return False, f"Label '{label}' no existe en el grafo. Labels validos: {schema['labels']}"

    return True, "OK"


# ============================================================
# LLM
# ============================================================

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
3. Recibiras los resultados y debes responder en lenguaje natural, claro y conciso, en espanol.
4. Si la pregunta NO esta relacionada con la base de datos, responde EXACTAMENTE: "Solo puedo responder preguntas sobre las publicaciones academicas de IA en la base de datos."

REGLAS CRITICAS:
- SOLO queries de lectura: MATCH, RETURN, WHERE, ORDER BY, LIMIT, WITH, COUNT.
- NUNCA uses CREATE, MERGE, DELETE, SET, REMOVE, DROP, SELECT.
- Para buscar por area de IA SIEMPRE usa el valor exacto:
  * "vision", "Vision", "Visión" → WHERE a.nombre = 'Visión Computacional'
  * "nlp", "NLP" → WHERE a.nombre = 'NLP'
  * "machine learning", "ML" → WHERE a.nombre = 'Machine Learning'
  * "ia generativa", "generativa" → WHERE a.nombre = 'IA Generativa'
  * "recomendacion", "recomendación" → WHERE a.nombre = 'Sistemas de Recomendación'
  * "robotica", "robótica" → WHERE a.nombre = 'Robótica'
- Para paises, autores, instituciones y titulos usa toLower() y CONTAINS
- Para anios: WHERE p.anio = 2024
- Si el usuario dice "esas", "esos", "los anteriores": usa el historial
- Nunca inventes datos. Si no hay resultados, dilo.
- Siempre LIMIT 20.

EJEMPLOS CORRECTOS:
MATCH (p:Publicacion)-[:PERTENECE_A]->(a:AreaIA)
WHERE a.nombre = 'Visión Computacional'
RETURN p.titulo, p.anio, p.numero_citas ORDER BY p.numero_citas DESC LIMIT 20

MATCH (p:Publicacion)-[:PERTENECE_A]->(a:AreaIA)
WHERE a.nombre = 'NLP' AND p.anio = 2024
RETURN p.titulo, p.numero_citas LIMIT 20

MATCH (a:Autor)-[:ESCRIBIO]->(p:Publicacion)
RETURN a.nombre_autor, count(p) AS total ORDER BY total DESC LIMIT 10

MATCH (p:Publicacion) WHERE p.anio = 2024
RETURN p.titulo, p.numero_citas ORDER BY p.numero_citas DESC LIMIT 20

MATCH (i:Institucion)
WHERE toLower(i.pais) CONTAINS 'per'
RETURN i.nombre_institucion, i.pais LIMIT 20
"""

GENERIC_RESPONSE = "Solo puedo responder preguntas sobre las publicaciones academicas de IA en la base de datos."


def build_messages(history: list, user_question: str) -> list:
    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    # Aplicar sliding window al historial
    windowed_history = apply_sliding_window(history)
    for msg in windowed_history:
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

    # EXTRA 1: Detectar prompt injection
    if is_injection(user_question):
        print(f"🚨 Prompt injection detectado: {user_question}")
        return GENERIC_RESPONSE

    # Paso 1: LLM genera Cypher
    messages = build_messages(history, user_question)
    response = llm.invoke(messages)
    llm_output = response.content

    if GENERIC_RESPONSE in llm_output or "Solo puedo responder" in llm_output:
        return GENERIC_RESPONSE

    cypher_query = extract_cypher(llm_output)

    if not cypher_query:
        return "No pude generar una consulta valida. Puedes reformular tu pregunta?"

    # EXTRA 1: Guardrail — bloquear queries destructivos
    if is_destructive(cypher_query):
        print(f"🚨 Query destructivo bloqueado: {cypher_query}")
        return GENERIC_RESPONSE

    # EXTRA 3: Validacion sintatica
    is_valid_syntax, syntax_error = validate_cypher_syntax(cypher_query)
    if not is_valid_syntax:
        print(f"⚠️ Error sintactico: {syntax_error}")
        correction_prompt = f"""El query generado tiene un error sintactico: {syntax_error}
Query: {cypher_query}
Genera un query corregido entre etiquetas <cypher> y </cypher>."""
        messages.append(AIMessage(content=llm_output))
        messages.append(HumanMessage(content=correction_prompt))
        retry = llm.invoke(messages)
        cypher_query = extract_cypher(retry.content)
        if not cypher_query:
            return "No pude generar una consulta valida."

    # EXTRA 3: Validacion semantica
    schema = get_graph_schema_labels()
    is_valid_semantic, semantic_error = validate_cypher_semantic(cypher_query, schema)
    if not is_valid_semantic:
        print(f"⚠️ Error semantico: {semantic_error}")
        correction_prompt = f"""El query usa labels que no existen en el grafo: {semantic_error}
Query: {cypher_query}
Genera un query corregido entre etiquetas <cypher> y </cypher>."""
        messages.append(AIMessage(content=llm_output))
        messages.append(HumanMessage(content=correction_prompt))
        retry = llm.invoke(messages)
        cypher_query = extract_cypher(retry.content)
        if not cypher_query:
            return "No pude generar una consulta valida."

    # Paso 2: Ejecutar en Neo4j con auto-correccion
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

    # Paso 3: LLM genera respuesta en lenguaje natural
    final_prompt = f"""El usuario pregunto: "{user_question}"

Query ejecutado:
{cypher_query}

Resultados:
{str(results[:20])}

Responde en espanol de forma clara y concisa, basandote SOLO en estos resultados. No inventes nada."""

    messages.append(AIMessage(content=llm_output))
    messages.append(HumanMessage(content=final_prompt))
    final_response = llm.invoke(messages)
    return final_response.content