"""
scraper_financeiro.py
=====================
Scraper dos dados financeiros do Portal de Transparência
da Câmara Municipal do Recife (Casa José Mariano).

O portal é uma SPA React — o conteúdo das tabelas é renderizado via
JavaScript após o carregamento inicial. Por isso usamos Playwright,
que abre um navegador real (headless) e espera o conteúdo aparecer.

Dados coletados:
  - Verba indenizatória por vereador (por ano)
  - Despesas totais
  - Detalhamento por credor/empenho
  - Contratos
  - Diárias e viagens
  - Duodécimo (receita)
  - Remuneração de servidores

Instalação:
    pip install playwright beautifulsoup4
    playwright install chromium

Uso:
    python scraper_financeiro.py                  # coleta tudo do ano atual
    python scraper_financeiro.py --ano 2024        # ano específico
    python scraper_financeiro.py --modulo verbas   # só um módulo
    python scraper_financeiro.py --visivel         # abre o navegador (debug)
"""

import asyncio
import json
import os
import re
import time
import argparse
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError:
    raise SystemExit(
        "Playwright não instalado.\n"
        "Execute: pip install playwright && playwright install chromium"
    )

# ── Configuração ──────────────────────────────────────────────────────────────

PORTAL   = "https://transparencia.recife.pe.leg.br"
DATA_DIR = "data"
TIMEOUT  = 50_000   # ms — tempo máximo por operação
DELAY    = 5      # segundos entre páginas

ANOS_VERBAS    = [2024, 2025, 2026]
ANOS_DIARIAS   = [2024, 2025, 2026]

URLS = {
    "verbas":       PORTAL + "/legislativo/verba-indenizatoria/{ano}",
    "despesas":     PORTAL + "/orcamento-financas/despesas/despesas-totais",
    "empenhos":     PORTAL + "/orcamento-financas/despesas/detalhamento-por-credor-empenho-1",
    "pagamentos":   PORTAL + "/orcamento-financas/despesas/ordem-cronologica-de-pagamentos",
    "contratos":    PORTAL + "/licitacoes-contratos/contratos",
    "licitacoes":   PORTAL + "/licitacoes-contratos/licitacoes/informacoes-gerais",
    "diarias":      PORTAL + "/rh/gastos-de-viagens-e-diarias/{ano}",
    "remuneracao":  PORTAL + "/rh/servidores/remuneracao",
    "duodecimo":    PORTAL + "/orcamento-financas/receitas/duodecimo",
    "fornecedores": PORTAL + "/licitacoes-contratos/fornecedores",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def garantir_pasta():
    os.makedirs(DATA_DIR, exist_ok=True)


def salvar(nome: str, dados):
    caminho = os.path.join(DATA_DIR, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    kb = os.path.getsize(caminho) / 1024
    print(f"  ✅  {caminho}  ({kb:.1f} KB,  {len(dados) if isinstance(dados, list) else dados.get('total', '?')} registros)")


def limpar_valor(texto: str) -> Optional[float]:
    """Converte 'R$ 1.234,56' ou '1.234,56' em float."""
    if not texto:
        return None
    limpo = re.sub(r"[R$\s]", "", texto).replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None


def extrair_tabela(html: str, seletor_tabela: str = "table") -> list[dict]:
    """
    Recebe HTML já renderizado, localiza a primeira tabela e
    retorna lista de dicts usando o <thead> como chave.
    """
    soup = BeautifulSoup(html, "html.parser")
    tabela = soup.select_one(seletor_tabela)
    if not tabela:
        return []

    # Cabeçalhos
    cabecalhos = []
    thead = tabela.find("thead")
    if thead:
        cabecalhos = [th.get_text(strip=True) for th in thead.find_all("th")]
    if not cabecalhos:
        primeira_tr = tabela.find("tr")
        if primeira_tr:
            cabecalhos = [td.get_text(strip=True) for td in primeira_tr.find_all(["td", "th"])]

    # Linhas
    tbody = tabela.find("tbody") or tabela
    linhas = []
    for tr in tbody.find_all("tr"):
        celulas = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if not any(celulas):
            continue
        if cabecalhos and len(celulas) == len(cabecalhos):
            linhas.append(dict(zip(cabecalhos, celulas)))
        elif celulas:
            linhas.append({"_cols": celulas})

    return linhas


async def aguardar_tabela(page, seletor: str = "table", timeout: int = TIMEOUT):
    """Espera a tabela aparecer na página."""
    try:
        await page.wait_for_selector(seletor, timeout=timeout)
        return True
    except PWTimeout:
        print(f"  ⚠️   Tabela '{seletor}' não apareceu em {timeout}ms")
        return False


async def rolar_ate_fim(page):
    """Rola a página até o fim para forçar carregamento lazy."""
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(0.5)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(0.5)


# ── Scrapers individuais ──────────────────────────────────────────────────────

async def scrape_verbas(page, ano: int) -> list[dict]:
    """Verba indenizatória por vereador."""
    url = URLS["verbas"].format(ano=ano)
    print(f"  → verba indenizatória {ano}: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    await rolar_ate_fim(page)
    html = await page.content()
    linhas = extrair_tabela(html)

    # Normaliza os campos de valor
    resultado = []
    for row in linhas:
        item = {"ano": ano, **row}
        # Tenta converter qualquer campo que parece valor monetário
        for chave, val in item.items():
            if isinstance(val, str) and ("R$" in val or re.match(r"^\d{1,3}(\.\d{3})*,\d{2}$", val.strip())):
                item[chave + "_num"] = limpar_valor(val)
        resultado.append(item)

    return resultado


async def scrape_despesas(page) -> list[dict]:
    """Despesas totais — tabela principal."""
    url = URLS["despesas"]
    print(f"  → despesas totais: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    await rolar_ate_fim(page)
    html = await page.content()
    linhas = extrair_tabela(html)

    for row in linhas:
        for chave in list(row.keys()):
            if isinstance(row[chave], str):
                v = limpar_valor(row[chave])
                if v is not None:
                    row[chave + "_num"] = v
    return linhas


async def scrape_empenhos(page) -> list[dict]:
    """Detalhamento por credor / empenho."""
    url = URLS["empenhos"]
    print(f"  → empenhos: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    # Tenta clicar em "próxima página" se existir paginação
    registros = []
    pagina = 1
    while True:
        await rolar_ate_fim(page)
        html = await page.content()
        linhas = extrair_tabela(html)
        registros.extend(linhas)
        print(f"    página {pagina}: {len(linhas)} linhas")

        # Verifica botão "próxima"
        proximo = page.locator("button[aria-label='próxima página'], button:has-text('Próximo'), a:has-text('»')")
        count = await proximo.count()
        if count == 0:
            break
        try:
            await proximo.first.click()
            await asyncio.sleep(DELAY)
            pagina += 1
            if pagina > 20:  # limite de segurança
                break
        except Exception:
            break

    return registros


async def scrape_contratos(page) -> list[dict]:
    """Contratos — lista paginada."""
    url = URLS["contratos"]
    print(f"  → contratos: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    registros = []
    pagina = 1
    while True:
        await rolar_ate_fim(page)
        html = await page.content()
        linhas = extrair_tabela(html)
        registros.extend(linhas)
        print(f"    página {pagina}: {len(linhas)} contratos")

        proximo = page.locator("button[aria-label='próxima página'], li.next > a, button:has-text('Próximo')")
        count = await proximo.count()
        if count == 0:
            break
        disabled = await proximo.first.get_attribute("disabled")
        if disabled is not None:
            break
        try:
            await proximo.first.click()
            await asyncio.sleep(DELAY)
            pagina += 1
            if pagina > 50:
                break
        except Exception:
            break

    return registros


async def scrape_diarias(page, ano: int) -> list[dict]:
    """Viagens e diárias por ano."""
    url = URLS["diarias"].format(ano=ano)
    print(f"  → diárias {ano}: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    await rolar_ate_fim(page)
    html = await page.content()
    linhas = extrair_tabela(html)
    for row in linhas:
        row["ano"] = ano
    return linhas


async def scrape_remuneracao(page) -> list[dict]:
    """Remuneração de servidores."""
    url = URLS["remuneracao"]
    print(f"  → remuneração servidores: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    await rolar_ate_fim(page)
    html = await page.content()
    return extrair_tabela(html)


async def scrape_duodecimo(page) -> list[dict]:
    """Duodécimo — repasse mensal."""
    url = URLS["duodecimo"]
    print(f"  → duodécimo: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    await rolar_ate_fim(page)
    html = await page.content()
    linhas = extrair_tabela(html)
    for row in linhas:
        for chave in list(row.keys()):
            v = limpar_valor(str(row[chave]))
            if v is not None:
                row[chave + "_num"] = v
    return linhas


async def scrape_licitacoes(page) -> list[dict]:
    """Licitações — informações gerais."""
    url = URLS["licitacoes"]
    print(f"  → licitações: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    await rolar_ate_fim(page)
    html = await page.content()
    return extrair_tabela(html)


async def scrape_fornecedores(page) -> list[dict]:
    """Fornecedores credenciados."""
    url = URLS["fornecedores"]
    print(f"  → fornecedores: {url}")
    await page.goto(url, wait_until="networkidle")
    await asyncio.sleep(DELAY)

    ok = await aguardar_tabela(page)
    if not ok:
        return []

    await rolar_ate_fim(page)
    html = await page.content()
    return extrair_tabela(html)


# ── Orquestrador principal ────────────────────────────────────────────────────

MODULOS = {
    "verbas":       "verba indenizatória",
    "despesas":     "despesas totais",
    "empenhos":     "empenhos por credor",
    "contratos":    "contratos",
    "diarias":      "diárias e viagens",
    "remuneracao":  "remuneração servidores",
    "duodecimo":    "duodécimo",
    "licitacoes":   "licitações",
    "fornecedores": "fornecedores",
}


async def run(modulo: Optional[str], ano: int, visivel: bool):
    garantir_pasta()

    print("=" * 60)
    print("  Observatório Casa José Mariano — Scraper Financeiro")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  |  ano={ano}")
    print("=" * 60)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not visivel)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (compatible; ObservatorioJoseMariano/1.0)",
            locale="pt-BR",
        )
        page = await context.new_page()

        # Bloqueia recursos desnecessários (imagens, fontes) para ser mais rápido
        await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}", lambda r: r.abort())

        def deve_rodar(nome):
            return modulo is None or modulo == nome

        # 1. Verba indenizatória (por ano)
        if deve_rodar("verbas"):
            print("\n🔄  Verba indenizatória...")
            verbas_todas = []
            anos_alvo = ANOS_VERBAS if modulo is None else [ano]
            for a in anos_alvo:
                rows = await scrape_verbas(page, a)
                verbas_todas.extend(rows)
                time.sleep(0.5)
            envelope = {
                "total": len(verbas_todas),
                "anos": anos_alvo,
                "gerado_em": datetime.now().isoformat(),
                "items": verbas_todas,
            }
            salvar("verbas_indenizatorias.json", envelope)

        # 2. Despesas totais
        if deve_rodar("despesas"):
            print("\n🔄  Despesas totais...")
            rows = await scrape_despesas(page)
            salvar("despesas_totais.json", {"total": len(rows), "gerado_em": datetime.now().isoformat(), "items": rows})

        # 3. Empenhos por credor
        if deve_rodar("empenhos"):
            print("\n🔄  Empenhos por credor...")
            rows = await scrape_empenhos(page)
            salvar("empenhos.json", {"total": len(rows), "gerado_em": datetime.now().isoformat(), "items": rows})

        # 4. Contratos
        if deve_rodar("contratos"):
            print("\n🔄  Contratos...")
            rows = await scrape_contratos(page)
            salvar("contratos.json", {"total": len(rows), "gerado_em": datetime.now().isoformat(), "items": rows})

        # 5. Diárias e viagens
        if deve_rodar("diarias"):
            print("\n🔄  Diárias e viagens...")
            diarias_todas = []
            anos_alvo = ANOS_DIARIAS if modulo is None else [ano]
            for a in anos_alvo:
                rows = await scrape_diarias(page, a)
                diarias_todas.extend(rows)
                time.sleep(0.5)
            salvar("diarias_viagens.json", {"total": len(diarias_todas), "gerado_em": datetime.now().isoformat(), "items": diarias_todas})

        # 6. Remuneração de servidores
        if deve_rodar("remuneracao"):
            print("\n🔄  Remuneração de servidores...")
            rows = await scrape_remuneracao(page)
            salvar("remuneracao_servidores.json", {"total": len(rows), "gerado_em": datetime.now().isoformat(), "items": rows})

        # 7. Duodécimo
        if deve_rodar("duodecimo"):
            print("\n🔄  Duodécimo...")
            rows = await scrape_duodecimo(page)
            salvar("duodecimo.json", {"total": len(rows), "gerado_em": datetime.now().isoformat(), "items": rows})

        # 8. Licitações
        if deve_rodar("licitacoes"):
            print("\n🔄  Licitações...")
            rows = await scrape_licitacoes(page)
            salvar("licitacoes.json", {"total": len(rows), "gerado_em": datetime.now().isoformat(), "items": rows})

        # 9. Fornecedores
        if deve_rodar("fornecedores"):
            print("\n🔄  Fornecedores...")
            rows = await scrape_fornecedores(page)
            salvar("fornecedores.json", {"total": len(rows), "gerado_em": datetime.now().isoformat(), "items": rows})

        await browser.close()

    print("\n" + "=" * 60)
    print("  ✅  Scraping financeiro concluído!")
    print(f"  📁  Arquivos salvos em: ./{DATA_DIR}/")
    print("=" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scraper financeiro do Portal de Transparência da Câmara do Recife"
    )
    parser.add_argument(
        "--ano", type=int, default=datetime.now().year,
        help="Ano de referência (padrão: ano atual)"
    )
    parser.add_argument(
        "--modulo", choices=list(MODULOS.keys()),
        help="Rodar somente um módulo específico"
    )
    parser.add_argument(
        "--visivel", action="store_true",
        help="Abre o navegador visível (útil para debug)"
    )
    args = parser.parse_args()

    if args.modulo:
        print(f"Modo: somente módulo '{args.modulo}' — {MODULOS[args.modulo]}")

    asyncio.run(run(args.modulo, args.ano, args.visivel))


if __name__ == "__main__":
    main()