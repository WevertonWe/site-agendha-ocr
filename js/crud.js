let dataTable;

async function carregarDados() {
    try {
        const dados = await getData();
        const tbody = document.querySelector("#tabela tbody");
        tbody.innerHTML = "";

        dados.slice(1).forEach((linha) => {
            const tr = document.createElement("tr");
            const colunasFiltradas = linha.filter((_, index) => ![0, 1].includes(index));
            colunasFiltradas.forEach((celula) => {
                const td = document.createElement("td");
                td.textContent = celula;
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });

        if ($.fn.DataTable.isDataTable("#tabela")) {
            $('#tabela').DataTable().destroy();
        }

        dataTable = $('#tabela').DataTable({
            paging: true,
            searching: true,
            info: false,
            lengthChange: false,
            pageLength: 25,
            language: {
                emptyTable: "Nenhum dado disponível na tabela",
                paginate: {
                    previous: "Anterior",
                    next: "Próximo"
                }
            }
        });

    } catch (error) {
        console.error('Erro ao carregar dados:', error);
        alert('Erro ao carregar dados.');
    }
}

document.addEventListener("DOMContentLoaded", () => {
    carregarDados();

    const searchInput = document.getElementById('searchInput');
    const searchButton = document.getElementById('searchButton');
    const clearButton = document.getElementById('clearFilterButton');

    function aplicarFiltroGlobal() {
        const termo = searchInput.value.trim();
        if (dataTable) {
            dataTable.search(termo).draw();
        }
    }

    if (searchButton) {
        searchButton.addEventListener('click', aplicarFiltroGlobal);
    }

    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                aplicarFiltroGlobal();
            }
        });
    }

    if (clearButton) {
        clearButton.addEventListener('click', () => {
            searchInput.value = "";
            if (dataTable) {
                dataTable.search("").draw();
            }
        });
    }
});
