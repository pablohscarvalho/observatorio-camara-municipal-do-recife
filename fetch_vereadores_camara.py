"""
Baixa a remuneracao dos vereadores da Camara Municipal do Recife.

Fonte:
https://transparenciacamara.recife.pe.gov.br/codigos/web/camara/remuneracaoServidores.php

Uso:
    python fetch_vereadores_camara.py --ano 2026 --meses 04 05 06
    python fetch_vereadores_camara.py --ano 2026 --ate-mes 06
"""

import argparse
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = (
    "https://transparenciacamara.recife.pe.gov.br/codigos/web/camara/"
    "remuneracaoServerProcessing.php"
)

CSV_HEADERS = [
    "CPF",
    "Matricula",
    "Nome",
    "Categoria",
    "Cargo",
    "Funcao",
    "Total de Vantagens",
    "Descontos Totais",
    "Valor Liquido",
    "Lotacao Secretaria/Diretoria",
    "Data de Desligamento",
    "Data de Admissao",
    "Carga Horaria",
]


def valor_brasileiro_para_decimal(valor):
    return str(valor or "").replace(".", "").replace(",", ".")


def pasta_saida(ano):
    for pasta in (Path("dados_extras") / f"remuneração_vereadores_{ano}",):
        if pasta.exists():
            return pasta
    return Path("dados_extras") / f"remuneração_vereadores_{ano}"


def baixar_mes(ano, mes):
    params = {
        "ano": str(ano),
        "mes": f"{int(mes):02d}",
        "orgao": "CAMARA MUNICIPAL DO RECIFE",
        "nome": "",
        "cpf": "",
        "matricula": "",
        "categoria": "VEREADORES",
        "cargo": "VEREADOR",
        "iDisplayStart": "0",
        "iDisplayLength": "5000",
        "sEcho": "1",
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=45) as resposta:
        payload = json.loads(resposta.read().decode("utf-8-sig"))

    linhas = []
    for item in payload.get("aaData", []):
        linhas.append(
            {
                "CPF": item[1] or "",
                "Matricula": item[2] or "",
                "Nome": item[3] or "",
                "Categoria": item[4] or "",
                "Cargo": item[5] or "",
                "Funcao": item[6] or "",
                "Total de Vantagens": valor_brasileiro_para_decimal(item[7]),
                "Descontos Totais": valor_brasileiro_para_decimal(item[8]),
                "Valor Liquido": valor_brasileiro_para_decimal(item[9]),
                "Lotacao Secretaria/Diretoria": item[10] or "",
                "Data de Desligamento": item[11] or "",
                "Data de Admissao": item[12] or "",
                "Carga Horaria": item[13] or "",
            }
        )
    return linhas


def salvar_csv(ano, mes, linhas):
    pasta = pasta_saida(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"remuneracao_vereadores_{int(mes):02d}_{ano}.csv"
    with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=CSV_HEADERS, delimiter=";")
        writer.writeheader()
        writer.writerows(linhas)
    return caminho


def main():
    parser = argparse.ArgumentParser(
        description="Baixa remuneracao dos vereadores da Camara do Recife."
    )
    parser.add_argument("--ano", type=int, default=2026)
    parser.add_argument("--meses", nargs="*", help="Meses especificos, ex: 04 05 06")
    parser.add_argument("--ate-mes", type=int, help="Baixa de janeiro ate este mes.")
    args = parser.parse_args()

    if args.meses:
        meses = [int(mes) for mes in args.meses]
    elif args.ate_mes:
        meses = list(range(1, args.ate_mes + 1))
    else:
        meses = [1, 2, 3, 4, 5, 6]

    for mes in meses:
        linhas = baixar_mes(args.ano, mes)
        caminho = salvar_csv(args.ano, mes, linhas)
        print(f"{caminho}: {len(linhas)} registros")


if __name__ == "__main__":
    main()
