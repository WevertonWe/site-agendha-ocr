// js/crud.js

import { getData } from './utils.js';
import { SHEET_URL } from './api.js';

let dataTable; // Variável para armazenar a instância do DataTables

async function carregarDados() {
    console.log("Iniciando carregarDados()...");
    try {
        const dados = await getData(SHEET_URL);
        console.log("Dados recebidos de getData:", dados);

        if (!dados || !Array.isArray(dados) || dados.length < 1) {
            console.error("Formato de dados inválido ou vazio recebido de getData.", dados);
            throw new Error("Formato de dados inválido ou vazio da planilha.");
        }
        
        const tbody = document.querySelector("#tabela tbody");
        if (!tbody) {
            console.error("Elemento tbody da tabela não encontrado!");
            return; 
        }
        tbody.innerHTML = ""; 

        // === AJUSTE AQUI CONFORME SUAS NECESSIDADES ===
        // Colunas da planilha original (0-indexado) a serem EXCLUÍDAS.
        // Sua planilha tem 16 colunas (índices 0 a 15).
        // A tabela HTML tem 12 cabeçalhos. Portanto, precisamos excluir 4 colunas.
        // Assumindo que:
        // - Coluna 0 ("Carimbo") da planilha é para excluir.
        // - Coluna 1 ("Código") da planilha é para excluir.
        // - "Localidade" no HTML corresponde à "Comunidade" (coluna 5 da planilha), então excluímos "Município" (coluna 4 da planilha).
        // - Coluna 15 ("Coluna 1") da planilha é para excluir.
        // SE "Localidade" no HTML for "Município" (coluna 4), então exclua a coluna 5 ("Comunidade") em vez da 4.
        const COLUNAS_EXCLUIDAS = [0, 1, 15]; // <--- AJUSTE ESTA LINHA
        // =============================================
        
        if (dados.length <= 1 && (dados[0] && dados[0].length > 0) ) { 
             console.warn("Nenhum dado para exibir (apenas cabeçalho ou vazio após cabeçalho).");
        } else if (dados.length > 1) {
            dados.slice(1).forEach((linha, rowIndex) => {
                if (!Array.isArray(linha)) {
                    console.warn(`Linha ${rowIndex} não é um array:`, linha);
                    return; 
                }
                const tr = document.createElement("tr");
                const colunasFiltradas = linha.filter((_, index) => !COLUNAS_EXCLUIDAS.includes(index));
                
                if (colunasFiltradas.length !== 13) { // Verifica se temos 12 colunas para a tabela HTML
                    console.warn(
                        `AVISO: Linha ${rowIndex} tem ${colunasFiltradas.length} colunas após filtro, mas a tabela HTML espera 12. ` +
                        `Isto pode causar erros no DataTables ou desalinhamento.` +
                        `Linha original da planilha (índices 0-15):`, linha, 
                        "Colunas após exclusão (deveriam ser 12):", colunasFiltradas
                    );
                }

                colunasFiltradas.forEach((celula) => {
                    const td = document.createElement("td");
                    td.textContent = celula !== null && celula !== undefined ? String(celula) : ""; 
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
        }


        if ($.fn.DataTable.isDataTable("#tabela")) {
            console.log("Destruindo instância DataTables existente.");
            $('#tabela').DataTable().destroy();
        }

        console.log("Inicializando DataTables...");
        dataTable = $('#tabela').DataTable({
            paging: true,
            searching: true, 
            info: false,
            lengthChange: false,
            pageLength: 25,
            language: {
                emptyTable: "Nenhum dado disponível na tabela",
                zeroRecords: "Nenhum registro encontrado com o filtro aplicado", 
                search: "Pesquisa Rápida Global:", 
                paginate: {
                    previous: "Anterior",
                    next: "Próximo"
                }
            }
        });
        console.log("DataTables inicializado com sucesso.");

    } catch (error) {
        console.error('Erro final em carregarDados:', error);
        const tbody = document.querySelector("#tabela tbody");
        if(tbody) { 
            tbody.innerHTML = `<tr><td colspan="13" style="text-align:center; color:red;">Erro ao carregar dados da planilha: ${error.message}. Verifique o console.</td></tr>`;
        }
    }
}

document.addEventListener("DOMContentLoaded", () => {
    carregarDados();

    const searchInput = document.getElementById('searchInput');
    const columnSelect = document.getElementById('columnSelect'); 
    const searchButton = document.getElementById('searchButton');
    const clearButton = document.getElementById('clearFilterButton');

    function aplicarFiltro() {
        if (!dataTable) {
            console.warn("DataTables não inicializado ainda, filtro não aplicado.");
            return; 
        }
        console.log("Aplicando filtro...");

        const termoPesquisa = searchInput.value.trim();
        const indiceColunaSelecionadaHTML = parseInt(columnSelect.value, 10);

        dataTable.search('').columns().search('').draw(); 

        if (termoPesquisa === "" && indiceColunaSelecionadaHTML === 0) {
            console.log("Filtro limpo (sem termo, todas as colunas).");
            return;
        } else if (indiceColunaSelecionadaHTML === 0) {
            console.log(`Aplicando filtro GLOBAL: "${termoPesquisa}"`);
            dataTable.search(termoPesquisa).draw();
        } else if (indiceColunaSelecionadaHTML > 0) {
            const dtColumnIndex = indiceColunaSelecionadaHTML - 1; 
            console.log(`Aplicando filtro na COLUNA ${dtColumnIndex} (HTML select val: ${indiceColunaSelecionadaHTML}): "${termoPesquisa}"`);
            dataTable.column(dtColumnIndex).search(termoPesquisa).draw();
        }
    }

    if (searchButton) {
        searchButton.addEventListener('click', aplicarFiltro);
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault(); 
                aplicarFiltro();
            }
        });
    }

    if (clearButton) {
        clearButton.addEventListener('click', () => {
            console.log("Limpando filtro...");
            searchInput.value = "";
            if (columnSelect) {
                columnSelect.value = "0"; 
            }
            if (dataTable) {
                dataTable.search("").columns().search("").draw();
            }
        });
    }
});
