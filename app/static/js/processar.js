// js/processar.js

import { getData } from './utils.js';
import { SHEET_URL } from './api.js';

document.addEventListener("DOMContentLoaded", () => {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const statusLog = document.getElementById('statusLog');
    const historicoBody = document.getElementById('historico').getElementsByTagName('tbody')[0];

    // Função para atualizar status em tempo real
    function atualizarStatus(mensagem) {
        const p = document.createElement('p');
        p.textContent = mensagem;
        statusLog.appendChild(p);
        // Auto-scroll para a última mensagem
        statusLog.scrollTop = statusLog.scrollHeight;
    }

    // Função para carregar histórico
    async function carregarHistorico() {
        try {
            const response = await fetch('/historico'); // Rota que criamos no backend
            if (!response.ok) {
                let errorMsg = `Erro HTTP ${response.status} ao carregar histórico.`;
                try {
                    const errDetails = await response.json();
                    errorMsg += ` Detalhes: ${errDetails.detail || JSON.stringify(errDetails)}`;
                } catch (e) {
                    // Não conseguiu parsear JSON, usa o status text
                    errorMsg += ` Status: ${response.statusText}`;
                }
                throw new Error(errorMsg);
            }
            const historico = await response.json();

            historicoBody.innerHTML = ""; // Limpa o corpo da tabela

            if (historico.length === 0) {
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = 4; // Número de colunas na sua tabela de histórico
                td.textContent = 'Nenhum histórico encontrado.';
                td.style.textAlign = 'center';
                tr.appendChild(td);
                historicoBody.appendChild(tr);
            } else {
                historico.forEach(entry => {
                    const tr = document.createElement('tr');

                    // Ajuste os nomes das chaves aqui para corresponder ao que `salvar_historico` está salvando
                    // No app.py atual, as chaves são "nome_beneficiario", "cpf_beneficiario", "status_processamento", "data_processamento"
                    const tdNome = document.createElement('td');
                    tdNome.textContent = entry.nome_beneficiario || entry.nome || "N/A"; // Adapte conforme seu JSON
                    tr.appendChild(tdNome);

                    const tdCpf = document.createElement('td');
                    tdCpf.textContent = entry.cpf_beneficiario || entry.cpf || "N/A"; // Adapte
                    tr.appendChild(tdCpf);

                    const tdStatus = document.createElement('td');
                    tdStatus.textContent = entry.status_processamento || entry.status || "N/A"; // Adapte
                    tr.appendChild(tdStatus);

                    const tdData = document.createElement('td');
                    tdData.textContent = entry.data_processamento || entry.data || "N/A"; // Adapte
                    tr.appendChild(tdData);

                    historicoBody.appendChild(tr);
                });
            }
        } catch (error) {
            console.error('Erro ao carregar histórico:', error);
            atualizarStatus(`Falha ao carregar histórico: ${error.message}`);
            historicoBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:red;">Falha ao carregar histórico.</td></tr>`;
        }
    }

    // Enviar arquivos para backend (MODIFICADO)
    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const selectedFiles = fileInput.files; // 'selectedFiles' é um FileList
        if (!selectedFiles.length) {
            alert('Por favor, selecione pelo menos um arquivo!');
            return;
        }

        // Opcional: Validar se são exatamente 2 arquivos, se essa for a regra.
        // if (selectedFiles.length !== 2) { 
        //     alert('Por favor, envie exatamente 2 arquivos PDF por beneficiário.');
        //     return;
        // }

        const formData = new FormData();
        for (let i = 0; i < selectedFiles.length; i++) {
            // A chave aqui DEVE ser 'files' para corresponder ao parâmetro no backend:
            // async def upload_documentos_beneficiario(files: List[UploadFile]...
            formData.append('files', selectedFiles[i], selectedFiles[i].name);
        }

        // Limpa o log de status antes de um novo envio (melhora a UX)
        // Se preferir manter o log anterior e adicionar, remova a linha abaixo.
        statusLog.innerHTML = ""; 
        atualizarStatus("Enviando arquivos ao servidor...");

        try {
            // Envia TODOS os arquivos selecionados em UMA ÚNICA requisição
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
                // Não defina 'Content-Type' manualmente para FormData;
                // o navegador o fará corretamente com o boundary necessário.
            });

            // Tenta ler a resposta do servidor como JSON, mesmo se response.ok for false
            // pois o servidor pode enviar detalhes do erro no corpo JSON.
            const result = await response.json();

            if (!response.ok) {
                // Se o servidor retornou um erro HTTP (4xx, 5xx)
                // A mensagem de erro deve vir do JSON do servidor (result.error ou result.detail)
                const errorMsgFromServer = result.error || result.detail || `Erro HTTP: ${response.status}`;
                throw new Error(errorMsgFromServer); // Lança para o catch block
            }
            
            // Mensagem de sucesso do servidor (result.message)
            // O WebSocket cuidará das mensagens de progresso subsequentes para este beneficiario_id
            // A mensagem inicial de "em processamento" já é útil.
            let successMsg = result.message || "Arquivos enviados com sucesso.";
            if (result.beneficiario_id) {
                successMsg += ` ID do Lote: ${result.beneficiario_id}. Aguardando processamento...`;
            }
            atualizarStatus(successMsg);
            
        } catch (error) {
            // error.message aqui virá do 'throw new Error' acima se response.ok for false,
            // ou será "TypeError: Failed to fetch" se for um erro de rede puro (como ERR_CONNECTION_REFUSED).
            console.error('Erro no upload:', error); // Mantém o log no console do dev
            atualizarStatus(`Falha no upload: ${error.message}`);
        } finally {
            // Limpar a seleção de arquivos após o envio (opcional)
             fileInput.value = ""; 
        }
    });

    // Conectar ao WebSocket
    // Garanta que a URL do WebSocket esteja correta para seu ambiente
    let wsUrl = 'ws://localhost:8000/ws';
    if (window.location.protocol === 'https:') {
        wsUrl = `wss://${window.location.host}/ws`;
    } else {
        wsUrl = `ws://${window.location.host}/ws`;
    }
    // Se estiver rodando localmente e acessando por 127.0.0.1, o localhost:8000 geralmente funciona.
    // Se estiver acessando de outra máquina na rede, use o IP da máquina servidora.
    // Para simplificar durante o desenvolvimento local:
    wsUrl = 'ws://127.0.0.1:8000/ws';


    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        atualizarStatus('Conectado ao servidor para status em tempo real...');
    };

    ws.onmessage = (event) => {
        const msg = event.data;
        atualizarStatus(msg);

        // Se receber 'concluído' no final da mensagem de status, recarrega histórico
        if (msg.toLowerCase().includes('concluído.')) { 
            setTimeout(carregarHistorico, 1000); // Pequeno delay para garantir que o JSON foi escrito
        }
    };

    ws.onerror = (event) => {
        console.error('Erro no WebSocket:', event);
        atualizarStatus('Erro na conexão com o servidor WebSocket. Tente recarregar a página.');
    };

    ws.onclose = (event) => {
        let reason = "";
        if (event.code === 1000) reason = "Fechamento normal";
        else if (event.code === 1001) reason = "Endpoint indo embora (servidor desligando ou navegação)";
        // Adicione outros códigos se necessário
        else reason = "Conexão fechada inesperadamente";
        atualizarStatus(`Desconectado do servidor WebSocket: ${reason} (Código: ${event.code})`);
        console.warn('WebSocket desconectado:', event);
    };

    // Carrega histórico ao abrir a página
    carregarHistorico();
});