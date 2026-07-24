import json
import os
import csv
import glob
import unicodedata
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

MESES_VERBA = [
    ("Jan", "Janeiro"),
    ("Fev", "Fevereiro"),
    ("Mar", "Março"),
    ("Abr", "Abril"),
    ("Mai", "Maio"),
    ("Jun", "Junho"),
    ("Jul", "Julho"),
    ("Ago", "Agosto"),
    ("Set", "Setembro"),
    ("Out", "Outubro"),
    ("Nov", "Novembro"),
    ("Dez", "Dezembro"),
]

NOMES_VERBA_ARQUIVO = {
    "aderaldo": "Aderaldo Pinto",
    "alcides": "Alcides Teixeira Neto",
    "alef": "Alef Collins",
    "andreza": "Andreza Romero",
    "carlos": "Carlos Muniz",
    "chico": "Chico Kiko",
    "cida": "Cida Pedrosa",
    "davi": "Davi Muniz",
    "douglas": "Douglas Brito Ativista",
    "eduardo_mota": "Eduardo Mota",
    "eduardo_moura": "Eduardo Moura",
    "eriberto": "Eriberto Rafael",
    "fabiano": "Fabiano Ferraz",
    "felipe_alecrim": "Felipe Alecrim",
    "felipe_francismar": "Felipe Francismar",
    "flavia": "Flávia de Nadegi",
    "fred": "Fred Ferreira",
    "gilberto": "Gilberto Alves",
    "gilson": "Gilson Machado Filho",
    "helio": "Hélio Guabiraba",
    "jairo": "Jairo Britto",
    "jo": "Jô Cavalcanti",
    "junior": "Júnior Bocão",
    "rubem": "Agora é Rubem",
}

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

def normalizar_chave(texto):
    return remover_acentos(str(texto or "")).upper().strip()

def obter_campo_normalizado(linha, nome_campo, padrao=""):
    alvo = normalizar_chave(nome_campo)
    for chave, valor in linha.items():
        if normalizar_chave(chave) == alvo:
            return valor
    return padrao

def formatar_data_br(data_iso):
    if not data_iso:
        return ""
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return data_iso

def limpar_valor_brasileiro(valor):
    texto = str(valor or "").strip()
    if not texto or texto == "-":
        return 0.0
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0

def arredondar_moeda(valor):
    return round(float(valor or 0), 2)

def extrair_periodo_remuneracao(caminho_arquivo):
    nome_base = os.path.basename(caminho_arquivo)
    partes = nome_base.replace(".csv", "").split("_")
    try:
        mes = int(partes[-2])
        ano = int(partes[-1])
        return {
            "mes": mes,
            "ano": ano,
            "periodo": f"{mes:02d}/{ano}"
        }
    except (ValueError, IndexError):
        return None

def chave_verba_arquivo(caminho_arquivo):
    nome = os.path.basename(caminho_arquivo).replace(".csv", "")
    return nome.replace("_verba_indenizatoria", "").strip("_")

def nome_verba_arquivo(chave):
    if chave in NOMES_VERBA_ARQUIVO:
        return NOMES_VERBA_ARQUIVO[chave]
    return " ".join(parte.capitalize() for parte in chave.split("_"))

def arquivos_verba_indenizatoria(ano):
    pastas = [
        os.path.join(DADOS_EXTRAS_DIR, f"verbas_indenizatorias_{ano}"),
        os.path.join(DADOS_EXTRAS_DIR, f"verbas_indenizatoras_{ano}"),
    ]
    arquivos = []
    for pasta in pastas:
        arquivos.extend(glob.glob(os.path.join(pasta, "*.csv")))
    return sorted(set(arquivos))

def carregar_verbas_indenizatorias(ano="2026"):
    registros = []
    for caminho_arquivo in arquivos_verba_indenizatoria(ano):
        chave = chave_verba_arquivo(caminho_arquivo)
        nome_vereador = nome_verba_arquivo(chave)
        meses_totais = {mes: 0.0 for mes, _ in MESES_VERBA}
        categorias = []
        total_vereador = 0.0

        try:
            with open(caminho_arquivo, mode="r", encoding="utf-8-sig", newline="") as f:
                leitor = csv.DictReader(f)
                for linha in leitor:
                    categoria = str(linha.get("Item", "")).strip()
                    if not categoria:
                        continue

                    valores_mes = {}
                    total_categoria = 0.0
                    for mes, _ in MESES_VERBA:
                        valor = limpar_valor_brasileiro(linha.get(mes, ""))
                        valores_mes[mes] = arredondar_moeda(valor)
                        meses_totais[mes] += valor
                        total_categoria += valor

                    total_vereador += total_categoria
                    categorias.append({
                        "categoria": categoria,
                        "total": arredondar_moeda(total_categoria),
                        "meses": valores_mes
                    })
        except Exception as e:
            print(f"Erro ao ler verba indenizatória {caminho_arquivo}: {e}")
            continue

        registros.append({
            "chave": chave,
            "nome": nome_vereador,
            "arquivo": os.path.basename(caminho_arquivo),
            "total": arredondar_moeda(total_vereador),
            "meses": {mes: arredondar_moeda(valor) for mes, valor in meses_totais.items()},
            "categorias": categorias
        })

    return registros

def resumir_verbas_indenizatorias(registros):
    total = 0.0
    categorias = {}
    meses = {mes: 0.0 for mes, _ in MESES_VERBA}

    for registro in registros:
        total += registro["total"]
        for mes, valor in registro["meses"].items():
            meses[mes] += valor
        for categoria in registro["categorias"]:
            nome = categoria["categoria"]
            categorias[nome] = categorias.get(nome, 0.0) + categoria["total"]

    return {
        "total": arredondar_moeda(total),
        "vereadores_com_dados": len(registros),
        "categorias": [
            {"categoria": nome, "total": arredondar_moeda(valor)}
            for nome, valor in sorted(categorias.items(), key=lambda item: item[1], reverse=True)
        ],
        "meses": [
            {"mes": mes, "nome": nome_mes, "total": arredondar_moeda(meses[mes])}
            for mes, nome_mes in MESES_VERBA
        ],
        "vereadores": [
            {
                "chave": registro["chave"],
                "nome": registro["nome"],
                "arquivo": registro["arquivo"],
                "total": registro["total"]
            }
            for registro in sorted(registros, key=lambda item: item["total"], reverse=True)
        ]
    }

def combina_verba_com_vereador(nome_vereador, registro):
    alvo = normalizar_chave(nome_vereador)
    if not alvo:
        return False

    nomes_possiveis = [
        normalizar_chave(registro["nome"]),
        normalizar_chave(registro["chave"].replace("_", " ")),
    ]
    for nome in nomes_possiveis:
        if nome and (nome in alvo or alvo in nome):
            return True
        partes = [p for p in nome.split() if len(p) > 2]
        if partes and all(parte in alvo for parte in partes):
            return True
    return False

def agregar_registros_verba(registros):
    resumo = resumir_verbas_indenizatorias(registros)
    categorias_detalhadas = {}

    for registro in registros:
        for categoria in registro["categorias"]:
            nome = categoria["categoria"]
            if nome not in categorias_detalhadas:
                categorias_detalhadas[nome] = {
                    "categoria": nome,
                    "total": 0.0,
                    "meses": {mes: 0.0 for mes, _ in MESES_VERBA}
                }
            categorias_detalhadas[nome]["total"] += categoria["total"]
            for mes, valor in categoria["meses"].items():
                categorias_detalhadas[nome]["meses"][mes] += valor

    categorias = []
    for categoria in categorias_detalhadas.values():
        categorias.append({
            "categoria": categoria["categoria"],
            "total": arredondar_moeda(categoria["total"]),
            "meses": {mes: arredondar_moeda(valor) for mes, valor in categoria["meses"].items()}
        })

    return {
        "total": resumo["total"],
        "meses": resumo["meses"],
        "categorias": sorted(categorias, key=lambda item: item["total"], reverse=True)
    }

def obter_status_suplente(vereador, status_config):
    nome = vereador.get("title", vereador.get("description", ""))
    descricao = vereador.get("description", "")
    suplentes = status_config.get("suplentes", {}) if isinstance(status_config, dict) else {}
    suplentes_por_nome = {normalizar_chave(k): v for k, v in suplentes.items()}

    status_manual = suplentes_por_nome.get(normalizar_chave(nome)) or suplentes_por_nome.get(normalizar_chave(descricao))
    mandatos = vereador.get("mandatos", [])
    mandato_suplente = None
    for mandato in mandatos:
        if str(mandato.get("id")) == "19" and normalizar_chave(mandato.get("natureza")) == "SUPLENTE":
            if not mandato_suplente or str(mandato.get("start", "")) > str(mandato_suplente.get("start", "")):
                mandato_suplente = mandato

    if not status_manual and not mandato_suplente:
        return None

    inicio = mandato_suplente.get("start", "") if mandato_suplente else ""
    fim = mandato_suplente.get("end", "") if mandato_suplente else ""
    titular = status_manual.get("titular_substituido", "") if status_manual else ""
    tag = status_manual.get("tag", "Suplente em exercício") if status_manual else "Suplente em exercício"

    observacao = tag
    periodo_texto = ""
    if inicio and fim:
        periodo_texto = f"{formatar_data_br(inicio)} a {formatar_data_br(fim)}"
        observacao = f"{tag} de {periodo_texto}"
    elif inicio:
        periodo_texto = f"desde {formatar_data_br(inicio)}"
        observacao = f"{tag} {periodo_texto}"

    if titular:
        observacao = f"{observacao}, substituindo {titular}."
    else:
        observacao = f"{observacao}."

    return {
        "tipo": "suplente",
        "tag": tag,
        "titular_substituido": titular,
        "inicio": inicio,
        "fim": fim,
        "periodo": periodo_texto,
        "observacao": observacao
    }

def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')

def normalizar_nome_pessoa(texto):
    texto = remover_acentos(str(texto or "")).upper()
    for caractere in ".,;-_/":
        texto = texto.replace(caractere, " ")
    return " ".join(texto.split())

def combinar_nomes(nome_perfil, nome_folha):
    n_p = normalizar_nome_pessoa(nome_perfil)
    n_f = normalizar_nome_pessoa(nome_folha)
    
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

def combinar_gabinete(nome_vereador, lotacao):
    nome_limpo = normalizar_nome_pessoa(nome_vereador)
    lotacao_limpa = normalizar_nome_pessoa(lotacao).replace("VER ", "").strip()
    if not nome_limpo or not lotacao_limpa:
        return False
    aliases_gabinete = {
        "ROMERINHO JATOBA": "ROMERO JATOBA CAVALCANTI NETO",
        "RONALDO LOPES": "ALEF COLLINS",
    }
    alias = aliases_gabinete.get(nome_limpo)
    if alias and alias in lotacao_limpa:
        return True
    if nome_limpo in lotacao_limpa or lotacao_limpa in nome_limpo:
        return True
    return combinar_nomes(nome_vereador, lotacao_limpa)

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
    periodos = []
    for caminho_arquivo in arquivos:
        periodo = extrair_periodo_remuneracao(caminho_arquivo)
        if periodo:
            periodos.append(periodo)
        try:
            with open(caminho_arquivo, mode="r", encoding="utf-8-sig") as f:
                leitor = csv.DictReader(f, delimiter=";")
                for linha in leitor:
                    bruto_str = linha.get("Total de Vantagens", "0")
                    if bruto_str.strip():
                        total_bruto += limpar_valor_brasileiro(bruto_str)
        except Exception as e:
            pass
    periodos = sorted(periodos, key=lambda item: (item["ano"], item["mes"]))
    return {
        "total": total_bruto,
        "periodo_inicial": periodos[0]["periodo"] if periodos else "",
        "periodo_final": periodos[-1]["periodo"] if periodos else "",
        "meses_carregados": len({item["periodo"] for item in periodos})
    }

@app.get("/stats/verba-indenizatoria")
def resumo_verba_indenizatoria(ano: str = "2026"):
    registros = carregar_verbas_indenizatorias(ano)
    resumo = resumir_verbas_indenizatorias(registros)
    return {
        "ano": ano,
        **resumo
    }

@app.get("/vereadores")
def listar_vereadores():
    dados = ler_json("vereadores_detalhados.json") or ler_json("vereadores.json")
    status_config = ler_json("vereadores_status.json")
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
        status_parlamentar = obter_status_suplente(v, status_config)
        items_formatados.append({
            "id": v.get("id"), "nome": nome, "partido": partido_sigla,
            "fotografia": foto_url, "comissoes": lista_comissoes_formatada,
            "telefone": v.get("telefone_gabinete", "Não informado"),
            "email": v.get("email", "Não informado"),
            "status_parlamentar": status_parlamentar
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
    historico_por_periodo = {}
    for caminho_arquivo in arquivos:
        periodo = extrair_periodo_remuneracao(caminho_arquivo)
        if not periodo:
            continue
        try:
            with open(caminho_arquivo, mode="r", encoding="utf-8-sig") as f:
                leitor = csv.DictReader(f, delimiter=";")
                for linha in leitor:
                    if combinar_nomes(nome_vereador, obter_campo_normalizado(linha, "Nome", "")):
                        chave = (periodo["ano"], periodo["mes"])
                        if chave not in historico_por_periodo:
                            historico_por_periodo[chave] = {
                                "periodo": periodo["periodo"],
                                "mes": periodo["mes"],
                                "ano": periodo["ano"],
                                "bruto": 0.0,
                                "liquido": 0.0
                            }
                        historico_por_periodo[chave]["bruto"] += limpar_valor_brasileiro(
                            obter_campo_normalizado(linha, "Total de Vantagens", 0)
                        )
                        historico_por_periodo[chave]["liquido"] += limpar_valor_brasileiro(
                            obter_campo_normalizado(linha, "Valor Liquido", 0)
                        )
        except: pass
    return sorted(historico_por_periodo.values(), key=lambda x: (x["ano"], x["mes"]))

@app.get("/vereadores/{vereador_id}/verba-indenizatoria")
def obter_verba_indenizatoria_vereador(vereador_id: str, nome_vereador: str = "", ano: str = "2026"):
    registros = carregar_verbas_indenizatorias(ano)
    registros_vereador = [
        registro for registro in registros
        if combina_verba_com_vereador(nome_vereador, registro)
    ]
    agregado = agregar_registros_verba(registros_vereador)
    return {
        "ano": ano,
        "vereador_id": vereador_id,
        "nome_vereador": nome_vereador,
        "arquivos": [registro["arquivo"] for registro in registros_vereador],
        **agregado
    }

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

# ==========================================
# NOVO ENDPOINT: CUSTO DE COMISSIONADOS
# ==========================================
@app.get("/vereadores/{vereador_id}/comissionados")
def obter_comissionados_gabinete(vereador_id: str, nome_vereador: str):
    folder = os.path.join(DADOS_EXTRAS_DIR, "remuneracao_comissionados")
    padrao = os.path.join(folder, "**", "remuneracao_gabinete_*.csv")
    arquivos = glob.glob(padrao, recursive=True)
    
    if not arquivos:
        return {"total": 0, "servidores": [], "periodo": "N/A"}

    # Organiza os arquivos para pegar o mês/ano mais recente
    def extrair_data(p):
        fname = os.path.basename(p).replace(".csv", "")
        partes = fname.split("_")
        try:
            mes = int(partes[-2])
            ano = int(partes[-1])
            return (ano, mes)
        except:
            return (0, 0)

    arquivos.sort(key=extrair_data, reverse=True)
    recente = arquivos[0]
    ano, mes = extrair_data(recente)
    periodo_str = f"{str(mes).zfill(2)}/{ano}" if ano > 0 else "N/A"
    
    total = 0.0
    servidores = []
    nome_ver_limpo = remover_acentos(nome_vereador).upper().strip()

    try:
        with open(recente, mode="r", encoding="utf-8-sig") as f:
            leitor = csv.DictReader(f, delimiter=";")
            for linha in leitor:
                # No CSV dos comissionados, a coluna se chama "Lotação Secretaria/Diretoria"
                lotacao = remover_acentos(
                    obter_campo_normalizado(linha, "Lotação Secretaria/Diretoria", "")
                ).upper().strip()
                
                # Se o nome do vereador está na lotação (mesmo com "VER." na frente)
                if combinar_gabinete(nome_vereador, lotacao):
                    bruto_str = linha.get("Total de Vantagens", "0").replace(",", ".")
                    try:
                        bruto = float(bruto_str)
                    except:
                        bruto = 0.0
                        
                    if bruto > 0:
                        total += bruto
                        servidores.append({
                            "nome": linha.get("Nome", "Desconhecido").strip(),
                            "bruto": bruto,
                            "cargo": linha.get("Função", linha.get("Cargo", "N/A")).strip()
                        })
    except Exception as e:
        print(f"Erro ao ler comissionados: {e}")

    return {
        "total": total,
        "periodo": periodo_str,
        "servidores": sorted(servidores, key=lambda x: x["bruto"], reverse=True)
    }

if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
