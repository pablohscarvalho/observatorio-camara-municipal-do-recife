"""
fetch_data.py
=============
Busca todos os dados públicos da API de Dados Abertos da
Câmara Municipal do Recife (Casa José Mariano) e salva
em arquivos JSON locais na pasta /data.

Uso:
    python fetch_data.py              # busca tudo
    python fetch_data.py --ano 2025   # proposições e sessões de um ano específico
    python fetch_data.py --endpoint vereadores  # só um endpoint

Dependências:
    pip install requests
"""

import requests
import json
import os
import time
import argparse
from datetime import datetime

# ── Configuração ──────────────────────────────────────────────────────────────

BASE_URL = "https://e-processo.recife.pe.leg.br"
DATA_DIR = "data"

ENDPOINTS = {
    "vereadores":   "/@@vereadores",
    "legislaturas": "/@@legislaturas",
    "comissoes":    "/@@comissoes",
}

# Endpoints que aceitam filtro por ano
ENDPOINTS_POR_ANO = {
    "sessoes":     "/@@sessoes",
    "materias":    "/@@materias",   # proposições
    "normas":      "/@@normas",     # legislação aprovada
}

ANOS = [2024, 2025, 2026]

TIPOS_MATERIA = [
    {"id": "10", "nome": "Projeto de Lei Ordinária"},
    {"id": "11", "nome": "Projeto de Lei do Executivo"},
    {"id": "6",  "nome": "Projeto de Decreto Legislativo"},
    {"id": "2",  "nome": "Projeto de Resolução"},
    {"id": "14", "nome": "Projeto de Emenda à Lei Orgânica"},
    {"id": "28", "nome": "Projeto de Lei Complementar"},
    {"id": "3",  "nome": "Requerimento"},
    {"id": "27", "nome": "Veto"},
]

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ObservatorioJoseMariano/1.0",
}

TIMEOUT = 30       # segundos por request
DELAY   = 0.5      # segundos entre requests (respeitar o servidor)


# ── Helpers ───────────────────────────────────────────────────────────────────

def garantir_pasta():
    """Cria a pasta /data se não existir."""
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"📁  Pasta '{DATA_DIR}/' pronta.")


def salvar_json(nome_arquivo: str, dados: dict | list):
    """Salva dados como JSON formatado."""
    caminho = os.path.join(DATA_DIR, nome_arquivo)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    tamanho = os.path.getsize(caminho) / 1024
    print(f"  ✅  Salvo: {caminho}  ({tamanho:.1f} KB)")


def buscar(endpoint: str, params: dict = None) -> dict | None:
    """Faz GET em um endpoint e retorna JSON ou None em caso de erro."""
    url = BASE_URL + endpoint
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"  ⚠️   HTTP {r.status_code} em {url} — {e}")
    except requests.exceptions.ConnectionError:
        print(f"  ❌  Erro de conexão em {url}")
    except requests.exceptions.Timeout:
        print(f"  ⏱️   Timeout em {url}")
    except Exception as e:
        print(f"  ❌  Erro inesperado em {url}: {e}")
    return None


# ── Funções de fetch ──────────────────────────────────────────────────────────

def fetch_simples(chave: str, endpoint: str):
    """Busca endpoints sem filtro de ano (vereadores, comissões, etc.)."""
    print(f"\n🔄  Buscando {chave}...")
    dados = buscar(endpoint)
    if dados:
        salvar_json(f"{chave}.json", dados)
    return dados


def fetch_por_ano(chave: str, endpoint: str, anos: list[int]):
    """
    Busca endpoints que aceitam ?ano=XXXX.
    Salva um JSON por ano E um arquivo consolidado.
    """
    print(f"\n🔄  Buscando {chave} por ano {anos}...")
    consolidado = []

    for ano in anos:
        print(f"  → ano {ano}")
        dados = buscar(endpoint, params={"ano": ano})
        time.sleep(DELAY)

        if dados:
            items = dados.get("items", dados if isinstance(dados, list) else [])
            # Adiciona campo 'ano' em cada item para facilitar filtragem depois
            for item in items:
                if isinstance(item, dict) and "ano" not in item:
                    item["_ano_fetch"] = ano

            salvar_json(f"{chave}_{ano}.json", dados)
            consolidado.extend(items)

    # Arquivo consolidado com todos os anos
    if consolidado:
        salvar_json(f"{chave}_todos.json", {
            "total":    len(consolidado),
            "anos":     anos,
            "gerado_em": datetime.now().isoformat(),
            "items":    consolidado,
        })
        print(f"  📦  Consolidado: {len(consolidado)} registros de {chave}")

    return consolidado


def fetch_materias_por_tipo(anos: list[int]):
    """
    Busca proposições também segmentadas por tipo.
    Útil para análises específicas (ex: só PLs, só requerimentos).
    """
    print(f"\n🔄  Buscando proposições por tipo...")
    consolidado_tipos = {}

    for tipo in TIPOS_MATERIA:
        tipo_id   = tipo["id"]
        tipo_nome = tipo["nome"]
        items_tipo = []

        for ano in anos:
            dados = buscar("/@@materias", params={"ano": ano, "tipo": tipo_id})
            time.sleep(DELAY)
            if dados:
                items = dados.get("items", [])
                items_tipo.extend(items)

        if items_tipo:
            consolidado_tipos[tipo_nome] = items_tipo
            print(f"  📄  {tipo_nome}: {len(items_tipo)} proposições")

    if consolidado_tipos:
        salvar_json("materias_por_tipo.json", {
            "total_tipos": len(consolidado_tipos),
            "anos":        anos,
            "gerado_em":   datetime.now().isoformat(),
            "tipos":       consolidado_tipos,
        })


def fetch_detalhes_vereadores(vereadores: list) -> list:
    """
    Para cada vereador, busca o endpoint individual com mais detalhes.
    Enriquece os dados com informações adicionais se disponíveis.
    """
    print(f"\n🔄  Enriquecendo dados dos vereadores...")
    enriquecidos = []

    for v in vereadores:
        vid = v.get("id")
        url_individual = v.get("@id")

        if url_individual:
            endpoint = url_individual.replace(BASE_URL, "")
            detalhe = buscar(endpoint)
            time.sleep(DELAY)

            if detalhe:
                # Mescla dados base com detalhes
                merged = {**v, **detalhe}
                enriquecidos.append(merged)
            else:
                enriquecidos.append(v)
        else:
            enriquecidos.append(v)

    if enriquecidos:
        salvar_json("vereadores_detalhados.json", {
            "total":     len(enriquecidos),
            "gerado_em": datetime.now().isoformat(),
            "items":     enriquecidos,
        })
        print(f"  👤  {len(enriquecidos)} vereadores enriquecidos")

    return enriquecidos


def gerar_resumo():
    """Gera um arquivo de metadados com info de quando foi gerado cada arquivo."""
    arquivos = {}
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".json"):
            path = os.path.join(DATA_DIR, fname)
            stat = os.stat(path)
            with open(path, encoding="utf-8") as f:
                try:
                    conteudo = json.load(f)
                    total = (
                        len(conteudo.get("items", []))
                        if isinstance(conteudo, dict)
                        else len(conteudo) if isinstance(conteudo, list)
                        else "—"
                    )
                except Exception:
                    total = "?"
            arquivos[fname] = {
                "tamanho_kb": round(stat.st_size / 1024, 1),
                "modificado": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "registros":  total,
            }

    resumo = {
        "gerado_em":  datetime.now().isoformat(),
        "fonte":      BASE_URL,
        "portal":     "https://transparencia.recife.pe.leg.br",
        "arquivos":   arquivos,
    }
    salvar_json("_resumo.json", resumo)
    return resumo


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch dos dados abertos da Câmara Municipal do Recife"
    )
    parser.add_argument(
        "--ano",
        type=int,
        help="Ano específico (ex: 2025). Se não informado, busca todos os anos configurados.",
    )
    parser.add_argument(
        "--endpoint",
        choices=list(ENDPOINTS.keys()) + list(ENDPOINTS_POR_ANO.keys()),
        help="Buscar somente um endpoint específico.",
    )
    parser.add_argument(
        "--sem-detalhes",
        action="store_true",
        help="Pula o enriquecimento individual dos vereadores (mais rápido).",
    )
    args = parser.parse_args()

    anos = [args.ano] if args.ano else ANOS

    print("=" * 60)
    print("  Observatório Casa José Mariano")
    print("  Câmara Municipal do Recife — Fetch de Dados")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)

    garantir_pasta()

    # ── Endpoint único ───────────────────────────────────────────────────────
    if args.endpoint:
        if args.endpoint in ENDPOINTS:
            fetch_simples(args.endpoint, ENDPOINTS[args.endpoint])
        else:
            fetch_por_ano(args.endpoint, ENDPOINTS_POR_ANO[args.endpoint], anos)
        gerar_resumo()
        return

    # ── Fetch completo ───────────────────────────────────────────────────────

    # 1. Endpoints simples
    for chave, endpoint in ENDPOINTS.items():
        dados = fetch_simples(chave, endpoint)

        # Enriquecimento de vereadores (pode ser lento — ~40 requests)
        if chave == "vereadores" and not args.sem_detalhes:
            items = dados.get("items", []) if dados else []
            if items:
                fetch_detalhes_vereadores(items)

        time.sleep(DELAY)

    # 2. Endpoints por ano
    for chave, endpoint in ENDPOINTS_POR_ANO.items():
        fetch_por_ano(chave, endpoint, anos)

    # 3. Proposições segmentadas por tipo
    fetch_materias_por_tipo(anos)

    # 4. Resumo final
    print("\n📊  Gerando resumo...")
    resumo = gerar_resumo()

    print("\n" + "=" * 60)
    print("  ✅  Fetch concluído!")
    print(f"  📁  Arquivos salvos em: ./{DATA_DIR}/")
    print(f"  📄  Total de arquivos: {len(resumo['arquivos'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()