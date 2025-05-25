const SHEET_URL = 'https://docs.google.com/spreadsheets/d/1_vPh76hpATEItZHuS6H0jpR6IEAUwPWmBo39gZrjBoU/export?format=csv';

/**
 * Faz uma requisição GET para buscar os dados da planilha no formato CSV.
 * @returns {Promise<Array>} - Retorna os dados da planilha como um array de arrays.
 */
async function getData() {
    console.log('Solicitando dados da planilha...');
    try {
        const response = await fetch(SHEET_URL);
        if (!response.ok) {
            console.error('Erro ao buscar dados:', response.status, response.statusText);
            throw new Error(`Erro ao buscar dados: ${response.status}`);
        }

        const csvText = await response.text();
        console.log('Dados CSV recebidos:', csvText);

        // Converte o CSV para um array de arrays
        const rows = csvText.split('\n').map(row => row.split(','));
        console.log('Dados convertidos para array:', rows);

        return rows;
    } catch (error) {
        console.error('Erro ao buscar dados:', error);
        throw error;
    }
}