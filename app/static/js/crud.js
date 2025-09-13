// js/crud.js

import { API_URL } from './api.js';

let dataTable; // Variável para armazenar a instância do DataTables

document.addEventListener("DOMContentLoaded", () => {
    console.log("DOM carregado. Inicializando DataTables...");

    // Inicializamos a tabela diretamente, passando a URL da nossa API
    dataTable = $('#tabela').DataTable({
        "ajax": {
            "url": API_URL,       // Pede os dados para o nosso back-end
            "dataSrc": ""         // Indica que os dados são um array na raiz do JSON
        },
        "columns": [
            // Mapeia cada coluna para a chave correspondente no JSON que o FastAPI envia.
            // O nome em 'data' DEVE ser exatamente igual ao nome da coluna no banco de dados.
            
            { "data": "codigo" },
            { "data": "nome_tecnico" },
            { "data": "cpf_tecnico",
                // Bônus: Aplicando a formatação de CPF que discutimos!
              "render": function(data, type, row) {
                  if (type === 'display' && data && data.length === 11) {
                      return data.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
                  }
                  return data;
              }
            },
            { "data": "municipio" },
            { "data": "comunidade" },
            { "data": "latitude" },
            { "data": "longitude" },
            { "data": "data_atividade" },
            { "data": "nome_familiar" },
            { "data": "cpf_familiar",
              // Bônus: Aplicando a formatação de CPF que discutimos!
              "render": function(data, type, row) {
                  if (type === 'display' && data && data.length === 11) {
                      return data.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
                  }
                  return data;
              }
            },
            { "data": "nis" },
            { "data": "renda_media" },
            { "data": "status" },
            { "data": "tecnico_agua_que_alimenta" },
            { "data": "doc_status" },
            { "data": "grh" },
            { "data": "verificado_bsf" }
            
            // Adicione mais colunas aqui se necessário, garantindo que o número
            // de colunas aqui seja igual ao número de <th> no seu HTML.
        ],
        // O resto das suas configurações do DataTables permanecem as mesmas
        paging: true,
        searching: true,
        info: false,
        lengthChange: false,
        pageLength: 25,
        language: {
            emptyTable: "Carregando dados do servidor...",
            zeroRecords: "Nenhum registro encontrado com o filtro aplicado",
            search: "Pesquisa Rápida Global:",
            paginate: {
                previous: "Anterior",
                next: "Próximo"
            }
        }
    });
    console.log("DataTables configurado para buscar dados da API.");

    // O restante do seu código para os filtros continua funcionando perfeitamente,
    // pois ele interage com a variável `dataTable`, que ainda existe.
    const searchInput = document.getElementById('searchInput');
    const columnSelect = document.getElementById('columnSelect');
    const searchButton = document.getElementById('searchButton');
    const clearButton = document.getElementById('clearFilterButton');

    function aplicarFiltro() {
        if (!dataTable) return;
        
        const termoPesquisa = searchInput.value.trim();
        const indiceColuna = parseInt(columnSelect.value, 10);

        dataTable.search('').columns().search('').draw();

        if (indiceColuna === 0) { // Pesquisa Global
            dataTable.search(termoPesquisa).draw();
        } else { // Pesquisa em Coluna Específica
            dataTable.column(indiceColuna - 1).search(termoPesquisa).draw();
        }
    }

    if (searchButton) searchButton.addEventListener('click', aplicarFiltro);
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
            searchInput.value = "";
            if (columnSelect) columnSelect.value = "0";
            if (dataTable) dataTable.search("").columns().search("").draw();
        });
    }
});