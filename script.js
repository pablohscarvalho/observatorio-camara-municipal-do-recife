const API_BASE =
    window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost"
        ? "http://127.0.0.1:8001"
        : "https://observatorio-camara-municipal-do-recife-1.onrender.com";

let chartSalarioInstance = null;
let chartPartidosInstance = null;
let chartVerbaCategoriasInstance = null;
let chartVerbaVereadorMesesInstance = null;

let historicoSalarioGlobal = [];
let vereadoresGlobal = [];
let proposicoesVereadorGlobal = []; 
let filtroPartidoAtual = null;
let filtroGrupoPoliticoAtual = null;
let dadosVerbaDashboardGlobal = null;
let verbaFiltroRequestId = 0;

function normalizarTexto(valor) {
    return String(valor || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toUpperCase();
}

function obterGrupoPolitico(nomePartido) {
    const p = normalizarTexto(nomePartido);
    if (p.includes("PSB") || p === "PT" || p.includes("PCDOB") || p.includes("PV") ||
        p.includes("MDB") || p === "REP" || p.includes("REPUBLICANOS") || p.includes("AVANTE") ||
        p.includes("PRD") || p.includes("PT, PCDOB, PV") || p.includes("FEDERACAO")) {
        return 'governo';
    }
    if (p.includes("PL") || p.includes("NOVO") || p.includes("PP") ||
        p.includes("PODEMOS") || p.includes("PSD") || p.includes("PSOL")) {
        return 'oposicao';
    }
    return 'neutro';
}

function obterCorDoPartido(nomePartido) {
    const grupo = obterGrupoPolitico(nomePartido);
    if (grupo === 'governo') return '#10b981';
    if (grupo === 'oposicao') return '#f43f5e';
    return '#94a3b8';
}

function escaparHtml(valor) {
    return String(valor ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function loadDashboard() {
    try {
        const resStats = await fetch(`${API_BASE}/stats`);
        const stats = await resStats.json();

        document.getElementById('total-proposicoes').innerText = stats.proposicoes?.total_2026 || 0;
        const labelProp = document.getElementById('total-proposicoes').previousElementSibling;
        if (labelProp) labelProp.innerText = "Proposições Protocoladas (2026)";

        document.getElementById('total-vereadores').innerText = stats.vereadores?.total || 0;
        document.getElementById('total-partidos').innerText = stats.vereadores?.partidos || 0;

        const dadosPartidos = stats.vereadores?.por_partido || {};
        const partidosOrdenados = Object.entries(dadosPartidos).sort((a, b) => b[1] - a[1]);
        const labelsPartidos = partidosOrdenados.map(([partido]) => partido);
        const dataPartidos = partidosOrdenados.map(([, total]) => total);
        const backgroundColors = labelsPartidos.map(p => obterCorDoPartido(p));

        if (chartPartidosInstance) chartPartidosInstance.destroy();

        chartPartidosInstance = new Chart(document.getElementById('chartPartidos'), {
            type: 'bar',
            data: {
                labels: labelsPartidos,
                datasets: [{
                    label: 'Qtd de Vereadores',
                    data: dataPartidos,
                    backgroundColor: backgroundColors,
                    borderColor: backgroundColors,
                    borderWidth: 1,
                    borderRadius: 8,
                    barThickness: 18
                }]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false,
                indexAxis: 'y',
                layout: { padding: { right: 10 } },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.parsed.x} vereador(es)`
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { precision: 0, color: '#64748b' },
                        grid: { color: 'rgba(148, 163, 184, 0.2)' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#334155', font: { weight: 700 } }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const labelClicado = chartPartidosInstance.data.labels[index];
                        
                        if (filtroPartidoAtual === labelClicado) {
                            limparFiltroPartido();
                        } else {
                            filtroPartidoAtual = labelClicado;
                            filtroGrupoPoliticoAtual = null;
                            renderizarGradeVereadores();
                        }
                    }
                }
            }
        });

        try {
            const resRemTotal = await fetch(`${API_BASE}/stats/remuneracao?ano=2026`);
            if (resRemTotal.ok) {
                const dadosRemTotal = await resRemTotal.json();
                document.getElementById('total-verbas').innerText = formatarMoeda(dadosRemTotal.total || 0);
            }
        } catch(e) { document.getElementById('total-verbas').innerText = "R$ 0,00"; }

        await carregarVerbaIndenizatoriaDashboard();
        await carregarVereadoresNaMemoria();

    } catch (error) { console.error("Erro fatal ao carregar dashboard:", error); }
}

async function carregarVerbaIndenizatoriaDashboard() {
    const totalEl = document.getElementById('total-verba-indenizatoria');
    const countEl = document.getElementById('verba-arquivos-count');
    const periodoEl = document.getElementById('verba-periodo-geral');
    const listaEl = document.getElementById('lista-verba-categorias');

    if (!totalEl || !countEl || !listaEl) return;

    try {
        const res = await fetch(`${API_BASE}/stats/verba-indenizatoria?ano=2026`);
        if (!res.ok) throw new Error('Resposta inválida ao carregar verba indenizatória.');
        const dados = await res.json();
        dadosVerbaDashboardGlobal = dados;
        const categoriasComValor = (dados.categorias || []).filter(item => item.total > 0);

        totalEl.innerText = formatarMoeda(dados.total || 0);
        countEl.innerText = `${dados.vereadores_com_dados || 0} arquivos`;
        if (periodoEl) periodoEl.innerText = "Soma dos valores pagos em verba indenizatória.";

        renderizarListaCategoriasVerba(listaEl, categoriasComValor, false, dados.total || 0);
        renderizarGraficoVerbaCategorias(categoriasComValor);
    } catch (error) {
        totalEl.innerText = "R$ 0,00";
        countEl.innerText = "Erro";
        listaEl.innerHTML = '<p class="texto-miudo">Não foi possível carregar a verba indenizatória.</p>';
        if (chartVerbaCategoriasInstance) chartVerbaCategoriasInstance.destroy();
    }
}

function renderizarResumoVerbaDashboard(dados, contexto = null) {
    const totalEl = document.getElementById('total-verba-indenizatoria');
    const countEl = document.getElementById('verba-arquivos-count');
    const periodoEl = document.getElementById('verba-periodo-geral');
    const listaEl = document.getElementById('lista-verba-categorias');

    if (!totalEl || !countEl || !listaEl || !dados) return;

    const categoriasComValor = (dados.categorias || []).filter(item => item.total > 0);
    totalEl.innerText = formatarMoeda(dados.total || 0);
    countEl.innerText = contexto
        ? `${dados.vereadores_com_dados || 0} vereador(es)`
        : `${dados.vereadores_com_dados || 0} arquivos`;

    if (periodoEl) {
        periodoEl.innerText = contexto
            ? `Soma dos valores pagos em verba indenizatória - ${contexto}.`
            : "Soma dos valores pagos em verba indenizatória.";
    }

    renderizarListaCategoriasVerba(listaEl, categoriasComValor, false, dados.total || 0);
    renderizarGraficoVerbaCategorias(categoriasComValor);
}

function obterRotuloFiltroAtual() {
    if (filtroPartidoAtual) return filtroPartidoAtual;
    if (filtroGrupoPoliticoAtual === 'governo') return 'Base do Governo';
    if (filtroGrupoPoliticoAtual === 'oposicao') return 'Oposição';
    return null;
}

function obterVereadoresFiltrados() {
    if (filtroPartidoAtual) {
        return vereadoresGlobal.filter(v => v.partido === filtroPartidoAtual);
    }
    if (filtroGrupoPoliticoAtual) {
        return vereadoresGlobal.filter(v => obterGrupoPolitico(v.partido || '') === filtroGrupoPoliticoAtual);
    }
    return vereadoresGlobal;
}

async function atualizarVerbaIndenizatoriaPorFiltro() {
    if (!dadosVerbaDashboardGlobal) return;

    const contexto = obterRotuloFiltroAtual();
    if (!contexto) {
        verbaFiltroRequestId += 1;
        renderizarResumoVerbaDashboard(dadosVerbaDashboardGlobal);
        return;
    }

    const requestId = ++verbaFiltroRequestId;
    const totalEl = document.getElementById('total-verba-indenizatoria');
    const countEl = document.getElementById('verba-arquivos-count');
    const periodoEl = document.getElementById('verba-periodo-geral');
    const listaEl = document.getElementById('lista-verba-categorias');

    if (totalEl) totalEl.innerText = '...';
    if (countEl) countEl.innerText = contexto;
    if (periodoEl) periodoEl.innerText = `Recalculando verba indenizatória - ${contexto}.`;
    if (listaEl) listaEl.innerHTML = '<p class="texto-miudo">Atualizando recorte selecionado...</p>';

    const selecionados = obterVereadoresFiltrados();
    const respostas = await Promise.all(selecionados.map(async (vereador) => {
        try {
            const res = await fetch(`${API_BASE}/vereadores/${vereador.id}/verba-indenizatoria?ano=2026&nome_vereador=${encodeURIComponent(vereador.nome)}`);
            if (!res.ok) return null;
            return await res.json();
        } catch (error) {
            return null;
        }
    }));

    if (requestId !== verbaFiltroRequestId) return;

    const categorias = {};
    let total = 0;
    let comDados = 0;

    respostas.filter(Boolean).forEach(dados => {
        total += dados.total || 0;
        if ((dados.total || 0) > 0) comDados += 1;
        (dados.categorias || []).forEach(item => {
            categorias[item.categoria] = (categorias[item.categoria] || 0) + (item.total || 0);
        });
    });

    renderizarResumoVerbaDashboard({
        total,
        vereadores_com_dados: comDados,
        categorias: Object.entries(categorias)
            .map(([categoria, valor]) => ({ categoria, total: valor }))
            .sort((a, b) => b.total - a.total)
    }, contexto);
}

function renderizarGraficoVerbaCategorias(categorias) {
    const canvas = document.getElementById('chartVerbaCategorias');
    if (!canvas) return;

    const topCategorias = categorias.slice(0, 6);
    const labelsCompletos = topCategorias.map(item => item.categoria);
    const labelsCurtos = labelsCompletos.map(label => label.length > 34 ? `${label.slice(0, 31)}...` : label);
    if (chartVerbaCategoriasInstance) chartVerbaCategoriasInstance.destroy();

    chartVerbaCategoriasInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labelsCurtos,
            datasets: [{
                label: 'Valor pago',
                data: topCategorias.map(item => item.total),
                backgroundColor: '#f59e0b',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => labelsCompletos[items[0].dataIndex],
                        label: (context) => formatarMoeda(context.parsed.x || 0)
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => formatarMoeda(value)
                    }
                },
                y: {
                    grid: { display: false },
                    ticks: { font: { size: 11 }, color: '#475569' }
                }
            }
        }
    });
}

function renderizarListaCategoriasVerba(container, categorias, detalhada, totalReferencia = null) {
    if (!container) return;

    if (!categorias.length) {
        container.innerHTML = '<p class="texto-miudo">Nenhum valor de verba indenizatória encontrado nos arquivos carregados.</p>';
        return;
    }

    container.innerHTML = categorias.map(item => {
        const percentual = totalReferencia ? ((item.total || 0) / totalReferencia) * 100 : null;
        const valorResumo = percentual === null
            ? formatarMoeda(item.total || 0)
            : `${percentual.toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
        const meses = Object.entries(item.meses || {})
            .filter(([, valor]) => valor > 0)
            .map(([mes, valor]) => `<span class="verba-month-chip">${escaparHtml(mes)} ${formatarMoeda(valor)}</span>`)
            .join('');

        return `
            <div class="verba-category-row">
                <div>
                    <strong>${escaparHtml(item.categoria)}</strong>
                    ${detalhada && meses ? `<div class="verba-month-list">${meses}</div>` : ''}
                </div>
                <span>${valorResumo}</span>
            </div>
        `;
    }).join('');
}

async function carregarTiposProposicoes() {
    try {
        const res = await fetch(`${API_BASE}/proposicoes/tipos?ano=2026`);
        if (res.ok) {
            const data = await res.json();
            const labels = [];
            const values = [];

            if (data && data.tipos) {
                data.tipos.forEach(item => { labels.push(item.tipo); values.push(item.count); });

                if (labels.length > 0) {
                    const headerTema = document.querySelector('#chartTemas').parentElement.previousElementSibling;
                    if(headerTema) headerTema.innerText = "Volume por Tipo de Matéria (2026)";

                    new Chart(document.getElementById('chartTemas'), {
                        type: 'bar',
                        data: {
                            labels: labels,
                            datasets: [{ label: 'Volume Protocolado', data: values, backgroundColor: '#0ea5e9', borderRadius: 4 }]
                        },
                        options: {
                            indexAxis: 'y', responsive: true, maintainAspectRatio: false,
                            plugins: { legend: { display: false } },
                            scales: { x: { beginAtZero: true }, y: { grid: { display: false }, ticks: { font: { size: 11 }, color: '#475569' } } }
                        }
                    });
                }
            }
        }
    } catch(e) {}
}

async function carregarVereadoresNaMemoria() {
    try {
        const res = await fetch(`${API_BASE}/vereadores`);
        const dados = await res.json();
        vereadoresGlobal = dados.items ? dados.items : dados;
        renderizarGradeVereadores(); 
    } catch (error) {
        document.getElementById('grid-vereadores').innerHTML = '<p style="color: red; grid-column: 1 / -1; text-align: center;">Erro ao carregar vereadores. Verifique se a API (localhost:8000) está rodando.</p>';
    }
}

function renderizarGradeVereadores() {
    const grid = document.getElementById('grid-vereadores');
    const indicador = document.getElementById('indicador-filtro-partido');
    const nomeFiltro = document.getElementById('nome-filtro-partido');
    
    grid.innerHTML = ''; 

    let lista = vereadoresGlobal;

    if (filtroPartidoAtual) {
        lista = vereadoresGlobal.filter(v => v.partido === filtroPartidoAtual);
        indicador.style.display = 'inline-block';
        nomeFiltro.innerText = filtroPartidoAtual;
    } else if (filtroGrupoPoliticoAtual) {
        lista = vereadoresGlobal.filter(v => obterGrupoPolitico(v.partido || '') === filtroGrupoPoliticoAtual);
        indicador.style.display = 'inline-block';
        nomeFiltro.innerText = obterRotuloFiltroAtual();
    } else {
        indicador.style.display = 'none';
    }

    atualizarBotoesGrupoPolitico();
    atualizarVerbaIndenizatoriaPorFiltro();

    if (lista.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1 / -1; text-align: center; color: #64748b; padding: 20px;">Nenhum vereador encontrado com este filtro.</p>';
        return;
    }

    lista.forEach(ver => {
        const card = document.createElement('div');
        const status = ver.status_parlamentar;
        card.className = 'vereador-card';
        card.style.cursor = 'pointer'; 
        
        const fotoUrl = ver.fotografia || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(ver.nome) + '&background=random';
        const corPartido = obterCorDoPartido(ver.partido);
        const tagStatus = status ? `
            <span class="tag tag-suplente" title="${escaparHtml(status.observacao)}">
                <i class="fas fa-user-clock"></i> ${escaparHtml(status.tag)}
            </span>
        ` : '';
        
        card.innerHTML = `
            <div style="text-align: center;">
                <img src="${fotoUrl}" alt="Foto de ${ver.nome}" style="width: 100px; height: 100px; border-radius: 50%; object-fit: cover; margin-bottom: 10px; border: 3px solid #f1f5f9;">
                <h3 style="margin: 5px 0; font-size: 1.1rem; color: #1e293b;">${ver.nome}</h3>
                <span style="background-color: ${corPartido}20; color: ${corPartido}; border: 1px solid ${corPartido}; font-weight: bold; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; display: inline-block; margin-bottom: 12px;">
                    ${ver.partido}
                </span>
                <div class="status-tags">${tagStatus}</div>
            </div>
            <div style="border-top: 1px solid #f1f5f9; padding-top: 12px; font-size: 0.85rem; color: #64748b; text-align: left;">
                <p style="margin: 4px 0;"><i class="fas fa-phone" style="width: 16px; color: #94a3b8;"></i> ${ver.telefone}</p>
                <p style="margin: 4px 0; word-break: break-all;"><i class="fas fa-envelope" style="width: 16px; color: #94a3b8;"></i> ${ver.email}</p>
            </div>
        `;

        card.addEventListener('click', () => abrirPerfilVereador(ver));
        grid.appendChild(card);
    });
}

function limparFiltroPartido() {
    filtroPartidoAtual = null;
    filtroGrupoPoliticoAtual = null;
    renderizarGradeVereadores();
}

function filtrarGrupoPolitico(grupo) {
    filtroPartidoAtual = null;
    filtroGrupoPoliticoAtual = filtroGrupoPoliticoAtual === grupo ? null : grupo;
    renderizarGradeVereadores();
}

function atualizarBotoesGrupoPolitico() {
    document.querySelectorAll('[data-grupo-politico]').forEach(botao => {
        const ativo = botao.dataset.grupoPolitico === filtroGrupoPoliticoAtual;
        botao.classList.toggle('ativo', ativo);
        botao.setAttribute('aria-pressed', ativo ? 'true' : 'false');
    });
}

async function abrirPerfilVereador(vereador) {
    document.querySelectorAll('.tela').forEach(t => t.style.display = 'none');
    document.getElementById('view-vereador-detalhe').style.display = 'block';
    
    window.scrollTo({ top: 0, behavior: 'smooth' });

    const fotoUrl = vereador.fotografia || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(vereador.nome) + '&background=random&size=150';
    document.getElementById('perfil-foto').src = fotoUrl;
    document.getElementById('perfil-nome').innerText = vereador.nome;
    document.getElementById('perfil-partido').innerText = vereador.partido || 'Sem Partido';
    const statusPerfilExistente = document.getElementById('perfil-status-parlamentar');
    if (statusPerfilExistente) statusPerfilExistente.remove();
    if (vereador.status_parlamentar) {
        const statusBox = document.createElement('div');
        statusBox.id = 'perfil-status-parlamentar';
        statusBox.className = 'perfil-status';
        statusBox.innerHTML = `
            <span class="tag tag-suplente"><i class="fas fa-user-clock"></i> ${escaparHtml(vereador.status_parlamentar.tag)}</span>
            <p>${escaparHtml(vereador.status_parlamentar.observacao)}</p>
        `;
        document.querySelector('.perfil-info').appendChild(statusBox);
    }

    const listaComissoes = document.getElementById('perfil-comissoes');
    if (vereador.comissoes && vereador.comissoes.length > 0) {
        listaComissoes.innerHTML = vereador.comissoes.map(c => `<li>${c}</li>`).join('');
    } else {
        listaComissoes.innerHTML = '<li>Nenhuma comissão registrada.</li>';
    }

    document.getElementById('perfil-volume-prop').innerText = '...';
    document.getElementById('lista-proposicoes-detalhe').innerHTML = '<p style="text-align:center;"><i class="fas fa-spinner fa-spin"></i> Carregando matérias...</p>';
    document.getElementById('filtros-proposicoes').innerHTML = ''; 
    
    try {
        const resProp = await fetch(`${API_BASE}/vereadores/${vereador.id}/proposicoes?ano=2026&nome_vereador=${encodeURIComponent(vereador.nome)}`);
        if(resProp.ok){
            const props = await resProp.json();
            document.getElementById('perfil-volume-prop').innerText = props.total || 0;
            proposicoesVereadorGlobal = props.items || [];
            
            gerarBotoesFiltroProposicao();
            filtrarListaDeProposicoesNaTela('todos', null);
        }
    } catch(e) { document.getElementById('lista-proposicoes-detalhe').innerHTML = '<p style="color: red; text-align: center;">Erro de conexão.</p>'; }

    // DADOS DE COMISSIONADOS
    document.getElementById('total-custo-comissionados').innerText = '...';
    document.getElementById('periodo-comissionados').innerText = 'Carregando...';
    document.getElementById('lista-comissionados').innerHTML = '<li>Buscando equipe...</li>';

    try {
        const resCom = await fetch(`${API_BASE}/vereadores/${vereador.id}/comissionados?nome_vereador=${encodeURIComponent(vereador.nome)}`);
        if (resCom.ok) {
            const dados = await resCom.json();
            document.getElementById('total-custo-comissionados').innerText = formatarMoeda(dados.total);
            document.getElementById('periodo-comissionados').innerText = dados.periodo;

            const lista = document.getElementById('lista-comissionados');
            if (dados.servidores.length > 0) {
                lista.innerHTML = dados.servidores.map(s => `
                    <li style="display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f1f5f9;">
                        <div style="display: flex; flex-direction: column;">
                            <span style="font-weight: 600; font-size: 0.9rem; color: #1e293b;">${s.nome}</span>
                            <span style="font-size: 0.75rem; color: #94a3b8;">${s.cargo}</span>
                        </div>
                        <span style="font-weight: bold; color: #10b981; font-size: 0.9rem;">${formatarMoeda(s.bruto)}</span>
                    </li>
                `).join('');
            } else {
                lista.innerHTML = '<li style="color: #94a3b8; font-size: 0.9rem;">Nenhum servidor identificado para este gabinete no mês atual.</li>';
            }
        }
    } catch (e) {
        document.getElementById('lista-comissionados').innerHTML = '<li style="color: red; font-size: 0.9rem;">Erro ao carregar dados dos comissionados.</li>';
    }

    await carregarVerbaIndenizatoriaVereador(vereador);

    document.getElementById('perfil-gasto-total').innerText = '...';
    document.getElementById('filtro-ano-salario').value = '2026'; 

    try {
        const resRem = await fetch(`${API_BASE}/vereadores/${vereador.id}/remuneracao?nome_vereador=${encodeURIComponent(vereador.nome)}`);
        if(resRem.ok) {
            historicoSalarioGlobal = await resRem.json();
            renderizarGraficoSalario('2026'); 
        } else { historicoSalarioGlobal = []; renderizarGraficoSalario('2026'); }
    } catch(e) { historicoSalarioGlobal = []; renderizarGraficoSalario('2026'); }
}

async function carregarVerbaIndenizatoriaVereador(vereador) {
    const totalEl = document.getElementById('total-verba-vereador');
    const statusEl = document.getElementById('status-verba-vereador');
    const periodoEl = document.getElementById('periodo-verba-vereador');
    const listaEl = document.getElementById('lista-verba-vereador-categorias');
    const canvas = document.getElementById('chartVerbaVereadorMeses');

    if (!totalEl || !statusEl || !listaEl || !canvas) return;

    totalEl.innerText = '...';
    statusEl.innerText = 'Carregando dados de verba indenizatória...';
    listaEl.innerHTML = '';
    if (periodoEl) periodoEl.innerText = '2026';
    if (chartVerbaVereadorMesesInstance) chartVerbaVereadorMesesInstance.destroy();

    try {
        const res = await fetch(`${API_BASE}/vereadores/${vereador.id}/verba-indenizatoria?ano=2026&nome_vereador=${encodeURIComponent(vereador.nome)}`);
        if (!res.ok) throw new Error('Resposta inválida ao carregar verba do vereador.');
        const dados = await res.json();
        const categoriasComValor = (dados.categorias || []).filter(item => item.total > 0);

        totalEl.innerText = formatarMoeda(dados.total || 0);
        if (periodoEl) periodoEl.innerText = dados.ano || '2026';

        if (!dados.total) {
            statusEl.innerText = 'Nenhum CSV de verba indenizatória identificado para este parlamentar.';
            listaEl.innerHTML = '<p class="texto-miudo">Os dados aparecerão aqui quando o arquivo correspondente for carregado.</p>';
            return;
        }

        statusEl.innerText = `${(dados.arquivos || []).length} arquivo(s) vinculado(s) a este parlamentar.`;
        renderizarGraficoVerbaVereadorMeses(dados.meses || []);
        renderizarListaCategoriasVerba(listaEl, categoriasComValor, true);
    } catch (error) {
        totalEl.innerText = 'R$ 0,00';
        statusEl.innerText = 'Não foi possível carregar a verba indenizatória deste parlamentar.';
        listaEl.innerHTML = '';
    }
}

function renderizarGraficoVerbaVereadorMeses(meses) {
    const canvas = document.getElementById('chartVerbaVereadorMeses');
    if (!canvas) return;

    if (chartVerbaVereadorMesesInstance) chartVerbaVereadorMesesInstance.destroy();

    chartVerbaVereadorMesesInstance = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: meses.map(item => item.mes),
            datasets: [{
                label: 'Verba indenizatória',
                data: meses.map(item => item.total),
                backgroundColor: '#f59e0b',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => formatarMoeda(context.parsed.y || 0)
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: (value) => formatarMoeda(value)
                    }
                },
                x: { grid: { display: false } }
            }
        }
    });
}

function gerarBotoesFiltroProposicao() {
    const container = document.getElementById('filtros-proposicoes');
    if (!container) return;
    
    const tiposUnicos = [...new Set(proposicoesVereadorGlobal.map(p => p.tipo))];
    if (tiposUnicos.length === 0) return;

    let html = `<button class="btn-filtro-prop ativo" onclick="filtrarListaDeProposicoesNaTela('todos', this)">Todos (${proposicoesVereadorGlobal.length})</button>`;
    
    tiposUnicos.forEach(tipo => {
        const qtd = proposicoesVereadorGlobal.filter(p => p.tipo === tipo).length;
        html += `<button class="btn-filtro-prop" onclick="filtrarListaDeProposicoesNaTela('${tipo}', this)">${tipo} (${qtd})</button>`;
    });
    
    container.innerHTML = html;
}

function filtrarListaDeProposicoesNaTela(tipoDesejado, botaoClicado) {
    const container = document.getElementById('lista-proposicoes-detalhe');
    if (!container) return;

    if (botaoClicado) {
        document.querySelectorAll('.btn-filtro-prop').forEach(b => b.classList.remove('ativo'));
        botaoClicado.classList.add('ativo');
    } else {
        const primeiroBotao = document.querySelector('.btn-filtro-prop');
        if(primeiroBotao) primeiroBotao.classList.add('ativo');
    }

    let listaFinal = proposicoesVereadorGlobal;
    if (tipoDesejado !== 'todos') {
        listaFinal = proposicoesVereadorGlobal.filter(p => p.tipo === tipoDesejado);
    }

    if (listaFinal.length > 0) {
        container.innerHTML = listaFinal.map(p => {
            const dataFormatada = p.data ? p.data.split('-').reverse().join('/') : '';
            return `
            <div class="prop-item">
                <div>
                    <span class="prop-tipo">${p.tipo}</span>
                    <span style="float: right; font-size: 0.8rem; color: #94a3b8;"><i class="far fa-calendar-alt"></i> ${dataFormatada}</span>
                </div>
                <h4 class="prop-desc-destaque" title="${p.descricao.replace(/"/g, '&quot;')}">${p.descricao}</h4>
                <p class="prop-titulo-menor"><i class="fas fa-hashtag"></i> ${p.titulo}</p>
                ${p.link ? `<a href="${p.link}" target="_blank" class="prop-link"><i class="fas fa-download"></i> Baixar Documento</a>` : ''}
            </div>
        `}).join('');
    } else {
        container.innerHTML = '<p style="color: #64748b; font-size: 0.9rem; text-align: center; padding: 20px;">Nenhuma matéria encontrada.</p>';
    }
}

function renderizarGraficoSalario(anoFiltro) {
    let dadosFiltrados = historicoSalarioGlobal;
    if (anoFiltro !== 'todos') {
        dadosFiltrados = historicoSalarioGlobal.filter(item => item.periodo.includes(anoFiltro));
        document.getElementById('label-gasto-total').innerText = `Bruto no ano de ${anoFiltro}`;
    } else {
        document.getElementById('label-gasto-total').innerText = `Bruto em todos os anos`;
    }

    let totalAcumulado = dadosFiltrados.reduce((acc, mes) => acc + mes.bruto, 0);
    document.getElementById('perfil-gasto-total').innerText = formatarMoeda(totalAcumulado);

    const labels = dadosFiltrados.map(item => item.periodo);
    const dadosBrutos = dadosFiltrados.map(item => item.bruto);

    if (chartSalarioInstance) { chartSalarioInstance.destroy(); }

    const ctx = document.getElementById('chartSalario').getContext('2d');
    chartSalarioInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'Salário bruto', data: dadosBrutos, borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.1)', borderWidth: 2, fill: true, tension: 0.3 }
            ]
        },
        options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true } } }
    });
}

document.getElementById('filtro-ano-salario').addEventListener('change', (evento) => {
    renderizarGraficoSalario(evento.target.value);
});

function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(valor);
}

document.getElementById('btn-voltar').addEventListener('click', () => {
    document.querySelectorAll('.tela').forEach(t => t.style.display = 'none');
    document.getElementById('view-dashboard').style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

window.limparFiltroPartido = limparFiltroPartido;
window.filtrarGrupoPolitico = filtrarGrupoPolitico;
window.filtrarListaDeProposicoesNaTela = filtrarListaDeProposicoesNaTela;

document.addEventListener('DOMContentLoaded', loadDashboard);
