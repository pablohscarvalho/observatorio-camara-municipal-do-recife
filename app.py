import json
import os
import csv
import glob
import unicodedata
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import zipfile

app = FastAPI(title="Observatório Casa José Mariano")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MAPEAMENTO DE PASTAS (Baseado na sua imagem) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DADOS_EXTRAS_DIR = os.path.join(BASE_DIR, "dados_extras")

def ler_json(nome_arquivo: str):
    """Procura o JSON ou o ZIP na pasta 'data' ou solto na raiz do projeto"""
    
    caminho_data = os.path.join(DATA_DIR, nome_arquivo)
    caminho_raiz = os.path.join(BASE_DIR, nome_arquivo)
    
    # 1. Tenta ler o JSON normal (ex: vereadores.json que deve estar em data)
    if os.path.exists(caminho_data):
        with open(caminho_data, "r", encoding="utf-8") as f: return json.load(f)
    if os.path.exists(caminho_raiz):
        with open(caminho_raiz, "r", encoding="utf-8") as f: return json.load(f)

    # 2. Tenta ler o ZIP (ex: materias_por_tipo.zip que está na raiz segundo a foto)
    nome_zip = nome_arquivo.replace('.json', '.zip')
    caminho_zip_data = os.path.join(DATA_DIR, nome_zip)
    caminho_zip_raiz = os.path.join(BASE_DIR, nome_zip)

    zip_alvo = None
    if os.path.exists(caminho_zip_raiz):
        zip_alvo = caminho_zip_raiz
    elif os.path.exists(caminho_zip_data):
        zip_alvo = caminho_zip_data

    if zip_alvo:
        try:
            with zipfile.ZipFile(zip_alvo, 'r') as z:
                for nome_interno in z.namelist():
                    if nome_arquivo in nome_interno:
                        with z.open(nome_interno) as f:
                            return json.load(f)
        except Exception as e:
            print(f"Erro ao ler zip: {e}")
            
    return {}

def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def combinar_nomes(nome_perfil, nome_folha):
    n_p = remover_acentos(nome_perfil).upper().strip()
    n_f = remover_acentos(nome_folha).upper().strip()
    
    prefixos = ["PROFESSORA ", "PROFESSOR ", "PASTOR ", "IRMA ", "DR. ", "DRA. "]
    for p in prefixos:
        n_p = n_p.replace(p, "")
    n_p = n_p.strip()
    
    apelidos_excecoes = {
        "RUBEM": "RUBEM RODRIGUES DA SILVA",
        "ERIBERTO RAFAEL": "RAFAEL ACIOLI MEDEIROS",
        "ZE NETO": "JOSE LOURENCO DE SOBRAL NETO",
        "JUNIOR DE CLETO": "CLETO CORREIA LIMA JUNIOR",
        "ROMERINHO JATOBA": "ROMERO JATOBA C NETO",
        "WILTON BRITO": "JOSE WILTON DE B CAVALCANTI",
        "CIDA PEDROSA": "MARIA APARECIDA P BEZERRA",
        "JUNIOR BOCAO": "INALDO GERSON P FREIRES",
        "FRED FERREIRA": "FREDERICO M DE M S FERREIRA",
        "JO CAVALCANTI": "MARIA JOSELITA P CAVALCANTI",
        "KARI SANTOS": "KARINA DA SILVA SANTOS",
        "CHICO KIKO": "FRANCISCO", 
        "DODUEL VARELA": "EDIVALDO"
    }
    
    for apelido, nome_real in apelidos_excecoes.items():
        if apelido in n_p and nome_real in n_f:
            return True

    if n_p in n_f: return True
    partes_p = n_p.split()
    partes_f = n_f.split()
    if not partes_p or not partes_f: return False
    if partes_p[0] == partes_f[0]:
        if partes_p[0] in ["ALCIDES", "EDUARDO", "CARLOS", "RODRIGO", "ANA", "JOSE", "MARIA", "JOAO", "LUIZ"]:
            return any(sobrenome in partes_f for sobrenome in partes_p[1:])
        return True 
    return False

@app.get("/stats")
def resumo_geral():
    vereadores_data = ler_json("vereadores_detalhados.json") or ler_json("vereadores.json")
    materias_tipo = ler_json("materias_por_tipo.json")
    
    lista_vereadores = vereadores_data.get("items", [])
    partidos = set()
    por_partido = {}
    
    for v in lista_vereadores:
        dado_partido = v.get("partido", "Sem Partido")
        if isinstance(dado_partido, list) and len(dado_partido) > 0:
            dado_partido = dado_partido[0]
        if isinstance(dado_partido, dict):
            sigla = dado_partido.get("token", dado_partido.get("title", "Sem Partido"))
        else:
            sigla = str(dado_partido).strip()
        if not sigla or sigla == "None" or sigla == "{}":
            sigla = "Sem Partido"
        partidos.add(sigla)
        por_partido[sigla] = por_partido.get(sigla, 0) + 1
        
    total_2026 = 0
    tipos_dict = materias_tipo.get("tipos", {})
    for nome_tipo, lista_materias in tipos_dict.items():
        for m in lista_materias:
            if "2026" in str(m.get("date", "")):
                total_2026 += 1
        
    return {
        "gerado_em": datetime.now().isoformat(),
        "vereadores": {
            "total": len(lista_vereadores),
            "partidos": len(partidos),
            "por_partido": por_partido
        },
        "proposicoes": {
            "total_2026": total_2026
        }
    }

@app.get("/stats/remuneracao")
def resumo_remuneracao_total(ano: str = "2026"):
    padrao = os.path.join(DADOS_EXTRAS_DIR, "**", f"remuneracao_vereadores_*_{ano}.csv")
    arquivos = glob.glob(padrao, recursive=True)
    total_bruto = 0.0
    for caminho_arquivo in arquivos:
        try:
            with open(caminho_arquivo, mode="r", encoding="utf-8-sig") as f:
                leitor = csv.DictReader(f, delimiter=";")
                for linha in leitor:
                    bruto_str = linha.get("Total de Vantagens", "0")
                    if bruto_str.strip():
                        total_bruto += float(bruto_str)
        except Exception as e:
            pass
    return {"total": total_bruto}

@app.get("/vereadores")
def listar_vereadores():
    dados = ler_json("vereadores_detalhados.json") or ler_json("vereadores.json")
    items_originais = dados.get("items", [])
    items_formatados = []
    for v in items_originais:
        nome = v.get("title", v.get("description", "Vereador Sem Nome"))
        partido_dado = v.get("partido")
        partido_sigla = "Sem Partido"
        if isinstance(partido_dado, list) and len(partido_dado) > 0:
             if isinstance(partido_dado[0], dict):
                 partido_sigla = partido_dado[0].get("token", partido_dado[0].get("title", "Sem Partido"))
        elif isinstance(partido_dado, dict):
             partido_sigla = partido_dado.get("token", partido_dado.get("title", "Sem Partido"))
        elif isinstance(partido_dado, str):
             partido_sigla = partido_dado
        foto_url = v.get("url_foto", "")
        if not foto_url:
            imagem_dado = v.get("image", [])
            if isinstance(imagem_dado, list) and len(imagem_dado) > 0 and isinstance(imagem_dado[0], dict):
                foto_url = imagem_dado[0].get("download", "")
        comissoes_dado = v.get("comissoes", [])
        lista_comissoes_formatada = [c.get("comissao", "") for c in comissoes_dado if isinstance(c, dict) and c.get("comissao")]
        items_formatados.append({
            "id": v.get("id"), "nome": nome, "partido": partido_sigla,
            "fotografia": foto_url, "comissoes": lista_comissoes_formatada,
            "telefone": v.get("telefone_gabinete", "Não informado"),
            "email": v.get("email", "Não informado")
        })
    return {"items": items_formatados}

@app.get("/vereadores/{vereador_id}/proposicoes")
def listar_proposicoes_vereador(vereador_id: str, nome_vereador: str = "", ano: str = "2026"):
    dados = ler_json("materias_por_tipo.json")
    tipos = dados.get("tipos", {})
    total_prop = 0
    lista_proposicoes = []
    contagem_tipos = {}
    for tipo_nome, materias in tipos.items():
        for m in materias:
            if ano in str(m.get("date", "")):
                autores = m.get("authorship", [])
                for autor in autores:
                    if nome_vereador.upper() in str(autor.get("title", "")).upper():
                        total_prop += 1
                        contagem_tipos[tipo_nome] = contagem_tipos.get(tipo_nome, 0) + 1
                        arquivos = m.get("file", [])
                        link_pdf = arquivos[0].get("download", "") if arquivos and isinstance(arquivos[0], dict) else ""
                        lista_proposicoes.append({
                            "tipo": tipo_nome, "titulo": m.get("title", "Sem título"),
                            "descricao": m.get("description", "").replace("\r\n", " ").strip(),
                            "data": m.get("date", ""), "link": link_pdf
                        })
                        break
    lista_proposicoes.sort(key=lambda x: x["data"], reverse=True)
    return {"total": total_prop, "resumo_tipos": contagem_tipos, "items": lista_proposicoes}

@app.get("/vereadores/{vereador_id}/remuneracao")
def obter_historico_remuneracao(vereador_id: str, nome_vereador: str):
    padrao = os.path.join(DADOS_EXTRAS_DIR, "**", "remuneracao_vereadores_*.csv")
    arquivos = glob.glob(padrao, recursive=True)
    historico = []
    for caminho_arquivo in arquivos:
        nome_base = os.path.basename(caminho_arquivo)
        partes = nome_base.replace(".csv", "").split("_")
        mes_ano = f"{partes[-2]}/{partes[-1]}"
        try:
            with open(caminho_arquivo, mode="r", encoding="utf-8-sig") as f:
                leitor = csv.DictReader(f, delimiter=";")
                for linha in leitor:
                    if combinar_nomes(nome_vereador, linha.get("Nome", "")):
                        historico.append({
                            "periodo": mes_ano, "bruto": float(linha.get("Total de Vantagens", 0)),
                            "liquido": float(linha.get("Valor Líquido", 0))
                        })
        except: pass
    return sorted(historico, key=lambda x: (x['periodo'].split('/')[1], x['periodo'].split('/')[0]))

@app.get("/proposicoes/tipos")
def listar_tipos_proposicoes(ano: str = "2025"):
    dados = ler_json("materias_por_tipo.json")
    tipos_dict = dados.get("tipos", {})
    resultado = []
    for nome_tipo, lista_materias in tipos_dict.items():
        qtd_no_ano = sum(1 for m in lista_materias if ano in str(m.get("date", "")))
        if qtd_no_ano > 0:
            resultado.append({"tipo": nome_tipo, "count": qtd_no_ano})
    resultado.sort(key=lambda x: x["count"], reverse=True)
    return {"tipos": resultado}