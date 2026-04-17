// AQUI: Voltado para rodar na SUA MÁQUINA, como combinado!
const API_BASE = "https://observatorio-camara-municipal-do-recife-1.onrender.com"; 

let chartSalarioInstance = null;
let chartPartidosInstance = null;

let historicoSalarioGlobal = [];
let vereadoresGlobal = [];
let proposicoesVereadorGlobal = []; 
let filtroPartidoAtual = null;      

function obterCorDoPartido(nomePartido) {
    const p = nomePartido.toUpperCase();
    if (p.includes("PSB") || p === "PT" || p.includes("PCDOB") || p.includes("PV") || 
        p.includes("MDB") || p.includes("REPUBLICANOS") || p.includes("AVANTE") || 
        p.includes("PRD") || p.includes("PT, PCDOB, PV") || p.includes("FEDERAÇÃO")) {
        return '#10b981'; 
    }
    if (p.includes("PL") || p.includes("NOVO") || p.includes("PP") || 
        p.includes("PODEMOS") || p.includes("PSD") || p.includes("PSOL")) {
        return '#f43f5e'; 
    }
    return '#94a3b8'; 
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
        const labelsPartidos = Object.keys(dadosPartidos);
        const dataPartidos = Object.values(dadosPartidos);
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
                    borderRadius: 4
                }]
            },
            options: { 
                responsive: true, 
                plugins: { legend: { display: false } },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        const labelClicado = chartPartidosInstance.data.labels[index];
                        
                        if (filtroPartidoAtual === labelClicado) {
                            limparFiltroPartido();
                        } else {
                            filtroPartidoAtual = labelClicado;
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

        carregarTiposProposicoes();
        await carregarVereadoresNaMemoria();

    } catch (error) { console.error("Erro fatal ao carregar dashboard:", error); }
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
    } else {
        indicador.style.display = 'none';
    }

    if (lista.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1 / -1; text-align: center; color: #64748b; padding: 20px;">Nenhum vereador encontrado com este filtro.</p>';
        return;
    }

    lista.forEach(ver => {
        const card = document.createElement('div');
        card.className = 'vereador-card';
        card.style.cursor = 'pointer'; 
        
        const fotoUrl = ver.fotografia || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(ver.nome) + '&background=random';
        const corPartido = obterCorDoPartido(ver.partido);
        
        card.innerHTML = `
            <div style="text-align: center;">
                <img src="${fotoUrl}" alt="Foto de ${ver.nome}" style="width: 100px; height: 100px; border-radius: 50%; object-fit: cover; margin-bottom: 10px; border: 3px solid #f1f5f9;">
                <h3 style="margin: 5px 0; font-size: 1.1rem; color: #1e293b;">${ver.nome}</h3>
                <span style="background-color: ${corPartido}20; color: ${corPartido}; border: 1px solid ${corPartido}; font-weight: bold; padding: 4px 10px; border-radius: 6px; font-size: 0.85rem; display: inline-block; margin-bottom: 12px;">
                    ${ver.partido}
                </span>
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
    renderizarGradeVereadores();
}

async function abrirPerfilVereador(vereador) {
    document.querySelectorAll('.tela').forEach(t => t.style.display = 'none');
    document.getElementById('view-vereador-detalhe').style.display = 'block';
    
    window.scrollTo({ top: 0, behavior: 'smooth' });

    const fotoUrl = vereador.fotografia || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(vereador.nome) + '&background=random&size=150';
    document.getElementById('perfil-foto').src = fotoUrl;
    document.getElementById('perfil-nome').innerText = vereador.nome;
    document.getElementById('perfil-partido').innerText = vereador.partido || 'Sem Partido';

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
    const dadosLiquidos = dadosFiltrados.map(item => item.liquido);

    if (chartSalarioInstance) { chartSalarioInstance.destroy(); }

    const ctx = document.getElementById('chartSalario').getContext('2d');
    chartSalarioInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                { label: 'Bruto (Total de Vantagens)', data: dadosBrutos, borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.1)', borderWidth: 2, fill: true, tension: 0.3 },
                { label: 'Valor Líquido Recebido', data: dadosLiquidos, borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)', borderWidth: 2, fill: true, tension: 0.3 }
            ]
        },
        options: { responsive: true, interaction: { mode: 'index', intersect: false }, plugins: { legend: { position: 'top' } }, scales: { y: { beginAtZero: true } } }
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

document.addEventListener('DOMContentLoaded', loadDashboard);