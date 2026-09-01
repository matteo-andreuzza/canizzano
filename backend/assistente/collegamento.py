"""
Come si collega un agente: le istruzioni, scritte una volta sola.

Servono in tre posti — nella pagina d'admin della chiave, nel comando
``./canizzano.sh mcp`` e nella paginetta che si vede aprendo /mcp/ col
browser — e in tre posti diversi divergerebbero al primo cambiamento.
"""

from __future__ import annotations

import os


def indirizzo_mcp() -> str:
    """
    L'indirizzo a cui l'agente deve bussare.

    Di norma e' il CMS sulla macchina di casa. Se il server viene esposto
    fuori (un tunnel, un dominio), si scrive ``MCP_URL_PUBBLICO`` nel .env e
    le istruzioni cambiano da sole ovunque.
    """
    pubblico = os.environ.get("MCP_URL_PUBBLICO", "").strip()
    if pubblico:
        base = pubblico.rstrip("/")
        return base + "/" if base.endswith("/mcp") else base + "/mcp/"
    porta = os.environ.get("CMS_PORT", "8000")
    return f"http://localhost:{porta}/mcp/"


def configurazione_json(chiave: str, indirizzo: str = "") -> str:
    """Il blocco da incollare nei client che si configurano a file (JSON)."""
    indirizzo = indirizzo or indirizzo_mcp()
    return f"""{{
  "mcpServers": {{
    "canizzano": {{
      "type": "http",
      "url": "{indirizzo}",
      "headers": {{
        "Authorization": "Bearer {chiave}"
      }}
    }}
  }}
}}"""


def comando_claude_code(chiave: str, indirizzo: str = "") -> str:
    indirizzo = indirizzo or indirizzo_mcp()
    return (
        f'claude mcp add --transport http canizzano {indirizzo} '
        f'--header "Authorization: Bearer {chiave}"'
    )


def prova_curl(chiave: str, indirizzo: str = "") -> str:
    indirizzo = indirizzo or indirizzo_mcp()
    return (
        f"curl -s {indirizzo} -H 'Authorization: Bearer {chiave}' "
        "-H 'Content-Type: application/json' -d '"
        '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
        "' | head -c 400"
    )


def istruzioni(chiave: str, nome: str = "") -> str:
    """Le istruzioni complete, in testo semplice: valgono per il terminale e per l'admin."""
    indirizzo = indirizzo_mcp()
    titolo = f"Chiave «{nome}»" if nome else "La chiave dell'assistente"
    return f"""\
{titolo}

  indirizzo   {indirizzo}
  chiave      {chiave}

Trattala come una password: chi ce l'ha può cambiare il sito.

1) Claude Code (dal terminale, una riga sola)

   {comando_claude_code(chiave, indirizzo)}

2) Claude Desktop, Cursor e gli altri client che si configurano a file

{_indenta(configurazione_json(chiave, indirizzo))}

3) Client che accettano solo un indirizzo, senza intestazioni

   {indirizzo}?chiave={chiave}

   Funziona, ma la chiave finisce nei log del server: usalo solo se il
   client non sa mandare l'intestazione «Authorization».

4) Per controllare che risponda

   {prova_curl(chiave, indirizzo)}

Se l'agente gira su un'altra macchina, il CMS deve essere raggiungibile da
lì: esponilo con un tunnel, scrivi l'indirizzo pubblico in MCP_URL_PUBBLICO
e aggiungilo a DJANGO_ALLOWED_HOSTS nel .env.
"""


def _indenta(testo: str, spazi: int = 3) -> str:
    prefisso = " " * spazi
    return "\n".join(prefisso + riga if riga else riga for riga in testo.splitlines())
